import os
import time
from tempfile import TemporaryDirectory

import pytest
from docker.models.images import Image
from mock import MagicMock, patch

from abejacli.config import (TRAIN_DEBUG_COMMAND_V1, TRAIN_DEBUG_COMMAND_V2,
                             TRAIN_LOCAL_COMMAND_V1, TRAIN_LOCAL_COMMAND_V2)
from abejacli.training.jobs import (TrainingJobDebugRun,
                                    TrainingJobLocalContainerRun,
                                    truncate_log_line)

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_ORG_ID = '1234567890123'
TEST_JOB_DEF_NAME = 'training-job-def-1'
TEST_JOB_DEF_VERSION = 1
TEST_DATASETS = {
    'train': '1700000000000'
}
TEST_ENVIRONMENT = {
    'DUMMY': 'dummy'
}


@pytest.fixture
def local_container_run():
    with patch.object(TrainingJobLocalContainerRun, '_setup_docker'):
        return TrainingJobLocalContainerRun(
            organization_id=TEST_ORG_ID,
            job_definition_name=TEST_JOB_DEF_NAME,
            job_definition_version=TEST_JOB_DEF_VERSION,
            datasets=TEST_DATASETS, environment=TEST_ENVIRONMENT,
            volume={'/tmp/data': {'bind': '/data', 'mode': 'rw'}},
            platform_user_id=TEST_CONFIG_USER_ID,
            platform_personal_access_token=TEST_CONFIG_TOKEN,
            polling_interval=1)


def generate_debug_run(
        handler='dummy:handler',
        image='abeja/all-cpu:19.04',
        organization_id=TEST_ORG_ID, datasets=None, environment=None,
        volume=None, platform_user_id=TEST_CONFIG_USER_ID, no_cache=True,
        platform_personal_access_token=TEST_CONFIG_TOKEN, v1flag=False):
    datasets = datasets or {}
    environment = environment or {}
    volume = volume or {'/tmp/data': {'bind': '/data', 'mode': 'rw'}}
    with patch.object(TrainingJobDebugRun, '_setup_docker'):
        return TrainingJobDebugRun(
            handler=handler, image=image, organization_id=organization_id,
            datasets=datasets, environment=environment, volume=volume,
            platform_user_id=platform_user_id, no_cache=no_cache,
            platform_personal_access_token=platform_personal_access_token, v1flag=v1flag)


debug_run = pytest.fixture(generate_debug_run)


@pytest.mark.parametrize(
    "given,expected",
    [
        ("1234567890", "1234567890"),
        ("1234567890abcdefg", "123456789..."),
        ("日本語abcdefg", "日本語..."),
        ('{"level": "info", "time": "2019-08-22T08:22:21Z"}', '{"level...')
    ]
)
def test_truncate_line(given, expected):
    log_line = {'message': given, 'timestamp': int(time.time() * 1000)}
    truncated = truncate_log_line(log_line, 55)
    actual = truncated['message']
    assert actual == expected, 'should be {}, but got {}'.format(expected, actual)


