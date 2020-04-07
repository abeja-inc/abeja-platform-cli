import os

import requests_mock
from abejacli.config import ABEJA_API_URL
from abejacli.datalake.download_job import (_get_default_file_path, _resolve_file_path,
                                            download_job, DOWNLOAD_RETRY_ATTEMPT_NUMBER)
from abejacli.datalake.process_file_job import (FINISH_REPORT,
                                                INITIALIZE_REPORT,
                                                PROGRESS_REPORT, RAISE_ERROR)
from nose.tools import assert_equals
from pyfakefs.fake_filesystem_unittest import TestCase

try:
    from unittest.mock import MagicMock, ANY
except ImportError:
    from mock import MagicMock, ANY


CHANNEL_ID = '1282495447337'
DOWNLOAD_DIR = '/target'
FILE_NAME = 'file.txt'
FILE_ID = '20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e'
DOWNLOAD_URI = "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071056-b2168632-7aae-47ad-8339-9e6463607e6e?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696"  # noqa

FILE_INFO = {
    "url_expires_on": "2017-11-21T02:18:16+00:00",
    "uploaded_at": "2017-11-16T07:10:56+00:00",
    "metadata": {
        "x-abeja-meta-filename": FILE_NAME
    },
    "file_id": FILE_ID,
    "download_uri": DOWNLOAD_URI,
    "content_type": "text/plain"
}


class ResolveFilePathTest(TestCase):

    def setUp(self):
        self.setUpPyfakefs()

    def test_duplicated(self):
        self.fs.create_dir(DOWNLOAD_DIR)
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.txt'))

        # default_file_path = os.path.join(DOWNLOAD_DIR, 'file.txt')
        file_path = _resolve_file_path(DOWNLOAD_DIR, 'file.txt')
        self.assertEquals('/target/file.1.txt', file_path)

    def test_duplicated_with_increments(self):
        self.fs.create_dir(DOWNLOAD_DIR)
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.txt'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.1.txt'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.2.txt'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.3.txt'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.4.txt'))

        # default_file_path = os.path.join(DOWNLOAD_DIR, 'file.txt')
        file_path = _resolve_file_path(DOWNLOAD_DIR, 'file.txt')
        self.assertEquals('/target/file.5.txt', file_path)

    def test_none_duplicated(self):
        self.fs.create_dir(DOWNLOAD_DIR)
        file_path = _get_default_file_path(DOWNLOAD_DIR, 'file.txt')
        self.assertEquals('/target/file.txt', file_path)

    def test_duplicated_multiple_ext(self):
        self.fs.create_dir(DOWNLOAD_DIR)
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.gz'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.1.gz'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.tar.gz'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.1.tar.gz'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.2.tar.gz'))
        self.fs.create_file(os.path.join(DOWNLOAD_DIR, 'file.3.tar.gz'))

        file_path = _resolve_file_path(DOWNLOAD_DIR, 'file.tar.gz')
        self.assertEquals('/target/file.4.tar.gz', file_path)


class DownloadWorkerTest(TestCase):

    def setUp(self):
        self.setUpPyfakefs()

    @requests_mock.Mocker()
    def test_download(self, mock):
        content = 'dummy content'
        worker_optioin = {
            'download_dir': DOWNLOAD_DIR
        }

        report_queue = MagicMock()

        # mock file
        self.fs.create_dir(DOWNLOAD_DIR)
        # mock download request
        mock.register_uri('GET', DOWNLOAD_URI, text=content)
        download_job(CHANNEL_ID, FILE_INFO, report_queue, worker_optioin)
        with open(os.path.join(DOWNLOAD_DIR, FILE_NAME), 'r') as f:
            download_content = f.read()
            assert_equals(download_content, content)
        result_options = {
            'source': FILE_ID,
            'destination': os.path.join(DOWNLOAD_DIR, FILE_NAME),
        }
        assert_equals(report_queue.put.call_count, 3)
        report_queue.put.assert_any_call((INITIALIZE_REPORT, ANY, 0, ANY))
        report_queue.put.assert_any_call(
            (PROGRESS_REPORT, ANY, len(content), None))
        report_queue.put.assert_any_call(
            (FINISH_REPORT, ANY, 0, result_options))

    @requests_mock.Mocker()
    def test_download_expired(self, mock):
        expired_download_uri = "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071056-b2168632-7aae-47ad-8339-9e6463607e6e-expired?AWSAccessKeyId=expired&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696"  # noqa
        content = 'dummy content'
        worker_optioin = {
            'download_dir': DOWNLOAD_DIR
        }

        report_queue = MagicMock()

        self.fs.create_dir(DOWNLOAD_DIR)
        # mock download request with expired download_uri
        mock.register_uri('GET', expired_download_uri, status_code=403)
        # mock request to get new download_uri
        mock.register_uri('GET', '{}/channels/{}/{}'.format(ABEJA_API_URL, CHANNEL_ID, FILE_ID),
                          json={'download_uri': DOWNLOAD_URI})
        # mock download request
        mock.register_uri('GET', DOWNLOAD_URI, text=content)
        download_job(CHANNEL_ID, FILE_INFO, report_queue, worker_optioin)
        with open(os.path.join(DOWNLOAD_DIR, FILE_NAME), 'r') as f:
            download_content = f.read()
            assert_equals(download_content, content)
        result_options = {
            'source': FILE_ID,
            'destination': os.path.join(DOWNLOAD_DIR, FILE_NAME),
        }
        assert_equals(report_queue.put.call_count, 3)
        report_queue.put.assert_any_call((INITIALIZE_REPORT, ANY, 0, ANY))
        report_queue.put.assert_any_call(
            (PROGRESS_REPORT, ANY, len(content), None))
        report_queue.put.assert_any_call(
            (FINISH_REPORT, ANY, 0, result_options))

    @requests_mock.Mocker()
    def test_download_fail(self, mock):
        worker_optioin = {
            'download_dir': DOWNLOAD_DIR
        }

        report_queue = MagicMock()

        # mock file
        self.fs.create_dir(DOWNLOAD_DIR)
        # mock download request
        mock.register_uri('GET', DOWNLOAD_URI, status_code=500)
        download_job(CHANNEL_ID, FILE_INFO, report_queue, worker_optioin)
        assert_equals(report_queue.put.call_count, DOWNLOAD_RETRY_ATTEMPT_NUMBER)
        expected_options = {
            'source': FILE_ID,
            'error': 'Failed to download {} of channel_id {}'.format(FILE_ID, CHANNEL_ID)
        }
        report_queue.put.assert_any_call(
            (RAISE_ERROR, ANY, 0, expected_options))
