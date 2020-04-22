import glob
import os
import uuid

from retrying import retry

from abejacli.config import (
    ABEJA_API_URL,
    HTTP_READ_CHUNK_SIZE,
    PLATFORM_REQUEST_TIMEOUT_SECONDS
)
from abejacli.datalake.process_file_job import (
    FINISH_REPORT,
    INITIALIZE_REPORT,
    PROGRESS_REPORT,
    RAISE_ERROR,
    SKIP_REPORT
)
from abejacli.session import generate_retry_session, generate_user_session


def _get_default_file_path(download_dir, file_name):
    return os.path.join(download_dir, file_name.replace('/', '-'))


def _resolve_file_path(download_dir, file_name):
    """
    return file path to save.
    Numbered file path is returned to resolve conflicts

    :param file_path:
    :return:
    """
    # separate file path to basename and extension
    basename = _get_default_file_path(download_dir, file_name)
    ext = ''
    while True:
        basename, new_ext = os.path.splitext(basename)
        if not new_ext:
            break
        ext = new_ext + ext

    # get existing files with same name
    # NOTICE: glob does not support regex, we expect "*" is number
    sibling_files = glob.glob('{}.*{}'.format(basename, ext))

    def number_from_path(path):
        """
        return number from file path
        ex) /target/file.1.txt -> 1
        ex) /target/file.2.tar.gz -> 2
        """
        try:
            num = int(path[len(basename) + 1:-len(ext)])
        except ValueError:
            return 0
        return num

    # find max number
    if not sibling_files:
        assign_number = 1
    else:
        max_numbered_path = max(sibling_files, key=number_from_path)
        max_number = number_from_path(max_numbered_path)
        assign_number = max_number + 1

    return ''.join([basename, '.', str(assign_number), ext])


def download_job(channel_id, file_info, report_queue, options):
    """
    download files until consuming all items in file queue

    :param channel_id: channel identifier
    :param file_info: information of file to download
    :param report_queue: queue to report progress for each file
    :param options: option including target download directory
    :return:
    """
    try:
        _download_job_proecess(channel_id, file_info, report_queue, options)
    except:
        # pass to keep the thread running
        pass


DOWNLOAD_RETRY_ATTEMPT_NUMBER = 3


@retry(stop_max_attempt_number=DOWNLOAD_RETRY_ATTEMPT_NUMBER)
def _download_job_proecess(channel_id, file_info, report_queue, options):
    """
    download files until consuming all items in file queue

    :param channel_id: channel identifier
    :param file_info: information of file to download
    :param report_queue: queue to report progress for each file
    :param options: option including target download directory
    :return:
    """

    publisher_id = uuid.uuid4().hex
    download_dir = options.get('download_dir', '.')
    saving_file_name_type = options.get('file_name_type')
    skip_duplicate = options.get('skip_duplicate', False)

    file_id = file_info.get('file_id')
    file_meta = file_info.get('metadata', {})
    download_uri = file_info.get('download_uri')

    if saving_file_name_type == 'id':
        file_name = file_id
    else:
        file_name = file_meta.get('x-abeja-meta-filename') or file_id

    download_path = None
    is_downloading = True
    try:
        # download file content
        with generate_retry_session() as session:
            download_stream_res = session.get(
                download_uri, stream=True, timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
        # update pre-signed url if expired
        if download_stream_res.status_code == 403:
            url = "{}/channels/{}/{}".format(ABEJA_API_URL,
                                             channel_id, file_id)
            with generate_user_session() as user_session:
                res = user_session.get(
                    url, timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
            res.raise_for_status()
            file_info = res.json()
            download_uri = file_info.get('download_uri')
            with generate_retry_session() as session:
                download_stream_res = session.get(
                    download_uri, stream=True, timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
        download_stream_res.raise_for_status()
        total_size = int(download_stream_res.headers.get('content-length', 0))

        initialize_options = {
            'file_name': file_name,
            'total': total_size,
        }
        report_queue.put(
            (INITIALIZE_REPORT, publisher_id, 0, initialize_options))
        download_path = _get_default_file_path(download_dir, file_name)
        result_options = {
            'source': file_id,
            'destination': download_path,
        }
        if os.path.exists(download_path):
            if skip_duplicate:
                report_queue.put(
                    (SKIP_REPORT, publisher_id, 0, result_options))
                return
            else:
                # update destination path ot resolve conflict
                result_options['destination'] = _resolve_file_path(
                    download_dir, file_name)
        is_downloading = True
        with open(download_path, 'wb') as f:
            for chunk in download_stream_res.iter_content(chunk_size=HTTP_READ_CHUNK_SIZE):
                # update tqdm progress bar with chunk data size
                report_queue.put(
                    (PROGRESS_REPORT, publisher_id, len(chunk), None))
                f.write(chunk)

        report_queue.put((FINISH_REPORT, publisher_id, 0, result_options))
    except:
        if is_downloading and download_path is not None and os.path.exists(download_path):
            os.remove(download_path)
        options = {
            'source': file_id,
            'error': 'Failed to download {} of channel_id {}'.format(file_id, channel_id)
        }
        report_queue.put((RAISE_ERROR, publisher_id, 0, options))
        raise
