import json
from unittest import TestCase

import requests_mock
from click.testing import CliRunner

from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.run import create_service, start_service, stop_service


class ModelServiceTest(TestCase):

    def setUp(self):
        self.runner = CliRunner()

    @requests_mock.Mocker()
    def test_create_service(self, mock):
        deployment_id = '1111111111111'
        version_id = '2222222222222'
        model_id = '4444444444444'
        instance_type = 'cpu-1'
        instance_number = 5
        min_instance_number = 5
        max_instance_number = 8
        record_channel_id = '3333333333333'

        url = '{}/deployments/{}/services'.format(
            ORGANIZATION_ENDPOINT, deployment_id)
        mock.register_uri('POST', url, json={'dummy': 'dummy'})

        cmd = [
            '--deployment_id', deployment_id,
            '--version_id', version_id,
            '--model_id', model_id,
            '--instance-type', instance_type,
            '--disable-autoscale',
            '--instance-number', instance_number,
            '--min-instance-number', min_instance_number,
            '--max-instance-number', max_instance_number,
            '--record-channel-id', record_channel_id,
        ]

        ret = self.runner.invoke(create_service, cmd)
        self.assertTrue(mock.called)
        self.assertEqual(ret.exit_code, 0)

        req = mock.request_history[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.url, url)
        body = json.loads(req.text)
        self.assertEqual(False,
                         body.get('enable_autoscale'))
        self.assertEqual(instance_number,
                         body.get('instance_number'))
        self.assertEqual(min_instance_number,
                         body.get('min_instance_number'))
        self.assertEqual(max_instance_number,
                         body.get('max_instance_number'))

    @requests_mock.Mocker()
    def test_stop_service(self, mock):
        deployment_id = '1111111111111'
        service_id = 'ser-2222222222222'

        url = '{}/deployments/{}/services/{}/stop'.format(
            ORGANIZATION_ENDPOINT, deployment_id, service_id)
        mock.register_uri('POST', url, json={'message': 'OK'})

        cmd = [
            '--deployment_id', deployment_id,
            '--service_id', service_id,
        ]

        ret = self.runner.invoke(stop_service, cmd)
        self.assertTrue(mock.called)
        self.assertEqual(ret.exit_code, 0)

        req = mock.request_history[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.url, url)
        body = json.loads(ret.output)
        self.assertEqual(body.get('message'), 'OK')

    @requests_mock.Mocker()
    def test_start_service(self, mock):
        deployment_id = '1111111111111'
        service_id = 'ser-2222222222222'

        url = '{}/deployments/{}/services/{}/start'.format(
            ORGANIZATION_ENDPOINT, deployment_id, service_id)
        mock.register_uri('POST', url, json={'message': 'OK'})

        cmd = [
            '--deployment_id', deployment_id,
            '--service_id', service_id,
        ]

        ret = self.runner.invoke(start_service, cmd)
        self.assertTrue(mock.called)
        self.assertEqual(ret.exit_code, 0)

        req = mock.request_history[0]
        self.assertEqual(req.method, 'POST')
        self.assertEqual(req.url, url)
        body = json.loads(ret.output)
        self.assertEqual(body.get('message'), 'OK')
