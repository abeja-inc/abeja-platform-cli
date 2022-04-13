import os.path

import requests_mock
from pyfakefs.fake_filesystem_unittest import TestCase

from abejacli.config import ABEJA_API_URL, FILE_READ_CHUNK_SIZE
from abejacli.datalake.process_file_job import (
    FINISH_REPORT,
    INITIALIZE_REPORT,
    PROGRESS_REPORT,
    RAISE_ERROR
)
from abejacli.datalake.upload_job import upload_job
from abejacli.fs_utils import UploadFile

try:
    from unittest.mock import ANY, MagicMock
except ImportError:
    from mock import ANY, MagicMock


CHANNEL_ID = '1282495447337'
FILE_ID = '20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e'
UPLOAD_FILE_PATH = 'target/dummy.jpeg'
UPLOAD_FILE_CONTENT_TYPE = 'image/jpeg'
UPLOAD_FILE_REQ_HEADERS = {
    'x-abeja-meta-filename': os.path.basename(UPLOAD_FILE_PATH),
    'content-type': UPLOAD_FILE_CONTENT_TYPE,
}
UPLOAD_FILE_CONTENTS = 'a,b,c\ne,f,g'


def request_body_matcher(request):
    # requests_mock set IterableToFileAdapter passed as request body to request.text
    # this method works to consume UploadFileIterator all as well
    request_text = ''
    while True:
        read_text = request.text.read(FILE_READ_CHUNK_SIZE).decode('utf-8')
        if not read_text:
            break
        request_text += read_text
    return request_text == UPLOAD_FILE_CONTENTS


class UploadWorkerTest(TestCase):

    def setUp(self):
        self.setUpPyfakefs()

    @requests_mock.Mocker()
    def test_upload(self, requests_mock):
        request_headers = UPLOAD_FILE_REQ_HEADERS.copy()
        response_headers = {
            'content-length': str(len(UPLOAD_FILE_CONTENTS))
        }

        file_info = UploadFile(UPLOAD_FILE_PATH)
        report_queue = MagicMock()

        # mock file
        self.fs.create_file(UPLOAD_FILE_PATH, contents=UPLOAD_FILE_CONTENTS)

        # mock upload request
        url = "{}/channels/{}/upload".format(ABEJA_API_URL, CHANNEL_ID)
        requests_mock.register_uri(
            'POST',
            url,
            request_headers=request_headers,
            headers=response_headers,
            additional_matcher=request_body_matcher,
            json={'file_id': FILE_ID})

        # execute upload job
        result_options = {
            'source': UPLOAD_FILE_PATH,
            'destination': FILE_ID,
            'metadata': {}
        }
        upload_job(CHANNEL_ID, file_info, report_queue, None)
        assert report_queue.put.call_count == 3
        report_queue.put.assert_any_call((INITIALIZE_REPORT, ANY, 0, ANY))
        report_queue.put.assert_any_call(
            (PROGRESS_REPORT, ANY, len(UPLOAD_FILE_CONTENTS), None))
        report_queue.put.assert_any_call(
            (FINISH_REPORT, ANY, 0, result_options))

    @requests_mock.Mocker()
    def test_upload_with_metadata_and_filename(self, requests_mock):

        metadata = (
            ('key1', 'value1'),
            ('key2', '日本語'),
            # JSON file spec can contain integer values
            ('key3', 12345),
            (12345, 67890),
        )
        metadata_res = dict([(str(k), v) for k, v in metadata])

        response_headers = {
            'content-length': str(len(UPLOAD_FILE_CONTENTS))
        }

        file_info = UploadFile('target/日本語.csv')
        report_queue = MagicMock()

        # mock file
        self.fs.create_file(file_info.path, contents=UPLOAD_FILE_CONTENTS)

        # mock upload request
        url = "{}/channels/{}/upload".format(ABEJA_API_URL, CHANNEL_ID)
        requests_mock.register_uri(
            'POST',
            url,
            json={'file_id': FILE_ID, 'metadata': metadata_res},
            headers=response_headers,
            additional_matcher=request_body_matcher
        )

        # execute upload job
        worker_options = {
            'metadata': metadata,
        }
        upload_job(CHANNEL_ID, file_info, report_queue, worker_options)
        assert report_queue.put.call_count == 3
        report_queue.put.assert_any_call((INITIALIZE_REPORT, ANY, 0, ANY))
        report_queue.put.assert_any_call(
            (PROGRESS_REPORT, ANY, len(UPLOAD_FILE_CONTENTS), None))
        result_options = {
            'source': file_info.path,
            'destination': FILE_ID,
            'metadata': metadata_res
        }
        report_queue.put.assert_any_call(
            (FINISH_REPORT, ANY, 0, result_options))

        req = requests_mock.request_history[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.headers['x-abeja-meta-filename'],
                         r'%E6%97%A5%E6%9C%AC%E8%AA%9E.csv')
        self.assertEqual(req.headers['x-abeja-meta-key1'], 'value1')
        self.assertEqual(
            req.headers['x-abeja-meta-key2'], r'%E6%97%A5%E6%9C%AC%E8%AA%9E')
        self.assertEqual(req.headers['x-abeja-meta-key3'], '12345')
        self.assertEqual(req.headers['x-abeja-meta-12345'], '67890')

    @requests_mock.Mocker()
    def test_upload_fail(self, requests_mock):
        request_headers = UPLOAD_FILE_REQ_HEADERS.copy()
        file_path = UPLOAD_FILE_PATH
        report_queue = MagicMock()

        # mock file
        self.fs.create_file(UPLOAD_FILE_PATH, contents=UPLOAD_FILE_CONTENTS)
        # mock upload request
        url = "{}/channels/{}/upload".format(ABEJA_API_URL, CHANNEL_ID)
        requests_mock.register_uri(
            'POST', url, request_headers=request_headers, status_code=403)
        # execute upload job
        upload_job(CHANNEL_ID, UploadFile(file_path), report_queue, None)
        assert report_queue.put.call_count == 1

        _name, args, kwargs = report_queue.put.mock_calls[0]

        self.assertEqual(args[0][0], RAISE_ERROR)
        self.assertEqual(args[0][2], 0)
        self.assertEqual(args[0][3]['source'], UPLOAD_FILE_PATH)
        self.assertNotIn('destination', args[0][3])
        self.assertIn('metadata', args[0][3])
        self.assertIsNotNone(args[0][3]['error'])
