import json
from io import StringIO
from operator import itemgetter
import os
import sys
from typing import Dict, Optional
import urllib

import click
import click_config_file

from abejacli.click_custom import (DATASET_PARAM_STR, ENVIRONMENT_STR, USER_PARAM_STR, VOLUME_PARAM_STR)
from abejacli.click_custom import convert_to_local_image_callback
from abejacli.common import json_output_formatter, progress_status, version_archive, training_model_archive
from abejacli.common import __try_get_organization_id
from abejacli.config import (ABEJA_PLATFORM_TOKEN, ABEJA_PLATFORM_USER_ID,
                             CONFIG, DEFAULT_EXCLUDE_FILES,
                             ERROR_EXITCODE, ORGANIZATION_ENDPOINT,
                             SUCCESS_EXITCODE)
from abejacli.exceptions import ConfigFileNotFoundError, InvalidConfigException, ResourceNotFound
from abejacli.docker.commands.run import build_volumes
from abejacli.logger import get_logger
from abejacli.session import api_get, api_post, api_patch
from abejacli.training import TrainingConfig, CONFIGFILE_NAME, read_training_config, is_valid_image_and_handler_pair
from abejacli.training.jobs import TrainingJobDebugRun
from abejacli.training.jobs import TrainingJobLocalContainerRun

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
def create_job_definition():
    try:
        config_data = training_config.read(training_config.default_schema)
        params = {
            "name": config_data['name']
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
def describe_job_definitions(job_definition_name, include_archived):
    if job_definition_name is None:
        url = "{}/training/definitions".format(ORGANIZATION_ENDPOINT)
        url = '{}?filter_archived=include_archived'.format(
            url) if include_archived else '{}?filter_archived=exclude_archived'.format(url)
    else:
        url = "{}/training/definitions/{}".format(ORGANIZATION_ENDPOINT, job_definition_name)
    try:
        r = api_get(url)
    except Exception as e:
        logger.error('create job definition aborted:{}'.format(e))
        click.echo('create job definition aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))

# ---------------------------------------------------
# notebook
# ---------------------------------------------------


@training.command(name='create-notebook')
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
def create_notebook(notebook_type, instance_type, image, datalakes, buckets, datasets):
    try:
        params = training_config.read(training_config.create_notebook_schema)

        image = image or params.get('image')
        if not image:
            raise InvalidConfigException('need to specify image')

        payload = {
            'image': image,
            'notebook_type': notebook_type
        }
        if instance_type is not None:
            payload['instance_type'] = instance_type
        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)
        if datasets:
            payload['datasets'] = dict(datasets)

        url = "{}/training/definitions/{}/notebooks".format(
            ORGANIZATION_ENDPOINT, params['name'])

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


@training.command(name='start-notebook')
@click.option('-n', '--notebook_id', '--notebook-id', 'notebook_id', type=str, help='notebook id', required=True)
@click.option('-t', '--notebook-type', type=str, required=False,
              help='Jupyter type. Choose from "notebook" or "lab".')
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
def start_notebook(notebook_id, notebook_type, instance_type, image, datalakes, buckets, datasets):
    try:
        params = training_config.read(training_config.create_notebook_schema)

        image = image or params.get('image')
        if not image:
            raise InvalidConfigException('need to specify image')

        payload = {
            'image': image
        }
        if notebook_type is not None:
            payload['notebook_type'] = notebook_type
        if instance_type is not None:
            payload['instance_type'] = instance_type
        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)
        if datasets:
            payload['datasets'] = dict(datasets)

        url = "{}/training/definitions/{}/notebooks/{}/start".format(
            ORGANIZATION_ENDPOINT, params['name'], notebook_id)

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
@training.command(name='create-version')
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
def create_training_version(description, environment, exclude, datalakes, buckets):
    if exclude is None:
        excludes = []
    else:
        excludes = list(exclude)

    archive = None
    try:
        params = dict(training_config.read(training_config.create_version_schema))

        handler = params.get('handler')
        image = params.get('image')
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

        environment = {**params.get('environment', {}), **dict(environment)}
        if environment:
            payload['environment'] = environment

        if datalakes:
            payload['datalakes'] = list(datalakes)
        if buckets:
            payload['buckets'] = list(buckets)

        user_exclude_files = params.pop('ignores', [])
        exclude_files = set(user_exclude_files + DEFAULT_EXCLUDE_FILES + excludes)

        archive = version_archive(params['name'], exclude_files)

        url = "{}/training/definitions/{}/versions".format(
            ORGANIZATION_ENDPOINT, params['name'])

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


