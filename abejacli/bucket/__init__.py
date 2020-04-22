import os
from collections import deque
from typing import Any, Iterable, Optional, Tuple

from abejacli.bucket.download_job import download_job
from abejacli.bucket.process_file_job import process_file_jobs
from abejacli.bucket.upload_job import upload_job
from abejacli.config import (
    DATALAKE_ITEMS_PER_PAGE,
    ORGANIZATION_ENDPOINT,
    PLATFORM_REQUEST_TIMEOUT_SECONDS
)
from abejacli.fs_utils import UploadBucketFile
from abejacli.session import generate_user_session

# Key-value metadata
Metadata = Iterable[Tuple[str, str]]


def generate_bucket_file_iter(bucket_id):
    """
    generate file iterator in bucket

    :param bucket_id: datalake bucket identifier
    :return:
    """
    url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, bucket_id)
    params = {
        'target_dir': '/',
        'items_per_page': DATALAKE_ITEMS_PER_PAGE
    }

    # Get upload url
    session = generate_user_session()
    queue = deque()

    while True:
        r = session.get(url, params=params,
                        timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        res = r.json()
        files = res.get('files', [])
        if len(files) == 0:
            if len(queue) == 0:
                break
            else:
                target_dir = queue.popleft()
                params.update({
                    'target_dir': target_dir,
                    'start_after': target_dir
                })
        else:
            # Iterate files
            for file_info in files:
                if file_info['is_file']:
                    yield file_info
                else:
                    queue.append(file_info['file_id'])
            next_start_after = res.get('next_start_after')
            params.update({
                'start_after': next_start_after
            })


def generate_bucket_file_iter_by_id(bucket_id, *file_ids):
    """
    generate file iterator for list of bucket file identifiers

    :param bucket_id: datalake bucket identifier
    :param file_ids: list of file id to iterate
    :return:
    """
    session = generate_user_session()

    for file_id in file_ids:
        url = "{}/buckets/{}/files/{}".format(ORGANIZATION_ENDPOINT, bucket_id, file_id)
        r = session.get(url, timeout=PLATFORM_REQUEST_TIMEOUT_SECONDS)
        r.raise_for_status()
        file_info = r.json()
        yield file_info


def download_from_bucket(bucket_id, file_iter, target_dir):
    """
    download files and store into target dir

    :param bucket_id: bucket identifier
    :param file_iter: iterator of file to download
    :param target_dir: download target dir
    :return:
    """
    file_list = list(file_iter)
    file_num = len(file_list)

    # Setup worker_option
    worker_option = {
        'download_dir': target_dir
    }
    return process_file_jobs(bucket_id, download_job, file_list, 'counter', file_num, worker_option)


def upload_to_bucket(
        bucket_id: str,
        upload_bucket_iter: Iterable[UploadBucketFile],
        metadata: Optional[Metadata] = None) -> Any:
    """
    Upload files in path iterator to datalake bucket

    :param bucket_id: bucket identifier
    :param upload_bucket_iter: iterator of ``UploadBucketFile`` object
    :param metadata: metadata for each file
    :return:
    """
    options = {}

    if metadata:
        options['metadata'] = metadata

    # We have to iterate a generator to calculate the total size of files.
    files = []
    total_size = 0
    for upload_bucket_file in upload_bucket_iter:
        files.append(upload_bucket_file)
        total_size = total_size + os.path.getsize(upload_bucket_file.path)

    return process_file_jobs(bucket_id, upload_job, files, 'size', total_size, options)
