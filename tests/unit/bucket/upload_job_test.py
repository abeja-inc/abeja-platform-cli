import requests_mock
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.bucket.process_file_job import (FINISH_REPORT,
                                              INITIALIZE_REPORT,
                                              PROGRESS_REPORT,
                                              RAISE_ERROR)
from abejacli.bucket.upload_job import upload_job
from abejacli.fs_utils import UploadBucketFile
from pyfakefs.fake_filesystem_unittest import TestCase

try:
    from unittest.mock import MagicMock, ANY
except ImportError:
    from mock import MagicMock, ANY


BUCKET_ID = '1282495447337'
FILE_ID = 'file/dummy.jpeg'
UPLOAD_FILE_PATH = 'target/file/dummy.jpeg'
UPLOAD_FILE_CONTENT_TYPE = 'image/jpeg'
UPLOAD_FILE_REQ_HEADERS = {
    'x-abeja-meta-filename': FILE_ID,
    'content-type': UPLOAD_FILE_CONTENT_TYPE,
}
UPLOAD_FILE_CONTENTS = 'a,b,c\ne,f,g'


class UploadWorkerTest(TestCase):

    def setUp(self):
        self.setUpPyfakefs()

    @requests_mock.Mocker()
    def test_upload(self, requests_mock):
        response = {
            'file_id': FILE_ID,
            'metadata': {}
        }

        file_info = UploadBucketFile(FILE_ID, UPLOAD_FILE_PATH)
        report_queue = MagicMock()

        # mock file
        self.fs.create_file(UPLOAD_FILE_PATH, contents=UPLOAD_FILE_CONTENTS)

        # mock upload request
        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, BUCKET_ID)
        requests_mock.register_uri('POST', url, json=response)

        # execute upload job
        result_options = {
            'source': UPLOAD_FILE_PATH,
            'destination': FILE_ID,
            'metadata': {}
        }
        upload_job(BUCKET_ID, file_info, report_queue, None)
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
        response = {
            'file_id': FILE_ID,
            'metadata': metadata_res
        }

        file_info = UploadBucketFile('日本語.csv', 'target/日本語.csv')
        report_queue = MagicMock()

        # mock file
        self.fs.create_file(file_info.path, contents=UPLOAD_FILE_CONTENTS)

        # mock upload request
        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, BUCKET_ID)
        requests_mock.register_uri(
            'POST',
            url,
            headers=response_headers,
            json=response,
        )

        # execute upload job
        worker_options = {
            'metadata': metadata,
        }
        upload_job(BUCKET_ID, file_info, report_queue, worker_options)
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
        file_id = FILE_ID
        file_path = UPLOAD_FILE_PATH
        report_queue = MagicMock()

        # mock file
        self.fs.create_file(UPLOAD_FILE_PATH, contents=UPLOAD_FILE_CONTENTS)
        # mock upload request
        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, BUCKET_ID)
        requests_mock.register_uri(
            'POST', url, request_headers=request_headers, status_code=403)
        # execute upload job
        upload_job(BUCKET_ID, UploadBucketFile(file_id, file_path), report_queue, None)
        assert report_queue.put.call_count == 2

        _name, args, kwargs = report_queue.put.mock_calls[1]

        self.assertEqual(args[0][0], RAISE_ERROR)
        self.assertEqual(args[0][2], 0)
        self.assertEqual(args[0][3]['source'], UPLOAD_FILE_PATH)
        self.assertIsNotNone(args[0][3]['destination'])
        self.assertIn('metadata', args[0][3])
        self.assertIsNotNone(args[0][3]['error'])
