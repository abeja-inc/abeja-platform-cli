import os

import requests_mock
from pyfakefs.fake_filesystem_unittest import TestCase

from abejacli.bucket.download_job import (DOWNLOAD_RETRY_ATTEMPT_NUMBER,
                                          _get_default_file_path, download_job)
from abejacli.bucket.process_file_job import (FINISH_REPORT, INITIALIZE_REPORT,
                                              PROGRESS_REPORT, RAISE_ERROR)
from abejacli.config import ORGANIZATION_ENDPOINT

try:
    from unittest.mock import MagicMock, ANY
except ImportError:
    from mock import MagicMock, ANY


ORGANIZATION_ID = '1122334455667'
BUCKET_ID = '1981155819522'
DOWNLOAD_DIR = '/target'
FILE_NAME = 'file2/file2-2.txt'
FILE_ID = 'file2/file2-2.txt'
DOWNLOAD_URI = "https://abeja-storage-bucket-dev.s3.amazonaws.com/1122334455667/1981155819522/file2/file2-2.txt?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696"  # noqa

FILE_INFO = {
    "expires": "2017-11-21T02:18:16+00:00",
    "metadata": {
        "x-abeja-meta-filename": FILE_ID
    },
    "file_id": FILE_ID,
    "is_file": True,
    "size": 4,
    "etag": "etag",
    "download_uri": DOWNLOAD_URI
}


class ResolveFilePathTest(TestCase):

    def setUp(self):
        self.setUpPyfakefs()

    def test_get_default_file_path(self):
        self.fs.create_dir(DOWNLOAD_DIR)
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.txt'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file2/file2-2.txt'))

        file_path = _get_default_file_path(DOWNLOAD_DIR, 'file.txt')
        self.assertEqual('/target/file.txt', file_path)
        file_path = _get_default_file_path(DOWNLOAD_DIR, 'file2/file2-2.txt')
        self.assertEqual('/target/file2/file2-2.txt', file_path)


class DownloadWorkerTest(TestCase):

    def setUp(self):
        self.setUpPyfakefs()

    @requests_mock.Mocker()
    def test_download(self, mock):
        content = 'dummy content'
        worker_option = {
            'download_dir': DOWNLOAD_DIR
        }

        report_queue = MagicMock()

        # mock file
        self.fs.create_dir(DOWNLOAD_DIR)
        self.fs.create_dir(os.path.join(DOWNLOAD_DIR, "file2"))
        # mock download request
        mock.register_uri('GET', DOWNLOAD_URI, text=content)
        download_job(BUCKET_ID, FILE_INFO, report_queue, worker_option)
        with open(os.path.join(DOWNLOAD_DIR, FILE_NAME), 'r') as f:
            download_content = f.read()
            assert download_content == content
        result_options = {
            'source': FILE_ID,
            'destination': os.path.join(DOWNLOAD_DIR, FILE_NAME),
        }
        assert report_queue.put.call_count == 3
        report_queue.put.assert_any_call((INITIALIZE_REPORT, ANY, 0, ANY))
        report_queue.put.assert_any_call(
            (PROGRESS_REPORT, ANY, len(content), None))
        report_queue.put.assert_any_call(
            (FINISH_REPORT, ANY, 0, result_options))

    @requests_mock.Mocker()
    def test_download_expired(self, mock):
        expired_download_uri = "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071056-b2168632-7aae-47ad-8339-9e6463607e6e-expired?AWSAccessKeyId=expired&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696"  # noqa
        content = 'dummy content'
        worker_option = {
            'download_dir': DOWNLOAD_DIR
        }

        report_queue = MagicMock()

        self.fs.create_dir(DOWNLOAD_DIR)
        self.fs.create_dir(os.path.join(DOWNLOAD_DIR, "file2"))
        # mock download request with expired download_uri
        mock.register_uri('GET', expired_download_uri, status_code=403)
        # mock request to get new download_uri
        mock.register_uri('GET', '{}/buckets/{}/files/{}'.format(ORGANIZATION_ENDPOINT, BUCKET_ID, FILE_ID),
                          json={'download_uri': DOWNLOAD_URI})
        # mock download request
        mock.register_uri('GET', DOWNLOAD_URI, text=content)
        download_job(BUCKET_ID, FILE_INFO, report_queue, worker_option)
        with open(os.path.join(DOWNLOAD_DIR, FILE_NAME), 'r') as f:
            download_content = f.read()
            assert download_content == content
        result_options = {
            'source': FILE_ID,
            'destination': os.path.join(DOWNLOAD_DIR, FILE_NAME),
        }
        assert report_queue.put.call_count == 3
        report_queue.put.assert_any_call((INITIALIZE_REPORT, ANY, 0, ANY))
        report_queue.put.assert_any_call(
            (PROGRESS_REPORT, ANY, len(content), None))
        report_queue.put.assert_any_call(
            (FINISH_REPORT, ANY, 0, result_options))

    @requests_mock.Mocker()
    def test_download_fail(self, mock):
        worker_option = {
            'download_dir': DOWNLOAD_DIR
        }

        report_queue = MagicMock()

        # mock file
        self.fs.create_dir(DOWNLOAD_DIR)
        # mock download request
        mock.register_uri('GET', DOWNLOAD_URI, status_code=500)
        download_job(BUCKET_ID, FILE_INFO, report_queue, worker_option)
        assert report_queue.put.call_count == DOWNLOAD_RETRY_ATTEMPT_NUMBER
        expected_options = {
            'source': FILE_ID,
            'error': 'Failed to download {} of bucket_id {}'.format(FILE_ID, BUCKET_ID)
        }
        report_queue.put.assert_any_call(
            (RAISE_ERROR, ANY, 0, expected_options))
