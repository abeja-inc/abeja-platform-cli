import json
import os
import sys
import urllib
from io import StringIO
from operator import itemgetter
from typing import Dict, Optional

import click
import click_config_file

from abejacli.click_custom import (
    DATASET_PARAM_STR,
    ENVIRONMENT_STR,
    USER_PARAM_STR,
    VOLUME_PARAM_STR,
    convert_to_local_image_callback
)
from abejacli.common import (
    __get_job_definition_name,
    __try_get_organization_id,
    json_output_formatter,
    progress_status,
    training_model_archive,
    version_archive
)
from abejacli.config import (
    ABEJA_PLATFORM_TOKEN,
    ABEJA_PLATFORM_USER_ID,
    CONFIG,
    DEFAULT_EXCLUDE_FILES,
    ERROR_EXITCODE,
    ORGANIZATION_ENDPOINT,
    SUCCESS_EXITCODE
)
from abejacli.docker.commands.run import build_volumes
from abejacli.exceptions import (
    ConfigFileNotFoundError,
    InvalidConfigException,
    ResourceNotFound
)
from abejacli.logger import get_logger
from abejacli.session import api_get, api_get_data, api_patch, api_post
from abejacli.training import (
    CONFIGFILE_NAME,
    TrainingConfig,
    is_valid_image_and_handler_pair,
    read_training_config
)
from abejacli.training.jobs import (
    TrainingJobDebugRun,
    TrainingJobLocalContainerRun
)

logger = get_logger()

training_config = TrainingConfig()


@click.group(help='Training operation commands')
@click.pass_context
def training(ctx):
    if not CONFIG:
        click.echo(
            "[error] there is no configuration, execute 'abeja config init'")
        ctx.abort()
        return


@training.command(name='init', help='Initialize training with training definition name')
@click.argument('name', required=True)
def initialize_training(name):
    try:
        training_config.write(name)
    except Exception as e:
        logger.error('training initialization failed: {}'.format(e))
        click.echo('training initialization failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo('training initialized')


# ---------------------------------------------------
# job definition
# ---------------------------------------------------
@training.command(name='create-job-definition', help='Create training job definition')
@click.option('-n', '--name', 'name', type=str,
              help='Training job definition name',
              required=False, default=None)
def create_job_definition(name):
    try:
        name = __get_job_definition_name(name, training_config)
        params = {
            "name": name
        }
        url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
        json_data = json.dumps(params)
        r = api_post(url, json_data)
    except ConfigFileNotFoundError:
        click.echo('training configuration file does not exists.')
        logger.error('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create job definition aborted:{}'.format(e))
        click.echo('create job definition aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='describe-job-definitions',
                  help='Gets information of job definition. Lists definitions if job-definition-name is not give')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--include-archived', 'include_archived', is_flag=True,
              help="Includes archived job definitions.")
@click.option('-l', '--limit', 'limit', type=int,
              help='Number of pagings', default=None, required=False)
@click.option('-o', '--offset', 'offset', type=int,
              help='Paging start index', default=None, required=False)
def describe_job_definitions(job_definition_name, include_archived, limit, offset):
    params = {}
    if job_definition_name is None:
        url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
        params["filter_archived"] = 'include_archived' if include_archived else 'exclude_archived'
        if limit:
            params['limit'] = limit
        if offset:
            params["offset"] = offset
    else:
        url = "{}/training/definitions/{}".format(ORGANIZATION_ENDPOINT, job_definition_name)
    try:
        r = api_get_data(url, params)
    except Exception as e:
        logger.error('create job definition aborted:{}'.format(e))
        click.echo('create job definition aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


# ---------------------------------------------------
# notebook
# ---------------------------------------------------
@training.command(name='create-notebook', help='Create Jupyter Notebook/Lab.')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-t', '--notebook-type', type=str, default='notebook', required=False,
              help='Jupyter type. Choose from "notebook" or "lab". Default is "notebook".')
@click.option('--instance-type', type=str, required=False,
              help='Instance Type of the machine where notebook is started. '
                   'By default, cpu-1 and gpu-1 is used for all-cpu and all-gpu images respectively.')
@click.option('-i', '--image', 'image', type=str, required=False,
              help='Specify base image name and tag in the "name:tag" format. ex) abeja-inc/all-gpu:19.10')
