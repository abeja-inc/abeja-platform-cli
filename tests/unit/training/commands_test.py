import json
import re
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

import pytest
import requests_mock
from click.testing import CliRunner
from ruamel.yaml import YAML

import abejacli.training
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.exceptions import ResourceNotFound
from abejacli.training.commands import (
    _get_latest_training_version,
    create_notebook,
    create_training_job,
    create_training_version,
    create_training_version_from_git,
    debug_local,
    describe_job_definitions,
    describe_jobs,
    describe_training_models,
    describe_training_versions,
    start_notebook,
    stop_training_job,
    train_local,
    update_training_version
)
from tests import get_tmp_training_file_name

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_CONFIG_ORG_NAME = 'test-inc'
TEST_CONFIG = {
    'abeja-platform-user': 'user-{}'.format(TEST_CONFIG_USER_ID),
    'personal-access-token': TEST_CONFIG_TOKEN,
    'organization-name': TEST_CONFIG_ORG_NAME
}

yaml = YAML()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def req_mock(request):
    m = requests_mock.Mocker()
    m.start()
    request.addfinalizer(m.stop)
    return m


@patch('abejacli.training.commands._describe_training_versions')
def test_get_latest_training_version(m):
    m.return_value = {'entries': []}
    name = 'dummy'
    with pytest.raises(ResourceNotFound):
        _get_latest_training_version(name)


