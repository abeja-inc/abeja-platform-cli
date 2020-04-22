import os.path

import click

from abejacli.configuration.config import ConfigSet
from abejacli.configuration.loader import ConfigSetLoader
from abejacli.exceptions import InvalidConfigException

ROOT_DIRECTORY = os.path.join(os.path.expanduser('~'), '.abeja')
CONFIG_FILE_PATH = os.path.join(ROOT_DIRECTORY, 'config')


def __ensure_configuration_exists(ctx: click.Context) -> ConfigSet:
    try:
        return ConfigSetLoader().load()
    except InvalidConfigException:
        click.echo(
            "[error] configuration not found or malformed, execute 'abeja config init'")
        ctx.abort()