@click.option('--datalake', '--datalakes', 'datalakes', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake channel ID for premount.')
@click.option('--bucket', '--buckets', 'buckets', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake bucket ID for premount.')
@click.option('--dataset', '--datasets', 'datasets', type=DATASET_PARAM_STR,
              help='[Alpha stage option] Dataset ID for premount.', default=None,
              required=False, multiple=True)
def create_notebook(job_definition_name, notebook_type, instance_type, image, datalakes, buckets, datasets):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        config_data = training_config.read(training_config.create_notebook_schema)

        image = image or config_data.get('image')
        if not image:
            raise InvalidConfigException('need to specify image')

        payload = {
            'image': image,
            'notebook_type': notebook_type
        }

        instance_type = instance_type or config_data.get('instance_type')
        if instance_type is not None:
            payload['instance_type'] = instance_type
        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)
        if datasets:
            payload['datasets'] = dict(datasets)

        url = "{}/training/definitions/{}/notebooks".format(
            ORGANIZATION_ENDPOINT, name)

        r = api_post(url, json.dumps(payload))
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create notebook aborted: {}'.format(e))
        click.echo('create notebook aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='start-notebook', help='Start an existing Jupyter Notebook/Lab.')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-n', '--notebook_id', '--notebook-id', 'notebook_id', type=str, help='notebook id', required=True)
@click.option('-t', '--notebook-type', type=str, required=False,
              help='Jupyter type. Choose from "notebook" or "lab".')
@click.option('--datalake', '--datalakes', 'datalakes', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake channel ID for premount.')
@click.option('--bucket', '--buckets', 'buckets', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake bucket ID for premount.')
@click.option('--dataset', '--datasets', 'datasets', type=DATASET_PARAM_STR,
              help='[Alpha stage option] Dataset ID for premount.', default=None,
              required=False, multiple=True)
def start_notebook(job_definition_name, notebook_id, notebook_type, datalakes, buckets, datasets):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)

        payload = dict()
        if notebook_type is not None:
            payload['notebook_type'] = notebook_type
        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)
        if datasets:
            payload['datasets'] = dict(datasets)

        url = "{}/training/definitions/{}/notebooks/{}/start".format(
            ORGANIZATION_ENDPOINT, name, notebook_id)

        r = api_post(url, json.dumps(payload))
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create notebook aborted: {}'.format(e))
        click.echo('create notebook aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


# ---------------------------------------------------
# job definition version
# ---------------------------------------------------
@training.command(name='create-version', help='Create a version of Training Job Definition.')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-h', '--handler', 'handler', type=str, help='Training handler', required=False)
@click.option('-i', '--image', 'image', type=str, required=False,
              help='Specify base image name and tag in the "name:tag" format. ex) abeja-inc/all-gpu:19.10')
@click.option('-d', '--description', type=str, required=False,
              help='Description for the training job, which must be less than or equal to 256 characters.')
@click.option('-e', '--environment', type=ENVIRONMENT_STR, default=None, required=False, multiple=True,
              help='Environment variables, ex. BATCH_SIZE:32')
@click.option('--exclude', type=str, help='Specify the file/dir to exclude from create-version.',
              required=False, multiple=True)
@click.option('--datalake', '--datalakes', 'datalakes', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake channel ID for premount.')
@click.option('--bucket', '--buckets', 'buckets', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake bucket ID for premount.')
@click.option('--dataset', '--datasets', 'datasets', type=DATASET_PARAM_STR,
              help='Datasets name', default=None,
              required=False, multiple=True)
@click.option('--dataset-premounted', is_flag=True, type=bool, required=False,
              help='[Alpha stage option] Flag for pre-mounting datasets. Use this along with "--datasets" option.')
def create_training_version(
        job_definition_name, handler, image, description, environment, exclude,
        datalakes, buckets, datasets, dataset_premounted):
    if exclude is None:
        excludes = []
    else:
        excludes = list(exclude)

    archive = None
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        config_data = training_config.read(training_config.create_version_schema)

        handler = handler or config_data.get('handler')
        image = image or config_data.get('image')
        if not handler or not image:
            raise InvalidConfigException('need to specify handler and image both')

        # FIXME: For "20.02" trial.
        if not is_valid_image_and_handler_pair(image, handler):
            raise InvalidConfigException('handler must be "file:method" format.')

        payload = {
            'handler': handler,
            'image': image
        }

        if description is not None:
            payload['description'] = description

        environment = {**dict(config_data.get('environment', {})), **dict(environment)}
        if environment:
            payload['environment'] = environment

        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)

        _datasets = dict(config_data.get('datasets', {}))
        datasets = {**_datasets, **dict(datasets)}
        if datasets:
            payload['datasets'] = datasets
            payload['dataset_premounted'] = dataset_premounted or False

        user_exclude_files = config_data.pop('ignores', [])
        exclude_files = set(user_exclude_files + DEFAULT_EXCLUDE_FILES + excludes)

        archive = version_archive(name, exclude_files)

        url = "{}/training/definitions/{}/versions".format(
            ORGANIZATION_ENDPOINT, name)

        r = _create_training_version(url, payload, archive)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except FileNotFoundError:
        logger.error('failed to archive the current directory.')
        click.echo('failed to archive the current directory.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training version aborted: {}'.format(e))
        click.echo('create training version aborted.')
        sys.exit(ERROR_EXITCODE)
    finally:
        if archive and os.path.exists(archive.name):
            archive.close()
            os.unlink(archive.name)
    click.echo(json_output_formatter(r))


def _create_training_version(url: str, payload: Dict[str, str], archive):
    with open(archive.name, 'rb') as archive_file:
        json_params = json.dumps(payload)
        files = {
            'source_code': ('archive.tar.gz', archive_file, 'application/tar+gzip'),
            'parameters': ('params.json', StringIO(json_params), 'application/json'),
        }
        return api_post(url, files=files)


@training.command(name='create-version-from-git',
                  help='Create a version of Training Job Definition from GitHub repository.')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--git-url', type=str, required=True,
              help='GitHub URL, which must start with "https://".')
@click.option('--git-branch', type=str, required=False,
              help='GitHub branch. Default "master"')
@click.option('-h', '--handler', 'handler', type=str, help='Training handler', required=False)
@click.option('-i', '--image', 'image', type=str, required=False,
              help='Specify base image name and tag in the "name:tag" format. ex) abeja-inc/all-gpu:19.10')
@click.option('-d', '--description', type=str, required=False,
              help='Description for the training job, which must be less than or equal to 256 characters.')
@click.option('-e', '--environment', type=ENVIRONMENT_STR, default=None, required=False, multiple=True,
              help='Environment variables, ex. BATCH_SIZE:32')
@click.option('--datalake', '--datalakes', 'datalakes', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake channel ID for premount.')
@click.option('--bucket', '--buckets', 'buckets', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake bucket ID for premount.')
@click.option('--dataset', '--datasets', 'datasets', type=DATASET_PARAM_STR,
              help='Datasets name', default=None,
              required=False, multiple=True)
@click.option('--dataset-premounted', is_flag=True, type=bool, required=False,
              help='[Alpha stage option] Flag for pre-mounting datasets. Use this along with "--datasets" option.')
def create_training_version_from_git(
        job_definition_name, git_url, git_branch, handler, image, description, environment,
        datalakes, buckets, datasets, dataset_premounted):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        config_data = training_config.read(training_config.create_version_schema)

        handler = handler or config_data.get('handler')
        image = image or config_data.get('image')
        if not handler or not image:
            raise InvalidConfigException('need to specify handler and image both')

        # FIXME: For "20.02" trial.
        if not is_valid_image_and_handler_pair(image, handler):
            raise InvalidConfigException('handler must be "file:method" format.')

        payload = {
            'git_url': git_url,
            'handler': handler,
            'image': image
        }

        if git_branch is not None:
            payload['git_branch'] = git_branch

        if description is not None:
            payload['description'] = description

        environment = {**dict(config_data.get('environment', {})), **dict(environment)}
        if environment:
            payload['environment'] = environment

        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)

        _datasets = dict(config_data.get('datasets', {}))
        datasets = {**_datasets, **dict(datasets)}
        if datasets:
            payload['datasets'] = datasets
            payload['dataset_premounted'] = dataset_premounted or False

        url = "{}/training/definitions/{}/git/versions".format(
            ORGANIZATION_ENDPOINT, name)

        r = api_post(url, json.dumps(payload))
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training version aborted: {}'.format(e))
        click.echo('create training version aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='update-version', help='Update a description of Training Job Definition Version.')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-v', '--version', type=str, required=False,
              help='Job definition version. By default, latest version is used')
@click.option('-d', '--description', type=str, required=False,
              help='Description for the training job, which must be less than or equal to 256 characters.')
def update_training_version(job_definition_name, version, description):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('update job definition version operation aborted: {}'.format(e))
        click.echo('update job definition version operation aborted.')
        sys.exit(ERROR_EXITCODE)

    params = {}
    if description is not None:
        params['description'] = description

    try:
        if version is None:
            try:
                version = _get_latest_training_version(name)
            except ResourceNotFound:
                logger.error('there is no available training versions.')
                click.echo(
                    'there is no available training versions. please create training version first.')
                sys.exit(ERROR_EXITCODE)

        url = "{}/training/definitions/{}/versions/{}".format(
            ORGANIZATION_ENDPOINT, name, version)
        r = api_patch(url, json.dumps(params))
        click.echo(json_output_formatter(r))
    except Exception as e:
        logger.error('update job definition version operation aborted: {}'.format(e))
        click.echo('update job definition version operation aborted.')
        sys.exit(ERROR_EXITCODE)


@training.command(name='describe-versions', help='Describe Training Job Definition Versions')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--include-archived', 'include_archived', is_flag=True,
              help="Includes archived training versions.")
def describe_training_versions(job_definition_name, include_archived):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _describe_training_versions(name, include_archived)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('describe job operation aborted: {}'.format(e))
        click.echo('describe job operation aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_training_versions(name: str, include_archived: Optional[bool] = None):
    url = "{}/training/definitions/{}/versions".format(
        ORGANIZATION_ENDPOINT, name)
    url = '{}?filter_archived=include_archived'.format(
        url) if include_archived else '{}?filter_archived=exclude_archived'.format(url)
    return api_get(url)


def _get_latest_training_version(name: str):
    res = _describe_training_versions(name)
    versions = res.get('entries', [])
    # sort by job_definition_version
    sorted_versions = sorted(versions, key=itemgetter(
        'job_definition_version'), reverse=True)
    if not sorted_versions:
        raise ResourceNotFound
    return sorted_versions[0]['job_definition_version']


# ---------------------------------------------------
# job
# ---------------------------------------------------
@training.command(name='create-job', help='Create training job')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-v', '--version', type=str, required=False,
              help='Job definition version. By default, latest version is used')
@click.option('-e', '--environment', type=ENVIRONMENT_STR, default=None, required=False, multiple=True,
              help='Environment variables, ex. BATCH_SIZE:32')
@click.option('-p', '--params', type=USER_PARAM_STR, default=None, required=False, multiple=True,
              help='[DEPRECATED] User parameters, ex. BATCH_SIZE:32. '
                   'If environment is specified, this will be ignored. '
                   'Please use `--environment` option. ')
@click.option('--instance-type', type=str, required=False,
              help='Instance Type of the machine where training job is executed. '
                   'By default, cpu-1 and gpu-1 is used for all-cpu and all-gpu images respectively.')
@click.option('-d', '--description', type=str, required=False,
              help='Description for the training job, which must be less than or equal to 256 characters.')
@click.option('--dataset', '--datasets', 'datasets', type=DATASET_PARAM_STR,
              help='Datasets name', default=None,
              required=False, multiple=True)
@click.option('--datalake', '--datalakes', 'datalakes', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake channel ID for premount.')
@click.option('--bucket', '--buckets', 'buckets', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake bucket ID for premount.')
@click.option('--dataset-premounted', is_flag=True, type=bool, required=False,
              help='[Alpha stage option] Flag for pre-mounting datasets. Use this along with "--datasets" option.')
@click.option('--export-log', is_flag=True, type=bool, required=False,
              help='Include the log in the model file. This feature is only available with 19.04 or later images.')
def create_training_job(job_definition_name, version, environment, params, instance_type, description,
                        datasets, datalakes, buckets, dataset_premounted, export_log):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        config_data = training_config.read(training_config.create_job_schema)
        if version is None:
            try:
                version = _get_latest_training_version(name)
            except ResourceNotFound:
                logger.error('there is no available training versions.')
                click.echo(
                    'there is no available training versions. please create training version first.')
                sys.exit(ERROR_EXITCODE)

        url = "{}/training/definitions/{}/versions/{}/jobs".format(
            ORGANIZATION_ENDPOINT, name, version)

        environment = dict(environment) or dict(params)
        env_vars = {**dict(config_data.get('environment', {})), **environment}

        _datasets = dict(config_data.get('datasets', {}))
        datasets = {**_datasets, **dict(datasets)}

        data = {}
        if env_vars:
            data['environment'] = env_vars
        instance_type = instance_type or config_data.get('instance_type')
        if instance_type is not None:
            data['instance_type'] = instance_type
        if datasets:
            data['datasets'] = datasets
            data['dataset_premounted'] = dataset_premounted or False
        if description is not None:
            data['description'] = description
        if datalakes:
            data['datalakes'] = list(datalakes)
        if buckets:
            data['buckets'] = list(buckets)
        if export_log is not None:
            data['export_log'] = export_log

        r = api_post(url, json.dumps(data))
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training job aborted: {}'.format(e))
        click.echo('create training job aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='describe-jobs', help='Show training job list for a specific training definition name')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--include-archived', 'include_archived', is_flag=True,
              help="Includes archived training jobs .")
@click.option('-l', '--limit', 'limit', type=int,
              help='Number of pagings', default=None, required=False)
@click.option('-o', '--offset', 'offset', type=int,
              help='Paging start index', default=None, required=False)
def describe_jobs(job_definition_name, include_archived, limit, offset):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        url = "{}/training/definitions/{}/jobs".format(ORGANIZATION_ENDPOINT, name)
        params = {}
        params["filter_archived"] = 'include_archived' if include_archived else 'exclude_archived'
        if limit:
            params['limit'] = limit
        if offset:
            params["offset"] = offset
        r = api_get_data(url, params)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('describe job operation aborted: {}'.format(e))
        click.echo('describe job operation aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='download-training-result', help='Download training result(artifact)')
@click.option('-jd', '--job_definisin_id', '--job-definisin-id', 'job_definisin_id', type=str,
              help='job definition id', required=True)
@click.option('-j', '--job_id', '--job-id', 'job_id', type=str, help='job id', required=True)
def download_jobs_result(job_definisin_id, job_id):
    try:
        r = _download_result(job_definisin_id, job_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo('Downloaded a file {}.'.format(r))


def _download_result(job_definition_id, job_id):

    url = '{}/training/definitions/{}/jobs/{}/result'.format(
        ORGANIZATION_ENDPOINT, job_definition_id, job_id)
    r = api_get(url)
    download_uri = r['artifacts']['complete']['uri']
    file_name = os.path.basename(download_uri[:download_uri.find('?')])
    target_file_name = '{}_{}_{}'.format(job_definition_id, job_id, file_name)
    urllib.request.urlretrieve(
        download_uri, target_file_name, progress_status)

    return target_file_name


def __training_config_provider(yaml_path, _cmd_name):
    try:
        config_data = read_training_config(yaml_path)
        if not config_data:
            return {}

        # DEPRECATED: datasets will be removed
        datasets = [
            '{}:{}'.format(k, v)
            for k, v in config_data.pop('datasets', {}).items()
        ]
        config_data['datasets'] = datasets

        environment = []
        for k, v in config_data.pop('environment', config_data.pop('params', {})).items():
            if v is None:
                v = ''
            environment.append('{}:{}'.format(k, v))
        if 'params' in config_data:
            config_data.pop('params', None)
        config_data['environment'] = environment
        return config_data
    except ConfigFileNotFoundError:
        return {}
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('something wrong occurred when loading training configuration file: {}'.format(e))
        click.echo('something wrong occurred when loading training configuration file.')
        sys.exit(ERROR_EXITCODE)


@training.command(name='archive-job', help='Archive training job')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--job-id', '--job_id', type=str, required=True,
              help='Training Job identifier')
def archive_job(job_definition_name, job_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        url = "{}/training/definitions/{}/jobs/{}/archive".format(
            ORGANIZATION_ENDPOINT, name, job_id)
        r = api_post(url)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training job aborted: {}'.format(e))
        click.echo('create training job aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='unarchive-job', help='Unarchive training job')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--job-id', '--job_id', type=str, required=True,
              help='Training Job identifier')
def unarchive_job(job_definition_name, job_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        url = "{}/training/definitions/{}/jobs/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, name, job_id)
        r = api_post(url)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training job aborted: {}'.format(e))
        click.echo('create training job aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='archive-version', help='Archive training job definition version')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-v', '--version-id', '--version_id', type=str, required=True,
              help='Training job version identifier')
def archive_version(job_definition_name, version_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        url = "{}/training/definitions/{}/versions/{}/archive".format(
            ORGANIZATION_ENDPOINT, name, version_id)
        r = api_post(url)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training job aborted: {}'.format(e))
        click.echo('create training job aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='unarchive-version', help='Unarchive training job definition version')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-v', '--version-id', '--version_id', type=str, required=True,
              help='Training job version identifier')
def unarchive_version(job_definition_name, version_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        url = "{}/training/definitions/{}/versions/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, name, version_id)
        r = api_post(url)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training job aborted: {}'.format(e))
        click.echo('create training job aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@training.command(name='stop-job', help='Stop training job')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--job-id', '--job_id', type=str, required=True,
              help='Training Job identifier')
def stop_training_job(job_definition_name, job_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        url = "{}/training/definitions/{}/jobs/{}/stop".format(
            ORGANIZATION_ENDPOINT, name, job_id)
        r = api_post(url, json.dumps({}))
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('stop training job aborted: {}'.format(e))
        click.echo('stop training job aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


# ---------------------------------------------------
# training models
# ---------------------------------------------------
@training.command(name='describe-training-models', help='Get training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', default='all',
              required=False)
@click.option('--include-archived', 'include_archived', is_flag=True,
              help="Includes archived training models.")
def describe_training_models(job_definition_name, model_id, include_archived):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _describe_training_models(name, model_id, include_archived)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('describe_training_models operation aborted: {}'.format(e))
        click.echo('describe_training_models operation aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_training_models(job_definition_name, model_id, include_archived=None):
    url = '{}/training/definitions/{}/models'.format(ORGANIZATION_ENDPOINT, job_definition_name)
    if model_id != "all":
        url = '{}/{}'.format(url, model_id)
        r = api_get(url)
        return r

    params = {}
    params["filter_archived"] = 'include_archived' if include_archived else 'exclude_archived'
    r = api_get_data(url, params)
    return r


@training.command(name='create-training-model', help='Create training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=False, default=None)
@click.option('-f', '--filepath', 'filepath', type=str, help='Model filepath', required=True)
@click.option('-d', '--description', 'description', type=str, required=False,
              help='Description for the training model, which must be less than or equal to 256 characters.')
@click.option('--user-parameters', '--user_parameters', 'user_parameters', type=ENVIRONMENT_STR,
              help='User parameters', default=None,
              required=False, multiple=True)
def create_training_model(job_definition_name, filepath, description, user_parameters):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _create_training_model(name, filepath, description, user_parameters)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create_training_model operation aborted: {}'.format(e))
        click.echo('create_training_model operation aborted.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _create_training_model(job_definition_name, filepath, description=None, user_parameters=None):
    parameter = {}
    if description:
        parameter.update({'description': description})
    if user_parameters:
        parameter.update({'user_parameters': dict(user_parameters)})

    url = "{}/training/definitions/{}/models".format(ORGANIZATION_ENDPOINT, job_definition_name)
    try:
        model_data = training_model_archive(filepath)
        json_params = json.dumps(parameter)
        files = {
            'model_data': ('model.zip', model_data, 'application/zip'),
            'parameters': ('params.json', StringIO(json_params), 'application/json'),
        }
        r = api_post(url, files=files)
    except FileNotFoundError:
        logger.error('failed to archive the current directory.')
        click.echo('failed to archive the current directory.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('create training model aborted: {}'.format(e))
        click.echo('create training model aborted.')
        sys.exit(ERROR_EXITCODE)
    finally:
        if model_data:
            model_data.close()
    return r


@training.command(name='update-training-model', help='Update training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=False, default=None)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
@click.option('-d', '--description', 'description', type=str, required=False,
              help='Description for the training model, which must be less than or equal to 256 characters.')
def update_training_model(job_definition_name, model_id, description):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _update_training_model(name, model_id, description)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('update_training_model operation aborted: {}'.format(e))
        click.echo('update_training_model operation aborted.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _update_training_model(job_definition_name, model_id, description):
    params = {}
    if description is not None:
        params['description'] = description
    url = '{}/training/definitions/{}/models/{}'.format(ORGANIZATION_ENDPOINT, job_definition_name, model_id)
    r = api_patch(url, json.dumps(params))

    return r


@training.command(name='download-training-model', help='Download training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=False, default=None)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
def download_training_model(job_definition_name, model_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _download_training_model(name, model_id)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('download_training_model operation aborted: {}'.format(e))
        click.echo('download_training_model operation aborted.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _download_training_model(job_definition_name, model_id):
    url = '{}/training/definitions/{}/models/{}/download'.format(
        ORGANIZATION_ENDPOINT, job_definition_name, model_id)
    r = api_get(url)

    return r


@training.command(name='archive-training-model', help='Archive training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=False, default=None)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
def archive_training_model(job_definition_name, model_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _archive_training_model(name, model_id)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('archive_training_model operation aborted: {}'.format(e))
        click.echo('archive_training_model operation aborted.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _archive_training_model(job_definition_name, model_id):
    url = '{}/training/definitions/{}/models/{}/archive'.format(
        ORGANIZATION_ENDPOINT, job_definition_name, model_id)
    r = api_post(url)

    return r


@training.command(name='unarchive-training-model', help='Unarchive training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=False, default=None)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
def unarchive_training_model(job_definition_name, model_id):
    try:
        name = __get_job_definition_name(job_definition_name, training_config)
        r = _unarchive_training_model(name, model_id)
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('unarchive_training_model operation aborted: {}'.format(e))
        click.echo('unarchive_training_model operation aborted.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _unarchive_training_model(job_definition_name, model_id):
    url = '{}/training/definitions/{}/models/{}/unarchive'.format(
        ORGANIZATION_ENDPOINT, job_definition_name, model_id)
    r = api_post(url)

    return r


# ---------------------------------------------------
# Run
# ---------------------------------------------------
@training.command(name='debug-local', help='Local train commands', context_settings=dict(
    ignore_unknown_options=True, allow_extra_args=True))
@click.option('-h', '--handler', 'handler', type=str, help='Training handler', required=False)
@click.option('-i', '--image', 'image', type=str, required=False,
              callback=convert_to_local_image_callback,
              help='Specify base image name and tag in the "name:tag" format. ex) abeja-inc/all-gpu:19.10')
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'this value is set as an environment variable named `ABEJA_ORGANIZATION_ID`.',
              callback=__try_get_organization_id)
@click.option('--datasets', type=DATASET_PARAM_STR, help='Datasets name', default=None,
              required=False, multiple=True)
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Environment variables', default=None,
              required=False, multiple=True)
@click.option('-v', '--volume', type=VOLUME_PARAM_STR,
              default=None, required=False, multiple=True,
              help='Volume driver options, ex) /path/source/on/host:/path/destination/on/container')
@click.option('--no-cache', '--no_cache', is_flag=True, type=bool, required=False,
              help='Not use built cache')
@click.option('--v1', is_flag=True, type=bool, help='Specify if you use old custom runtime image', default=False,
              required=False)
@click.option('--runtime', 'runtime', type=str, required=False,
              help='Runtime, equivalent to docker run `--runtime` option')
@click.option('--build-only', is_flag=True, type=bool,
              help='Build a docker image only. Not run train command.', required=False)
@click.option('-q', '--quiet', is_flag=True, type=bool, help='Suppress info logs', required=False)
@click_config_file.configuration_option(
    provider=__training_config_provider, implicit=True,
    default=CONFIGFILE_NAME,  # by setting `default`, not allow to use `click.get_app_dir`
    config_file_name=CONFIGFILE_NAME,
    help='Read Configuration from PATH. By default read from `{}`'.format(CONFIGFILE_NAME))
def debug_local(
        handler, image, organization_id, datasets, environment, volume,
        no_cache, quiet, v1, runtime=None, build_only=False):
    try:
        config_data = training_config.read(training_config.debug_schema)

        handler = handler or config_data.get('handler')
        image = image or config_data.get('image')
        if not handler or not image:
            raise InvalidConfigException('need to specify handler and image both')

        datasets = {**dict(config_data.get('datasets', {})), **dict(datasets)}

        environment = {**dict(config_data.get('environment', {})), **dict(environment)}

        volume = build_volumes(volume) if volume else {}

        with TrainingJobDebugRun(
            handler=handler, image=image, organization_id=organization_id,
            datasets=datasets, environment=environment, volume=volume, no_cache=no_cache,
            build_only=build_only, quiet=quiet, stdout=click.echo, runtime=runtime,
            platform_user_id=ABEJA_PLATFORM_USER_ID,
            platform_personal_access_token=ABEJA_PLATFORM_TOKEN, v1flag=v1
        ) as job:
            if job.build_only:
                sys.exit(SUCCESS_EXITCODE)
            job.watch()
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('debug_local operation aborted: {}'.format(e))
        click.echo('debug_local operation aborted.')
        sys.exit(ERROR_EXITCODE)


@training.command(name='train-local', help='Local train commands', context_settings=dict(
    ignore_unknown_options=True, allow_extra_args=True))
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'this value is set as an environment variable named `ABEJA_ORGANIZATION_ID`.',
              callback=__try_get_organization_id)
@click.option('--name', 'name', type=str, help='Training Job Definition Name', required=False)
@click.option('--version', 'version', type=str, help='Training Job Definition Version', required=True)
@click.option('-d', '--description', 'description', type=str, help='Training Job description', required=False)
@click.option('--datasets', type=DATASET_PARAM_STR, help='Datasets name', default=None,
              required=False, multiple=True)
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Environment variables', default=None,
              required=False, multiple=True)
@click.option('-v', '--volume', type=VOLUME_PARAM_STR,
              default=None, required=False, multiple=True,
              help='Volume driver options, ex) /path/source/on/host:/path/destination/on/container')
@click.option('--v1', is_flag=True, type=bool, help='Specify if you use old custom runtime image', default=False,
              required=False)
@click.option('--runtime', 'runtime', type=str, required=False,
              help='Runtime, equivalent to docker run `--runtime` option')
@click_config_file.configuration_option(
    provider=__training_config_provider, implicit=True,
    default=CONFIGFILE_NAME,  # by setting `default`, not allow to use `click.get_app_dir`
    config_file_name=CONFIGFILE_NAME,
    help='Read Configuration from PATH. By default read from `{}`'.format(CONFIGFILE_NAME))
def train_local(organization_id, name, version, description, datasets, environment, volume, v1, runtime=None):
    try:
        name = __get_job_definition_name(name, training_config)
        config_data = training_config.read(training_config.local_schema)

        job_definition_version = _describe_training_version(name, version)
        version_datasets = job_definition_version.get('datasets')
        if not version_datasets:
            version_datasets = {}
        version_environment = job_definition_version.get('environment')
        if not version_environment:
            version_environment = {}

        datasets = {**version_datasets, **dict(config_data.get('datasets', {})), **dict(datasets)}

        environment = {**version_environment, **dict(config_data.get('environment', {})), **dict(environment)}

        volume = build_volumes(volume) if volume else {}

        with TrainingJobLocalContainerRun(
            organization_id=organization_id, job_definition_name=name,
            job_definition_version=version, description=description,
            datasets=datasets, environment=environment, volume=volume, runtime=runtime,
            stdout=click.echo, platform_user_id=ABEJA_PLATFORM_USER_ID,
            platform_personal_access_token=ABEJA_PLATFORM_TOKEN, v1flag=v1
        ) as job:
            job.watch()
    except ConfigFileNotFoundError:
        logger.error('training configuration file does not exists.')
        click.echo('training configuration file does not exists.')
        sys.exit(ERROR_EXITCODE)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('train_local operation aborted: {}'.format(e))
        click.echo('train_local operation aborted.')
        sys.exit(ERROR_EXITCODE)


def _describe_training_version(name: str, job_definition_version: str):
    url = "{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, name, job_definition_version)
    return api_get(url)
