import json
import os
import urllib.parse
import uuid
from io import BytesIO
from mimetypes import guess_type

from abejacli.bucket.process_file_job import (
    FINISH_REPORT,
    INITIALIZE_REPORT,
    PROGRESS_REPORT,
    RAISE_ERROR
)
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.fs_utils import UploadBucketFile
from abejacli.session import generate_user_session


def upload_job(bucket_id, upload_file: UploadBucketFile, report_queue, options):
    """
    upload files until consuming all items in file queue

    :param bucket_id: bucket identifier
    :param upload_file: ``UploadBucketFile`` object to upload
    :param report_queue: queue to report progress for each file
    :param options: job options
    :return:
    """

    publisher_id = uuid.uuid4().hex
    file_path = upload_file.path
    file_id = upload_file.key
    options = options if options else {}
    metadata = {}

    try:
        finished_status = FINISH_REPORT
        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, bucket_id)

        type, _ = guess_type(file_path)
        headers = {}

        # Runtime option `metadata` overwrites metadata specified in
        # file list spec.
        metadata = upload_file.metadata or metadata
        metadata['filename'] = upload_file.key
        for key, value in options.get('metadata', ()):
            metadata[key] = value

        for key, value in metadata.items():
            key = urllib.parse.quote(str(key), encoding='utf-8')
            value = urllib.parse.quote(str(value), encoding='utf-8')
            headers['x-abeja-meta-{}'.format(key)] = value

        total = os.path.getsize(file_path)
        initialize_options = {
            'file_name': file_path,
            'total': total,
        }
        report_queue.put(
            (INITIALIZE_REPORT, publisher_id, 0, initialize_options))
        with generate_user_session(json_content_type=False) as session:
            with open(str(file_path), 'rb') as file_obj:
                params = {}
                params = BytesIO(json.dumps(params).encode())
                files = {
                    'file': (file_id, file_obj, type),
                    'parameters': ('params.json', params, 'application/json')
                }
                # Uploading file shouldn't be timed out!
                upload_res = session.post(
                    url, files=files, headers=headers, timeout=None)
                report_queue.put(
                    (PROGRESS_REPORT, publisher_id, total, None))

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
            'destination': file_id,
            'metadata': metadata,
            'error': 'Failed to upload {} to bucket_id {} (Reason: {})'.format(
                file_path, bucket_id, e)
        }
        report_queue.put((RAISE_ERROR, publisher_id, 0, options))
