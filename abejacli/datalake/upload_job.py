import os
import urllib.parse
import uuid
from mimetypes import guess_type

from abejacli.config import ABEJA_API_URL, FILE_READ_CHUNK_SIZE
from abejacli.datalake.process_file_job import (
    FINISH_REPORT,
    INITIALIZE_REPORT,
    PROGRESS_REPORT,
    RAISE_ERROR,
    SKIP_REPORT
)
from abejacli.session import generate_user_session


class UploadFileIterator(object):

    def __init__(self, path, publisher_id, report_queue, chunk_size=FILE_READ_CHUNK_SIZE):
        self.path = path
        self.publisher_id = publisher_id
        self.report_queue = report_queue
        self.chunk_size = chunk_size
        self.total_size = os.path.getsize(path)

    def __iter__(self):
        initialize_options = {
            'file_name': os.path.basename(self.path),
            'total': self.total_size,
        }
        self.report_queue.put(
            (INITIALIZE_REPORT, self.publisher_id, 0, initialize_options))
        with open(self.path, 'rb') as upload_file:
            while True:
                data = upload_file.read(self.chunk_size)
                if not data:
                    break
                # update progress with chunk data size
                self.report_queue.put(
                    (PROGRESS_REPORT, self.publisher_id, len(data), None))
                yield data

    def __len__(self):
        return self.total_size


class IterableToFileAdapter(object):

    def __init__(self, iterable):
        self.iterator = iter(iterable)
        self.length = len(iterable)
        self.buffer = b''
        self.total_read = 0

    def read(self, size):
        result = self.buffer
        while len(result) < size:
            try:
                retrieved = next(self.iterator)
            except StopIteration:
                break
            result = b''.join([result, retrieved])
        result, self.buffer = result[:size], result[size:]
        self.total_read += len(result)
        return result

    def __len__(self):
        return self.length


def upload_job(channel_id, upload_file, report_queue, options):
    """
    upload files until consuming all items in file queue

    :param channel_id: channel identifier
    :param upload_file: ``UploadFile`` object to upload
    :param report_queue: queue to report progress for each file
    :param options: job options
    :return:
    """

    publisher_id = uuid.uuid4().hex
    file_path = upload_file.path
    options = options if options else {}
    metadata = {}

    try:
        finished_status = FINISH_REPORT
        url = "{}/channels/{}/upload".format(ABEJA_API_URL, channel_id)

        conflict_target = options.get('conflict_target')
        if conflict_target:
            url = '{}?conflict_target={}'.format(url, conflict_target)

        type, _ = guess_type(file_path)
        headers = {
            'Content-Type': type if type else 'application/octet-stream'
        }

        # Runtime option `metadata` overwrites metadata specified in
        # file list spec.
        metadata = upload_file.metadata or metadata
        metadata['filename'] = os.path.basename(file_path)
        for key, value in options.get('metadata', ()):
            metadata[key] = value

        for key, value in metadata.items():
            key = urllib.parse.quote(str(key), encoding='utf-8')
            value = urllib.parse.quote(str(value), encoding='utf-8')
            headers['x-abeja-meta-{}'.format(key)] = value

        # File iterator
        it = UploadFileIterator(file_path, publisher_id, report_queue)
        data_adapter = IterableToFileAdapter(it)

        with generate_user_session() as session:
            # Uploading file shouldn't be timed out!
            upload_res = session.post(
                url, data=data_adapter, headers=headers, timeout=None)

        # 409 conflict when conflict_target option specified can be ignored.
        if conflict_target and upload_res.status_code == 409:
            finished_status = SKIP_REPORT
        else:
            upload_res.raise_for_status()

        content = upload_res.json()
        report_queue.put(
            (finished_status, publisher_id, 0, {
                'source': file_path,
                'destination': content.get('file_id', ''),
                'metadata': content.get('metadata', {})
            }))
    except Exception as e:
        options = {
            'source': file_path,
            'metadata': metadata,
            'error': 'Failed to upload {} to channel_id {} (Reason: {})'.format(
                file_path, channel_id, e)
        }
        report_queue.put((RAISE_ERROR, publisher_id, 0, options))
