import os
import random
from unittest import mock

import pytest

from abejacli.configuration.config import Config, ConfigSet


@pytest.fixture
def config_set():
    return ConfigSet()


def random_token(n):
    # Python 3.5 lacks `secrets` module
    ''.join([
        random.choice(['0', '1', '2', '3', '4', '5', '6', '7',
                       '8', '9', 'a', 'b', 'c', 'd', 'e', 'f'])
        for _ in range(n)
    ])


def random_config():
    return {
        'user': str(random.randint(1000000000000, 9999999999999)),
        'token': random_token(20),
        'organization': random.choice(['abeja-inc', 'abejainc-com', 'abeja-corp'])
    }


class TestConfig(object):

    def test_name(self):
        plain_config = random_config()
        config = Config(**plain_config, name='A')
        assert config.name == 'A'
        d = config.asdict()
        assert d['configuration-name'] == config.name

    def test_api_url(self):
        plain_config = random_config()
        api_url = os.environ.get('ABEJA_API_URL', 'https://api.dev.abeja.io')
        config = Config(**plain_config, api_url=api_url)
        assert config.api_url == api_url
        d = config.asdict()
        assert d['abeja-api-url'] == config.api_url

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_without_env(self):
        plain_config = random_config()
        config = Config(**plain_config)

        assert config.name is None
        assert config.user == ('user-' + plain_config['user'])
        assert config.token == plain_config['token']
        assert config.organization == plain_config['organization']
        assert config.asdict() == {
            'abeja-platform-user': plain_config['user'],
            'personal-access-token': plain_config['token'],
            'organization-name': plain_config['organization']
        }

    def test_with_environ(self, fake_environ):
        with mock.patch.dict(os.environ, fake_environ):
            plain_config = random_config()
            config = Config(**plain_config)

            assert config.name is None
            assert config.user == fake_environ['ABEJA_CLI_USER']
            assert config.token == fake_environ['ABEJA_CLI_TOKEN']
            assert config.organization == fake_environ['ABEJA_CLI_ORGANIZATION']
            assert config.asdict() == {
                'abeja-platform-user': plain_config['user'],
                'personal-access-token': plain_config['token'],
                'organization-name': plain_config['organization']
            }

    def test_with_environ_mix(self, fake_environ, fake_environ_deprecated):
        env = {}
        env.update(fake_environ)
        env.update(fake_environ_deprecated)
        with mock.patch.dict(os.environ, env):
            plain_config = random_config()
            config = Config(**plain_config)

            assert config
            assert config.name is None
            assert config.user == fake_environ['ABEJA_CLI_USER']
            assert config.token == fake_environ['ABEJA_CLI_TOKEN']
            assert config.organization == fake_environ['ABEJA_CLI_ORGANIZATION']
            assert config.asdict() == {
                'abeja-platform-user': plain_config['user'],
                'personal-access-token': plain_config['token'],
                'organization-name': plain_config['organization']
            }

    def test_with_environ_deprecated(self, fake_environ_deprecated):
        with mock.patch.dict(os.environ, fake_environ_deprecated):
            plain_config = random_config()
            config = Config(**plain_config)

            assert config
            assert config.name is None
            assert config.user == fake_environ_deprecated['ABEJA_PLATFORM_USER']
            assert config.token == fake_environ_deprecated['PERSONAL_ACCESS_TOKEN']
            assert config.organization == fake_environ_deprecated['ORGANIZATION_NAME']
            assert config.asdict() == {
                'abeja-platform-user': plain_config['user'],
                'personal-access-token': plain_config['token'],
                'organization-name': plain_config['organization']
            }

    def test_with_environ_platform_auth_token(self, fake_environ_auth_token):
        with mock.patch.dict(os.environ, fake_environ_auth_token):
            config = Config(None, None, None)

            assert config
            assert config.name is None
            assert config.user is None
            assert config.token is None
            assert config.organization == fake_environ_auth_token['ABEJA_CLI_ORGANIZATION']
            assert config.platform_auth_token == fake_environ_auth_token['PLATFORM_AUTH_TOKEN']
            assert config.asdict() == {
                'abeja-platform-user': None,
                'personal-access-token': None,
                'organization-name': None
            }

    def test_with_environ_on_job(self, fake_environ_job):
        with mock.patch.dict(os.environ, fake_environ_job):
            plain_config = random_config()
            config = Config(**plain_config)

            assert config
            assert config.name is None
            assert config.user == fake_environ_job['ABEJA_PLATFORM_USER_ID']
            assert config.token == fake_environ_job['ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN']
            assert config.organization == fake_environ_job['ABEJA_CLI_ORGANIZATION']
            assert config.asdict() == {
                'abeja-platform-user': plain_config['user'],
                'personal-access-token': plain_config['token'],
                'organization-name': plain_config['organization']
            }


class TestConfigSet(object):

    def test_len(self, config_set):
        assert len(config_set) == 0
        config_set.add(Config(**random_config(), name='A'))
        assert len(config_set) == 1
        config_set.add(Config(**random_config(), name='B'))
        assert len(config_set) == 2

    def test_iter(self, config_set):
        assert len(list(config_set)) == 0

        config_set.add(Config(**random_config(), name='A'))
        for c in config_set:
            assert c.name == 'A'

        config_set.add(Config(**random_config(), name='B'))
        config_set.add(Config(**random_config(), name='C'))

        # order must be preserved
        it = iter(config_set)
        assert it.__next__().name == 'A'
        assert it.__next__().name == 'B'
        assert it.__next__().name == 'C'
        with pytest.raises(StopIteration):
            it.__next__()

    def test_contains(self, config_set):
        assert 'A' not in config_set
        config_set.add(Config(**random_config(), name='A'))
        assert 'A' in config_set
        config_set.add(Config(**random_config(), name='B'))
        assert 'B' in config_set
        config_set.add(Config(**random_config()))
        assert None in config_set

    def test_remove(self, config_set):
        config_set.add(Config(**random_config()))
        config_set.add(Config(**random_config(), name='A'))
        config_set.add(Config(**random_config(), name='B'))

        config_set.remove('A')
        assert 'A' not in config_set
        config_set.remove('B')
        assert 'B' not in config_set
        config_set.remove(None)
        assert None not in config_set
        with pytest.raises(KeyError):
            config_set.remove('C')

    def test_get_item(self, config_set):
        with pytest.raises(KeyError):
            config_set['A']

        config1 = Config(**random_config(), name='A')
        config_set.add(config1)
        assert config_set['A'] == config1
        with pytest.raises(KeyError):
            config_set['B']

    def test_get(self, config_set):
        assert not config_set.get('A')
        config1 = Config(**random_config(), name='A')
        config_set.add(config1)
        assert config_set.get('A') == config1
        assert config_set.get('B') is None

    def test_unnamed_config(self, config_set):
        config = Config(**random_config())
        config_set.add(config)
        assert len(config_set) == 1
        assert config_set.get(None) == config

    def test_activation(self, config_set):
        assert config_set.active_config_name is None
        with pytest.raises(KeyError):
            config_set.active_config_name = 'A'

        config_set.add(Config(**random_config()))
        config_set.active_config_name = None
        assert config_set.active_config_name is None
        assert config_set.active_config
        assert config_set.active_config.name is None

        config_set.add(Config(**random_config(), name='A'))
        config_set.active_config_name = 'A'
        assert config_set.active_config_name == 'A'
        assert config_set.active_config
        assert config_set.active_config.name == 'A'