class TestTrainingJobLocalContainerRun:
    @patch('abejacli.training.jobs.create_local_training_job')
    @patch('abejacli.training.jobs.describe_training_version')
    def test_prepare(
            self, mock_describe_training_version,
            mock_create_local_training_job, local_container_run):
        mock_describe_training_version.return_value = {
            'handler': 'train:handler',
            'image': 'abeja-inc/all-cpu:19.04',
            'datasets': {
                'train': '1400000000000',
                'test': '1800000000000'
            },
            'user_parameters': {
                "C": "1",
                "NUM_EPOCHS": "1"
            }
        }
        mock_create_local_training_job.return_value = {
            'token': 'dummy',
            'training_job_id': '1230000000000'
        }
        local_container_run._prepare_command = MagicMock()
        local_container_run._prepare_image = MagicMock()

        local_container_run._prepare()

        assert local_container_run.datasets == {
            'train': '1700000000000',
            'test': '1800000000000'
        }
        assert local_container_run.environment == {
            'C': '1',
            'NUM_EPOCHS': '1',
            'DUMMY': 'dummy'
        }

    def test_watch(self, local_container_run):
        mock_container = MagicMock()
        mock_logs = MagicMock(return_value=(
            'message'.encode('utf-8')   # 7 bytes
            for _ in range(110)
        ))
        mock_container.logs = mock_logs

        local_container_run._get_container = MagicMock(
            return_value=mock_container)
        mock_send_logs = MagicMock()
        local_container_run.log_max_size = 5000
        local_container_run.log_flush_interval = float('Inf')
        local_container_run._send_logs = mock_send_logs
        local_container_run._get_remote_status = MagicMock(return_value=None)

        local_container_run.watch()

        assert mock_send_logs.call_count == 2
        assert len(mock_send_logs.call_args_list[0][0][0]) == 100
        assert len(mock_send_logs.call_args_list[1][0][0]) == 10

    def test_watch_flush_logs_at_time_interval(self, local_container_run):
        # FIXME: this is fragile and need to find better way.
        # this is because `freezegun` cannot stop time of `time.monotonic`
        mock_container = MagicMock()

        def mock_logs(**kwargs):
            for i in range(15):
                yield 'message_{}'.format(i).encode('utf-8')
                if (i + 1) % 10 == 0:
                    time.sleep(1)

        mock_container.logs = mock_logs

        local_container_run._get_container = MagicMock(
            return_value=mock_container)
        mock_send_logs = MagicMock()
        local_container_run.log_flush_interval = 1
        local_container_run._send_logs = mock_send_logs
        local_container_run._get_remote_status = MagicMock(return_value=None)

        local_container_run.watch()

        assert mock_send_logs.call_count == 2

    def test_watch_too_large_log_line(self, local_container_run):
        mock_container = MagicMock()
        mock_logs = MagicMock(return_value=[
            # length of below is 2,020
            ('message_length_of_20' * 101).encode('utf-8')
        ])
        mock_container.logs = mock_logs

        local_container_run._get_container = MagicMock(
            return_value=mock_container)
        mock_send_logs = MagicMock()
        local_container_run.log_max_size = 2000
        local_container_run.log_flush_interval = float('Inf')
        local_container_run._send_logs = mock_send_logs
        local_container_run._get_remote_status = MagicMock(return_value=None)

        local_container_run.watch()

        assert mock_send_logs.call_count == 1

        log_line = mock_send_logs.call_args_list[0][0][0][0]
        assert '...' in log_line['message'], 'message should be trimmed'

    def test_prepare_command(self, local_container_run):
        mock_temp_dir = MagicMock(spec_set=TemporaryDirectory())
        mock_temp_dir.name = 'dummy_temp_dir'
        local_container_run.temporary_archive_dir = mock_temp_dir
        local_container_run.image = MagicMock(
            spec_set=Image, id='dummy_image_id')
        local_container_run.image_name = 'abeja/dummy_image:18.10'

        local_container_run._prepare_command()
        cmd = local_container_run.command.to_dict()

        assert cmd['image'] == 'dummy_image_id'
        # command should include `abeja-model download_training_source_code`
        # to download training code of specified training job definition version.
        assert cmd['command'] == [
            '/bin/sh', '-c',
            'abeja-model download_training_source_code && abeja-model train']
        # volume for output should be set
        assert 'dummy_temp_dir' in cmd['volumes']
        assert cmd['volumes']['dummy_temp_dir'] == {'bind': '/output', 'mode': 'rw'}
        assert '/tmp/data' in cmd['volumes']
        assert cmd['volumes']['/tmp/data'] == {'bind': '/data', 'mode': 'rw'}
        assert os.getcwd() not in cmd['volumes']
        # the path should be set in environment variable so that training code can use it.
        assert 'ABEJA_TRAINING_RESULT_DIR=/output' in cmd['environment']

    @pytest.mark.parametrize(
        '_, v1flag, image_name, run_command', [
            (
                'v2',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/all-cpu:19.04',
                TRAIN_LOCAL_COMMAND_V2
            ), (
                'v1-18.10',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/all-cpu:18.10',
                TRAIN_LOCAL_COMMAND_V1
            ), (
                'v1-0.1.0',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/minimal:0.1.0',
                TRAIN_LOCAL_COMMAND_V1
            ), (
                'v1-0.1.0-arm64v8',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/pytorch:0.1.0-arm64v8',
                TRAIN_LOCAL_COMMAND_V1
            ), (
                'v1-v1flag=True',
                True,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/custom/1122334455667/face_identification:20190419054311',
                TRAIN_LOCAL_COMMAND_V1
            ), (
                'v2-because-not-contain-in-rule',
                False,
                'registry.abeja.io/custom/1122334455667/my-image:whatever',
                TRAIN_LOCAL_COMMAND_V2
            ),
        ]
    )
    def test_get_run_command(self, local_container_run, _, v1flag, image_name, run_command):
        local_container_run.v1flag = v1flag
        local_container_run.image_name = image_name
        cmd = local_container_run._get_run_command()
        assert cmd == run_command


class TestTrainingJobDebugRun:

    @pytest.mark.parametrize(
        '_, v1flag, image_name, run_command', [
            (
                'v2',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/all-cpu:19.04',
                TRAIN_DEBUG_COMMAND_V2
            ), (
                'v1-18.10',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/all-cpu:18.10',
                TRAIN_DEBUG_COMMAND_V1
            ), (
                'v1-0.1.0',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/minimal:0.1.0',
                TRAIN_DEBUG_COMMAND_V1
            ), (
                'v1-0.1.0-arm64v8',
                False,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/abeja-inc/pytorch:0.1.0-arm64v8',
                TRAIN_DEBUG_COMMAND_V1
            ), (
                'v1-v1flag=True',
                True,
                '935669904089.dkr.ecr.us-west-2.amazonaws.com/custom/1122334455667/face_identification:20190419054311',
                TRAIN_DEBUG_COMMAND_V1
            ), (
                'v2-because-not-contain-in-rule',
                False,
                'registry.abeja.io/custom/1122334455667/my-image:whatever',
                TRAIN_DEBUG_COMMAND_V2
            ),
        ]
    )
    def test_get_run_command(self, _, v1flag, image_name, run_command):
        job = generate_debug_run(
            handler='dummy:handler', image=image_name, organization_id=TEST_ORG_ID,
            datasets={}, environment={}, volume={'/tmp/data': {'bind': '/data', 'mode': 'rw'}},
            platform_user_id=TEST_CONFIG_USER_ID, no_cache=True,
            platform_personal_access_token=TEST_CONFIG_TOKEN, v1flag=v1flag)
        cmd = job._get_run_command()
        assert cmd == run_command

    def test_prepare_command(self, debug_run):
        debug_run.image = MagicMock()
        debug_run._prepare_command()
        cmd = debug_run.command.to_dict()

        current_dir = os.getcwd()
        assert current_dir in cmd['volumes']
        assert cmd['volumes'][current_dir] == {'bind': '/srv/app', 'mode': 'rw'}
