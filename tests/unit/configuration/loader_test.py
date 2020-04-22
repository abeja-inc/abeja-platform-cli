import json
import os
from unittest import mock

import pytest

from abejacli.configuration.config import Config
from abejacli.configuration.loader import ConfigSetLoader
from abejacli.exceptions import InvalidConfigException


@pytest.fixture
def config_file(tmpdir_factory, plain_config):
    fn = tmpdir_factory.mktemp("data").join("config.json")
    with open(str(fn), 'w') as fp:
        json.dump(plain_config, fp)
    return str(fn)


class TestConfigSetLoader(object):

    def test_init(self):
        loader = ConfigSetLoader()
        assert loader

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_build_config(self, plain_config):
        loader = ConfigSetLoader()
        config = loader.build_config(plain_config)

        assert config
        assert config.name is None
        assert config.user == plain_config['abeja-platform-user']
        assert config.token == plain_config['personal-access-token']
        assert config.organization == plain_config['organization-name']

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_build_config_wo_user_prefix(self, plain_config_without_user_prefix):
        loader = ConfigSetLoader()
        config = loader.build_config(plain_config_without_user_prefix)

        assert config
        assert config.name is None
        assert config.user == Config.prefixed_user(
            plain_config_without_user_prefix['abeja-platform-user'])
        assert config.token == plain_config_without_user_prefix['personal-access-token']
        assert config.organization == plain_config_without_user_prefix['organization-name']

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_load_from_file(self, config_file, plain_config):
        with open(config_file) as fp:
            loader = ConfigSetLoader()
            config_set = loader.load_from_file(fp)
            assert len(config_set) == 1

            config = config_set[None]
            assert config
            assert config.name is None
            assert config.user == plain_config['abeja-platform-user']
            assert config.token == plain_config['personal-access-token']
            assert config.organization == plain_config['organization-name']

    def test_load_override_with_environ(self, plain_config, fake_environ):
        with mock.patch.dict(os.environ, fake_environ):
            loader = ConfigSetLoader()
            config_set = loader.load_from_dict(plain_config)
            assert len(config_set) == 1

            config = config_set[None]
            assert config
            assert config.name is None
            assert config.user == fake_environ['ABEJA_CLI_USER']
            assert config.token == fake_environ['ABEJA_CLI_TOKEN']
            assert config.organization == fake_environ['ABEJA_CLI_ORGANIZATION']

    def test_load_override_with_environ_mix(
            self, plain_config, fake_environ, fake_environ_deprecated, fake_environ_job):
        env = {}
        env.update(fake_environ)
        env.update(fake_environ_deprecated)
        env.update(fake_environ_job)
        with mock.patch.dict(os.environ, env):
            loader = ConfigSetLoader()
            config_set = loader.load_from_dict(plain_config)
            assert len(config_set) == 1

            config = config_set[None]
            assert config.name is None
            assert config.user == fake_environ['ABEJA_CLI_USER']
            assert config.token == fake_environ['ABEJA_CLI_TOKEN']
            assert config.organization == fake_environ_job['ABEJA_CLI_ORGANIZATION']

    def test_load_from_dict_override_with_environ(self, plain_config, fake_environ):
        with mock.patch.dict(os.environ, fake_environ):
            loader = ConfigSetLoader()
            config_set = loader.load_from_dict(plain_config)
            assert len(config_set) == 1

            config = config_set[None]
            assert config
            assert config.name is None
            assert config.user == fake_environ['ABEJA_CLI_USER']
            assert config.token == fake_environ['ABEJA_CLI_TOKEN']
            assert config.organization == fake_environ['ABEJA_CLI_ORGANIZATION']

    def test_load_override_with_environ_deprecated(self, plain_config, fake_environ_deprecated):
        with mock.patch.dict(os.environ, fake_environ_deprecated):
            loader = ConfigSetLoader()
            config_set = loader.load_from_dict(plain_config)
            assert len(config_set) == 1

            config = config_set[None]
            assert config
            assert config.name is None
            assert config.user == fake_environ_deprecated['ABEJA_PLATFORM_USER']
            assert config.token == fake_environ_deprecated['PERSONAL_ACCESS_TOKEN']
            assert config.organization == fake_environ_deprecated['ORGANIZATION_NAME']

    def test_load_override_with_environ_job(self, plain_config, fake_environ_job):
        with mock.patch.dict(os.environ, fake_environ_job):
            loader = ConfigSetLoader()
            config_set = loader.load_from_dict(plain_config)
            assert len(config_set) == 1

            config = config_set[None]
            assert config
            assert config.name is None
            assert config.user == fake_environ_job['ABEJA_PLATFORM_USER_ID']
            assert config.token == fake_environ_job['ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN']
            assert config.organization == fake_environ_job['ABEJA_CLI_ORGANIZATION']

    def test_load_with_environ_auth_token(self, fake_environ_auth_token):
        with mock.patch.dict(os.environ, fake_environ_auth_token):
            loader = ConfigSetLoader()
            config_set = loader.load_from_dict({})
            assert len(config_set) == 1

            config = config_set[None]
            assert config
            assert config.name is None
            assert config.user is None
            assert config.token is None
            assert config.organization == fake_environ_auth_token['ABEJA_CLI_ORGANIZATION']
            assert config.platform_auth_token == fake_environ_auth_token['PLATFORM_AUTH_TOKEN']

    def test_no_configuration(self):
        loader = ConfigSetLoader()
        with pytest.raises(InvalidConfigException):
            loader.load_from_dict({})

    def test_no_configuration_with_insufficient_environ(self):
        with mock.patch.dict(os.environ, {}):
            loader = ConfigSetLoader()
            with pytest.raises(InvalidConfigException):
                loader.load_from_dict({})

        with mock.patch.dict(os.environ, {'ABEJA_ORGANIZATION_ID': 'dummy'}):
            loader = ConfigSetLoader()
            with pytest.raises(InvalidConfigException):
                loader.load_from_dict({})

        with mock.patch.dict(os.environ, {
            'ABEJA_ORGANIZATION_ID': 'dummy', 'ABEJA_PLATFORM_USER_ID': 'dummy'
        }):
            loader = ConfigSetLoader()
            with pytest.raises(InvalidConfigException):
                loader.load_from_dict({})

        with mock.patch.dict(os.environ, {
            'ABEJA_ORGANIZATION_ID': 'dummy', 'ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN': 'dummy'
        }):
            loader = ConfigSetLoader()
            with pytest.raises(InvalidConfigException):
                loader.load_from_dict({})

    def test_no_unnamed_configuration(self, plain_config):
        loader = ConfigSetLoader()

        plain_config['configuration-name'] = 'test'
        config_set = loader.load_from_dict({
            "active-configuration-name": "test",
            "configurations": [plain_config]
        })

        assert len(config_set) == 1
        assert config_set.active_config_name == 'test'
