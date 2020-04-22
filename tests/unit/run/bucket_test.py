import json
import os.path
from unittest import TestCase

import requests_mock
from click.testing import CliRunner
from pyfakefs import fake_filesystem_unittest

from abejacli.config import (
    INVALID_PARAMETER_EXITCODE,
    ORGANIZATION_ENDPOINT,
    SUCCESS_EXITCODE
)
from abejacli.run import bucket
from tests.unit import ConfigPatcher


class BucketRunnerTest(TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.config_patcher = ConfigPatcher().any().start()
        self.fakefs_patcher = fake_filesystem_unittest.Patcher()
        self.fakefs_patcher.setUp()

    def tearDown(self):
        self.fakefs_patcher.tearDown()
        self.config_patcher.stop()

    # create-bucket

    @requests_mock.Mocker()
    def test_create_bucket_with_no_args(self, mock):
        cmd = ['create-bucket']
        url = "{}/buckets".format(ORGANIZATION_ENDPOINT)
        res = {"dummy": "dummy"}
        m = mock.register_uri('POST', url, json=res)

        r = self.runner.invoke(bucket, cmd)

        actual_response = json.loads(r.output[r.output.index('{'):])  # FIXME: Use `r.output` after GA release.
        self.assertEqual(actual_response, res)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)
        self.assertTrue(m.called)

        params = m.last_request.json()
        self.assertEqual(params, {})

    # upload

    @requests_mock.Mocker()
    def test_upload_no_file(self, mock):
        cmd = ['upload', '-b', 12345]
        r = self.runner.invoke(bucket, cmd)
        self.assertRegex(r.output, r'Error: Missing argument.')
        self.assertEqual(r.exit_code, INVALID_PARAMETER_EXITCODE)

    @requests_mock.Mocker()
    def test_upload_dry_run(self, mock):
        files = sorted([
            '/dummy/test1.txt',
            '/dummy/test2.txt',
        ])

        for f in files:
            self.fakefs_patcher.fs.create_file(f, contents='test')

        cmd = ['upload', '-b', 12345, '--dry-run', '/dummy']
        r = self.runner.invoke(bucket, cmd)
        self.assertRegex(r.output, '\n    '.join(files))
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)

    @requests_mock.Mocker()
    def test_upload(self, mock):
        files = sorted([
            '/dummy/test1.txt',
            '/dummy/test2.txt',
        ])

        for f in files:
            self.fakefs_patcher.fs.create_file(f, contents='test')
        bucket_id = 12345
        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, bucket_id)
        mock.register_uri(
            'POST', url, json={'file_id': 'test.csv'})

        cmd = ['upload', '-b', bucket_id, '/dummy']
        r = self.runner.invoke(bucket, cmd)
        self.assertEqual(r.exit_code, SUCCESS_EXITCODE)

    @requests_mock.Mocker()
    def test_upload_file_with_metadata(self, mock):
        bucket_id = 12345
        filepath = '/dummy/test.csv'
        self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')

        result_filepath = '/output/result.json'
        self.fakefs_patcher.fs.create_file(result_filepath, contents='')

        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, bucket_id)
        m = mock.register_uri(
            'POST', url, json={'file_id': 'test.csv'})

        cmd = [
            'upload', '-b', 12345, '--meta-data', 'label:neko',
            '--save-result', result_filepath,
            'dummy']
        r = self.runner.invoke(bucket, cmd)
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
                    'bucket_id': 12345,
                    'source': 'dummy/test.csv',
                    'file_id': 'test.csv'
                }
            ])

    # create and upload

    @requests_mock.Mocker()
    def test_create_and_upload(self, mock):
        bucket_id = 12345
        url = "{}/buckets".format(ORGANIZATION_ENDPOINT)
        res = {"bucket": {"bucket_id": bucket_id}}
        m1 = mock.register_uri('POST', url, json=res)

        filepath = '/dummy/test.csv'
        self.fakefs_patcher.fs.create_file(filepath, contents='1\t2\t3')
        result_filepath = '/output/result.json'
        self.fakefs_patcher.fs.create_file(result_filepath, contents='')

        url = "{}/buckets/{}/files".format(ORGANIZATION_ENDPOINT, bucket_id)
        m2 = mock.register_uri(
            'POST', url, json={'file_id': 'test.csv'})

        cmd = [
            'create-and-upload', '--meta-data', 'label:neko',
            '--save-result', result_filepath,
            'dummy']
        r = self.runner.invoke(bucket, cmd)
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
                    'bucket_id': 12345,
                    'source': 'dummy/test.csv',
                    'file_id': 'test.csv'
                }
            ])
