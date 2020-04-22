import os
from typing import Iterable, Optional


class Config(object):
    """
    User configuration object

    Reading value from environment variables
    ----------------------------------------
    Methods `user`, `token` and `organization` also read configuration
    value from environment variables in order:

    1. Environment variables
      - `ABEJA_CLI_USER`
      - `ABEJA_CLI_TOKEN`
      - `ABEJA_CLI_ORGANIZATION`
    2. Environment variables (obsolete)
      - `ABEJA_PLATFORM_USER`
      - `PERSONAL_ACCESS_TOKEN`
      - `ORGANIZATION_NAME`

    Notice `asdict` method doesn't regard environment variables.
    """

    def __init__(self, user: str, token: str, organization: str,
                 api_url: Optional[str] = None, name: Optional[str] = None):
        super().__init__()
        self.__name = name
        self.__user = user
        self.__token = token
        self.__organization = organization
        self.__api_url = api_url

    @staticmethod
    def prefixed_user(user: str) -> str:
        if user and not user.startswith('user-'):
            return 'user-{}'.format(user)
        else:
            return user

    @property
    def name(self):
        return self.__name

    @property
    def printable_name(self):
        """Returns printable name even if the config doesn't have a name.
        """
        return self.__name or '(default)'

    @property
    def user(self):
        user = os.environ.get(
            'ABEJA_CLI_USER', os.environ.get(
                'ABEJA_PLATFORM_USER', os.environ.get(
                    'ABEJA_PLATFORM_USER_ID', self.__user)))
        return self.prefixed_user(user)

    @property
    def token(self):
        return os.environ.get(
            'ABEJA_CLI_TOKEN', os.environ.get(
                'PERSONAL_ACCESS_TOKEN', os.environ.get(
                    'ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN', self.__token)))

    @property
    def organization(self):
        return os.environ.get(
            'ABEJA_CLI_ORGANIZATION', os.environ.get(
                'ORGANIZATION_NAME', os.environ.get(
                    'ABEJA_ORGANIZATION_ID', self.__organization)))

    @property
    def platform_auth_token(self):
        return os.environ.get('PLATFORM_AUTH_TOKEN', None)

    @property
    def api_url(self):
        return os.environ.get('ABEJA_API_URL', self.__api_url)

    def asdict(self):
        """Converts the config instance to a dict"""

        d = {
            'abeja-platform-user': self.__user,
            'personal-access-token': self.__token,
            'organization-name': self.__organization
        }
        if self.__name:
            d['configuration-name'] = self.__name
        if self.__api_url:
            d['abeja-api-url'] = self.__api_url

        return d


class ConfigSet():
    """
    Manages multiple named configurations and one unnamed configuration.
    This class behaves like a Set which contains instances of `Config` only.

    Unnamed configuration
    ---------------------
    Previously, ABEJA Platform CLI has only one configuration and it has no name.
    So this class supports unnamed configuration.

    As its name mentioned, an unnamed configuration's `name` is `None`. You have to
    pass `None` value to lookup methods to find an unnamed configuration.

        set.get(None)
        set.remove(None)
    """

    def __init__(self):
        super().__init__()
        self.__configs = []
        self.__active_config_name = None

    def __len__(self) -> int:
        return len(self.__configs)

    def __iter__(self) -> Iterable[Config]:
        return iter(self.__configs)

    def __contains__(self, name: Optional[str]) -> bool:
        c = self.get(name)
        return c is not None

    def __getitem__(self, name: Optional[str]) -> Config:
        c = self.get(name)
        if c is None:
            raise KeyError('config named "{}" doesn\'t exist.'.format(name))
        else:
            return c

    def get(self, name: Optional[str]) -> Optional[Config]:
        for c in self.__configs:
            if c.name == name:
                return c
        return None

    def add(self, config: Config, replace: bool = False):
        if config.name in self:
            if replace:
                self.remove(config.name)
            else:
                raise ValueError(
                    'config named "{}" already exist.'.format(config.name))
        self.__configs.append(config)

    def remove(self, name: Optional[str]):
        """
        Remove config named ``name`` from the set. Raises ``KeyError``
        if ``name`` is not contained in the set.
        """
        removed_list = list(filter(lambda x: x.name != name, self.__configs))

        if len(removed_list) == len(self.__configs):
            raise KeyError('config named "{}" doesn\'t exist.'.format(name))
        self.__configs = removed_list

    @property
    def active_config(self) -> Config:
        return self[self.__active_config_name]

    @property
    def active_config_name(self):
        return self.__active_config_name

    @active_config_name.setter
    def active_config_name(self, name: Optional[str]):
        self.__active_config_name = self[name].name

    def asdict(self):
        """Converts the instance to a dict"""
        d = {}
        if self.__active_config_name:
            d['active-configuration-name'] = self.__active_config_name

        for c in self.__configs:
            if c.name is None:
                d = {**d, **c.asdict()}
                # For backward compatibility
                d['abeja-platform-user'] = Config.prefixed_user(
                    d['abeja-platform-user'])
            else:
                configurations = d.get('configurations') or []
                configurations.append(c.asdict())
                d['configurations'] = configurations
        return d
