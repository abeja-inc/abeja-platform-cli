import json
import re
from collections import OrderedDict
from typing import Dict, List

from abejacli.configuration.config import Config, ConfigSet


class ConfigFormatter(object):

    def __init__(self, config: Config):
        super().__init__()
        self.__config = config

    @staticmethod
    def build(config: Config, format: str = None):
        if format == 'json':
            return JSONConfigFormatter(config)
        else:
            return PlainConfigFormatter(config)

    @property
    def config(self) -> Config:
        return self.__config

    def format(self, user: bool = False, token: bool = False, organization: bool = False) -> str:
        config = self.config

        if user:
            return self.format_dict({'abeja-platform-user': config.user})
        elif token:
            return self.format_dict({'personal-access-token': config.token})
        elif organization:
            return self.format_dict({'organization-name': config.organization})
        else:
            return self.format_dict(OrderedDict([
                ('abeja-platform-user', config.user),
                ('personal-access-token', config.token),
                ('organization-name', config.organization),
            ]))

    def format_dict(self, dict: Dict[str, str]) -> str:
        raise NotImplementedError


class ConfigSetListFormatter(object):

    def __init__(self, config_set: ConfigSet):
        super().__init__()
        self.__config_set = config_set

    @staticmethod
    def build(config_set: ConfigSet, format: str = None):
        if format == 'plain':
            return PlainConfigSetListFormatter(config_set)
        else:
            raise NotImplementedError()

    @property
    def config_set(self) -> ConfigSet:
        return self.__config_set

    def format(self) -> str:
        raise NotImplementedError()

# ConfigFormatter


class PlainConfigFormatter(ConfigFormatter):

    def format_dict(self, dict: Dict[str, str]) -> str:
        items = ['{}:{}'.format(k, v) for k, v in dict.items()]
        return '\n'.join(items)


class JSONConfigFormatter(ConfigFormatter):

    def format_dict(self, dict: Dict[str, str]) -> str:
        return json.dumps(dict, indent=2)

# ConfigSetListFormatter


class PlainConfigSetListFormatter(ConfigSetListFormatter):
    TOKEN_VISIBLE_CHARS = 4

    def format(self):
        config_set = self.config_set
        rows = [['', 'NAME', 'ORGANIZATION', 'USER', 'TOKEN']]

        for c in config_set:
            active_mark = '*' if c.name == config_set.active_config_name else ''
            rows.append([active_mark,
                         c.printable_name,
                         c.organization,
                         self.__remove_user_prefix(c.user),
                         self.__mask_token(c.token)])

        return self.__format_table(rows)

    def __format_table(self, rows: List[List[str]]) -> str:
        lines = []
        # Calculate max width for each rows.
        # e.g. [5, 10, ...]
        widths = [max(map(len, col)) for col in zip(*rows)]
        for row in rows:
            # Format each rows with spaces
            line = '  '.join((val.ljust(width)
                              for val, width in zip(row, widths)))
            lines.append(line)
        return '\n'.join(lines)

    def __remove_user_prefix(self, user: str) -> str:
        return re.sub(r'^user-', r'', user)

    def __mask_token(self, token: str) -> str:
        n = self.TOKEN_VISIBLE_CHARS
        return re.sub(r'.', r'*', token[:-n]) + token[-n:]
