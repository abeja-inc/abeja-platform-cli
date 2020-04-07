import json
import os.path
import time
from unittest import TestCase

from abejacli.config import (ABEJA_API_URL, ERROR_EXITCODE,
                             JOB_WORKER_THREAD_NUM, SUCCESS_EXITCODE)
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.run import datalake
from click.testing import CliRunner

import requests_mock
from pyfakefs import fake_filesystem_unittest

from tests.unit import ConfigPatcher


def request_body_matcher(request):
    # requests_mock set IterableToFileAdapter passed as request body to request.text
    # this method works to consume UploadFileIterator all as well
    while request.text.read(1024):
        pass

    return True


class DataLakeRunnerTest(TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.config_patcher = ConfigPatcher().any().start()
        self.fakefs_patcher = fake_filesystem_unittest.Patcher()
        self.fakefs_patcher.setUp()

    def tearDown(self):
        self.fakefs_patcher.tearDown()
        self.config_patcher.stop()

    # create-channel

    @requests_mock.Mocker()
    def test_create_datalake_channel_with_no_args(self, mock):
        cmd = ['create-channel']
        url = "{}/channels".format(ORGANIZATION_ENDPOINT)
        res = {"dummy": "dummy"}
        m = mock.register_uri('POST', url, json=res)

        r = self.runner.invoke(datalake, cmd)

        self.assertEqual(json.loads(r.output), res)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

        params = m.last_request.json()
        self.assertEqual(params, {})

    # archive-channel

    @requests_mock.Mocker()
    def test_archive_datalake_channel(self, mock):
        testing_channel_id = '123456789'
        cmd = ['archive-channel', '-c', testing_channel_id]
        url = "{}/channels/{}/archive".format(ORGANIZATION_ENDPOINT, testing_channel_id)
        res = {"dummy": "dummy"}
        m = mock.register_uri('POST', url, json=res)

        r = self.runner.invoke(datalake, cmd)

        self.assertEqual(json.loads(r.output), res)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

    # upload

    @requests_mock.Mocker()
    def test_upload_no_file(self, mock):
        cmd = ['upload', '-c', 12345]
        r = self.runner.invoke(datalake, cmd)
        self.assertRegex(r.output, r'No file specified')
        self.assertEqual(r.exit_code, ERROR_EXITCODE)

    @requests_mock.Mocker()
    def test_upload_dry_run(self, mock):
        files = sorted([
            '/dummy/test1.txt',
            '/dummy/test2.txt',
        ])

        for f in files:
            self.fakefs_patcher.fs.create_file(f, contents='test')

        cmd = ['upload', '-c', 12345, '--dry-run', *files]
        r = self.runner.invoke(datalake, cmd)
        self.assertRegex(r.output, '\n    '.join(files))
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)

    @requests_mock.Mocker()
    def test_upload_file_with_metadata(self, mock):
        channel_id = 12345
        filepath = '/dummy/test.csv'
        self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')

        result_filepath = '/dummy/result.json'
        self.fakefs_patcher.fs.create_file(result_filepath, contents='')

        url = "{}/channels/{}/upload".format(ABEJA_API_URL, channel_id)
        m = mock.register_uri(
            'POST', url, json={'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF'},
            additional_matcher=request_body_matcher)

        cmd = [
            'upload', '-c', 12345, '--meta-data', 'label:neko',
            '--save-result', result_filepath,
            filepath]
        r = self.runner.invoke(datalake, cmd)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

        req = m.last_request
        self.assertEqual(req.method, 'POST')
        self.assertEqual(
            req.headers['x-abeja-meta-filename'], os.path.basename(filepath))
        self.assertEqual(req.headers['x-abeja-meta-label'], 'neko')

        with open(result_filepath, 'r') as f:
            result = json.load(f)
            self.assertListEqual(result, [
                {
                    'channel_id': 12345,
                    'file': '/dummy/test.csv',
                    'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF',
                    'metadata': {}
                }
            ])

    @requests_mock.Mocker()
    def test_upload_file_with_metadata_and_filelist(self, mock):
        channel_id = 12345
        filepath = '/dummy/test.csv'
        listpath = '/dummy/list.json'
        self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')
        self.fakefs_patcher.fs.create_file(listpath, contents=json.dumps([
            {
                'file': filepath,
                'metadata': {
                    'label2': 'cat'
                }
            }
        ]))

        url = "{}/channels/{}/upload".format(ABEJA_API_URL, channel_id)
        m = mock.register_uri(
            'POST', url, json={'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF'},
            additional_matcher=request_body_matcher)

        cmd = ['upload', '-c', 12345, '--metadata',
               'label:neko', '--file-list', listpath]
        r = self.runner.invoke(datalake, cmd)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

        req = m.last_request
        self.assertEqual(req.method, 'POST')
        self.assertEqual(
            req.headers['x-abeja-meta-filename'], os.path.basename(filepath))
        self.assertEqual(req.headers['x-abeja-meta-label'], 'neko')
        self.assertEqual(req.headers['x-abeja-meta-label2'], 'cat')

    @requests_mock.Mocker()
    def test_upload_files_many_files_and_upload_error(self, mock):
        channel_id = 12345
        listpath = '/dummy/list.json'

        # Create files. The number of files is more than JOB_WORKER_THREAD_NUM
        n_files = JOB_WORKER_THREAD_NUM + 1
        file_list = []
        for i in range(n_files):
            filepath = 'dummy{}.txt'.format(i)
            self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')
            file_list.append({'file': filepath})

        self.fakefs_patcher.fs.create_file(
            listpath, contents=json.dumps(file_list))

        # Set up request mocker for failures and simulate low speed network
        def low_speed_failure_response(req, context):
            time.sleep(1)
            context.status_code = 403
            return 'Forbidden'

        url = "{}/channels/{}/upload".format(ABEJA_API_URL, channel_id)
        m = mock.register_uri(
            'POST', url, additional_matcher=request_body_matcher,
            text=low_speed_failure_response)

        cmd = ['upload', '-c', 12345, '--file-list', listpath, '--retry', 'no']
        r = self.runner.invoke(datalake, cmd)
        self.assertIsNone(r.exception)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

    @requests_mock.Mocker()
    def test_upload_file_with_skip_duplicate_files(self, mock):
        channel_id = 12345
        filepath = '/dummy/test.csv'
        self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')

        result_filepath = '/dummy/result.json'
        self.fakefs_patcher.fs.create_file(result_filepath, contents='')

        url = "{}/channels/{}/upload?conflict_target=filename".format(
            ABEJA_API_URL, channel_id)
        m = mock.register_uri(
            'POST', url, json={'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF'},
            status_code=409,
            additional_matcher=request_body_matcher)

        cmd = [
            'upload', '-c', channel_id,
            '--save-result', result_filepath,
            '--skip-duplicate-files',
            filepath]
        r = self.runner.invoke(datalake, cmd)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

        req = m.last_request
        self.assertEqual(req.method, 'POST')
        self.assertEqual(
            req.headers['x-abeja-meta-filename'], os.path.basename(filepath))

        with open(result_filepath, 'r') as f:
            result = json.load(f)
            self.assertListEqual(result, [
                {
                    'channel_id': 12345,
                    'file': '/dummy/test.csv',
                    'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF',
                    'metadata': {}
                }
            ])

    # create and upload

    @requests_mock.Mocker()
    def test_create_and_upload(self, mock):
        channel_id = 12345
        url = "{}/channels".format(ORGANIZATION_ENDPOINT)
        res = {"channel": {"channel_id": channel_id}}
        m1 = mock.register_uri('POST', url, json=res)

        filepath = '/dummy/test.csv'
        self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')
        result_filepath = '/dummy/result.json'
        self.fakefs_patcher.fs.create_file(result_filepath, contents='')

        url = "{}/channels/{}/upload".format(ABEJA_API_URL, channel_id)
        m2 = mock.register_uri(
            'POST', url, json={'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF'},
            additional_matcher=request_body_matcher)

        cmd = [
            'create-and-upload', '--meta-data', 'label:neko',
            '--save-result', result_filepath,
            filepath]
        r = self.runner.invoke(datalake, cmd)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)

        self.assertTrue(m1.called)
        params = m1.last_request.json()
        self.assertEqual(params, {})

        self.assertTrue(m2.called)
        req = m2.last_request
        self.assertEqual(req.method, 'POST')
        self.assertEqual(
            req.headers['x-abeja-meta-filename'], os.path.basename(filepath))
        self.assertEqual(req.headers['x-abeja-meta-label'], 'neko')

        with open(result_filepath, 'r') as f:
            result = json.load(f)
            self.assertListEqual(result, [
                {
                    'channel_id': 12345,
                    'file': '/dummy/test.csv',
                    'file_id': '180912-4DD2AF3E-D1EE-46AA-8B07-6303F88776EF',
                    'metadata': {}
                }
            ])
