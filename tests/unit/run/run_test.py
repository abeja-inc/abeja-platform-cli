import json
import os
import tempfile
from unittest import TestCase

import pytest
import requests_mock
from click.testing import CliRunner
from mock import patch
from ruamel.yaml import YAML

import abejacli.training
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.configuration.config import Config
from abejacli.registry.commands import (
    create_repository,
    delete_repository,
    describe_repositories,
    describe_repository,
    describe_repository_tags
)
from abejacli.run import (
    delete_configuration,
    describe_datalake_buckets,
    describe_datalake_channels,
    initialize_configuragtion,
    list_configurations,
    deployment,
    show_configuration,
    switch_configuration
)
from abejacli.training import training_default_configuration
from abejacli.training.commands import (
    archive_job,
    archive_training_model,
    archive_version,
    create_job_definition,
    create_training_job,
    create_training_model,
    create_training_version,
    describe_jobs,
    describe_training_models,
    describe_training_versions,
    download_training_model,
    initialize_training,
    unarchive_job,
    unarchive_training_model,
    unarchive_version,
    update_training_model
)
from tests import get_tmp_training_file_name
from tests.unit import ConfigPatcher

TEST_CONFIG_FILE_ROOT = '/tmp/.abeja'
TEST_CONFIG_FILE_PATH = os.path.join(TEST_CONFIG_FILE_ROOT, 'config')

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_CONFIG_ORG_NAME = 'test-inc'
TEST_CONFIG = {
    'abeja-platform-user': Config.prefixed_user(TEST_CONFIG_USER_ID),
    'personal-access-token': TEST_CONFIG_TOKEN,
    'organization-name': TEST_CONFIG_ORG_NAME
}

TEST_CONFIG_USER_ID_2 = '2039587479106'
TEST_CONFIG_TOKEN_2 = '34676abf4875998fbe7fd4637'
TEST_CONFIG_ORG_NAME_2 = 'banana-fish'
TEST_CONFIG_2 = {
    'abeja-platform-user': Config.prefixed_user(TEST_CONFIG_USER_ID_2),
    'personal-access-token': TEST_CONFIG_TOKEN_2,
    'organization-name': TEST_CONFIG_ORG_NAME_2
}

TEST_ORGANIZATION_DOMAIN = 'http://apidomain/organizations/test'
yaml = YAML()

CHANNEL_ID = '1111111111111'

CHANNEL_RESPONSE = {
    "channels": [
        {
            "channel_id": "1335597259091",
            "created_at": "2018-01-15T07:39:29Z",
            "storage_type": "datalake",
            "updated_at": "2018-01-15T07:39:29Z",
            "description": "Movie Spliter Output"
        },
        {
            "channel_id": "1325662709070",
            "created_at": "2018-01-04T02:09:58Z",
            "description": "image-detection-result-channel",
            "updated_at": "2018-01-04T02:09:59Z",
            "storage_type": "rdb"
        },
        {
            "channel_id": "1325660026189",
            "created_at": "2018-01-04T02:05:36Z",
            "description": "test-image-in",
            "updated_at": "2018-01-04T02:05:36Z",
            "storage_type": "datalake"
        },
        {
            "created_at": "2017-12-21T16:00:24Z",
            "channel_id": "1313786614091",
            "description": "kawasaki-test",
            "storage_type": "file",
            "updated_at": "2017-12-21T16:00:24Z"
        },
        {
            "storage_type": "rdb",
            "updated_at": "2017-12-21T05:36:17Z",
            "description": "test",
            "created_at": "2017-12-21T05:36:17Z",
            "channel_id": "1313403161930"
        }
    ],
    "updated_at": "2017-05-10T02:36:00Z",
    "created_at": "2017-04-27T08:26:11Z",
    "offset": 0,
    "limit": 300,
    "organization_id": "1122334455667",
    "has_next": False,
    "organization_name": "abeja-inc"
}
CHANNEL_FILES_RESPONSE = {
    'files': [
        {
            "url_expires_on": "2017-11-21T02:18:16+00:00",
            "uploaded_at": "2017-11-16T07:10:56+00:00",
            "metadata": {
                "x-abeja-meta-filename": "file1.txt",
                "x-abeja-meta-label": "1"
            },
            "file_id": "20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e",
            "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071056-b2168632-7aae-47ad-8339-9e6463607e6e?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
            "content_type": "text/plain"
        },
        {
            "url_expires_on": "2017-11-21T02:18:16+00:00",
            "uploaded_at": "2017-11-16T07:11:00+00:00",
            "metadata": {
                "x-abeja-meta-filename": "file2.txt",
                "x-abeja-meta-label": "2"
            },
            "file_id": "20171116T071100-6e82c7ef-ad2a-40ab-888b-3c2c5567de0f",
            "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071100-6e82c7ef-ad2a-40ab-888b-3c2c5567de0f?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=T1%2BcHb3A0D892Dfw5HYmY%2BIhROA%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
            "content_type": "text/plain"
        },
        {
            "url_expires_on": "2017-11-21T02:18:16+00:00",
            "uploaded_at": "2017-11-16T07:11:01+00:00",
            "metadata": {
                "x-abeja-meta-filename": "file3.txt",
                "x-abeja-meta-label": "3"
            },
            "file_id": "20171116T071101-959db0d1-e853-4dd0-9aa0-d81692d2d88b",
            "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071101-959db0d1-e853-4dd0-9aa0-d81692d2d88b?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=dE07nbdjtR08B0CzVLiwgap%2BK1E%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
            "content_type": "text/plain"
        }
    ]
}
BUCKET_RESPONSE = {
    "buckets": [
        {
            "bucket_id": "1335597259091",
            "created_at": "2018-01-15T07:39:29Z",
            "updated_at": "2018-01-15T07:39:29Z",
            "description": "Movie Spliter Output"
        },
        {
            "bucket_id": "1325660026189",
            "created_at": "2018-01-04T02:05:36Z",
            "updated_at": "2018-01-04T02:05:36Z",
            "description": "test-image-in"
        },
    ],
    "updated_at": "2017-05-10T02:36:00Z",
    "created_at": "2017-04-27T08:26:11Z",
    "offset": 0,
    "limit": 300,
    "organization_id": "1122334455667",
    "has_next": False,
    "organization_name": "abeja-inc"
}
DATASET_ID = '9999999999999'
DATASET_ITEM_RESPONSE = {
    'dataset_id': DATASET_ID,
    'source_data': [
        {
            'data_type': 'image/jpeg',
            'data_uri': 'datalake://1234567890123/20170815T044617-f20dde80-1e3b-4496-bc06-1b63b026b872'
        }
    ],
    'attributes': {
        'classification': {
            'label': 'inu'
        }
    }
}