@training.command(name='update-version')
@click.option('-v', '--version', type=str, required=False,
              help='Job definition version. By default, latest version is used')
@click.option('-d', '--description', type=str, required=False,
              help='Description for the training job, which must be less than or equal to 256 characters.')
def update_training_version(version, description):
    try:
        config = training_config.read(training_config.create_version_schema)
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
                version = _get_latest_training_version(config['name'])
            except ResourceNotFound:
                logger.error('there is no available training versions.')
                click.echo(
                    'there is no available training versions. please create training version first.')
                sys.exit(ERROR_EXITCODE)

        url = "{}/training/definitions/{}/versions/{}".format(
            ORGANIZATION_ENDPOINT, config['name'], version)
        r = api_patch(url, json.dumps(params))
        click.echo(json_output_formatter(r))
    except Exception as e:
        logger.error('update job definition version operation aborted: {}'.format(e))
        click.echo('update job definition version operation aborted.')
        sys.exit(ERROR_EXITCODE)


@training.command(name='describe-versions')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name',
              required=False, default=None)
@click.option('--include-archived', 'include_archived', is_flag=True,
              help="Includes archived training versions.")
def describe_training_versions(job_definition_name, include_archived):
    if job_definition_name:
        name = job_definition_name
    else:
        try:
            config_data = training_config.read(training_config.default_schema)
        except ConfigFileNotFoundError:
            click.echo(
                'Trainining config file not found. Please specify job-definition-name or set training config file.'
            )
            sys.exit(ERROR_EXITCODE)
        name = config_data['name']
    try:
        r = _describe_training_versions(name, include_archived)
    except InvalidConfigException as e:
        logger.error('invalid training configuration file: {}'.format(e))
        click.echo('invalid training configuration file.')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        logger.error('describe job operation aborted: {}'.format(e))
        click.echo('describe job operation aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_training_versions(name: str, include_archived: Optional[bool]=None):
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
@click.option('--description', type=str, required=False,
              help='Description for the training job, which must be less than or equal to 256 characters.')
@click.option('-d', '--dataset', '--datasets', 'datasets', type=DATASET_PARAM_STR,
              help='Datasets name', default=None,
              required=False, multiple=True)
@click.option('--datalake', '--datalakes', 'datalakes', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake channel ID for premount.')
@click.option('--bucket', '--buckets', 'buckets', type=str, default=None, required=False, multiple=True,
              help='[Alpha stage option] Datalake bucket ID for premount.')
@click.option('--dataset-premounted', is_flag=True, type=bool, required=False,
              help='[Alpha stage option] Flag for pre-mounting datasets. Use this along with "--datasets" option.')
def create_training_job(version, environment, params, instance_type, description,
                        datasets, datalakes, buckets, dataset_premounted):
    try:
        config_data = training_config.read(training_config.default_schema)
        if version is None:
            try:
                version = _get_latest_training_version(config_data['name'])
            except ResourceNotFound:
                logger.error('there is no available training versions.')
                click.echo(
                    'there is no available training versions. please create training version first.')
                sys.exit(ERROR_EXITCODE)

        url = "{}/training/definitions/{}/versions/{}/jobs".format(
            ORGANIZATION_ENDPOINT, config_data['name'], version)

        environment = dict(environment) or dict(params)
        env_vars = {**dict(config_data.get('environment', {})), **environment}

        _datasets = dict(config_data.get('datasets', {}))
        datasets = {**_datasets, **dict(datasets)}

        data = {}
        if env_vars:
            data['environment'] = env_vars
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
def describe_jobs(job_definition_name, include_archived):
    if job_definition_name:
        name = job_definition_name
    else:
        try:
            config_data = training_config.read(training_config.default_schema)
        except ConfigFileNotFoundError:
            click.echo(
                'Trainining config file not found. Please specify job-definition-name or set training config file.'
            )
            sys.exit(ERROR_EXITCODE)
        name = config_data['name']
    try:
        url = "{}/training/definitions/{}/jobs".format(ORGANIZATION_ENDPOINT, name)
        url = '{}?filter_archived=include_archived'.format(
            url) if include_archived else '{}?filter_archived=exclude_archived'.format(url)
        r = api_get(url)
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
        config = read_training_config(yaml_path)
        if not config:
            return {}

        # DEPRECATED: datasets will be removed
        datasets = [
            '{}:{}'.format(k, v)
            for k, v in config.pop('datasets', {}).items()
        ]
        config['datasets'] = datasets

        environment = []
        for k, v in config.pop('environment', config.pop('params', {})).items():
            if v is None:
                v = ''
            environment.append('{}:{}'.format(k, v))
        if 'params' in config:
            config.pop('params', None)
        config['environment'] = environment
        return config
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
@click.option('--job-id', '--job_id', type=str, required=True,
              help='Training Job identifier')
def archive_job(job_id):
    try:
        config_data = training_config.read(training_config.default_schema)
        url = "{}/training/definitions/{}/jobs/{}/archive".format(
            ORGANIZATION_ENDPOINT, config_data['name'], job_id)
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
@click.option('--job-id', '--job_id', type=str, required=True,
              help='Training Job identifier')
def unarchive_job(job_id):
    try:
        config_data = training_config.read(training_config.default_schema)
        url = "{}/training/definitions/{}/jobs/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, config_data['name'], job_id)
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
@click.option('-v', '--version-id', '--version_id', type=str, required=True,
              help='Training job version identifier')
def archive_version(version_id):
    try:
        config_data = training_config.read(training_config.default_schema)
        url = "{}/training/definitions/{}/versions/{}/archive".format(
            ORGANIZATION_ENDPOINT, config_data['name'], version_id)
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
@click.option('-v', '--version-id', '--version_id', type=str, required=True,
              help='Training job version identifier')
def unarchive_version(version_id):
    try:
        config_data = training_config.read(training_config.default_schema)
        url = "{}/training/definitions/{}/versions/{}/unarchive".format(
            ORGANIZATION_ENDPOINT, config_data['name'], version_id)
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
    if job_definition_name:
        name = job_definition_name
    else:
        try:
            config_data = training_config.read(training_config.default_schema)
        except ConfigFileNotFoundError:
            click.echo(
                'Trainining config file not found. Please specify job-definition-name or set training config file.'
            )
            sys.exit(ERROR_EXITCODE)
        name = config_data['name']
    try:
        r = _describe_training_models(name, model_id, include_archived)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_training_models(job_definition_name, model_id, include_archived=None):
    url = '{}/training/definitions/{}/models'.format(ORGANIZATION_ENDPOINT, job_definition_name)
    if model_id != "all":
        url = '{}/{}'.format(url, model_id)
        r = api_get(url)
        return r

    url = '{}?filter_archived=include_archived'.format(
        url) if include_archived else '{}?filter_archived=exclude_archived'.format(url)
    r = api_get(url)
    return r


@training.command(name='create-training-model', help='Create training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=True)
@click.option('-f', '--filepath', 'filepath', type=str, help='Model filepath', required=True)
@click.option('-d', '--description', 'description', type=str, required=False,
              help='Description for the training model, which must be less than or equal to 256 characters.')
@click.option('--user-parameters', '--user_parameters', 'user_parameters', type=ENVIRONMENT_STR,
              help='User parameters', default=None,
              required=False, multiple=True)
def create_training_model(job_definition_name, filepath, description, user_parameters):
    try:
        r = _create_training_model(job_definition_name, filepath, description, user_parameters)
    except:
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
              help='Training job definition name', required=True)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
@click.option('-d', '--description', 'description', type=str, required=False,
              help='Description for the training model, which must be less than or equal to 256 characters.')
def update_training_model(job_definition_name, model_id, description):
    try:
        r = _update_training_model(job_definition_name, model_id, description)
    except:
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
              help='Training job definition name', required=True)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
def download_training_model(job_definition_name, model_id):
    try:
        r = _download_training_model(job_definition_name, model_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _download_training_model(job_definition_name, model_id):
    url = '{}/training/definitions/{}/models/{}/download'.format(
        ORGANIZATION_ENDPOINT, job_definition_name, model_id)
    r = api_get(url)

    return r


@training.command(name='archive-training-model', help='Archive training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=True)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
def archive_training_model(job_definition_name, model_id):
    try:
        r = _archive_training_model(job_definition_name, model_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _archive_training_model(job_definition_name, model_id):
    url = '{}/training/definitions/{}/models/{}/archive'.format(
        ORGANIZATION_ENDPOINT, job_definition_name, model_id)
    r = api_post(url)

    return r


@training.command(name='unarchive-training-model', help='Unarchive training model')
@click.option('-j', '--job_definition_name', '--job-definition-name', 'job_definition_name', type=str,
              help='Training job definition name', required=True)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=True)
def unarchive_training_model(job_definition_name, model_id):
    try:
        r = _unarchive_training_model(job_definition_name, model_id)
    except:
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
@click.option('-h', '--handler', 'handler', type=str, help='Training handler', required=True)
@click.option('-i', '--image', 'image', type=str, required=True,
              callback=convert_to_local_image_callback,
              help='Specify base image name and tag in the "name:tag" format. ex) abeja-inc/all-gpu:19.10')
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'this value is set as an environment variable named `ABEJA_ORGANIZATION_ID`.',
              callback=__try_get_organization_id)
@click.option('-d', '--datasets', type=DATASET_PARAM_STR, help='Datasets name', default=None,
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
        config = training_config.read(training_config.default_schema)

        datasets = {**dict(config.get('datasets', {})), **dict(datasets)}

        environment = {**dict(config.get('environment', {})), **dict(environment)}

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
    except Exception as e:
        logger.error('debug local aborted: {}'.format(e))
        click.echo('debug local aborted.')
        sys.exit(ERROR_EXITCODE)


@training.command(name='train-local', help='Local train commands', context_settings=dict(
    ignore_unknown_options=True, allow_extra_args=True))
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'this value is set as an environment variable named `ABEJA_ORGANIZATION_ID`.',
              callback=__try_get_organization_id)
@click.option('--name', 'name', type=str, help='Training Job Definition Name', required=True)
@click.option('--version', 'version', type=str, help='Training Job Definition Version', required=True)
@click.option('--description', 'description', type=str, help='Training Job description', required=False)
@click.option('-d', '--datasets', type=DATASET_PARAM_STR, help='Datasets name', default=None,
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
        config = training_config.read(training_config.default_schema)

        job_definition_version = _describe_training_version(name, version)
        version_datasets = job_definition_version.get('datasets')
        if not version_datasets:
            version_datasets = {}
        version_environment = job_definition_version.get('environment')
        if not version_environment:
            version_environment = {}

        datasets = {**version_datasets, **dict(**config.get('datasets', {})), **dict(datasets)}

        environment = {**version_environment, **dict(**config.get('environment', {})), **dict(environment)}

        volume = build_volumes(volume) if volume else {}

        with TrainingJobLocalContainerRun(
            organization_id=organization_id, job_definition_name=name,
            job_definition_version=version, description=description,
            datasets=datasets, environment=environment, volume=volume, runtime=runtime,
            stdout=click.echo, platform_user_id=ABEJA_PLATFORM_USER_ID,
            platform_personal_access_token=ABEJA_PLATFORM_TOKEN, v1flag=v1
        ) as job:
            job.watch()
    except Exception as e:
        logger.error('train local aborted: {}'.format(e))
        click.echo('train local aborted.')
        sys.exit(ERROR_EXITCODE)


def _describe_training_version(name: str, job_definition_version: str):
    url = "{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, name, job_definition_version)
    return api_get(url)
