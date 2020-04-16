#!/usr/bin/env python3
# -*- coding: utf-8 -*
import os
import time
import unittest
from datetime import datetime

from abejacli.bucket import (download_from_bucket,
                             generate_bucket_file_iter,
                             upload_to_bucket)
from abejacli.datalake import (download_from_datalake,
                               generate_channel_file_iter_by_period,
                               upload_to_datalake)
from abejacli.fs_utils import generate_upload_file_iter, generate_upload_bucket_iter
from abejacli.run import (_create_deployment, _create_endpoint,
                          _create_service, _create_trigger,
                          _delete_deployment, _delete_endpoint,
                          _delete_service, _delete_trigger,
                          _describe_deployments, _describe_endpoints,
                          _describe_services,
                          _describe_triggers,
                          _update_endpoint,
                          _create_deployment_version, _describe_deployment_versions,
                          _download_deployment_version, _delete_deployment_version,
                          _create_deployment_version_from_git)
from backports import tempfile
from tests import session_decorator


TRIGGER_INPUT_DATALAKE_ID = os.environ.get(
    'TRIGGER_INPUT_DATALAKE_ID', '1332934178129')
TRIGGER_OUTPUT_DATALAKE_ID = os.environ.get(
    'TRIGGER_OUTPUT_DATALAKE_ID', '1241204926735')
DATALAKE_CHANNEL_ID = os.environ.get('DATALAKE_CHANNEL_ID', '1282495226152')
DATALAKE_BUCKET_ID = os.environ.get('DATALAKE_BUCKET_ID', '1995386829827')