DEFAULT_TRAINING_JOB_DEFINITION_NAME = 'training-1'

DEFAULT_TRAINING_CONFIG = {
    'name': DEFAULT_TRAINING_JOB_DEFINITION_NAME,
    'handler': 'train:handler',
    'image': 'abeja-inc/minimal:0.1.0',
    'params': {
        'param1': 'value1',
        'parma2': 'value2',
    },
    'datasets': {
        'dataset_name1': 'value1',
        'dataset_name2': 'value2',
    }
}

TRAINING_MODEL_ID = '4444444444444'

BASE_ENVIRON = {'LC_ALL': 'C.UTF-8', 'LANG': 'C.UTF-8'}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_file_path():
    if not os.path.exists(TEST_CONFIG_FILE_ROOT):
        os.makedirs(TEST_CONFIG_FILE_ROOT, mode=0o711)
    elif os.path.exists(TEST_CONFIG_FILE_PATH):
        os.unlink(TEST_CONFIG_FILE_PATH)

    return TEST_CONFIG_FILE_PATH


@pytest.fixture
def config_file(config_file_path):
    with open(config_file_path, "w") as f:
        json.dump(TEST_CONFIG, f)
        f.close
    return TEST_CONFIG


class TestNoConfig(object):
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_init_configure(self, runner, config_file_path):
        input_config = '{}\n{}\n{}\n'.format(
            TEST_CONFIG_USER_ID, TEST_CONFIG_TOKEN, TEST_CONFIG_ORG_NAME)
        result = runner.invoke(
            initialize_configuragtion, input=input_config)
        assert not result.exception
        with open(config_file_path, 'r') as f:
            json_data = json.load(f)
        assert TEST_CONFIG == json_data

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_show_configure(self, runner, config_file):
        result = runner.invoke(show_configuration, ['--format=json'])
        assert not result.exception
        assert json.loads(result.output) == TEST_CONFIG
        result = runner.invoke(show_configuration, ['-u'])
        assert not result.exception
        assert result.output == 'abeja-platform-user:user-{}\n'.format(
            TEST_CONFIG_USER_ID)
        result = runner.invoke(show_configuration, ['-t'])
        assert not result.exception
        assert result.output == 'personal-access-token:{}\n'.format(
            TEST_CONFIG_TOKEN)
        result = runner.invoke(show_configuration, ['-o'])
        assert not result.exception
        assert result.output == 'organization-name:{}\n'.format(
            TEST_CONFIG_ORG_NAME)

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_show_named_configuration(self, runner, config_file):
        # Add another configuration
        input_config = '{}\n{}\n{}\n'.format(
            TEST_CONFIG_USER_ID_2, TEST_CONFIG_TOKEN_2, TEST_CONFIG_ORG_NAME_2)
        result = runner.invoke(
            initialize_configuragtion, ['test'], input=input_config)
        assert not result.exception

        result = runner.invoke(show_configuration, ['--format=json', 'test'])
        assert json.loads(result.output) == TEST_CONFIG_2

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_show_default_configuration(self, runner, config_file):
        # Add another configuration
        input_config = '{}\n{}\n{}\n'.format(
            TEST_CONFIG_USER_ID_2, TEST_CONFIG_TOKEN_2, TEST_CONFIG_ORG_NAME_2)
        result = runner.invoke(
            initialize_configuragtion, ['test'], input=input_config)
        assert not result.exception

        # Activate
        result = runner.invoke(switch_configuration, ['test'])
        assert not result.exception

        result = runner.invoke(show_configuration, ['--format=json'])
        assert json.loads(result.output) == TEST_CONFIG_2

        # Show default
        result = runner.invoke(show_configuration, [
                               '--format=json', '--default'])
        assert json.loads(result.output) == TEST_CONFIG

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_list_configurations(self, runner, config_file):
        result = runner.invoke(list_configurations)
        assert not result.exception
        assert result.output == "   NAME       ORGANIZATION  USER   TOKEN      \n" \
            "*  (default)  test-inc      12345  *******2345\n"

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_delete_default_configuration(self, runner, config_file_path, config_file):
        # Add another configuration
        input_config = '{}\n{}\n{}\n'.format(
            TEST_CONFIG_USER_ID_2, TEST_CONFIG_TOKEN_2, TEST_CONFIG_ORG_NAME_2)
        result = runner.invoke(
            initialize_configuragtion, ['test'], input=input_config)
        assert not result.exception

        # Delete default
        result = runner.invoke(delete_configuration, ['--assume-yes'])
        assert not result.exception

        # Active confiuration changed
        result = runner.invoke(show_configuration, ['--format=json'])
        assert json.loads(result.output) == TEST_CONFIG_2

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_delete_default_configuration_not_activated(self, runner, config_file_path, config_file):
        # Add another configuration
        input_config = '{}\n{}\n{}\n'.format(
            TEST_CONFIG_USER_ID_2, TEST_CONFIG_TOKEN_2, TEST_CONFIG_ORG_NAME_2)
        result = runner.invoke(
            initialize_configuragtion, ['test'], input=input_config)
        assert not result.exception

        # Switch
        result = runner.invoke(switch_configuration, ['test'])
        assert not result.exception

        # Delete default
        result = runner.invoke(delete_configuration, ['--assume-yes'])
        assert not result.exception

        # Active confiuration NOT changed
        result = runner.invoke(show_configuration, ['--format=json'])
        assert json.loads(result.output) == TEST_CONFIG_2

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_delete_default_configuration_then_empty(self, runner, config_file_path, config_file):
        result = runner.invoke(delete_configuration, ['--assume-yes'])
        assert not result.exception
        # Configuration file should be deleted
        assert not os.path.exists(config_file_path)

    @patch.dict(os.environ, BASE_ENVIRON, clear=True)
    @patch('abejacli.configuration.CONFIG_FILE_PATH', TEST_CONFIG_FILE_PATH)
    def test_delete_named_configuration(self, runner, config_file_path, config_file):
        # Add another configuration
        input_config = '{}\n{}\n{}\n'.format(
            TEST_CONFIG_USER_ID_2, TEST_CONFIG_TOKEN_2, TEST_CONFIG_ORG_NAME_2)
        result = runner.invoke(
            initialize_configuragtion, ['test'], input=input_config)
        assert not result.exception

        # Delete default
        result = runner.invoke(delete_configuration, ['--assume-yes'])
        assert not result.exception

        # Active confiuration changed
        result = runner.invoke(show_configuration, ['--format=json'])
        assert json.loads(result.output) == TEST_CONFIG_2


