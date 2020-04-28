import json
import os
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import click
import requests
from click.exceptions import MissingParameter
from pygments import formatters, highlight, lexers
from pygments.styles import get_style_by_name

from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.exceptions import ConfigFileNotFoundError
from abejacli.session import api_get
from abejacli.training import TrainingConfig


def json_output_formatter(parsed_json):
    """
    Applies syntax highlighting to output
    :params parsed_json: (dict) JSON response requests response.json()
    :returns: (str) syntax highlighted text
    """
    formatted_json = json.dumps(
        parsed_json, sort_keys=True,
        ensure_ascii=False, indent=4)
    output_style = get_style_by_name('emacs')
    colorful_json = highlight(
        formatted_json, lexers.JsonLexer(),
        formatters.Terminal256Formatter(style=output_style))
    return colorful_json


def progress_status(block_num, block_size, total_size):
    if block_size > total_size:
        sys.stdout.write("read %d KB\n" % total_size / 1024)
        return

    if total_size > 0:
        percent = block_num * block_size * 1e2 / total_size
        sys.stdout.write(" %.2f %% ( %d KB )\r"
                         % (percent, total_size / 1024))
        if (block_num * block_size) >= total_size:
            sys.stdout.write("\n")
    else:
        sys.stdout.write("read %d KB\n" %
                         ((block_num * block_size) * 1e2 / 1024,))


def add_files_to_archive(tar_file, root_path, exclude_paths):
    for path in root_path.iterdir():
        add = True
        for exclude_path in exclude_paths:
            if path.samefile(exclude_path):
                add = False
                break
        if add:
            tar_file.add(str(path), arcname=str(path), recursive=False)
            if path.is_dir():
                add_files_to_archive(tar_file, path, exclude_paths)


def training_model_archive(filepath):
    """
    Create zip archive file for training model.
    :param filepath:
    :return: temporary archive file
    """
    if zipfile.is_zipfile(filepath):
        return open(filepath, 'rb')
    tmp_file = tempfile.NamedTemporaryFile(suffix='.zip')
    with zipfile.ZipFile(tmp_file.name, 'w', compression=zipfile.ZIP_DEFLATED) as new_zip:
        new_zip.write(filepath)
    tmp_file.seek(0)
    return tmp_file


def version_archive(name, exclude_filenames=None):
    """
    Create .tar.gz archive file for current directory excluding .git
    Set model name as archive name prefix
    :param: name
    :return: temporary archive file
    """

    root_dir = Path(os.curdir)
    if exclude_filenames is None:
        exclude_filenames = []
    exclude_paths = [Path(x) for x in exclude_filenames]
    exclude_paths = [x for x in exclude_paths if x.exists()]
    tmp_file = tempfile.NamedTemporaryFile(
        prefix=name, suffix='.tar.gz', delete=False)
    with tarfile.open(fileobj=tmp_file, mode="w:gz") as tar:
        add_files_to_archive(tar, root_dir, exclude_paths)
    tmp_file.seek(0)
    return tmp_file


def get_organization_id() -> Optional[str]:
    try:
        r = api_get(ORGANIZATION_ENDPOINT)
        return r.get('id')
    except requests.exceptions.HTTPError as e:
        if 400 <= e.response.status_code < 500:
            # better to let users to know something wrong with api.
            click.secho(
                '[error] something wrong with credential setting.', err=True, fg='red')
        else:
            # better to let users to know something wrong with api.
            click.secho(
                '[error] something wrong with API, please try later.', err=True, fg='red')
        return None


def convert_to_local_image_name(image: str) -> str:
    """NOTE: get available image name
    For example, `abeja-inc/all-cpu:19.04` locates inside Platform.
    and cannot access it from outside of Platform.
    Therefore let use same images in DockerHub which name starts with `abeja/`.

    """
    if image.startswith('abeja-inc/'):
        return image.replace('abeja-inc/', 'abeja/', 1)
    return image


def __try_get_organization_id(ctx, param, value):
    """NOTE: currently ~/.abeja/config does not have `organization_id`
    therefore get it via API.
    Ideally, `organization_id` is included in ~/.abeja/config and remove this method.

    Raises:
        - MissingParameter: failed to get `organization_id` via API
    """
    if value is None:
        organization_id = get_organization_id()
        if organization_id is None:
            raise MissingParameter(ctx=ctx, param=param)
        return organization_id
    return value


def __get_job_definition_name(job_definition_name: str, training_config: TrainingConfig) -> str:
    if job_definition_name:
        return job_definition_name
    else:
        config_data = training_config.read(training_config.default_schema)
        if 'name' in config_data:
            return config_data['name']
        else:
            click.echo(
                'Please specify job-definition-name or set config file.'
            )
            raise ConfigFileNotFoundError('configuration file not found')
