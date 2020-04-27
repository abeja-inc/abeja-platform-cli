import json
from typing import Dict
from typing.io import BinaryIO

# run_test.py will rewrite the variable `CONFIG_FILE_PATH` so we have to access
# the variable through the module. Don't import variable directly.
import abejacli.configuration
from abejacli.configuration.config import Config, ConfigSet
from abejacli.exceptions import InvalidConfigException


class ConfigSetLoader(object):
    """
    The loader class which loads a user configurations from
    a dictionary (or its JSON serialization form).
    """

    def load(self) -> ConfigSet:
        try:
            with open(abejacli.configuration.CONFIG_FILE_PATH, 'r') as f:
                return self.load_from_file(f)
        except FileNotFoundError:
            # Try to read configuration from environment variables only
            return self.load_from_dict({})

    def load_from_file(self, fp: BinaryIO) -> ConfigSet:
        try:
            return self.load_from_dict(json.load(fp))
        except json.JSONDecodeError:
            raise InvalidConfigException('malformed configuration file')

    def load_from_string(self, string: str) -> ConfigSet:
        try:
            return self.load_from_dict(json.loads(string))
        except json.JSONDecodeError:
            raise InvalidConfigException('malformed configuration')

    def load_from_dict(self, plain_config: Dict[str, str]) -> ConfigSet:
        config_set = ConfigSet()

        # Named configurations
        for c in (plain_config.get('configurations') or []):
            config_set.add(self.build_config(c))

        # Unnamed configuration. If there are no named configurations,
        # an unnamed configuration must exist.
        try:
            config_set.add(self.build_config(plain_config))
        except InvalidConfigException:
            if len(config_set) == 0:
                raise

        name = plain_config.get('active-configuration-name')
        if name:
            config_set.active_config_name = name

        return config_set

    def build_config(self, plain_config: Dict[str, str]) -> Config:
        name = plain_config.get('configuration-name')
        user = plain_config.get('abeja-platform-user')
        token = plain_config.get('personal-access-token')
        organization = plain_config.get('organization-name')
        api_url = plain_config.get('abeja-api-url')

        config = Config(user=user, token=token,
                        organization=organization, api_url=api_url, name=name)

        if config.organization is None:
            raise InvalidConfigException(
                'missing config value: {}'.format('organization-name'))
        if (config.user is None or config.token is None) and config.platform_auth_token is None:
            raise InvalidConfigException(
                'missing config value: {} or {}'.format('abeja-platform-user', 'personal-access-token'))

        return config