@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_update_training_version(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, config_data['name'], 1)

    def match_request_text(request):
        return json.loads(request.text) == {
            'description': 'dummy description'
        }

    req_mock.register_uri(
        'PATCH', url,
        json={"description": "dummy description"},
        additional_matcher=match_request_text)

    cmd = [
        '--version', '1',
        '--description', 'dummy description',
    ]
    r = runner.invoke(update_training_version, cmd)
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        ([],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10'
        }),
        (['-t', 'lab'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'lab',
             'image': 'abeja-inc/all-gpu:19.10'
        }),
        (['--instance-type', 'gpu-1'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10',
             'instance_type': 'gpu-1'
        }),
        (['--image', 'abeja-inc/all-gpu:19.10'],
         {},
         {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10'
        }),
        (['--datalake', '1234567890123'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10',
             'datalakes': ['1234567890123']
        }),
        (['--bucket', '1234567890123'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10',
             'buckets': ['1234567890123']
        }),
        (['--datalake', '1234567890123', '--bucket', '1234567890123'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10',
             'datalakes': ['1234567890123'],
             'buckets': ['1234567890123']
        }),
        (['--dataset', 'train:1600000000000'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10',
             'datasets': {'train': '1600000000000'}
        }),
        (['--image', 'abeja-inc/all-gpu:18.10'],
         {
             'image': 'abeja-inc/all-gpu:19.10'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:18.10'
        }),
        ([],
         {
             'image': 'abeja-inc/all-gpu:19.10',
             'instance_type': 'gpu-1'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10',
             'instance_type': 'gpu-1'
        }),
        ([],
         {
             'image': 'abeja-inc/all-gpu:19.10',
             'dummy': 'dummy'
        },
            {
             'notebook_type': 'notebook',
             'image': 'abeja-inc/all-gpu:19.10'
        }),
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_create_notebook(
        req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/notebooks".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    req_mock.register_uri(
        'POST', url,
        json=expected_payload)

    r = runner.invoke(create_notebook, cmd)
    assert req_mock.called
    assert r.exit_code == 0


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['-n', '9876543210987'],
         {},
         {}),
        (['-n', '9876543210987', '-t', 'lab'],
         {},
         {
            'notebook_type': 'lab'
        }),
        (['-n', '9876543210987', '--datalake', '1234567890123'],
         {},
         {
            'datalakes': ['1234567890123']
        }),
        (['-n', '9876543210987', '--bucket', '1234567890123'],
         {},
         {
            'buckets': ['1234567890123']
        }),
        (['-n', '9876543210987', '--datalake', '1234567890123', '--bucket', '1234567890123'],
         {},
         {
            'datalakes': ['1234567890123'],
            'buckets': ['1234567890123']
        }),
        (['-n', '9876543210987', '--dataset', 'train:1600000000000'],
         {},
         {
            'datasets': {'train': '1600000000000'}
        }),
        (['-n', '9876543210987'],
         {
             'dummy': 'dummy'
        },
            {}),
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_start_notebook(
        req_mock, runner, cmd, additional_config, expected_payload):
    notebook_id = '9876543210987'
    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/notebooks/{}/start".format(
        ORGANIZATION_ENDPOINT, config_data['name'], notebook_id)

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    r = runner.invoke(start_notebook, cmd)
    assert req_mock.called
    assert r.exit_code == 0


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--description', 'dummy description'],
         {
            'handler': 'train:handler',
            'image': 'abeja-inc/all-cpu:18.10'
        },
            {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'description': 'dummy description'
        }),
        ([
            '--handler', 'train:handler', '--image', 'abeja-inc/all-cpu:18.10',
            '--description', 'dummy description', '--environment', 'BATCH_SIZE:32'
        ],
            {},
            {
                'handler': 'train:handler',
                'image': 'abeja-inc/all-cpu:18.10',
                'description': 'dummy description',
                'environment': {'BATCH_SIZE': '32'}
        }),
        (['--description', 'dummy description'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'params': {'key9': 'value9'}
        },
            {
                'handler': 'train:handler',
                'image': 'abeja-inc/all-cpu:18.10',
                'description': 'dummy description',
                'environment': {'key9': 'value9'}
        }),
        (['--description', 'dummy description'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'environment': {'key1': 'value1', 'key2': 'value2'}
        },
            {
                'handler': 'train:handler',
                'image': 'abeja-inc/all-cpu:18.10',
                'description': 'dummy description',
                'environment': {'key1': 'value1', 'key2': 'value2'}
        }),
        (['--description', 'dummy description'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
                'handler': 'train:handler',
                'image': 'abeja-inc/all-cpu:18.10',
                'description': 'dummy description',
                'environment': {'key1': 'value1', 'key2': 'value2'}
        }),
        ([
            '--datasets', 'train:1600000000000',
            '--datalake', '1234567890123',
            '--bucket', '2345678901234'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
        },
            {
                'handler': 'train:handler',
                'image': 'abeja-inc/all-cpu:18.10',
                'datasets': {'train': '1600000000000'},
                'dataset_premounted': False,
                'datalakes': ['1234567890123'],
                'buckets': ['2345678901234']
        }),
        (['--datalake', '1234567890123', '--bucket', '2345678901234', '--dataset-premounted'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'datasets': {'train': '1600000000000'},
        },
            {
                'handler': 'train:handler',
                'image': 'abeja-inc/all-cpu:18.10',
                'datasets': {'train': '1600000000000'},
                'dataset_premounted': True,
                'datalakes': ['1234567890123'],
                'buckets': ['2345678901234']
        })
    ]
)
@patch('abejacli.training.commands.version_archive', MagicMock(return_value=None))
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_create_training_version(
        req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    with patch('abejacli.training.commands._create_training_version') as mock:
        mock.return_value = {}  # dummy response
        r = runner.invoke(create_training_version, cmd)
        args = mock.call_args[0]
        assert args[0] == url
        assert args[1] == expected_payload
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        ([],
         {
            'handler': 'train',
            'image': 'abeja-inc/all-cpu:20.02a'
        },
            {
                'handler': 'train',
                'image': 'abeja-inc/all-cpu:20.02a'
        }),
        ([
            '--handler', 'train', '--image', 'abeja-inc/all-cpu:20.02a'
        ],
            {},
            {
                'handler': 'train',
                'image': 'abeja-inc/all-cpu:20.02a'
        })
    ]
)
@patch('abejacli.training.commands.version_archive', MagicMock(return_value=None))
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_create_training_version_for_2002_image(
        req_mock, runner, cmd, additional_config, expected_payload):

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    with patch('abejacli.training.commands._create_training_version') as mock:
        mock.return_value = {}  # dummy response
        r = runner.invoke(create_training_version, cmd)
        args = mock.call_args[0]
        assert args[0] == url
        assert args[1] == expected_payload
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config',
    [
        ([],
         {
            'handler': 'train',
            'image': 'abeja-inc/all-cpu:18.10'
        }),
        ([
            '--handler', 'train', '--image', 'abeja-inc/all-cpu:18.10'
        ],
            {})
    ]
)
@patch('abejacli.training.commands.version_archive', MagicMock(return_value=None))
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_create_training_version_for_2002_image_invalid(
        req_mock, runner, cmd, additional_config):

    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    req_mock.register_uri(
        'POST', url,
        json={})
    r = runner.invoke(create_training_version, cmd)
    assert r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
          '--description', 'dummy description'],
         {
            'handler': 'train:handler',
            'image': 'abeja-inc/all-cpu:18.10'
        },
            {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'description': 'dummy description'
        }),
        (['--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
          '--git-branch', 'develop',
          '--handler', 'train:handler', '--image', 'abeja-inc/all-cpu:18.10',
          '--description', 'dummy description'],
         {},
         {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'git_branch': 'develop',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'description': 'dummy description'
        }),
        (['--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
          '--description', 'dummy description', '--environment', 'BATCH_SIZE:32'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10'
        },
            {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'description': 'dummy description',
             'environment': {'BATCH_SIZE': '32'}
        }),
        (['--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
          '--description', 'dummy description'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'params': {'key9': 'value9'}
        },
            {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'description': 'dummy description',
             'environment': {'key9': 'value9'}
        }),
        (['--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
          '--description', 'dummy description'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'environment': {'key1': 'value1', 'key2': 'value2'}
        },
            {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'description': 'dummy description',
             'environment': {'key1': 'value1', 'key2': 'value2'}
        }),
        (['--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
          '--description', 'dummy description'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'description': 'dummy description', 'environment': {'key1': 'value1', 'key2': 'value2'}
        }),
        ([
            '--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
            '--datasets', 'train:1600000000000',
            '--datalake', '1234567890123',
            '--bucket', '2345678901234'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
        },
            {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'datasets': {'train': '1600000000000'},
             'dataset_premounted': False,
             'datalakes': ['1234567890123'],
             'buckets': ['2345678901234']
        }),
        ([
            '--git-url', 'https://github.com/abeja-inc/platform-template-image-classification.git',
            '--datalake', '1234567890123', '--bucket', '2345678901234', '--dataset-premounted'],
         {
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'datasets': {'train': '1600000000000'},
        },
            {
             'git_url': 'https://github.com/abeja-inc/platform-template-image-classification.git',
             'handler': 'train:handler',
             'image': 'abeja-inc/all-cpu:18.10',
             'datasets': {'train': '1600000000000'},
             'dataset_premounted': True,
             'datalakes': ['1234567890123'],
             'buckets': ['2345678901234']
        })
    ]
)
@patch('abejacli.training.commands.version_archive', MagicMock(return_value=None))
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_create_training_version_from_git(
        req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/git/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    r = runner.invoke(create_training_version_from_git, cmd)
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--version', '1', '--description', 'dummy description'],
         {},
         {
             'description': 'dummy description'
        }),
        (['--version', '1', '--description', 'dummy description',
          '--environment', 'BATCH_SIZE:32', '--datasets', 'train:1600000000000'],
         {},
         {
             'description': 'dummy description',
             'datasets': {'train': '1600000000000'},
             'dataset_premounted': False,
             'environment': {'BATCH_SIZE': '32'}
        }),
        (['--version', '1', '--description', 'dummy description'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'datasets': {'train': '1600000000000'},
             'dataset_premounted': False,
             'environment': {'key1': 'value1', 'key2': 'value2'}
        }),
        (['--version', '1', '--description', 'dummy description',
          '--environment', 'BATCH_SIZE:32'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'datasets': {'train': '1600000000000'},
             'dataset_premounted': False,
             'environment': {'key1': 'value1', 'key2': 'value2', 'BATCH_SIZE': '32'}
        }),
        (['--version', '1', '--description', 'dummy description',
          '--environment', 'BATCH_SIZE:32', '--datasets', 'train:1600000000001'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'datasets': {'train': '1600000000001'},
             'dataset_premounted': False,
             'environment': {'key1': 'value1', 'key2': 'value2', 'BATCH_SIZE': '32'}
        }),
        (['--version', '1', '--description', 'dummy description',
          '--environment', 'BATCH_SIZE:32', '--datasets', 'val:1600000000001',
          '--datasets', 'test:1600000000002'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'datasets': {'train': '1600000000000', 'val': '1600000000001', 'test': '1600000000002'},
             'dataset_premounted': False,
             'environment': {'key1': 'value1', 'key2': 'value2', 'BATCH_SIZE': '32'}
        }),
        (['--version', '1', '--description', 'dummy description',
          '--environment', 'BATCH_SIZE:32', '--datasets', 'val:1600000000001',
          '--datasets', 'test:1600000000002', '--instance-type', 'cpu-4'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'datasets': {'train': '1600000000000', 'val': '1600000000001', 'test': '1600000000002'},
             'dataset_premounted': False,
             'environment': {'key1': 'value1', 'key2': 'value2', 'BATCH_SIZE': '32'},
             'instance_type': 'cpu-4'
        }),
        (['--version', '1', '--description', 'dummy description',
          '--environment', 'BATCH_SIZE:32', '--datasets', 'val:1600000000001',
          '--datasets', 'test:1600000000002', '--instance-type', 'cpu-4',
          '--dataset-premounted'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'datasets': {'train': '1600000000000', 'val': '1600000000001', 'test': '1600000000002'},
             'dataset_premounted': True,
             'environment': {'key1': 'value1', 'key2': 'value2', 'BATCH_SIZE': '32'},
             'instance_type': 'cpu-4'
        }),
        (['--version', '1', '--description', 'dummy description', '--datalake', '1234567890123'],
         {},
         {
             'description': 'dummy description',
             'datalakes': ['1234567890123']
        }),
        (['--version', '1', '--description', 'dummy description', '--bucket', '2345678901234'],
         {},
         {
             'description': 'dummy description',
             'buckets': ['2345678901234']
        }),
        (['--version', '1', '--description', 'dummy description',
          '--datalake', '1234567890123', '--bucket', '2345678901234'],
         {},
         {
             'description': 'dummy description',
             'datalakes': ['1234567890123'],
             'buckets': ['2345678901234']
        }),
        (['--version', '1'],
         {
             'instance_type': 'gpu-1'
        },
            {
             'instance_type': 'gpu-1'
        }),
        (['--version', '1', '--instance-type', 'cpu-4'],
         {
             'instance_type': 'gpu-1'
        },
            {
             'instance_type': 'cpu-4'
        }),
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_create_training_job(req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1'
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, config_data['name'], 1)

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    r = runner.invoke(create_training_job, cmd)
    assert not r.exception


