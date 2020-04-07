import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner
import pytest
import requests_mock
from ruamel.yaml import YAML

from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.exceptions import ResourceNotFound
from abejacli.training import CONFIGFILE_NAME
from abejacli.training.commands import debug_local, train_local
from abejacli.training.commands import create_notebook
from abejacli.training.commands import start_notebook
from abejacli.training.commands import create_training_version
from abejacli.training.commands import create_training_job
from abejacli.training.commands import update_training_version
from abejacli.training.commands import _get_latest_training_version
from abejacli.training.commands import describe_job_definitions
from abejacli.training.commands import describe_training_versions
from abejacli.training.commands import describe_jobs
from abejacli.training.commands import describe_training_models


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
def test_update_training_version(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
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
         {},
         {
             'notebook_type': 'notebook'
        }),
        (['-t', 'lab'],
         {},
         {
             'notebook_type': 'lab'
        }),
        (['--instance-type', 'gpu-1'],
         {},
         {
             'notebook_type': 'notebook',
             'instance_type': 'gpu-1'
        }),
        (['--image', 'abeja-inc/all-gpu:19.10'],
         {},
         {
             'image': 'abeja-inc/all-gpu:19.10'
        }),
        (['--datalake', '1234567890123'],
         {},
         {
             'notebook_type': 'notebook',
             'datalakes': ['1234567890123']
        }),
        (['--bucket', '1234567890123'],
         {},
         {
             'notebook_type': 'notebook',
             'buckets': ['1234567890123']
        }),
        (['--datalake', '1234567890123', '--bucket', '1234567890123'],
         {},
         {
             'notebook_type': 'notebook',
             'datalakes': ['1234567890123'],
             'buckets': ['1234567890123']
        }),
        (['--dataset', 'train:1600000000000'],
         {},
         {
             'notebook_type': 'notebook',
             'datasets': {'train': '1600000000000'}
        })
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
def test_create_notebook(
        req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    config_data = {**config_data, **additional_config}
    with open(CONFIGFILE_NAME, 'w') as configfile:
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
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'notebook'
        }),
        (['-n', '9876543210987', '--instance-type', 'gpu-1'],
         {},
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'notebook',
             'instance_type': 'gpu-1'
        }),
        (['-n', '9876543210987', '--image', 'abeja-inc/all-gpu:19.10'],
         {},
         {
            'training_notebook_id': '9876543210987',
            'image': 'abeja-inc/all-gpu:19.10'
        }),
        (['-n', '9876543210987', '-t', 'lab'],
         {},
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'lab'
        }),
        (['-n', '9876543210987', '--datalake', '1234567890123'],
         {},
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'notebook',
             'datalakes': ['1234567890123']
        }),
        (['-n', '9876543210987', '--bucket', '1234567890123'],
         {},
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'notebook',
             'buckets': ['1234567890123']
        }),
        (['-n', '9876543210987', '--datalake', '1234567890123', '--bucket', '1234567890123'],
         {},
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'notebook',
             'datalakes': ['1234567890123'],
             'buckets': ['1234567890123']
        }),
        (['-n', '9876543210987', '--dataset', 'train:1600000000000'],
         {},
         {
             'training_notebook_id': '9876543210987',
             'notebook_type': 'notebook',
             'datasets': {'train': '1600000000000'}
        })
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
def test_start_notebook(
        req_mock, runner, cmd, additional_config, expected_payload):
    notebook_id = '9876543210987'
    config_data = {
        'name': 'training-1',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    config_data = {**config_data, **additional_config}
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/notebooks/{}/start".format(
        ORGANIZATION_ENDPOINT, config_data['name'], notebook_id)

    req_mock.register_uri(
        'POST', url,
        json=expected_payload)

    r = runner.invoke(start_notebook, cmd)
    assert req_mock.called
    assert r.exit_code == 0


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--description', 'dummy description'],
         {},
         {
             'description': 'dummy description'
        }),
        (['--description', 'dummy description', '--environment', 'BATCH_SIZE:32'],
         {},
         {
             'description': 'dummy description',
             'environment': {'BATCH_SIZE': '32'}
        }),
        (['--description', 'dummy description'],
         {
             'datasets': {'train': '1600000000000'},
             'params': {'key9': 'value9'}
        },
            {
             'description': 'dummy description',
             'environment': {'key9': 'value9'}
        }),
        (['--description', 'dummy description'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'}
        },
            {'description': 'dummy description', 'environment': {'key1': 'value1', 'key2': 'value2'}}),
        (['--description', 'dummy description'],
         {
             'datasets': {'train': '1600000000000'},
             'environment': {'key1': 'value1', 'key2': 'value2'},
             'params': {'key9': 'value9'}
        },
            {'description': 'dummy description', 'environment': {'key1': 'value1', 'key2': 'value2'}}),
        (['--datalake', '1234567890123'],
         {},
         {
             'datalakes': ['1234567890123']
        }),
        (['--bucket', '2345678901234'],
         {},
         {
             'buckets': ['2345678901234']
        }),
        (['--datalake', '1234567890123', '--bucket', '2345678901234'],
         {},
         {
             'datalakes': ['1234567890123'],
             'buckets': ['2345678901234']
        })
    ]
)
@patch('abejacli.training.commands.version_archive', MagicMock(return_value=None))
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
def test_create_training_version(
        req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    config_data = {**config_data, **additional_config}
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    expected_payload = {**expected_payload, **{'handler': config_data['handler'], 'image': config_data['image']}}
    with patch('abejacli.training.commands._create_training_version') as mock:
        mock.return_value = {}  # dummy response
        r = runner.invoke(create_training_version, cmd)
        args = mock.call_args[0]
        assert args[0] == url
        assert args[1] == expected_payload
    assert not r.exception

    # For 20.02 image.
    # Invalid pair of "image" and "handler".
    config_data = {
        'name': 'training-1',
        'handler': 'train',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    config_data = {**config_data, **additional_config}
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)
    r = runner.invoke(create_training_version, cmd)
    assert r.exception

    # Valid pair of "image" and "handler".
    # "handler" does not need to specify METHOD field.
    config_data = {
        'name': 'training-1',
        'handler': 'train',
        'image': 'abeja-inc/all-cpu:20.02a'
    }
    config_data = {**config_data, **additional_config}
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, config_data['name'])

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    expected_payload = {**expected_payload, **{'handler': config_data['handler'], 'image': config_data['image']}}
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
        })
    ]
)
@patch('abejacli.training.commands.CONFIG', TEST_CONFIG)
def test_create_training_job(req_mock, runner, cmd, additional_config, expected_payload):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    config_data = {**config_data, **additional_config}
    with open(CONFIGFILE_NAME, 'w') as configfile:
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
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    default_cmd = [
        '--image', 'abeja/all-gpu:18.10',  # not `abeja-inc/all-cpu:18.10`
        '--organization_id', '1122334455667',
        '--volume', '/tmp:/data',
        '--volume', '/usr/bin/hoge:/hoge',
        '--config', CONFIGFILE_NAME,
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
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    cmd = [
        '--image', 'abeja/all-gpu:18.10',   # not `abeja-inc/all-cpu:18.10`
        '--organization_id', '1122334455667',
        '--environment', 'USER_ID:1234567890123',
        '--environment', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
        '--environment', 'MAX_ITEMS:',
        '--volume', '/tmp:/data',
        '--volume', '/usr/bin/hoge:/hoge',
        '--config', CONFIGFILE_NAME,
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
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    r = runner.invoke(debug_local, [
        '--organization_id', '1122334455667',
        '--config', CONFIGFILE_NAME
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
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)

    cmd = [
        '--image', 'abeja/all-gpu:18.10',  # not `abeja-inc/all-cpu:18.10`
        # '--organization_id', '1122334455667',
        '--environment', 'USER_ID:1234567890123',
        '--environment', 'ACCESS_KEY:373be7309f0146c0d283440e500843d8',
        '--config', CONFIGFILE_NAME,
    ]
    r = runner.invoke(debug_local, cmd)

    assert r.exit_code == 0, r.output

    mock_get_organization_id.assert_called_once_with()

    args = mock_debug_job.call_args[1]
    assert args['organization_id'] == '1122334455667'


@patch('abejacli.common.get_organization_id')
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
    with open(CONFIGFILE_NAME, 'w') as configfile:
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
        '--config', CONFIGFILE_NAME,
    ]

    r = runner.invoke(train_local, cmd)

    assert r.exit_code == 0, r.output
    mock_get_organization_id.assert_called_once_with()
    args = mock_train_local.call_args[1]
    expect_environment = {
        'param1': 'value1',
        'param2': 'value2',
        'param3': 'value333',
        'USER_ID': '1234567890123',
        'foo': 'bar'
    }
    assert args['environment'] == expect_environment

# Job definitions


def test_describe_job_definitions(req_mock, runner):
    url = "{}/training/definitions?filter_archived=exclude_archived".format(ORGANIZATION_ENDPOINT)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception


def test_describe_job_definition(req_mock, runner):
    test_job_name = 'test-job'
    url = "{}/training/definitions/{}".format(ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['--job-definition-name', test_job_name]
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception


def test_describe_job_definitions_include_archived(req_mock, runner):
    url = "{}/training/definitions?filter_archived=include_archived".format(ORGANIZATION_ENDPOINT)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['--include-archived']
    r = runner.invoke(describe_job_definitions, cmd)
    assert not r.exception

# Job definition versions


def test_describe_job_definition_versions(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/versions?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name]
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception


def test_describe_job_definition_versions_from_config(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/versions?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, config_data["name"])

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception


def test_describe_job_definition_versions_option_overwrites_config(req_mock, runner):
    testing_name = 'dummy-name'
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/versions?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, testing_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', testing_name]
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception


def test_describe_job_definition_versions_include_archived(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/versions?filter_archived=include_archived".format(
        ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, '--include-archived']
    r = runner.invoke(describe_training_versions, cmd)
    assert not r.exception

# Traininig models


def test_describe_training_models(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/models?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name]
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception


def test_describe_training_models_from_config(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/models?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, config_data["name"])

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception


def test_describe_training_models_option_overwrites_config(req_mock, runner):
    testing_name = 'dummy-name'
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/models?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, testing_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', testing_name]
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception


def test_describe_training_models_include_archived(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/models?filter_archived=include_archived".format(
        ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, '--include-archived']
    r = runner.invoke(describe_training_models, cmd)
    assert not r.exception

# Jobs


def test_describe_jobs(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/jobs?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name]
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception


def test_describe_jobs_from_config(req_mock, runner):
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/jobs?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, config_data["name"])

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception


def test_describe_jobs_option_overwrites_config(req_mock, runner):
    testing_name = 'dummy-name'
    config_data = {
        'name': 'training-1',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-cpu:18.10'
    }
    with open(CONFIGFILE_NAME, 'w') as configfile:
        yaml.dump(config_data, configfile)
    url = "{}/training/definitions/{}/jobs?filter_archived=exclude_archived".format(
        ORGANIZATION_ENDPOINT, testing_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', testing_name]
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception


def test_describe_jobs_include_archived(req_mock, runner):
    test_job_name = 'test-job-name'
    url = "{}/training/definitions/{}/jobs?filter_archived=include_archived".format(
        ORGANIZATION_ENDPOINT, test_job_name)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json={},
        additional_matcher=match_request_url)

    cmd = ['-j', test_job_name, '--include-archived']
    r = runner.invoke(describe_jobs, cmd)
    assert not r.exception