class RunTest(TestCase):

    def setUp(self):
        self.runner = CliRunner()
        self.config_patcher = ConfigPatcher() \
            .add(user=TEST_CONFIG_USER_ID, token=TEST_CONFIG_TOKEN, organization=TEST_CONFIG_ORG_NAME) \
            .start()

    def tearDown(self):
        self.config_patcher.stop()

    @patch('abejacli.run.ORGANIZATION_ENDPOINT', TEST_ORGANIZATION_DOMAIN)
    @patch('abejacli.run.api_post')
    def test_create_trigger(self, mock_api_post):
        deployment_id = '1111111111111'
        version_id = 'ver-1111111111111'
        model_id = '4444444444444'
        input_service_name = 'datalake'
        input_service_id = '2222222222222'
        output_service_name = 'datamart'
        output_service_id = '3333333333333'
        environment = 'DEBUG:x'

        url = "{}/deployments/{}/triggers".format(
            TEST_ORGANIZATION_DOMAIN, deployment_id)
        data = {
            'version_id': version_id,
            'input_service_name': input_service_name,
            'input_service_id': input_service_id,
            'retry_count': 5,
            'environment': {
                'DEBUG': 'x'
            },
            'models': {
                'alias': model_id
            },
            'output_service_name': output_service_name,
            'output_service_id': output_service_id,
        }
        mock_api_post.return_value = data

        options = [
            'create-trigger',
            '--deployment_id={}'.format(deployment_id),
            '--version_id={}'.format(version_id),
            '--model_id={}'.format(model_id),
            '--input_service_name={}'.format(input_service_name),
            '--input_service_id={}'.format(input_service_id),
            '--output_service_name={}'.format(output_service_name),
            '--output_service_id={}'.format(output_service_id),
            '--environment={}'.format(environment)
        ]

        result = self.runner.invoke(deployment, options)
        assert not result.exception
        call_args, call_kwargs = mock_api_post.call_args
        self.assertEqual(call_args[0], url)
        self.assertDictEqual(json.loads(call_args[1]), data)

    @patch('abejacli.run.ORGANIZATION_ENDPOINT', TEST_ORGANIZATION_DOMAIN)
    @patch('abejacli.run.api_post')
    def test_create_trigger_without_output(self, mock_api_post):
        deployment_id = '1111111111111'
        version_id = 'ver-1111111111111'
        input_service_name = 'datalake'
        input_service_id = '2222222222222'
        retry_count = 5
        environment = 'DEBUG:x'

        url = "{}/deployments/{}/triggers".format(
            TEST_ORGANIZATION_DOMAIN, deployment_id)
        data = {
            'version_id': version_id,
            'input_service_name': input_service_name,
            'input_service_id': input_service_id,
            'retry_count': retry_count,
            'environment': {
                'DEBUG': 'x'
            }
        }
        mock_api_post.return_value = data

        options = [
            'create-trigger',
            '--deployment_id={}'.format(deployment_id),
            '--version_id={}'.format(version_id),
            '--input_service_name={}'.format(input_service_name),
            '--input_service_id={}'.format(input_service_id),
            '--retry_count={}'.format(retry_count),
            '--environment={}'.format(environment)
        ]

        result = self.runner.invoke(deployment, options)
        assert not result.exception
        mock_api_post.assert_called_once_with(url, json.dumps(data))

    def test_create_trigger_with_invalid_output_option(self):
        deployment_id = '1111111111111'
        version_id = 'ver-1111111111111'
        input_service_name = 'datalake'
        input_service_id = '2222222222222'
        output_service_name = 'datalake'
        retry_count = 5
        environment = 'DEBUG:x'

        options = [
            'create-trigger',
            '--deployment_id={}'.format(deployment_id),
            '--version_id={}'.format(version_id),
            '--input_service_name={}'.format(input_service_name),
            '--input_service_id={}'.format(input_service_id),
            '--output_service_name'.format(output_service_name),
            '--retry_count={}'.format(retry_count),
            '--environment={}'.format(environment)
        ]

        result = self.runner.invoke(deployment, options)
        assert result.exception

    @patch('abejacli.run.ORGANIZATION_ENDPOINT', TEST_ORGANIZATION_DOMAIN)
    @patch('abejacli.run.api_post')
    def test_submit_run(self, mock_api_post):
        deployment_id = '1111111111111'
        version_id = 'ver-1111111111111'
        model_id = '3333333333333'
        input_operator = '$datalake:1'
        input_target = '2222222222222/20180101T112233-22222222-4444-6666-8888-000000000000'
        output_operator = '$datamart-rdb:1'
        output_target = '2222222222222'
        environment = 'DEBUG:x'

        url = "{}/deployments/{}/runs".format(
            TEST_ORGANIZATION_DOMAIN, deployment_id)
        data = {
            'version_id': version_id,
            'input_data': {input_operator: input_target},
            'retry_count': 5,
            'environment': {
                'DEBUG': 'x'
            },
            'models': {
                'alias': model_id
            },
            'output_template': {output_operator: output_target},
        }
        mock_api_post.return_value = data

        options = [
            'submit-run',
            '--deployment_id={}'.format(deployment_id),
            '--version_id={}'.format(version_id),
            '--model_id={}'.format(model_id),
            '--input_operator={}'.format(input_operator),
            '--input_target={}'.format(input_target),
            '--output_operator={}'.format(output_operator),
            '--output_target={}'.format(output_target),
            '--environment={}'.format(environment)
        ]

        result = self.runner.invoke(deployment, options)
        assert not result.exception
        call_args, call_kwargs = mock_api_post.call_args
        self.assertEqual(call_args[0], url)
        self.assertDictEqual(json.loads(call_args[1]), data)

    @patch('abejacli.run.ORGANIZATION_ENDPOINT', TEST_ORGANIZATION_DOMAIN)
    @patch('abejacli.run.api_post')
    def test_submit_run_without_output(self, mock_api_post):
        deployment_id = '1111111111111'
        version_id = 'ver-1111111111111'
        input_operator = '$datalake:1'
        input_target = '2222222222222/20180101T112233-22222222-4444-6666-8888-000000000000'
        environment = 'DEBUG:x'

        url = "{}/deployments/{}/runs".format(
            TEST_ORGANIZATION_DOMAIN, deployment_id)
        data = {
            'version_id': version_id,
            'input_data': {input_operator: input_target},
            'retry_count': 5,
            'environment': {
                'DEBUG': 'x'
            }
        }
        mock_api_post.return_value = data

        options = [
            'submit-run',
            '--deployment_id={}'.format(deployment_id),
            '--version_id={}'.format(version_id),
            '--input_operator={}'.format(input_operator),
            '--input_target={}'.format(input_target),
            '--environment={}'.format(environment)
        ]

        result = self.runner.invoke(deployment, options)
        assert not result.exception
        mock_api_post.assert_called_once_with(url, json.dumps(data))

    def test_submit_run_with_invalid_output_option(self):
        deployment_id = '1111111111111'
        version_id = 'ver-1111111111111'
        input_operator = '$datalake:1'
        input_target = '2222222222222/20180101T112233-22222222-4444-6666-8888-000000000000'
        output_target = '2222222222222'
        environment = 'DEBUG:x'

        options = [
            'submit-run',
            '--deployment_id={}'.format(deployment_id),
            '--version_id={}'.format(version_id),
            '--input_operator={}'.format(input_operator),
            '--input_target={}'.format(input_target),
            '--output_target={}'.format(output_target),
            '--environment={}'.format(environment)
        ]

        result = self.runner.invoke(deployment, options)
        assert result.exception

    @requests_mock.Mocker()
    def test_describe_datalake_channels_all(self, mock):
        cmd = [

        ]
        expected_response = {
            "channels": [
                {
                    "channel_id": "1335597259091",
                    "created_at": "2018-01-15T07:39:29Z",
                    "storage_type": "datalake",
                    "updated_at": "2018-01-15T07:39:29Z",
                    "description": "Movie Spliter Output"
                },
                {
                    "channel_id": "1325660026189",
                    "created_at": "2018-01-04T02:05:36Z",
                    "description": "test-image-in",
                    "updated_at": "2018-01-04T02:05:36Z",
                    "storage_type": "datalake"
                },
            ],
            "created_at": "2017-04-27T08:26:11Z",
            "organization_id": "1122334455667",
            "organization_name": "2017-04-27T08:26:11Z",
            "updated_at": "2017-05-10T02:36:00Z"
        }
        url = "{}/channels?limit={}".format(ORGANIZATION_ENDPOINT, 1000)
        mock.register_uri('GET', url, json=CHANNEL_RESPONSE)
        r = self.runner.invoke(describe_datalake_channels, cmd)
        self.assertDictEqual(json.loads(r.output), expected_response)

    @requests_mock.Mocker()
    def test_describe_datalake_buckets_all(self, mock):
        cmd = [

        ]
        expected_response = {
            "buckets": [
                {
                    "bucket_id": "1335597259091",
                    "created_at": "2018-01-15T07:39:29Z",
                    "updated_at": "2018-01-15T07:39:29Z",
                    "description": "Movie Spliter Output"
                },
                {
                    "bucket_id": "1325660026189",
                    "created_at": "2018-01-04T02:05:36Z",
                    "updated_at": "2018-01-04T02:05:36Z",
                    "description": "test-image-in"
                },
            ],
            "created_at": "2017-04-27T08:26:11Z",
            "organization_id": "1122334455667",
            "organization_name": "2017-04-27T08:26:11Z",
            "updated_at": "2017-05-10T02:36:00Z"
        }
        url = "{}/buckets".format(ORGANIZATION_ENDPOINT)
        mock.register_uri('GET', url, json=BUCKET_RESPONSE)
        r = self.runner.invoke(describe_datalake_buckets, cmd)
        actual_response = json.loads(r.output[r.output.index('{'):])  # FIXME: Use `r.output` after GA release.
        self.assertDictEqual(actual_response, expected_response)

    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_initialize_training(self):
        cmd = [
            'training-1'
        ]
        r = self.runner.invoke(initialize_training, cmd)
        actual_file = open(abejacli.training.CONFIGFILE_NAME, 'r').read()
        self.assertEqual(actual_file, training_default_configuration)
        self.assertEqual(r.output, 'training initialized\n')

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_job_definition(self, mock):
        cmd = []

        data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)
        url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
        mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(create_job_definition, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    def test_create_training_version_without_config_file(self, req_mock):
        with self.runner.isolated_filesystem():
            url = "{}/training/definitions/{}/versions".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            req_mock.register_uri('POST', url, json={"dummy": "dummy"})

            r = self.runner.invoke(create_training_version, [])
            self.assertEqual(
                r.output, 'training configuration file does not exists.\n')

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_training_version_with_invalid_configuration(self, req_mock):
        config = DEFAULT_TRAINING_CONFIG.copy()
        del config['handler']

        with self.runner.isolated_filesystem():
            with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
                yaml.dump(config, configfile)
            with open('train.py', 'w') as f:
                f.write('dummy')

            url = "{}/training/definitions/{}/versions".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            req_mock.register_uri('POST', url, json={"dummy": "dummy"})

            r = self.runner.invoke(create_training_version, [])
            self.assertEqual(
                r.output, 'invalid training configuration file.\n')

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_training_version(self, req_mock):
        with self.runner.isolated_filesystem():
            with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
                yaml.dump(DEFAULT_TRAINING_CONFIG, configfile)
            with open('train.py', 'w') as f:
                f.write('dummy')

            url = "{}/training/definitions/{}/versions".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            req_mock.register_uri('POST', url, json={"dummy": "dummy"})

            r = self.runner.invoke(create_training_version, [])
            self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})
            self.assertTrue(req_mock.called)
            req = req_mock.request_history[0]

            self.assertEqual(req.method, 'POST')
            self.assertRegex(
                req.headers['Content-Type'], r'^multipart/form-data; boundary=')
            self.assertRegex(req.body, b'Content-Disposition:')

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_describe_training_versions(self, req_mock):
        with self.runner.isolated_filesystem():
            with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
                yaml.dump(DEFAULT_TRAINING_CONFIG, configfile)
            with open('train.py', 'w') as f:
                f.write('dummy')

            url = "{}/training/definitions/{}/versions".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            req_mock.register_uri('GET', url, text=json.dumps({
                "entries": [
                    {
                        "created_at": "2019-04-03T05:23:04.844581Z",
                        "datasets": {},
                        "handler": "train:handler",
                        "image": "abeja-inc/all-gpu:18.10",
                        "job_definition_id": "1727436091178",
                        "job_definition_version": 3,
                        "modified_at": "2019-04-03T05:23:04.938196Z",
                        "user_parameters": {}
                    }
                ]
            }))

            self.runner.invoke(describe_training_versions)
            self.assertTrue(req_mock.called)

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_training_version_without_datasets(self, req_mock):
        config = DEFAULT_TRAINING_CONFIG.copy()
        del config['datasets']

        with self.runner.isolated_filesystem():
            with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
                yaml.dump(config, configfile)
            with open('train.py', 'w') as f:
                f.write('dummy')

            url = "{}/training/definitions/{}/versions".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            req_mock.register_uri('POST', url, json={"dummy": "dummy"})

            r = self.runner.invoke(create_training_version, [])
            self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_training_job(self, mock):
        cmd = [
            '--version', '1',
            '--params', 'USER_ID:1234567890123',
            '--params', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
            '--description', 'Initial job',
            '--instance-type', 'gpu:b-4'
        ]
        config_data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(config_data, configfile)
        url = "{}/training/definitions/{}/versions/{}/jobs".format(
            ORGANIZATION_ENDPOINT, config_data['name'], '1')
        matcher = mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(create_training_job, cmd)
        request_body = matcher.last_request.json()
        self.assertEqual(request_body['description'], 'Initial job')
        self.assertEqual(request_body['instance_type'], 'gpu:b-4')
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_training_job_without_version(self, mock):
        cmd = [
            '--params', 'USER_ID:1234567890123',
            '--params', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
        ]
        config_data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(config_data, configfile)
        list_versions_url = "{}/training/definitions/{}/versions".format(
            ORGANIZATION_ENDPOINT, config_data['name'])
        mock.register_uri('GET', list_versions_url, text=json.dumps({
            'entries': [
                {'job_definition_version': 1}
            ]
        }))
        create_job_url = "{}/training/definitions/{}/versions/{}/jobs".format(
            ORGANIZATION_ENDPOINT, config_data['name'], '1')
        mock.register_uri('POST', create_job_url, json={"dummy": "dummy"})
        r = self.runner.invoke(create_training_job, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_create_training_job_without_version_not_exist(self, mock):
        cmd = [
            '--params', 'USER_ID:1234567890123',
            '--params', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
        ]
        config_data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(config_data, configfile)
        list_versions_url = "{}/training/definitions/{}/versions".format(
            ORGANIZATION_ENDPOINT, config_data['name'])
        mock.register_uri('GET', list_versions_url,
                          text=json.dumps({'entries': []}))
        create_job_url = "{}/training/definitions/{}/versions/{}/jobs".format(
            ORGANIZATION_ENDPOINT, config_data['name'], '1')
        mock.register_uri('POST', create_job_url, json={"dummy": "dummy"})
        r = self.runner.invoke(create_training_job, cmd)
        self.assertEqual(r.output, 'there is no available training versions. '
                                   'please create training version first.\n')

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_archive_version(self, mock):
        cmd = [
            '--version-id', '1234567890123'
        ]

        data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)
        url = "{}/training/definitions/{}/versions/{}/archive".format(
            ORGANIZATION_ENDPOINT, data['name'], '1234567890123')
        mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(archive_version, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_unarchive_version(self, mock):
        cmd = [
            '--version-id', '1234567890123'
        ]

        data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)
        url = "{}/training/definitions/{}/versions/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, data['name'], '1234567890123')
        mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(unarchive_version, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_describe_job(self, mock):
        cmd = []

        data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)
        url = "{}/training/definitions/{}/jobs".format(
            ORGANIZATION_ENDPOINT, data['name'])
        mock.register_uri('GET', url, json={"dummy": "dummy"})
        r = self.runner.invoke(describe_jobs, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_archive_job(self, mock):
        cmd = [
            '--job-id', '1234567890123'
        ]

        data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)
        url = "{}/training/definitions/{}/jobs/{}/archive".format(
            ORGANIZATION_ENDPOINT, data['name'], '1234567890123')
        mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(archive_job, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    @patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
    def test_unarchive_job(self, mock):
        cmd = [
            '--job-id', '1234567890123'
        ]

        data = yaml.load(training_default_configuration)
        with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)
        url = "{}/training/definitions/{}/jobs/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, data['name'], '1234567890123')
        mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(unarchive_job, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    def test_create_repository(self, mock):
        cmd = [
            '--name', 'test_repository',
            '--description', 'test_description',
        ]
        url = "{}/registry/repositories".format(ORGANIZATION_ENDPOINT)
        mock.register_uri('POST', url, json={"dummy": "dummy"})
        r = self.runner.invoke(create_repository, cmd)
        self.assertEqual(r.exit_code, 0)

    @requests_mock.Mocker()
    def test_delete_repository(self, mock):
        repository_id = '1234567890123'
        cmd = [
            '--repository_id', repository_id
        ]
        url = "{}/registry/repositories/{}".format(
            ORGANIZATION_ENDPOINT, repository_id)
        mock.register_uri('DELETE', url, json={})
        r = self.runner.invoke(delete_repository, cmd)
        self.assertEqual(r.exit_code, 0)

    @requests_mock.Mocker()
    def test_describe_repository(self, mock):
        repository_id = '1234567890123'
        mock_res = {
            "id": "1234567890123",
            "organization_id": "1410000000000",
            "name": "registry-repository-3",
            "description": 'null',
            "creator": {
                "updated_at": "2018-01-04T03:02:12Z",
                "role": "admin",
                "is_registered": 'true',
                "id": "1122334455660",
                "email": "test@abeja.asia",
                "display_name": 'null',
                "created_at": "2017-05-26T01:38:46Z"
            },
            "created_at": "2018-06-07T04:42:34.913644Z",
            "updated_at": "2018-06-07T04:42:3pp4.913726Z"
        }
        cmd = [
            '--repository_id', repository_id
        ]
        url = "{}/registry/repositories/{}".format(
            ORGANIZATION_ENDPOINT, repository_id)
        mock.register_uri('GET', url, json=mock_res)
        r = self.runner.invoke(describe_repository, cmd)
        self.assertEqual(r.exit_code, 0)

    @requests_mock.Mocker()
    def test_describe_repositories(self, mock):
        cmd = [
            '--limit', 100,
            '--offset', 10
        ]
        mock_res = {
            "offset": 0,
            "limit": 10,
            "has_next": 'false',
            "organization_name": "test-org",
            "organization_id": "1122334455667",
            "created_at": "2019-05-23T05:13:13Z",
            "updated_at": "2019-05-23T05:13:15Z",
            "entries": [
                {
                    "id": "1234567890123",
                    "organization_id": "1410000000000",
                    "name": "registry-repository-3",
                    "description": 'null',
                    "creator": {
                        "updated_at": "2018-01-04T03:02:12Z",
                        "role": "admin",
                        "is_registered": 'true',
                        "id": "1122334455660",
                        "email": "test@abeja.asia",
                        "display_name": 'null',
                        "created_at": "2017-05-26T01:38:46Z"
                    },
                    "created_at": "2018-06-07T04:42:34.913644Z",
                    "updated_at": "2018-06-07T04:42:34.913726Z"
                }
            ]
        }
        url = "{}/registry/repositories".format(ORGANIZATION_ENDPOINT)
        mock.register_uri('GET', url, json=mock_res)
        r = self.runner.invoke(describe_repositories, cmd)
        self.assertEqual(r.exit_code, 0)

    @requests_mock.Mocker()
    def test_describe_repository_tags(self, mock):
        repository_id = '1234567890123'
        mock_res = {
            "id": "1234567890123",
            "organization_id": "1410000000000",
            "name": "registry-repository-3",
            "description": 'null',
            "creator": {
                "updated_at": "2018-01-04T03:02:12Z",
                "role": "admin",
                "is_registered": 'true',
                "id": "1122334455660",
                "email": "test@abeja.asia",
                "display_name": 'null',
                "created_at": "2017-05-26T01:38:46Z"
            },
            "created_at": "2018-06-07T04:42:34.913644Z",
            "updated_at": "2018-06-07T04:42:34.913726Z"
        }
        cmd = [
            '--repository_id', repository_id,
            '--limit', 100,
            '--offset', 10
        ]
        url = "{}/registry/repositories/{}/tags".format(
            ORGANIZATION_ENDPOINT, repository_id)
        mock.register_uri('GET', url, json=mock_res)
        r = self.runner.invoke(describe_repository_tags, cmd)
        self.assertEqual(r.exit_code, 0)

    @requests_mock.Mocker()
    def test_describe_training_models(self, mock):
        cmd = [
            '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME
        ]

        url = "{}/training/definitions/{}/models".format(
            ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
        mock.register_uri('GET', url, json={"dummy": "dummy"})
        r = self.runner.invoke(describe_training_models, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

        cmd = [
            '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
            '--model_id', TRAINING_MODEL_ID
        ]
        url = "{}/training/definitions/{}/models/{}".format(
            ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME, TRAINING_MODEL_ID)
        mock.register_uri('GET', url, json={"dummy": "dummy"})
        r = self.runner.invoke(describe_training_models, cmd)
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    def test_create_training_model(self, mock):
        with tempfile.NamedTemporaryFile(suffix='.txt') as f:
            cmd = [
                '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
                '--filepath', f.name
            ]

            url = "{}/training/definitions/{}/models".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            mock.register_uri('POST', url, json={"dummy": "dummy"})
            r = self.runner.invoke(create_training_model, cmd)
            self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

        with tempfile.NamedTemporaryFile(suffix='.zip') as f:
            cmd = [
                '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
                '--filepath', f.name,
                '--description', 'dummy',
                '--user_parameters', 'DEBUG:x'
            ]

            url = "{}/training/definitions/{}/models".format(
                ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME)
            mock.register_uri('POST', url, json={"dummy": "dummy"})
            r = self.runner.invoke(create_training_model, cmd)
            self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @patch('abejacli.training.commands.api_patch')
    def test_update_training_model(self, mock_api_patch):
        cmd = [
            '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
            '--model_id', TRAINING_MODEL_ID,
            '--description', 'dummy'
        ]
        data = {"dummy": "dummy"}
        mock_api_patch.return_value = data
        r = self.runner.invoke(update_training_model, cmd)
        assert not r.exception
        self.assertDictEqual(json.loads(r.output), {"dummy": "dummy"})

    @requests_mock.Mocker()
    def test_download_training_model(self, mock):
        cmd = [
            '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
            '--model_id', TRAINING_MODEL_ID
        ]

        url = "{}/training/definitions/{}/models/{}/download".format(
            ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME, TRAINING_MODEL_ID)
        mock.register_uri('GET', url, json={"download_uri": "dummy"})
        r = self.runner.invoke(download_training_model, cmd)
        self.assertDictEqual(json.loads(r.output), {"download_uri": "dummy"})

    @requests_mock.Mocker()
    def test_archive_training_model(self, mock):
        cmd = [
            '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
            '--model_id', TRAINING_MODEL_ID
        ]

        url = "{}/training/definitions/{}/models/{}/archive".format(
            ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME, TRAINING_MODEL_ID)
        mock.register_uri('POST', url, json={"message": "dummy"})
        r = self.runner.invoke(archive_training_model, cmd)
        self.assertDictEqual(json.loads(r.output), {"message": "dummy"})

    @requests_mock.Mocker()
    def test_unarchive_training_model(self, mock):
        cmd = [
            '--job_definition_name', DEFAULT_TRAINING_JOB_DEFINITION_NAME,
            '--model_id', TRAINING_MODEL_ID
        ]

        url = "{}/training/definitions/{}/models/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, DEFAULT_TRAINING_JOB_DEFINITION_NAME, TRAINING_MODEL_ID)
        mock.register_uri('POST', url, json={"message": "dummy"})
        r = self.runner.invoke(unarchive_training_model, cmd)
        self.assertDictEqual(json.loads(r.output), {"message": "dummy"})
