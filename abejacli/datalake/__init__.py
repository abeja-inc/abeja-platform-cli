import os
from typing import Any, Iterable, Optional, Tuple

from abejacli.config import (
    ABEJA_API_URL,
    DATALAKE_ITEMS_PER_PAGE,
    PLATFORM_REQUEST_TIMEOUT_SECONDS
)
from abejacli.datalake.download_job import download_job
from abejacli.datalake.process_file_job import process_file_jobs
from abejacli.datalake.upload_job import upload_job
from abejacli.exceptions import InvalidDatalakeTimeInterval
from abejacli.fs_utils import UploadFile
from abejacli.logger import get_logger
from abejacli.session import generate_user_session

# Key-value metadata
Metadata = Iterable[Tuple[str, str]]

logger = get_logger()


def generate_channel_file_iter_by_period(channel_id, start=None, end=None):
    """
    generate file iterator in channel from specified start date to specified end date

    :param channel_id: datalake channel identifier
    :param start: start date (YYYYMMDD)
    :param end: send date (YYYYMMDD)
    :return:
    """
    url = "{}/channels/{}".format(ABEJA_API_URL, channel_id)
    params = {
        'items_per_page': DATALAKE_ITEMS_PER_PAGE
    }

    if start and end:
        params['start'] = start
        params['end'] = end
    if (start and not end) or (not start and end):
        logger.error(
            'both start and end are required for period of datalake file list')
        raise InvalidDatalakeTimeInterval()

    # Get upload url
    session = generate_user_session()

    while True:
        r = session.get(url, params=params,
                        timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        res = r.json()
        files = res.get('files')
        if not files or len(files) == 0:
            break
        # Iterate files
        for file_info in files:
            yield file_info
        next_page_token = res.get('next_page_token')
        if not next_page_token:
            break
        params = {
            'next_page_token': next_page_token
        }


def generate_channel_file_iter_by_id(channel_id, *file_ids):
    """
    generate file iterator for list of datalake file identifiers

    :param channel_id: datalake channel identifier
    :param file_ids: list of file id to iterate
    :return:
    """
    session = generate_user_session()

    for file_id in file_ids:
        url = "{}/channels/{}/{}".format(ABEJA_API_URL, channel_id, file_id)
        r = session.get(url, timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        file_info = r.json()
        yield file_info


def download_from_datalake(channel_id, file_iter, target_dir, file_name_type, skip_duplicate):
    """
    download files and store into target dier

    :param channel_id: channel identifier
    :param file_iter: iterator of file to download
    :param target_dir: download target dir
    :param file_name_type: saving file name type: file_name or file_id
    :param skip_duplicate: skip if target file already exists in target dir
    :return:
    """
    file_list = list(file_iter)
    file_num = len(file_list)

    # Setup worker_option
    worker_option = {
        'file_name_type': file_name_type,
        'download_dir': target_dir,
        'skip_duplicate': skip_duplicate
    }
    return process_file_jobs(channel_id, download_job, file_list, 'counter', file_num, worker_option)


def upload_to_datalake(
        channel_id: str,
        upload_file_iter: Iterable[UploadFile],
        metadata: Optional[Metadata] = None,
        conflict_target: Optional[str] = None) -> Any:
    """
    Upload files in path iterator to datalake channel

    :param channel_id: channel identifier
    :param upload_file_iter: iterator of ``UploadFile`` object
    :param metadata: metadata for each file
    :return:
    """
    options = {}

    if metadata:
        options['metadata'] = metadata
    if conflict_target:
        options['conflict_target'] = conflict_target

    # We have to iterate a generator to calculate the total size of files.
    files = []
    total_size = 0
    for upload_file in upload_file_iter:
        files.append(upload_file)
        total_size = total_size + os.path.getsize(upload_file.path)

    return process_file_jobs(channel_id, upload_job, files, 'size', total_size, options)
