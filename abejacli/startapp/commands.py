import datetime
import os
import shutil
import stat
import sys
from pathlib import Path

import click

import abejacli
import abejacli.version
from abejacli.common import json_output_formatter
from abejacli.config import ERROR_EXITCODE
from abejacli.logger import get_logger

__version__ = abejacli.version.VERSION
date = datetime.datetime.today()
logger = get_logger()


@click.group(help='Application generation commands')
@click.pass_context
def startapp(ctx):
    pass


# ---------------------------------------------------
# application generation command
# ---------------------------------------------------
@startapp.command(name='startapp', help='Generate application template')
@click.option('-n', '--name', type=str, help='Application name', required=True)
@click.option('-d', '--dir', 'dir', type=str, help='Destination', default='./', required=False)
def startapp(name, dir):
    try:
        r = _startapp(name, dir)
    except Exception as e:
        logger.error('startapp failed: {}'.format(e))
        click.echo('startapp failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _startapp(name, dir):
    destination = Path(dir, name)
    if destination.exists():
        raise Exception("'{}' already exists".format(destination.absolute()))
    destination.mkdir(parents=True, exist_ok=False)

    template_suffix = "-tpl"
    template_dir = Path(abejacli.__path__[0], 'template')

    for root, dirs, files in os.walk(template_dir):
        for dirname in dirs[:]:
            if dirname.startswith('.') or dirname == '__pycache__':
                dirs.remove(dirname)

        for filename in files:
            if not filename.endswith(template_suffix):
                # Ignore some files as they cause various breakages.
                continue
            old_path = Path(root, filename)
            new_path = Path(destination, filename)
            if str(new_path).endswith(template_suffix):
                new_path = Path(str(new_path)[:-len(template_suffix)])

            if new_path.exists():
                raise Exception("{} already exists, overlaying a "
                                "project into an existing directory "
                                "won't replace conflicting files".format(new_path))

            with old_path.open(mode='r', encoding='utf-8') as template_file:
                content = template_file.read()
            with new_path.open(mode='w', encoding='utf-8') as new_file:
                new_file.write(content)

            try:
                shutil.copymode(str(old_path), str(new_path))
                _make_writeable(str(new_path))
            except OSError:
                click.secho(
                    "[error] Notice: Couldn't set permission bits on {}. You're "
                    "probably using an uncommon filesystem setup. No "
                    "problem.".format(new_path),
                    err=True, fg='red')

    return {'message': '"{}" application is successfully generated.'.format(name)}


def _make_writeable(filename):
    """
    Make sure that the file is writeable.
    Useful if our source is read-only.
    """
    if not os.access(filename, os.W_OK):
        st = os.stat(filename)
        new_permissions = stat.S_IMODE(st.st_mode) | stat.S_IWUSR
        os.chmod(filename, new_permissions)