def test_stop_training_job(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    training_job_id = '1500000000000'

    url = "{}/training/definitions/{}/jobs/{}/stop".format(
        ORGANIZATION_ENDPOINT, config_data['name'], training_job_id)

    def match_request_text(request):
        return json.loads(request.text) == {}

    req_mock.register_uri(
        'POST', url,
        json={},
        additional_matcher=match_request_text)

    r = runner.invoke(stop_training_job, ['--job-id', training_job_id])
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_environment,expected_datasets',
    [
        ([], {}, {}, {}),
        ([], {'environment': {'key1': 'value1'}}, {'key1': 'value1'}, {}),
        (['--environment', 'key1:updated'],
         {'environment': {'key1': 'value1', 'key2': 'value2'}},
         {'key1': 'updated', 'key2': 'value2'},
         {}),
        ([],
         {'environment': {'key1': 'value1'}, 'datasets': {'train': '1600000000000'}},
         {'key1': 'value1'}, {'train': '1600000000000'}),
        (['--datasets', 'val:1600000000001'],
         {'environment': {'key1': 'value1'}, 'datasets': {'train': '1600000000000'}},
         {'key1': 'value1'}, {'train': '1600000000000', 'val': '1600000000001'}),
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
@patch('abejacli.training.commands.TrainingJobDebugRun')
def test_debug_local_params(
        mock_debug_job, runner, cmd, additional_config,
        expected_environment, expected_datasets):
    mock_job = MagicMock()
    mock_debug_job.return_value = mock_job

    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10',
        'ignores': ['.gitignore']
    }
    config_data = {**config_data, **additional_config}
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    default_cmd = [
        '--image', 'abeja/all-gpu:18.10',  # not `abeja-inc/all-cpu:18.10`
        '--organization_id', '1122334455667',
        '--volume', '/tmp:/data',
        '--volume', '/usr/bin/hoge:/hoge',
        '--config', abejacli.training.CONFIGFILE_NAME,
    ]
    r = runner.invoke(debug_local, default_cmd + cmd)

    assert r.exit_code == 0, r.output

    # command line argument is prioritized
    args = mock_debug_job.call_args[1]

    # command line argument is prioritized for environment
    # and env vars specified in training.yaml are not included.
    assert dict(args['environment']) == expected_environment
    assert dict(args['datasets']) == expected_datasets


@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
@patch('abejacli.training.commands.TrainingJobDebugRun')
def test_debug_local(mock_debug_job, runner):
    mock_job = MagicMock()
    mock_debug_job.return_value = mock_job

    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10',
        'params': {
            'param1': 'value1',
            'param2': 'value2',
        },
        'datasets': {'dataset_name1': 'value1'},
        'ignores': ['.gitignore']
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    cmd = [
        '--image', 'abeja/all-gpu:18.10',   # not `abeja-inc/all-cpu:18.10`
        '--organization_id', '1122334455667',
        '--environment', 'USER_ID:1234567890123',
        '--environment', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
        '--environment', 'MAX_ITEMS:',
        '--volume', '/tmp:/data',
        '--volume', '/usr/bin/hoge:/hoge',
        '--config', abejacli.training.CONFIGFILE_NAME,
    ]
    r = runner.invoke(debug_local, cmd)

    assert r.exit_code == 0

    # command line argument is prioritized
    args = mock_debug_job.call_args[1]
    assert args['image'] == 'abeja/all-gpu:18.10'

    # value of training.yaml is used when not specified in command line argument
    assert args['handler'] == 'train:handler'

    # command line argument is prioritized for environment
    # and env vars specified in training.yaml are not included.
    environment = dict(args['environment'])
    assert environment == {
        'USER_ID': '1234567890123',
        'ACCESS_KEY': '373be7309f0146c0d283440e500843d8',
        'MAX_ITEMS': '',
        'param1': 'value1',
        'param2': 'value2',
    }
    volume = dict(args['volume'])
    assert volume == {
        '/tmp': {
            'bind': '/data',
            'mode': 'rw'
        },
        '/usr/bin/hoge': {
            'bind': '/hoge',
            'mode': 'rw'
        }
    }
    assert args['datasets'] == {
        'dataset_name1': 'value1'
    }


@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
@patch('abejacli.training.commands.TrainingJobDebugRun')
def test_debug_local_with_default_params(mock_debug_job, runner):
    mock_job = MagicMock()
    mock_debug_job.return_value = mock_job

    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10',
        'params': {
            'param1': 'value1',
            'param2': '',
            'param3': None
        },
        'datasets': {'dataset_name1': 'value1'},
        'ignores': ['.gitignore']
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    r = runner.invoke(debug_local, [
        '--organization_id', '1122334455667',
        '--config', abejacli.training.CONFIGFILE_NAME
    ])

    assert r.exit_code == 0

    args = mock_debug_job.call_args[1]
    environment = dict(args['environment'])
    assert environment == {
        'param1': 'value1',
        'param2': '',
        'param3': ''
    }


@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
@patch('abejacli.common.get_organization_id')
@patch('abejacli.training.commands.TrainingJobDebugRun')
def test_debug_local_debug_without_organization_id(
        mock_debug_job, mock_get_organization_id, runner):
    mock_job = MagicMock()
    mock_debug_job.return_value = mock_job
    mock_get_organization_id.return_value = '1122334455667'

    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10',
        'environment': {
            'param1': 'value1', 'param2': 'value2'
        },
        'datasets': {'dataset_name1': 'value1'},
        'ignores': ['.gitignore']
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    cmd = [
        '--image', 'abeja/all-gpu:18.10',  # not `abeja-inc/all-cpu:18.10`
        # '--organization_id', '1122334455667',
        '--environment', 'USER_ID:1234567890123',
        '--environment', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
        '--config', abejacli.training.CONFIGFILE_NAME,
    ]
    r = runner.invoke(debug_local, cmd)

    assert r.exit_code == 0, r.output

    mock_get_organization_id.assert_called_once_with()

    args = mock_debug_job.call_args[1]
    assert args['organization_id'] == '1122334455667'


@patch('abejacli.common.get_organization_id')
@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
@patch('abejacli.training.commands.TrainingJobLocalContainerRun')
def test_train_local_environment(mock_train_local, mock_get_organization_id, runner, req_mock):
    mock_job = MagicMock()
    mock_train_local.return_value = mock_job
    mock_get_organization_id.return_value = '1122334455667'

    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10',
        'environment': {
            'param1': 'value1', 'param2': 'value2', 'param3': 'value3'
        },
        'datasets': {'dataset_name1': 'value1'},
        'ignores': ['.gitignore']
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    version_info = {
        'job_definition_id': '1111111111111',
        'job_definition_version': 1,
        'image': 'abeja-inc/all-cpu:18.10',
        'environment': {
            'param2': 'value22',
            'param3': 'value33',
            'foo': 'bar'
        },
        'archived': False
    }
    url = "{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, 'training_def_version_1', 1)
    req_mock.register_uri(
        'GET', url,
        json=version_info)

    cmd = [
        '--name', 'training_def_version_1',
        '--version', '1',
        '--environment', 'USER_ID:1234567890123',
        '--environment', 'param3:value333',
        '--config', abejacli.training.CONFIGFILE_NAME,
    ]

    r = runner.invoke(train_local, cmd)

    assert r.exit_code == 0, r.output
    mock_get_organization_id.assert_called_once_with()
    args = mock_train_local.call_args[1]
    assert args['job_definition_name'] == 'training_def_version_1'
    expect_environment = {
        'param1': 'value1',
        'param2': 'value2',
        'param3': 'value333',
        'USER_ID': '1234567890123',
        'foo': 'bar'
    }
    assert args['environment'] == expect_environment

    # Test without `--name`
    url = "{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, 'training-1', 1)
    req_mock.register_uri(
        'GET', url,
        json=version_info)
    cmd = [
        '--version', '1',
        '--config', abejacli.training.CONFIGFILE_NAME,
    ]
    r = runner.invoke(train_local, cmd)
    assert r.exit_code == 0, r.output
    args = mock_train_local.call_args[1]
    assert args['job_definition_name'] == 'training-1'

# Job definitions


def test_describe_job_definitions(req_mock, runner):
    url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception


def test_describe_job_definitions_limit_offset(req_mock, runner):
    url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
        "limit": ['444'],
        "offset": ["333"]
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ["--limit", "444", "--offset", "333"]
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception


def test_describe_job_definition(req_mock, runner):
    test_job_name = 'test-job'
    url = "{}/training/definitions/{}".format(ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}$".format(url)
    matcher = re.compile(re_url)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['--job-definition-name', test_job_name]
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception


def test_describe_job_definitions_include_archived(req_mock, runner):
    url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["include_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['--include-archived']
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception

# Job definition versions


def test_describe_job_definition_versions(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"]
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name]
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception


@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_describe_job_definition_versions_from_config(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data["name"])
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception


@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_describe_job_definition_versions_option_overwrites_config(req_mock, runner):
    testing_name = 'dummy-name'
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, testing_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', testing_name]
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception


def test_describe_job_definition_versions_include_archived(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["include_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, '--include-archived']
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception

# Traininig models


def test_describe_training_models(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/models".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name]
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception


@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_describe_training_models_from_config(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/models".format(
        ORGANIZATION_ENDPOINT, config_data["name"])
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception


@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_describe_training_models_option_overwrites_config(req_mock, runner):
    testing_name = 'dummy-name'
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/models".format(
        ORGANIZATION_ENDPOINT, testing_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', testing_name]
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception


def test_describe_training_models_include_archived(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/models".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["include_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, '--include-archived']
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception

# Jobs


def test_describe_jobs(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name]
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception


def test_describe_jobs_limit_offset(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
        "limit": ["444"],
        "offset": ["333"]
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, "--limit", "444", "--offset", "333"]
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception


@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_describe_jobs_from_config(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, config_data["name"])
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_jobs, cmd)
    print(r.output)
    assert not r.exception


@patch('abejacli.training.CONFIGFILE_NAME', get_tmp_training_file_name())
def test_describe_jobs_option_overwrites_config(req_mock, runner):
    testing_name = 'dummy-name'
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(abejacli.training.CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, testing_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        "filter_archived": ["exclude_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', testing_name]
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception


def test_describe_jobs_include_archived(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, test_job_name)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)
    expected_params = {
        "filter_archived": ["include_archived"],
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, '--include-archived']
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception
