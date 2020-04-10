"""Tests related to ``model`` and ``deployment``"""
from unittest import TestCase

import requests_mock
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.run import create_deployment
from click.testing import CliRunner


class ModelDeploymentTest(TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def _create_deployment(self, mock, extra_cmd):
        cmd = extra_cmd

        url = '{}/deployments'.format(ORGANIZATION_ENDPOINT)
        mock.register_uri('POST', url, json={'dummy': 'dummy'})

        ret = self.runner.invoke(create_deployment, cmd)
        self.assertTrue(mock.called)
        self.assertEqual(ret.exit_code, 0)

        req = mock.request_history[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.url, url)

        return req

    @requests_mock.Mocker()
    def test_create_deployment(self, mock):
        deployment_name = 'Test deployment'

        req = self._create_deployment(mock, [
            '--name', deployment_name,
        ])

        self.assertEqual(req.json(), {
            'name': deployment_name,
        })

    @requests_mock.Mocker()
    def test_create_deployment_with_env_and_description(self, mock):
        req = self._create_deployment(mock, [
            '--name', 'Test deployment',
            '--environment', 'USER_ID:1234567890123',
            '--environment', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
            '--description', 'description'
        ])

        req_json = req.json()
        self.assertEqual(req_json['default_environment'], {
            'USER_ID': '1234567890123',
            'ACCESS_KEY': '373be7309f0146c0d283440e500843d8',
        })
        self.assertEqual(req_json['description'], 'description')