class AbejaCliTest(unittest.TestCase):

    @session_decorator
    def test_trigger(self):
        # create
        # create-deployment
        name = 'default'
        description = 'default_description'

        r = _create_deployment(name, description=description)

        self.assertEqual(name, r['name'])
        self.assertEqual(
            description, r['description'], "Response (r): {}".format(r))

        deployment_id = r['deployment_id']

        # create-version
        version = '1.0.0'
        image = 'abeja-inc/minimal:0.1.0'
        ctx = "none"

        r = _create_deployment_version(ctx, deployment_id, version, image)
        self.assertEqual(version, r['version'], "Response (r): {}".format(r))

        version_id = r['version_id']

        # create-trigger
        input_service_name = 'datalake'
        input_service_id = TRIGGER_INPUT_DATALAKE_ID
        output_service_name = 'datalake'
        output_service_id = TRIGGER_OUTPUT_DATALAKE_ID
        environment = {'DEBUG': 'x'}
        retry_count = 5

        r = _create_trigger(deployment_id, version_id, input_service_name,
                            input_service_id, output_service_name, output_service_id, retry_count, environment)
        self.assertEqual(input_service_name,
                         r['input_service_name'], "Response (r): {}".format(r))
        self.assertEqual(input_service_id,
                         r['input_service_id'], "Response (r): {}".format(r))
        self.assertEqual(output_service_name,
                         r['output_service_name'], "Response (r): {}".format(r))
        self.assertEqual(output_service_id,
                         r['output_service_id'], "Response (r): {}".format(r))
        self.assertEqual(
            environment, r['user_env_vars'], "Response (r): {}".format(r))
        trigger_id = r['trigger_id']

        # describe (single)
        # describe-triggers (single)
        r = _describe_triggers(deployment_id, trigger_id)
        self.assertEqual(trigger_id, r['trigger_id'],
                         "Response (r): {}".format(r))

        # delete
        # delete-trigger
        r = _delete_trigger(deployment_id, trigger_id)
        self.assertIn(trigger_id, r['message'], "Response (r): {}".format(r))

        # delete-version
        r = _delete_deployment_version(deployment_id, version_id)
        self.assertIn(version_id, r['message'], "Response (r): {}".format(r))

        # delete-deployment
        r = _delete_deployment(deployment_id)
        self.assertIn(deployment_id, r['message'])

    @session_decorator
    def test_datalake(self):

        with tempfile.TemporaryDirectory() as dir_name:
            sub_dir_name = os.path.join(dir_name, 'sub/')
            os.makedirs(sub_dir_name)
            paths = set([
                os.path.join(dir_name, 'file1.txt'),
                os.path.join(dir_name, 'file2.txt'),
                os.path.join(dir_name, 'file3.txt'),
                os.path.join(sub_dir_name, 'file4.txt'),
            ])
            for path in paths:
                with open(path, 'w') as f:
                    f.write('dummy')

            path_iter = generate_upload_file_iter(
                paths=[dir_name], recursive=True)
            upload_success, _ = upload_to_datalake(
                DATALAKE_CHANNEL_ID, path_iter, None)
            # list of uploaded file paths
            upload_sources = map(lambda x: x[0], upload_success)
            # list of uploaded file identifiers
            upload_destinations = map(lambda x: x[1], upload_success)
            self.assertSetEqual(set(upload_sources), paths)

            today = datetime.utcnow().date().strftime("%Y%m%d")
            file_iter = generate_channel_file_iter_by_period(
                DATALAKE_CHANNEL_ID, today, today)

        with tempfile.TemporaryDirectory() as dir_name:
            download_success, _ = download_from_datalake(
                DATALAKE_CHANNEL_ID, file_iter, dir_name, 'name', False)
            # list of downloaded file identifiers
            download_sources = list(map(lambda x: x[0], download_success))
            for upload_file_id in upload_destinations:
                # check if all uploaded files are downloaded
                self.assertTrue(upload_file_id in download_sources)

        with tempfile.TemporaryDirectory() as dir_name:
            download_success, _ = download_from_datalake(
                DATALAKE_CHANNEL_ID, file_iter, dir_name, 'id', False)
            # list of downloaded file identifiers
            download_sources = list(map(lambda x: x[0], download_success))
            for upload_file_id in upload_destinations:
                # check if all uploaded files are downloaded
                self.assertTrue(upload_file_id in download_sources)

    @session_decorator
    def test_bucket(self):

        with tempfile.TemporaryDirectory() as dir_name:
            sub_dir_name = os.path.join(dir_name, 'sub/')
            os.makedirs(sub_dir_name)
            paths = set([
                os.path.join(dir_name, 'file1.txt'),
                os.path.join(dir_name, 'file2.txt'),
                os.path.join(dir_name, 'file3.txt'),
                os.path.join(sub_dir_name, 'file4.txt'),
            ])
            for path in paths:
                with open(path, 'w') as f:
                    f.write('dummy')

            path_iter = generate_upload_bucket_iter(
                path=dir_name, recursive=True)
            upload_success, _ = upload_to_bucket(
                DATALAKE_BUCKET_ID, path_iter, None)
            # list of uploaded file paths
            upload_sources = map(lambda x: x[0], upload_success)
            # list of uploaded file identifiers
            upload_destinations = map(lambda x: x[1], upload_success)
            self.assertSetEqual(set(upload_sources), paths)

            file_iter = generate_bucket_file_iter(
                DATALAKE_BUCKET_ID)

        with tempfile.TemporaryDirectory() as dir_name:
            download_success, _ = download_from_bucket(
                DATALAKE_BUCKET_ID, file_iter, dir_name)
            # list of downloaded file identifiers
            download_sources = list(map(lambda x: x[0], download_success))
            for upload_file_id in upload_destinations:
                # check if all uploaded files are downloaded
                upload_file_id = "/{}".format(upload_file_id)
                self.assertTrue(upload_file_id in download_sources)

    @session_decorator
    def test_deployment_deploy(self):
        # create
        # create-deployment
        name = 'default'
        description = 'default_description'

        r = _create_deployment(name, description=description)

        self.assertEqual(name, r['name'])
        self.assertEqual(
            description, r['description'], "Response (r): {}".format(r))

        deployment_id = r['deployment_id']

        # create-version
        version = '1.0.0'
        image = 'abeja-inc/minimal:0.1.0'
        ctx = "none"

        r = _create_deployment_version(ctx, deployment_id, version, image)
        self.assertEqual(version, r['version'], "Response (r): {}".format(r))

        version_id = r['version_id']

        # download-version
        r = _download_deployment_version(deployment_id, version_id)
        self.assertIsNotNone(r)

        # create-service
        environment = (('BASE_URL', 'http://modelurl.com'),
                       ('MODEL_TOKEN', 'XXX'))
        r = _create_service(deployment_id, version_id, environment)
        self.assertEqual(
            version_id, r['model_version_id'], "Response (r): {}".format(r))
        self.assertEqual({'BASE_URL': 'http://modelurl.com', 'MODEL_TOKEN': 'XXX'}, r['user_env_vars'],
                         "Response (r): {}".format(r))

        service_id = r['service_id']

        # create-endpoint
        time.sleep(10.0)
        custom_alias = "default"

        r = _create_endpoint(deployment_id, service_id, custom_alias)
        self.assertEqual(
            custom_alias, r['custom_alias'], "Response (r): {}".format(r))

        endpoint_id = r['endpoint_id']

        # update-endpoint
        r = _update_endpoint(deployment_id, service_id, endpoint_id)
        self.assertIn(endpoint_id, r['message'], "Response (r): {}".format(r))

        # describe (single)
        # describe-deployments (single)
        r = _describe_deployments(deployment_id)
        self.assertEqual(deployment_id, r['deployment_id'], "Response (r): {}".format(r))

        # describe-versions (single)
        r = _describe_deployment_versions(deployment_id, version_id)
        self.assertEqual(version_id, r['version_id'],
                         "Response (r): {}".format(r))

        # describe-services (single)
        r = _describe_services(deployment_id, service_id)
        self.assertEqual(service_id, r['service_id'],
                         "Response (r): {}".format(r))

        # describe-endpoints (single)
        r = _describe_endpoints(deployment_id, endpoint_id)
        self.assertEqual(
            endpoint_id, r['endpoint_id'], "Response (r): {}".format(r))

        # delete
        # delete-endpoint
        r = _delete_endpoint(deployment_id, endpoint_id)
        self.assertIn(endpoint_id, r['message'], "Response (r): {}".format(r))

        # delete-service
        r = _delete_service(deployment_id, service_id)
        self.assertIn(service_id, r['message'], "Response (r): {}".format(r))

        # delete-version
        r = _delete_deployment_version(deployment_id, version_id)
        self.assertIn(version_id, r['message'], "Response (r): {}".format(r))

        # delete-deployment
        r = _delete_deployment(deployment_id)
        self.assertIn(deployment_id, r['message'])

    @session_decorator
    def test_deployment_deploy_from_git(self):
        # create
        # create-deployment
        name = 'default'
        description = 'default_description'

        r = _create_deployment(name, description=description)

        self.assertEqual(name, r['name'])
        self.assertEqual(
            description, r['description'], "Response (r): {}".format(r))

        deployment_id = r['deployment_id']

        # create-version-from-git
        version = '1.0.0'
        image = 'abeja-inc/minimal:0.1.0'
        ctx = "none"
        git_url = "https://github.com/abeja-inc/platform-template-image-classification.git"
        git_branch = "master"

        r = _create_deployment_version_from_git(ctx, deployment_id, git_url, git_branch, version, image)
        self.assertEqual(version, r['version'], "Response (r): {}".format(r))

        version_id = r['version_id']

        # download-version
        r = _download_deployment_version(deployment_id, version_id)
        self.assertIsNotNone(r)

        # create-service
        environment = (('BASE_URL', 'http://modelurl.com'),
                       ('MODEL_TOKEN', 'XXX'))
        r = _create_service(deployment_id, version_id, environment)
        self.assertEqual(
            version_id, r['model_version_id'], "Response (r): {}".format(r))
        self.assertEqual({'BASE_URL': 'http://modelurl.com', 'MODEL_TOKEN': 'XXX'}, r['user_env_vars'],
                         "Response (r): {}".format(r))

        service_id = r['service_id']

        # create-endpoint
        time.sleep(10.0)
        custom_alias = "default"

        r = _create_endpoint(deployment_id, service_id, custom_alias)
        self.assertEqual(
            custom_alias, r['custom_alias'], "Response (r): {}".format(r))

        endpoint_id = r['endpoint_id']

        # update-endpoint
        r = _update_endpoint(deployment_id, service_id, endpoint_id)
        self.assertIn(endpoint_id, r['message'], "Response (r): {}".format(r))

        # describe (single)
        # describe-deployments (single)
        r = _describe_deployments(deployment_id)
        self.assertEqual(deployment_id, r['deployment_id'], "Response (r): {}".format(r))

        # describe-versions (single)
        r = _describe_deployment_versions(deployment_id, version_id)
        self.assertEqual(version_id, r['version_id'],
                         "Response (r): {}".format(r))

        # describe-services (single)
        r = _describe_services(deployment_id, service_id)
        self.assertEqual(service_id, r['service_id'],
                         "Response (r): {}".format(r))

        # describe-endpoints (single)
        r = _describe_endpoints(deployment_id, endpoint_id)
        self.assertEqual(
            endpoint_id, r['endpoint_id'], "Response (r): {}".format(r))

        # delete
        # delete-endpoint
        r = _delete_endpoint(deployment_id, endpoint_id)
        self.assertIn(endpoint_id, r['message'], "Response (r): {}".format(r))

        # delete-service
        r = _delete_service(deployment_id, service_id)
        self.assertIn(service_id, r['message'], "Response (r): {}".format(r))

        # delete-version
        r = _delete_deployment_version(deployment_id, version_id)
        self.assertIn(version_id, r['message'], "Response (r): {}".format(r))

        # delete-deployment
        r = _delete_deployment(deployment_id)
        self.assertIn(deployment_id, r['message'])


if __name__ == '__main__':
    unittest.main()
