from unittest import TestCase

from abejacli.config import RESERVED_ENV_VAR
from abejacli.docker.commands.run import (
    ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN,
    ABEJA_PLATFORM_USER_ID,
    ModelRunCommand,
    TrainRunCommand,
    build_volumes
)


def convert_to_dict(env_vars):
    d = {}
    for var in env_vars:
        k, v = var.split('=')
        d[k] = v
    return d


class CommandTest(TestCase):
    def test_model_run_command_create(self):
        image = 'abeja/all-cpu:18.10'
        handler = 'predict:handler'
        device_type = 'x86_cpu'
        env_vars = {'DUMMY': 'dummy'}

        model_run_command = ModelRunCommand.create(
            image=image, handler=handler, device_type=device_type,
            env_vars=env_vars)

        params = model_run_command.to_dict()

        env_vars = convert_to_dict(params['environment'])

        assert env_vars['DUMMY'] == 'dummy'
        assert env_vars['PYTHONUNBUFFERED'] == 'x'
        assert env_vars['ABEJA_STORAGE_DIR_PATH'] == '/cache/.abeja/.cache'
        assert env_vars['SERVICE_TYPE'] == 'HTTP'
        assert env_vars['HANDLER'] == 'predict:handler'
        assert env_vars['ABEJA_TRAINING_RESULT_DIR'] == '.'

        assert ABEJA_PLATFORM_USER_ID in env_vars
        assert ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN in env_vars

        assert params['image'] == image

    def test_model_run_command_create_with_tokens(self):
        image = 'abeja/all-cpu:18.10'
        handler = 'predict:handler'
        device_type = 'x86_cpu'
        env_vars = {
            'DUMMY': 'dummy',
            ABEJA_PLATFORM_USER_ID: '1234567890123',
            ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN: 'xxxxx',
        }

        model_run_command = ModelRunCommand.create(
            image=image, handler=handler, device_type=device_type,
            env_vars=env_vars, organization_id='1230000000000')

        params = model_run_command.to_dict()

        env_vars = convert_to_dict(params['environment'])

        assert env_vars['DUMMY'] == 'dummy'
        assert env_vars['PYTHONUNBUFFERED'] == 'x'
        assert env_vars['ABEJA_STORAGE_DIR_PATH'] == '/cache/.abeja/.cache'
        assert env_vars['SERVICE_TYPE'] == 'HTTP'
        assert env_vars['HANDLER'] == 'predict:handler'
        assert env_vars['ABEJA_TRAINING_RESULT_DIR'] == '.'
        assert env_vars[ABEJA_PLATFORM_USER_ID] == '1234567890123'
        assert env_vars[ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN] == 'xxxxx'
        assert env_vars[RESERVED_ENV_VAR['organization_id']] == '1230000000000'

    def test_train_run_command_create(self):
        image = 'abeja/all-cpu:18.10'
        handler = 'predict:handler'
        env_vars = {'DUMMY': 'dummy'}
        custom_runtime = 'nvidia'
        volume = {
            '/tmp': {
                'bind': '/data',
                'mode': 'rw'
            }
        }

        train_run_command = TrainRunCommand.create(
            image=image, handler=handler, volume=volume,
            env_vars=env_vars, runtime=custom_runtime)

        params = train_run_command.to_dict()

        self.assertSetEqual(
            set(params['environment']), {
                'DUMMY=dummy',
                'PYTHONUNBUFFERED=x',
                'ABEJA_STORAGE_DIR_PATH=/cache/.abeja/.cache',
                'HANDLER=predict:handler'
            })
        self.assertEqual(params['image'], image)
        self.assertEqual(params['runtime'], custom_runtime)
        self.assertIn('/tmp', params['volumes'])
        self.assertDictEqual(params['volumes']['/tmp'], {
            'bind': '/data',
            'mode': 'rw'
        })

    def test_build_volumes(self):
        volume_params = (
            ('/tmp', '/tmp'),
            ('/tmp/data', '/data'),
        )
        volumes = build_volumes(volume_params)
        assert volumes == {
            '/tmp': {
                'bind': '/tmp', 'mode': 'rw'
            },
            '/tmp/data': {
                'bind': '/data', 'mode': 'rw'
            }
        }
