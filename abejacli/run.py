#!/usr/bin/env python3
# -*- coding: utf-8 -*
import datetime
import json
import mimetypes
import os
import sys
import time
import urllib
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from pathlib import Path
from typing import Optional

import click
import requests

# run_test.py will rewrite the variable `CONFIG_FILE_PATH` so we have to access
# the variable through the module. Don't import variable directly.
import abejacli.configuration
import abejacli.version
from abejacli.bucket import (
    download_from_bucket,
    generate_bucket_file_iter,
    generate_bucket_file_iter_by_id,
    upload_to_bucket
)
from abejacli.click_custom import (
    DATE_STR,
    ENVIRONMENT_STR,
    METADATA_STR,
    PORT_NUMBER,
    MutuallyExclusiveAndRequireOption,
    convert_to_local_image_callback
)
from abejacli.common import (
    __try_get_organization_id,
    json_output_formatter,
    progress_status,
    version_archive
)
from abejacli.config import (
    DEFAULT_EXCLUDE_FILES,
    ERROR_EXITCODE,
    ORGANIZATION_ENDPOINT,
    ROOT_DIRECTORY,
    RUN_DEFAULT_RETRY_COUNT,
    SUCCESS_EXITCODE,
    TRIGGER_DEFAULT_RETRY_COUNT,
    WEB_API_ENDPOINT
)
from abejacli.configuration import __ensure_configuration_exists
from abejacli.configuration.config import Config, ConfigSet
from abejacli.configuration.formatter import (
    ConfigFormatter,
    ConfigSetListFormatter
)
from abejacli.configuration.loader import ConfigSetLoader
from abejacli.datalake import (
    download_from_datalake,
    generate_channel_file_iter_by_id,
    generate_channel_file_iter_by_period,
    upload_to_datalake
)
from abejacli.dataset.commands import dataset
from abejacli.docker.commands.run import ModelRunCommand
from abejacli.docker.utils import check_docker_installation
from abejacli.dx_template.commands import dx_template
from abejacli.fs_utils import (
    InvalidPathException,
    UploadBucketFile,
    UploadFile,
    generate_upload_bucket_iter,
    generate_upload_file_iter,
    get_compressed_file
)
from abejacli.labs.commands import labs
from abejacli.logger import get_logger
from abejacli.model.docker_handler import (
    LOCAL_MODEL_TYPE_KEY,
    LocalModelHandler
)
from abejacli.model.local_server_manager import LocalServerManager
from abejacli.model.runtime_utils import (
    format_container_log,
    get_runtime_command
)
from abejacli.registry.commands import registry
from abejacli.session import (
    api_delete,
    api_get,
    api_get_data,
    api_patch,
    api_post
)
from abejacli.startapp.commands import startapp
from abejacli.training.commands import training

# "Assume yes" option
OPTION_ASSUME_YES_PARAM_NAMES = ['-y', '--yes', '--assume-yes']

OPTION_ASSUME_YES_OPTS = {
    'is_flag': True,
    'help': 'Automatically respond yes to confirmation prompts; '
    'assume "yes" as answer to all prompts and run non-interactively.'
}


__version__ = abejacli.version.VERSION
date = datetime.datetime.today()
logger = get_logger()


@click.group(help='ABEJA command line interface')
@click.version_option(version=__version__, message='v%(version)s')
@click.pass_context
def main(ctx):
    pass


@main.group(help='Model operation commands')
@click.pass_context
def model(ctx):
    __ensure_configuration_exists(ctx)


@main.group(help='DataLake operation commands')
@click.pass_context
def datalake(ctx):
    __ensure_configuration_exists(ctx)


@main.group(help='Bucket operation commands')
@click.pass_context
def bucket(ctx):
    __ensure_configuration_exists(ctx)


@main.group(help='Configuration operation commands')
@click.pass_context
def config(ctx):
    pass


# ---------------------------------------------------
# Configure
# ---------------------------------------------------

def __ensure_name_in_config_set(ctx, name: str, config_set: ConfigSet) -> Config:
    if name not in config_set:
        if name:
            ctx.fail('Named configuration not found: {}'.format(name))
        else:
            ctx.fail('The default configuration doesn\'t exist yet')
    return config_set[name]


def __save_config_set(config_set: ConfigSet):
    with open(abejacli.configuration.CONFIG_FILE_PATH, "w") as f:
        json.dump(config_set.asdict(), f)


@config.command(name='show')
@click.pass_context
@click.option('-u', '--user', 'user', help="Display credential's userID", is_flag=True)
@click.option('-t', '--token', 'token', help="Display credential's user token", is_flag=True)
@click.option('-o', '--organization', 'organization', help="Display credential's organizationID", is_flag=True)
@click.option('--format', 'output_format', help="Display credential in defined format", type=click.Choice(['json']))
@click.option('--default', 'use_default', help="Display default credential", is_flag=True)
@click.argument('name', required=False)
def show_configuration(
        ctx, user: bool, token: bool, organization: bool, output_format: str,
        use_default: bool, name: Optional[str]):
    """Show the current active configuration details
    """
    config_set = __ensure_configuration_exists(ctx)

    if name or use_default:
        config = __ensure_name_in_config_set(ctx, name, config_set)
    else:
        config = config_set.active_config

    formatter = ConfigFormatter.build(config, format=output_format)
    out = formatter.format(user=user, token=token, organization=organization)

    click.echo(out)


@config.command(name='list', short_help='Lists the configurations')
@click.pass_context
def list_configurations(ctx):
    """Lists the configurations and shows which configuration is currently active
    """
    config_set = __ensure_configuration_exists(ctx)
    formatter = ConfigSetListFormatter.build(config_set, format='plain')
    out = formatter.format()

    click.echo(out)


@config.command(name='switch')
@click.pass_context
@click.argument('name', required=False)
def switch_configuration(ctx, name: str):
    """Activates an existing named or unnamed configuration
    """
    config_set = __ensure_configuration_exists(ctx)
    __ensure_name_in_config_set(ctx, name, config_set)

    config_set.active_config_name = name
    __save_config_set(config_set)

    click.echo('[INFO]: The configuration "{}" successfully activated.'.format(
        config_set.active_config.printable_name))


@config.command(name='delete', short_help='Removes an existing configuration',
                help='Removes an existing configuration. If you want to delete the default configuration, '
                'run `abeja config delete`.')
@click.pass_context
@click.option(*OPTION_ASSUME_YES_PARAM_NAMES, 'assume_yes', **OPTION_ASSUME_YES_OPTS)
@click.argument('name', required=False)
def delete_configuration(ctx, name: Optional[str], assume_yes: bool):
    """Removes an existing configuration.
    If you want to delete the default configuration, run `abeja config delete`.
    """
    config_set = __ensure_configuration_exists(ctx)

    config = __ensure_name_in_config_set(ctx, name, config_set)

    # Confirm for override
    if not assume_yes:
        click.confirm(
            'The configuration "{}" will be removed. Do you want to continue?'.format(config.printable_name),
            abort=True)

    c = config_set[name]
    config_set.remove(name)

    if len(config_set) == 0:
        # There are no configurations
        os.unlink(abejacli.configuration.CONFIG_FILE_PATH)
        return

    # Change active configuration
    if name == config_set.active_config_name:
        if name is None:
            # default configuration removed. choose the first one.
            config_set.active_config_name = next(iter(config_set)).name
            __save_config_set(config_set)
        else:
            if None in config_set:
                config_set.active_config_name = None
            else:
                config_set.active_config_name = next(iter(config_set)).name

            __save_config_set(config_set)

    click.echo('[INFO]: The configuration "{}" successfully deleted.'.format(
        c.printable_name))


@config.command(name='init', help='Initialize ABEJA credentials')
@click.pass_context
@click.option(*OPTION_ASSUME_YES_PARAM_NAMES, 'assume_yes', **OPTION_ASSUME_YES_OPTS)
@click.argument('name', required=False)
def initialize_configuragtion(ctx, name: str, assume_yes: bool):
    # Loading existing configuration if one exists.
    try:
        with open(abejacli.configuration.CONFIG_FILE_PATH, 'r') as f:
            loader = ConfigSetLoader()
            config_set = loader.load_from_file(f)
    except FileNotFoundError:
        config_set = ConfigSet()

    # Confirm for override
    if (name in config_set) and not assume_yes:
        click.confirm(
            'The configuration already exists. Do you want to continue?', abort=True)

    user = input('User ID              : ').strip()
    token = input('Personal Access Token: ').strip()
    org = input('Organization ID      : ').strip()

    if not (user and token and org):
        click.echo(
            "[error] any of user-id, access-token, organization-name is not set")
        ctx.abort()

    config_set.add(
        Config(user=user, token=token, organization=org, name=name),
        replace=True)

    os.makedirs(ROOT_DIRECTORY, mode=0o711, exist_ok=True)
    __save_config_set(config_set)

    click.echo('[INFO]: ABEJA credentials setup completed!')


# ---------------------------------------------------
# deployments
# ---------------------------------------------------
@model.command(name='create-deployment', help='Deploy a specific model')
@click.option('-n', '--name', 'name', type=str, help='Deployment name', required=True)
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Default environment variable', default=None,
              required=False, multiple=True)
@click.option('-d', '--description', type=str, help='Description', required=False, default=None)
def create_deployment(name, environment, description):
    try:
        r = _create_deployment(name, environment, description)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _create_deployment(name, environment=None, description=None):
    parameter = {'name': name}
    if environment:
        parameter.update({'default_environment': dict(environment)})
    if description:
        parameter.update({'description': description})

    json_data = json.dumps(parameter)

    url = "{}/deployments".format(ORGANIZATION_ENDPOINT)
    r = api_post(url, json_data)

    return r


@model.command(name='describe-deployments', help='Get to deployment or deployment list')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              default='all', required=False)
def describe_deployments(deployment_id):
    try:
        r = _describe_deployments(deployment_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _describe_deployments(deployment_id):
    url = '{}/deployments'.format(ORGANIZATION_ENDPOINT)
    if deployment_id != "all":
        url = '{}/{}'.format(url, deployment_id)
    r = api_get(url)

    return r


@model.command(name='delete-deployment', help='Delete deployment')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
def delete_deployment(deployment_id):
    try:
        r = _delete_deployment(deployment_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _delete_deployment(deployment_id):
    url = '{}/deployments/{}'.format(ORGANIZATION_ENDPOINT, deployment_id)
    r = api_delete(url)

    return r


# ---------------------------------------------------
# deployment code versions
# ---------------------------------------------------
@model.command(name='create-deployment-version', help='Create version & upload application')
@click.pass_context
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version', 'version', type=str, help='Deployment code version', required=True)
@click.option('-i', '--image', 'image', type=str, help='Base-image name. ex) abeja-inc/all-cpu:19.10', required=True)
@click.option('-h', '--handler', 'handler', type=str, help='Path to handler in the model archive.')
@click.option('--user-parameters', '--user_parameters', type=ENVIRONMENT_STR, help='Environment variable',
              default=None, required=False, multiple=True)
def create_deployment_version(ctx, deployment_id, version, image, handler, user_parameters):
    try:
        r = _create_deployment_version(
            ctx, deployment_id, version, image, handler, user_parameters)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _create_deployment_version(ctx, deployment_id, version, image, handler=None, user_parameters=None):
    parameter = {
        'image': image,
        'version': version
    }
    if handler:
        parameter['handler'] = handler
    if user_parameters:
        parameter['user_parameters'] = dict(user_parameters)
    json_data = json.dumps(parameter)

    url = '{}/deployments/{}/versions'.format(
        ORGANIZATION_ENDPOINT, deployment_id)
    r = api_post(url, json_data)
    result = {
        'version': r['version'],
        'version_id': r['version_id']
    }

    upload_url = r['upload_url']
    name = _get_deployment_name(deployment_id)
    try:
        temp_file = version_archive(name, DEFAULT_EXCLUDE_FILES)
        # TODO:  Confirm what is this doing?  Should we use it's result?
        _version_upload(upload_url, temp_file.name)
    finally:
        if os.path.exists(temp_file.name):
            temp_file.close()
            os.unlink(temp_file.name)
    return result


def _get_deployment_name(deployment_id):
    url = '{}/deployments/{}'.format(ORGANIZATION_ENDPOINT, deployment_id)
    r = api_get(url)
    return r['name']


def _version_upload(upload_url, tar_name):
    with open(tar_name, "rb") as file:
        result = requests.put(upload_url, data=file)

    return result


@model.command(name='create-deployment-version-from-git', help='Create version & upload application')
@click.pass_context
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('--git-url', type=str, required=True,
              help='GitHub URL, which must start with "https://".')
@click.option('--git-branch', type=str, required=False,
              help='GitHub branch. Default "master"')
@click.option('-v', '--version', 'version', type=str, help='Deployment code version', required=True)
@click.option('-i', '--image', 'image', type=str, help='Base-image name. ex) abeja-inc/all-cpu:19.10', required=True)
@click.option('-h', '--handler', 'handler', type=str, help='Path to handler in the model archive.')
@click.option('--user-parameters', '--user_parameters', type=ENVIRONMENT_STR, help='Environment variable',
              default=None, required=False, multiple=True)
def create_deployment_version_from_git(
        ctx, deployment_id, git_url, git_branch, version, image, handler, user_parameters):
    try:
        r = _create_deployment_version_from_git(
            ctx, deployment_id, git_url, git_branch, version, image, handler, user_parameters)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _create_deployment_version_from_git(
        ctx, deployment_id, git_url, git_branch, version, image, handler=None, user_parameters=None):
    parameter = {
        'git_url': git_url,
        'image': image,
        'version': version
    }
    if handler:
        parameter['handler'] = handler
    if user_parameters:
        parameter['user_parameters'] = dict(user_parameters)
    if git_branch is not None:
        parameter['git_branch'] = git_branch
    json_data = json.dumps(parameter)

    url = '{}/deployments/{}/git/versions'.format(
        ORGANIZATION_ENDPOINT, deployment_id)
    r = api_post(url, json_data)
    result = {
        'version': r['version'],
        'version_id': r['version_id']
    }
    return result


@model.command(name='describe-deployment-versions', help='Get to version or version list')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str, help='Version identifier', default='all',
              required=False)
def describe_deployment_versions(deployment_id, version_id):
    try:
        r = _describe_deployment_versions(deployment_id, version_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _describe_deployment_versions(deployment_id, version_id):
    url = '{}/deployments/{}/versions'.format(
        ORGANIZATION_ENDPOINT, deployment_id)
    if version_id != "all":
        url = '{}/{}'.format(url, version_id)

    r = api_get(url)
    return r


@model.command(name='download-deployment-version', help='Download version')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version-id', '--version_id', 'version_id', type=str, help='Version identifier', required=True)
def download_deployment_version(deployment_id, version_id):
    try:
        r = _download_deployment_version(deployment_id, version_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo('Downloaded a file {}.'.format(r))


def _download_deployment_version(deployment_id, version_id):
    url = '{}/deployments/{}/versions/{}/download'.format(
        ORGANIZATION_ENDPOINT, deployment_id, version_id)
    r = api_get(url)
    download_uri = r['download_uri']
    file_name = os.path.basename(download_uri[:download_uri.find('?')])
    _, ext = os.path.splitext(file_name)
    target_file_name = '{}_{}{}'.format(deployment_id, version_id, ext)
    urllib.request.urlretrieve(
        download_uri, target_file_name, progress_status)

    cf = get_compressed_file(target_file_name)
    if cf is not None:
        n, _ = os.path.splitext(target_file_name)
        os.rename(target_file_name, '{}{}'.format(n, cf.extension_name))

    return target_file_name


@model.command(name='delete-deployment-version', help='Delete version')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str, help='Version identifier', required=True)
def delete_deployment_version(deployment_id, version_id):
    try:
        r = _delete_deployment_version(deployment_id, version_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _delete_deployment_version(deployment_id, version_id):
    url = '{}/deployments/{}/versions/{}'.format(
        ORGANIZATION_ENDPOINT, deployment_id, version_id)
    r = api_delete(url)

    return r


# ---------------------------------------------------
# service
# ---------------------------------------------------
@model.command(name='create-service', help='Create http service')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str, help='Version identifier', required=True)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=False,
              default=None)
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Service environment variable', default=None,
              required=False, multiple=True)
@click.option('--instance-type', '--instance_type', 'instance_type', type=str, help='Instance type',
              default=None, required=False)
@click.option('--disable-autoscale', '--disable_autoscale', 'disable_autoscale',
              help='Disable autscale. Autoscale is enabled by default',
              default=False, is_flag=True)
@click.option('--instance-number', '--instance_number', 'instance_number', type=int,
              help='Number of intances. Available values are 1 to 300. Default is 1',
              default=None, required=False)
@click.option('--min-instance-number', '--min_instance_number', 'min_instance_number', type=int,
              help='Minimum number of instances of autoscaling. Default is same as instance-number',
              default=None, required=False, hidden=True)
@click.option('--max-instance-number', '--max_instance_number', 'max_instance_number', type=int,
              help='Max number of instances of autoscaling. Default is double of instance-number',
              default=None, required=False)
@click.option('--record-channel-id', '--record_channel_id', 'record_channel_id', type=str,
              help='Channel identifier where input data will be saved', default=None, required=False)
def create_service(
        deployment_id, version_id, environment, instance_type,
        disable_autoscale, instance_number, min_instance_number, max_instance_number, record_channel_id, model_id):
    # TODO: When min_instance_number is supported in model-api,
    # remove hidden option of min-intance-number and this caution
    if min_instance_number:
        __print_feature_deprecation(
            'Currently, `--min-instance-number` is ignored. min-instance-number is set to the value of instance-number')

    try:
        r = _create_service(deployment_id, version_id, environment, instance_type,
                            disable_autoscale, instance_number, min_instance_number, max_instance_number,
                            record_channel_id, model_id)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _create_service(deployment_id, version_id, environment=None, instance_type=None,
                    disable_autoscale=False, instance_number=None, min_instance_number=None, max_instance_number=None,
                    record_channel_id=None, model_id=None):
    parameter = {
        'version_id': version_id
    }

    if model_id:
        parameter.update({'models': {'alias': model_id}})
    if environment:
        parameter.update({'environment': dict(environment)})
    if instance_type:
        parameter.update({'instance_type': instance_type})
    if disable_autoscale:
        parameter.update({"enable_autoscale": False})
    if instance_number:
        parameter.update({'instance_number': instance_number})
    if min_instance_number:
        parameter.update({'min_instance_number': min_instance_number})
    if max_instance_number:
        parameter.update({'max_instance_number': max_instance_number})
    if record_channel_id:
        parameter.update({'record_channel_id': record_channel_id})
    json_data = json.dumps(parameter)
    url = "{}/deployments/{}/services".format(
        ORGANIZATION_ENDPOINT, deployment_id)
    r = api_post(url, json_data)

    return r


@model.command(name='describe-services', help='Get to service or service list')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', default='all',
              required=False)
def describe_services(deployment_id, service_id):
    try:
        r = _describe_services(deployment_id, service_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _describe_services(deployment_id, service_id):
    url = '{}/deployments/{}/services'.format(
        ORGANIZATION_ENDPOINT, deployment_id)
    if service_id != "all":
        url = '{}/{}'.format(url, service_id)
    r = api_get(url)

    return r


@model.command(name='delete-service', help='Delete service')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=True)
def delete_service(deployment_id, service_id):
    try:
        r = _delete_service(deployment_id, service_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _delete_service(deployment_id, service_id):
    url = '{}/deployments/{}/services/{}'.format(
        ORGANIZATION_ENDPOINT, deployment_id, service_id)
    r = api_delete(url)

    return r


@model.command(name='stop-service', help='Stop service')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=True)
def stop_service(deployment_id, service_id):
    try:
        r = _stop_service(deployment_id, service_id)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _stop_service(deployment_id, service_id):
    url = '{}/deployments/{}/services/{}/stop'.format(
        ORGANIZATION_ENDPOINT, deployment_id, service_id)
    return api_post(url)


@model.command(name='start-service', help='Start stopped service')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=True)
def start_service(deployment_id, service_id):
    try:
        r = _start_service(deployment_id, service_id)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _start_service(deployment_id, service_id):
    url = '{}/deployments/{}/services/{}/start'.format(
        ORGANIZATION_ENDPOINT, deployment_id, service_id)
    return api_post(url)


# ---------------------------------------------------
# endpoint
# ---------------------------------------------------
@model.command(name='create-endpoint', help='Create endpoint')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=True)
@click.option('-c', '--custom_alias', '--custom-alias', 'custom_alias', type=str, help='Custom_alias name',
              required=True)
def create_endpoint(deployment_id, service_id, custom_alias):
    try:
        r = _create_endpoint(deployment_id, service_id, custom_alias)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _create_endpoint(deployment_id, service_id, custom_alias):
    parameter = {
        'service_id': service_id,
        'custom_alias': custom_alias,
    }
    json_data = json.dumps(parameter)
    time.sleep(15)
    url = "{}/deployments/{}/endpoints".format(
        ORGANIZATION_ENDPOINT, deployment_id)
    r = api_post(url, json_data)

    return r


@model.command(name='describe-endpoints', help='Get to endpoint or endpoint list')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-e', '--endpoint_id', '--endpoint-id', 'endpoint_id', type=str, help='Endpoint identifier',
              default='all', required=False)
def describe_endpoints(deployment_id, endpoint_id):
    try:
        r = _describe_endpoints(deployment_id, endpoint_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _describe_endpoints(deployment_id, endpoint_id):
    url = '{}/deployments/{}/endpoints'.format(
        ORGANIZATION_ENDPOINT, deployment_id)
    if endpoint_id != "all":
        url = '{}/{}'.format(url, endpoint_id)
    r = api_get(url)

    return r


@model.command(name='delete-endpoint', help='Delete endpoint')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-e', '--endpoint_id', '--endpoint-id', 'endpoint_id', type=str, help='Endpoint identifier',
              required=True)
def delete_endpoint(deployment_id, endpoint_id):
    try:
        r = _delete_endpoint(deployment_id, endpoint_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _delete_endpoint(deployment_id, endpoint_id):
    url = '{}/deployments/{}/endpoints/{}'.format(
        ORGANIZATION_ENDPOINT, deployment_id, endpoint_id)
    r = api_delete(url)

    return r


@model.command(name='update-endpoint', help='Update endpoint')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=True)
@click.option('-e', '--endpoint_id', '--endpoint-id', 'endpoint_id', type=str, help='Endpoint identifier',
              required=True)
def update_endpoint(deployment_id, service_id, endpoint_id):
    try:
        r = _update_endpoint(deployment_id, service_id, endpoint_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _update_endpoint(deployment_id, service_id, endpoint_id):
    parameter = {
        'service_id': service_id,
    }
    jsonData = json.dumps(parameter)
    time.sleep(15)
    url = "{}/deployments/{}/endpoints/{}".format(
        ORGANIZATION_ENDPOINT, deployment_id, endpoint_id)
    r = api_patch(url, jsonData)

    return r


@model.command(name='check-endpoint-json', help='Check endpoint json')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=False)
@click.option('-k', '--key', 'key', type=str, help='Key', required=True)
@click.option('-v', '--value', 'value', type=str, help='Value', required=True)
def check_endpoint_json(deployment_id, service_id, key, value):
    try:
        r = _check_endpoint_json(deployment_id, service_id, key, value)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _check_endpoint_json(deployment_id, service_id, key, value):
    parameter = {
        key: value,
    }
    json_data = json.dumps(parameter)

    if service_id:
        url = "{}/deployments/{}/services/{}".format(
            WEB_API_ENDPOINT, deployment_id, service_id)
    else:
        url = "{}/deployments/{}".format(WEB_API_ENDPOINT, deployment_id)
    r = api_post(url, json_data)

    return r


@model.command(name='check-endpoint-image', help='Check endpoint image')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=False)
@click.option('-t', '--type', 'type', type=str, help='Contant type', required=True)
@click.option('-i', '--image_path', '--image-path', 'image_path', type=str, help='Image file', required=True)
def check_endpoint_image(deployment_id, service_id, type, image_path):
    try:
        r = _check_endpoint_image(deployment_id, service_id, type, image_path)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _check_endpoint_image(deployment_id, service_id, type, image_path):
    if not os.path.exists(image_path):
        click.echo('image {} not found'.format(image_path))
        raise click.Abort()

    if service_id:
        url = "{}/deployments/{}/services/{}".format(
            WEB_API_ENDPOINT, deployment_id, service_id)
    else:
        url = "{}/deployments/{}".format(WEB_API_ENDPOINT, deployment_id)
    content_type = "image/{}".format(type)
    with open(image_path, 'rb') as f:
        data = f.read()
    headers = {
        'Content-Type': content_type
    }

    r = api_post(url, data=data, headers=headers)

    return r.json()


# ---------------------------------------------------
# submit-run
# ---------------------------------------------------
@model.command(name='submit-run', help='Submit run')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str, help='Version identifier', required=True)
@click.option('--input_operator', '--input-operator', 'input_operator', type=str, required=True,
              help='Input oparator.')
@click.option('--input_target', '--input-target', 'input_target', type=str, required=True, help='Input target.')
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=False,
              default=None)
@click.option('--output_operator', '--output-operator', 'output_operator', type=str, help='Output operator',
              required=False)
@click.option('--output_target', '--output-target', 'output_target', type=str, help='Output target',
              required=False)
@click.option('--retry_count', '--retry-count', 'retry_count', type=int, required=False,
              default=RUN_DEFAULT_RETRY_COUNT,
              help='Retry count. By default, retries {} times.'.format(RUN_DEFAULT_RETRY_COUNT))
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Trigger environment variable', default=None,
              required=False, multiple=True)
def submit_run(deployment_id, version_id, input_operator, input_target,
               output_operator, output_target, retry_count, environment, model_id):
    if output_operator is None and output_target:
        raise click.BadArgumentUsage('Error: Missing option "--output_operator", '
                                     'when option "--output_target" is given.')
    elif output_operator and output_target is None:
        raise click.BadArgumentUsage('Error: Missing option "--output_target", '
                                     'when option "--output_operator" is given.')

    try:
        user_env_vars = dict(environment)
        r = _submit_run(deployment_id, version_id, input_operator, input_target,
                        output_operator, output_target, retry_count, user_env_vars, model_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _submit_run(deployment_id, version_id, input_operator, input_target,
                output_operator, output_target, retry_count, environment, model_id):
    parameter = {
        'version_id': version_id,
        'input_data': {input_operator: input_target},
        'retry_count': retry_count,
        'environment': environment
    }
    if model_id:
        parameter['models'] = {'alias': model_id}
    if output_operator and output_target:
        parameter['output_template'] = {output_operator: output_target}

    json_data = json.dumps(parameter)
    url = "{}/deployments/{}/runs".format(ORGANIZATION_ENDPOINT, deployment_id)
    r = api_post(url, json_data)

    return r


@model.command(name='describe-runs', help='Get to run or run list')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-r', '--run_id', '--run-id', 'run_id', type=str, help='Run identifier', default='all', required=False)
def describe_runs(deployment_id, run_id):
    try:
        r = _describe_runs(deployment_id, run_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _describe_runs(deployment_id, run_id):
    url = '{}/deployments/{}/runs'.format(ORGANIZATION_ENDPOINT, deployment_id)
    if run_id != "all":
        url = '{}/{}'.format(url, run_id)
    r = api_get(url)

    return r


# ---------------------------------------------------
# trigger
# ---------------------------------------------------
@model.command(name='create-trigger', help='Create trigger')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str, help='Version identifier', required=True)
@click.option('--input_service_name', '--input-service-name', 'input_service_name', type=str, help='Input service name',
              required=True)
@click.option('--input_service_id', '--input-service-id', 'input_service_id', type=str, help='Input service id',
              required=True)
@click.option('-m', '--model_id', '--model-id', 'model_id', type=str, help='Model identifier', required=False,
              default=None)
@click.option('--output_service_name', '--output-service-name', 'output_service_name', type=str, required=False,
              default=None, help='Output service name')
@click.option('--output_service_id', '--output-service-id', 'output_service_id', type=str, required=False,
              default=None, help='Output service id')
@click.option('--retry_count', '--retry-count', 'retry_count', type=int, required=False,
              default=TRIGGER_DEFAULT_RETRY_COUNT,
              help='Retry count. By default, retries {} times.'.format(TRIGGER_DEFAULT_RETRY_COUNT))
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Trigger environment variable', default=None,
              required=False, multiple=True)
def create_trigger(deployment_id, version_id, input_service_name, input_service_id,
                   output_service_name, output_service_id, retry_count, environment, model_id):
    if output_service_name is None and output_service_id:
        raise click.BadArgumentUsage('Error: Missing option "--output_service_name", '
                                     'when option "--output_service_id" is given.')
    elif output_service_name and output_service_id is None:
        raise click.BadArgumentUsage('Error: Missing option "--output_service_id", '
                                     'when option "--output_service_name" is given.')

    try:
        user_env_vars = dict(environment)
        r = _create_trigger(deployment_id, version_id, input_service_name, input_service_id,
                            output_service_name, output_service_id, retry_count, user_env_vars, model_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _create_trigger(deployment_id, version_id, input_service_name, input_service_id,
                    output_service_name=None, output_service_id=None,
                    retry_count=TRIGGER_DEFAULT_RETRY_COUNT, environment=None, model_id=None):
    parameter = {
        'version_id': version_id,
        'input_service_name': input_service_name,
        'input_service_id': input_service_id,
        'retry_count': retry_count,
        'environment': environment
    }
    if model_id:
        parameter['models'] = {'alias': model_id}
    if output_service_name:
        parameter['output_service_name'] = output_service_name

    if output_service_id:
        parameter['output_service_id'] = output_service_id

    json_data = json.dumps(parameter)

    url = "{}/deployments/{}/triggers".format(
        ORGANIZATION_ENDPOINT, deployment_id)
    r = api_post(url, json_data)

    return r


@model.command(name='describe-triggers', help='Get to trigger or trigger list')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-t', '--trigger_id', '--trigger-id', 'trigger_id', type=str, help='Trigger identifier', default='all',
              required=False)
def describe_triggers(deployment_id, trigger_id):
    try:
        r = _describe_triggers(deployment_id, trigger_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _describe_triggers(deployment_id, trigger_id):
    url = '{}/deployments/{}/triggers'.format(
        ORGANIZATION_ENDPOINT, deployment_id)
    if trigger_id != "all":
        url = '{}/{}'.format(url, trigger_id)
    r = api_get(url)

    return r


@model.command(name='delete-trigger', help='Delete trigger')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-t', '--trigger_id', '--trigger-id', 'trigger_id', type=str, help='Trigger identifier', required=True)
def delete_trigger(deployment_id, trigger_id):
    try:
        r = _delete_trigger(deployment_id, trigger_id)
    except:
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _delete_trigger(deployment_id, trigger_id):
    url = '{}/deployments/{}/triggers/{}'.format(
        ORGANIZATION_ENDPOINT, deployment_id, trigger_id)
    r = api_delete(url)

    return r


# ---------------------------------------------------
# log
# ---------------------------------------------------
@model.command(name='describe-service-logs', help='Get service log')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-s', '--service_id', '--service-id', 'service_id', type=str, help='Service identifier', required=True)
@click.option('--start_time', '--start-time', 'start_time', type=str, help='Start time / 2017-01-01T00:00:00Z',
              default=None, required=False)
@click.option('--end_time', '--end-time', 'end_time', type=str, help='End time / 2017-12-31T00:00:00Z', default=None,
              required=False)
@click.option('--next_token', '--next-token', 'next_token', type=str, help='Next token', default=None, required=False)
def describe_service_logs(deployment_id, service_id, start_time, end_time, next_token):
    params = {
        'next_token': next_token,
        'start_time': start_time,
        'end_time': end_time
    }
    url = "{}/deployments/{}/services/{}/logs".format(
        ORGANIZATION_ENDPOINT, deployment_id, service_id)
    try:
        r = api_get_data(url, params)
    except:
        sys.exit(ERROR_EXITCODE)

    return click.echo(json_output_formatter(r))


@model.command(name='describe-run-logs', help='Get run log')
@click.option('-d', '--deployment_id', '--deployment-id', 'deployment_id', type=str, help='Deployment identifier',
              required=True)
@click.option('-r', '--run_id', '--run-id', 'run_id', type=str, help='Run identifier', required=True)
@click.option('--start_time', '--start-time', 'start_time', type=str, help='Start time', default=None, required=False)
@click.option('--end_time', '--end-time', 'end_time', type=str, help='End time', default=None, required=False)
@click.option('--next_token', '--next-token', 'next_token', type=str, help='Next token', default=None, required=False)
def describe_run_logs(deployment_id, run_id, start_time, end_time, next_token):
    params = {
        'next_token': next_token,
        'start_time': start_time,
        'end_time': end_time
    }
    url = "{}/deployments/{}/runs/{}/logs".format(
        ORGANIZATION_ENDPOINT, deployment_id, run_id)
    try:
        r = api_get_data(url, params)
    except:
        sys.exit(ERROR_EXITCODE)

    return click.echo(json_output_formatter(r))


@model.command(name='run-local', help='Local run commands')
@click.option('-h', '--handler', 'handler', type=str, help='Model hanlder', required=True)
@click.option('-i', '--image', 'image', type=str, help='Base-image name. ex) abeja-inc/all-cpu:19.10', required=True,
              callback=convert_to_local_image_callback)
@click.option('-d', '--device_type', '--device-type', 'device_type',
              type=click.Choice(
                  ['x86_cpu', 'x86_gpu', 'jetson_tx2', 'raspberry3']),
              help='Device type', default='x86_cpu')
@click.option('--input', 'input', type=str, help='Input data', required=True)
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Environment variables', default=None,
              required=False, multiple=True)
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'this value is set as an environment variable named `ABEJA_ORGANIZATION_ID`. '
                   '`ABEJA_ORGANIZATION_ID` from this arg takes priority over one in `--environment`.',
              callback=__try_get_organization_id)
@click.option('--no-cache', '--no_cache', is_flag=True, type=bool, help='Not use built cache', required=False)
@click.option('-q', '--quiet', is_flag=True, type=bool, help='Suppress info logs', required=False)
@click.option('--v1', is_flag=True, type=bool, help='Specify if you use old custom runtime image', default=False,
              required=False)
def run_local(handler, image, device_type, input, environment, organization_id, no_cache, quiet, v1):
    image = str(image)
    local_model = LocalModelHandler()

    if not check_docker_installation():
        click.secho("[error] docker command is required", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    if not quiet:
        click.echo("[info] preparing image : {}".format(image))
    try:
        image, tag = image.split(':')
    except ValueError:
        click.secho("[error] invalid image and tag format : {}".format(
            image), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    if not quiet:
        click.echo("[info] building image")
    try:
        stdout = None
        if not quiet:
            stdout = click.echo
        built_image = local_model.build_run_image(
            image, tag, model_type=LOCAL_MODEL_TYPE_KEY, no_cache=no_cache, stdout=stdout)
    except:
        click.secho("[error] failed to build image", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    runtime_command = get_runtime_command(image, tag, v1)

    if not quiet:
        click.echo("[info] setting up local server")
    try:
        command = ModelRunCommand.create(
            image=built_image.id, handler=handler, device_type=device_type,
            env_vars=dict(environment), command=runtime_command,
            organization_id=organization_id)
        local_server = local_model.create_local_server(command)
    except:
        click.secho("[error] failed to create local server",
                    err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    endpoint = local_server.endpoint
    health_check_url = '{}/health_check'.format(endpoint)
    headers, data = _get_headers_and_data(input)

    with ThreadPoolExecutor() as executor:
        def server_logging():
            for log in local_server.logs():
                formatted_message = format_container_log(log)
                click.echo(formatted_message)

        if not quiet:
            # This thread finish when local server container is skilled,
            # because it permanently tails all coming logs from the container.
            executor.submit(server_logging)

        with LocalServerManager(local_server) as manager:
            if not quiet:
                click.echo("[info] waiting server running")
            try:
                manager.wait_until_running(health_check_url)
            except Exception as e:
                click.secho("[error] failed to run local server : {}".format(
                    e), err=True, fg='red')
                click.secho("\n ------ Local Server Error ------ ",
                            err=True, fg='red')
                click.secho(manager.dump_logs(), err=True, fg='red')
                sys.exit(ERROR_EXITCODE)

            if not quiet:
                click.echo("[info] sending request to model")
            # TODO: need to support get and other methods
            # post request to local server
            try:
                res = manager.send_request('post', endpoint, headers, data)
            except Exception as e:
                click.secho("[error] failed to send request : {}".format(
                    e), err=True, fg='red')
                click.secho("\n ------ Local Server Error ------ ",
                            err=True, fg='red')
                click.secho(manager.dump_logs(), err=True, fg='red')
                sys.exit(ERROR_EXITCODE)

    if not quiet:
        click.echo("[info] finish requesting to model")
    try:
        click.echo(json.dumps(res.json(), indent=4))
    except:
        click.echo(res.content)


def _get_headers_and_data(input):
    mimetype, _ = mimetypes.guess_type(input)
    if not mimetypes:
        click.secho("[error] not supported file format {}: ".format(
            input), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    if not os.path.exists(input):
        click.secho("[error] specifield file doesn't exist {}: ".format(
            input), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    if mimetype in ('application/json',):
        with open(input, 'r') as f:
            _data = f.read()
            data = json.dumps(json.loads(_data))
    elif mimetype in ('image/jpeg', 'image/png', 'image/gif'):
        with open(input, 'rb') as f:
            data = f.read()
    else:
        click.secho("[error] not supported {}: ".format(
            input), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)
    headers = {'Content-Type': mimetype}
    return headers, data


@model.command(name='run-local-server', help='Local run commands')
@click.option('-h', '--handler', 'handler', type=str, help='Model hanlder', required=True)
@click.option('-i', '--image', 'image', type=str, help='Base-image name. ex) abeja-inc/all-cpu:19.10', required=True,
              callback=convert_to_local_image_callback)
@click.option('-d', '--device_type', '--device-type', 'device_type',
              type=click.Choice(
                  ['x86_cpu', 'x86_gpu', 'jetson_tx2', 'raspberry3']),
              help='Device type', default='x86_cpu')
@click.option('-e', '--environment', type=ENVIRONMENT_STR, help='Environment variables', default=None,
              required=False, multiple=True)
@click.option('-p', '--port', type=PORT_NUMBER, default=None, required=False,
              help='port number assigned to local server ( arbitrary number in 1 - 65535 )')
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'This value is set as an environment variable named `ABEJA_ORGANIZATION_ID`. '
                   '`ABEJA_ORGANIZATION_ID` from this arg takes priority over one in `--environment`.',
              callback=__try_get_organization_id)
@click.option('--no-cache', '--no_cache', 'no_cache', is_flag=True, type=bool, help='Not use built cache',
              required=False)
@click.option('--v1', is_flag=True, type=bool, help='Specify if you use old custom runtime image', default=False,
              required=False)
def run_local_server(handler, image, device_type, environment, port, organization_id, no_cache, v1):
    local_model = LocalModelHandler()

    if not check_docker_installation():
        click.secho("[error] docker command is required", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    click.echo("[info] preparing image : {}".format(image))
    try:
        image, tag = image.split(':')
    except ValueError:
        click.secho("[error] invalid image and tag format : {}".format(
            image), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    click.echo("[info] building image")
    try:
        built_image = local_model.build_run_image(
            image, tag, model_type=LOCAL_MODEL_TYPE_KEY, no_cache=no_cache, stdout=click.echo)
    except:
        click.secho("[error] failed to build image", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    runtime_command = get_runtime_command(image, tag, v1)

    click.echo("[info] setting up local server")
    try:
        command = ModelRunCommand.create(
            image=built_image.id, handler=handler, device_type=device_type,
            port=port, env_vars=dict(environment), command=runtime_command,
            organization_id=organization_id)
        local_server = local_model.create_local_server(command)
    except:
        click.secho("[error] failed to create local server",
                    err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    endpoint = local_server.endpoint
    health_check_url = '{}/health_check'.format(endpoint)

    with LocalServerManager(local_server) as manager:
        # here multithreading is used to keep emitting container logs
        # until local server gets ready
        #
        # `with` clause is not used intentionally.
        # because when exiting `with` clause, executor will wait submitted function finished.
        # but here server_logging function never ends and keeps waiting logs from container.
        executor = ThreadPoolExecutor()

        def server_logging():
            for log in local_server.logs():
                formatted_message = format_container_log(log)
                click.echo(formatted_message)

        try:
            # This thread finish when local server container is killed,
            # because it permanently tails all coming logs from the container.
            executor.submit(server_logging)

            click.echo("[info] waiting server running")

            manager.wait_until_running(health_check_url)
            executor.shutdown(wait=False)
        except Exception as e:
            click.secho("[error] failed to run local server : {}".format(
                e), err=True, fg='red')
            click.secho("\n ------ Local Server Error ------ ",
                        err=True, fg='red')
            click.secho(manager.dump_logs(), err=True, fg='red')
            executor.shutdown(wait=False)
            sys.exit(ERROR_EXITCODE)

        click.secho(" ----- Local Server ----- ", fg='green')
        click.secho(" Started successfully!\n", fg='green', bold=True)

        click.secho(" Endpoint : {}".format(endpoint), bold=True)
        click.secho(" Handler :  {}".format(handler), bold=True)
        click.secho(" Image :    {}:{}".format(image, tag), bold=True)

        click.secho("\n you can now access this http api!")

        click.secho("\n press Ctrl + C to stop", bold=True)
        click.secho(" ------------------------ ", fg='green')

        try:
            # when Ctrl + C pressed, KeyboardInterrupt exception raises here.
            # then LocalServerManager#__exit__ will stop local_server.
            #
            # `since` is passed to skip logs which are already displayed until now.
            for log in local_server.logs(since=datetime.datetime.now()):
                click.echo(log.decode('utf-8').rstrip('\n'))
        except Exception as e:
            click.secho("[error] failed to send request : {}".format(
                e), err=True, fg='red')
            click.secho("\n ------ Local Server Error ------ ",
                        err=True, fg='red')
            click.secho(manager.dump_logs(), err=True, fg='red')
            sys.exit(ERROR_EXITCODE)


# ---------------------------------------------------
# datalake command
# ---------------------------------------------------
def __click_create_datalake_channel(f):
    f = click.option('-n', '--name', type=str, help='Name', required=False)(f)
    f = click.option('-d', '--description', type=str, help='Description', required=False)(f)
    return f


@datalake.command(name='create-channel', help='Create DataLake channel')
@__click_create_datalake_channel
def create_datalake_channel(name, description):
    try:
        r = __create_datalake_channel(name, description)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def __create_datalake_channel(name, description):
    parameters = {
        'name': name,
        'description': description
    }
    parameters = {k: v for k, v in parameters.items() if v is not None}

    json_data = json.dumps(parameters)
    url = "{}/channels".format(ORGANIZATION_ENDPOINT)
    return api_post(url, json_data)


def _describe_channels(channel_id, storage_type, include_archived=None, limit=None, offset=None):
    if channel_id == 'all':
        url = "{}/channels".format(ORGANIZATION_ENDPOINT)
        params = {}
        params["filter_archived"] = 'include_archived' if include_archived else 'exclude_archived'
        params['limit'] = limit or 1000
        if offset:
            params["offset"] = offset
        r = api_get_data(url, params)
        filtered_channels = list(
            filter(lambda x: x['storage_type'] == storage_type, r['channels']))
        response = {
            "created_at": r["created_at"],
            "organization_name": r["created_at"],
            "organization_id": r["organization_id"],
            "channels": filtered_channels,
            "updated_at": r['updated_at']
        }
    else:
        url = "{}/channels/{}".format(ORGANIZATION_ENDPOINT, channel_id)
        response = api_get(url)
        if response['channel']['storage_type'] != storage_type:
            response = {}
    return response


@datalake.command(name='describe-channels', help='Describe DataLake channels')
@click.option('-c', '--channel_id', '--channel-id', 'channel_id', type=str, help='Channel id', default='all',
              required=False)
@click.option('--include-archived', 'include_archived', is_flag=True,
              help="Includes archived Channels.")
@click.option('-l', '--limit', 'limit', type=int,
              help='Number of pagings (default: 1000)', default=None, required=False)
@click.option('-o', '--offset', 'offset', type=int,
              help='Paging start index', default=None, required=False)
def describe_datalake_channels(channel_id, include_archived, limit, offset):
    try:
        r = _describe_channels(channel_id, 'datalake', include_archived, limit=limit, offset=offset)
    except Exception as e:
        logger.error('describe-channels aborted:{}'.format(e))
        click.echo('describe-channels aborted.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@datalake.command(name='archive-channel', help='Archive datalake channel')
@click.option('-c', '--channel_id', '--channel-id', 'channel_id', type=str, help='Channel id', required=True)
def archive_channel(channel_id):
    try:
        url = "{}/channels/{}/archive".format(ORGANIZATION_ENDPOINT, channel_id)
        r = api_post(url)
    except Exception as e:
        logger.error('archive-channel failed: {}'.format(e))
        click.echo('archive-channel failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def __click_file_upload(f):
    f = click.argument('paths', nargs=-1, type=click.Path(exists=True, resolve_path=True))(f)
    f = click.option('--dry-run', '--dry_run', 'dry_run', is_flag=True,
                     help='Dry run, only shows upload candidate files')(f)
    f = click.option('-r', '--recursive', 'recursive', is_flag=True, help='Recursively upload directory')(f)
    f = click.option('-m', '--metadata', '--meta-data', '--meta_data', 'metadata',
                     type=METADATA_STR, multiple=True,
                     help='Metadata to add all upload files')(f)
    f = click.option('-l', '--file-list', '--file_list', 'file_list_path',
                     type=click.Path(exists=True, resolve_path=True),
                     help='JSON file which list files and metadata')(f)
    f = click.option('--retry', type=click.Choice(['ask', 'no', 'force']), default='ask',
                     help="Retry to upload files if there are files couldn't be uploaded (default: 'ask')")(f)
    f = click.option('--save-result', 'result_fp', type=click.File('w', encoding='utf-8'),
                     help='Save uploaded file info as JSON at the specified path.')(f)
    f = click.option('--skip-duplicate-files', 'skip_duplicate', is_flag=True,
                     help="Don't upload file if the file whose name is same already exists in the channel.")(f)
    return f


@datalake.command(name='upload', help='Upload file or directory')
@__click_file_upload
@click.option('-c', '--channel_id', '--channel-id', 'channel_id', type=str, help='Channel identifier', required=True)
@click.pass_context
def file_upload(ctx, paths, channel_id, recursive, dry_run, metadata,
                file_list_path=None, retry=None, result_fp=None, skip_duplicate=False):
    try:
        upload_file_iter = __generate_upload_file_iter(paths, recursive, dry_run, file_list_path)
        __file_upload(upload_file_iter, channel_id, metadata, retry, result_fp, skip_duplicate)
    except InvalidPathException as e:
        click.secho("[error] invalid path {}: ".format(
            e.path), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)
    except Exception:
        click.secho("[error] cannot write result", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)


def __generate_upload_file_iter(paths, recursive, dry_run, file_list_path):
    if len(paths) == 0 and not file_list_path:
        click.secho("[error] No file specified", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)

    upload_file_iter = generate_upload_file_iter(
        paths=paths,
        recursive=recursive,
        file_list_path=file_list_path)

    if dry_run:
        paths = []
        for upload_file in upload_file_iter:
            paths.append(upload_file.path)

        click.echo("[info] upload files:")
        click.echo('    ' + '\n    '.join(sorted(paths)))
        sys.exit(SUCCESS_EXITCODE)

    return upload_file_iter


def __file_upload(upload_file_iter, channel_id, metadata, retry, result_fp, skip_duplicate):
    result_list = [] if result_fp else None
    upload_kwargs = {}
    if skip_duplicate:
        upload_kwargs['conflict_target'] = 'filename'

    while True:
        (success, errors) = upload_to_datalake(
            channel_id, upload_file_iter, metadata, **upload_kwargs)

        if result_list is not None:
            for info in success:
                result_list.append({
                    'channel_id': channel_id,
                    'file': info.source,
                    'file_id': info.destination,
                    'metadata': info.metadata
                })

        # Retry if user confirmed
        if len(errors) > 0:
            prompt = 'Upload failed for {} file(s). Do you want to retry?'.format(
                len(errors))
            if __handle_datalake_retry_option(retry, prompt, default=True):
                upload_file_iter = iter(
                    [UploadFile(e.source, e.metadata) for e in errors])
                continue

        break

    # Write results as JSON if needed
    if result_list is not None:
        assert result_fp
        json.dump(result_list, result_fp)


def __handle_datalake_retry_option(retry_option, prompt_msg, **confirm_opts):
    if retry_option == 'ask':
        return click.confirm(prompt_msg, confirm_opts)
    else:
        return (retry_option == 'force')


@datalake.command(name='create-and-upload', help='Create datalake channel and upload files')
@__click_create_datalake_channel
@__click_file_upload
@click.pass_context
def create_channel_and_upload_files(ctx, paths, name, description, recursive, dry_run, metadata,
                                    file_list_path=None, retry=None, result_fp=None, skip_duplicate=False):
    upload_file_iter = __generate_upload_file_iter(paths, recursive, dry_run, file_list_path)
    r = __create_datalake_channel(name, description)
    click.echo(json_output_formatter(r))
    __file_upload(upload_file_iter, r['channel']['channel_id'], metadata, retry, result_fp, skip_duplicate)


@datalake.command(name='download', help='Download files')
@click.option('-c', '--channel_id', '--channel-id', 'channel_id', type=str, help='Channel identifier', required=True)
@click.option('-o', '--output_path', '--output-path', 'output_path', type=str, help='Output directory path',
              required=True)
@click.option('-f', '--file_id', '--file-id', 'file_id', type=str, help='File identifier', multiple=True,
              cls=MutuallyExclusiveAndRequireOption, mutually_exclusive=["start", "end"])
@click.option('-s', '--start', 'start', type=DATE_STR, help='Start date',
              cls=MutuallyExclusiveAndRequireOption, mutually_exclusive=["file_id"], requires=['end'])
@click.option('-e', '--end', 'end', type=DATE_STR, help='End date',
              cls=MutuallyExclusiveAndRequireOption, mutually_exclusive=["file_id"], requires=['start'])
@click.option('--dry-run', '--dry_run', 'dry_run', is_flag=True, help='Dry run, only shows upload candidate files')
@click.option('--file-name', 'file_name_type', help="Defines the output file's name type; [id|name].",
              type=click.Choice(['id', 'name']), default="name")
@click.option('--skip-duplicate-files', 'skip_duplicate', is_flag=True,
              help="Don't download file if the file whose name is same already exists in output directory path.")
@click.pass_context
def file_download(ctx, channel_id, output_path, file_id, start, end, dry_run, file_name_type, skip_duplicate=False):
    if file_id:
        file_iter = generate_channel_file_iter_by_id(channel_id, *file_id)
    elif start and end:
        file_iter = generate_channel_file_iter_by_period(
            channel_id, start=start, end=end)
    else:
        file_iter = generate_channel_file_iter_by_period(channel_id)

    if not Path(output_path).exists():
        Path(output_path).mkdir(parents=True)
    if dry_run:
        click.echo("[info] download files:")
        show_download_files(file_iter)
        sys.exit(SUCCESS_EXITCODE)

    download_from_datalake(channel_id, file_iter,
                           output_path, file_name_type, skip_duplicate)


def show_download_files(file_iter):
    def format_file_info(file_info):
        file_id = file_info.get('file_id')
        file_meta = file_info.get('metadata', {})
        file_name = file_meta.get('x-abeja-meta-filename')
        if file_name:
            return '{}: {}'.format(file_id, file_name)
        return file_id
    files = list(map(format_file_info, file_iter))
    click.echo('    ' + '\n    '.join(files))


# ---------------------------------------------------
# bucket command
# ---------------------------------------------------
def __click_create_datalake_bucket(f):
    f = click.option('-n', '--name', type=str, help='Name', required=False)(f)
    f = click.option('-d', '--description', type=str, help='Description', required=False)(f)
    return f


@bucket.command(name='create-bucket', help='Create DataLake bucket')
@__click_create_datalake_bucket
def create_datalake_bucket(name, description):
    __print_feature_new('This feature is an alpha stage. Invited members can use this feature. '
                        'This feature may be deprecated. Please use at your own risk.')
    try:
        r = __create_datalake_bucket(name, description)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def __create_datalake_bucket(name, description):
    parameters = {
        'name': name,
        'description': description
    }
    parameters = {k: v for k, v in parameters.items() if v is not None}

    json_data = json.dumps(parameters)
    url = "{}/buckets".format(ORGANIZATION_ENDPOINT)
    return api_post(url, json_data)


def _describe_buckets(bucket_id):
    bucket_limit = 1000
    if bucket_id == 'all':
        url = "{}/buckets?limit={}".format(
            ORGANIZATION_ENDPOINT, bucket_limit)
        r = api_get(url)
        response = {
            "created_at": r["created_at"],
            "organization_name": r["created_at"],
            "organization_id": r["organization_id"],
            "buckets": r['buckets'],
            "updated_at": r['updated_at']
        }
    else:
        url = "{}/buckets/{}".format(ORGANIZATION_ENDPOINT, bucket_id)
        response = api_get(url)
    return response


@bucket.command(name='describe-buckets', help='Describe DataLake buckets')
@click.option('-b', '--bucket_id', '--bucket-id', 'bucket_id', type=str, help='Bucket id', default='all',
              required=False)
def describe_datalake_buckets(bucket_id):
    __print_feature_new('This feature is an alpha stage. Invited members can use this feature. '
                        'This feature may be deprecated. Please use at your own risk.')
    try:
        r = _describe_buckets(bucket_id)
    except:
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def __click_bucket_file_upload(f):
    f = click.argument('path', type=str)(f)
    f = click.option('--dry-run', '--dry_run', 'dry_run', is_flag=True,
                     help='Dry run, only shows upload candidate files')(f)
    f = click.option('-r', '--recursive', 'recursive', is_flag=True, help='Recursively upload directory')(f)
    f = click.option('-m', '--metadata', '--meta-data', '--meta_data', 'metadata',
                     type=METADATA_STR, multiple=True,
                     help='Metadata to add all upload files')(f)
    f = click.option('--retry', type=click.Choice(['ask', 'no', 'force']), default='ask',
                     help="Retry to upload files if there are files couldn't be uploaded (default: 'ask')")(f)
    f = click.option('--save-result', 'result_fp', type=click.File('w', encoding='utf-8'),
                     help='Save uploaded file info as JSON at the specified path.')(f)
    return f


@bucket.command(name='upload', help='Upload file or directory')
@__click_bucket_file_upload
@click.option('-b', '--bucket_id', '--bucket-id', 'bucket_id', type=str, help='Bucket identifier', required=True)
@click.pass_context
def bucket_file_upload(ctx, path, bucket_id, recursive, dry_run, metadata,
                       retry=None, result_fp=None):
    __print_feature_new('This feature is an alpha stage. Invited members can use this feature. '
                        'This feature may be deprecated. Please use at your own risk.')
    try:
        upload_bucket_iter = __generate_upload_bucket_iter(path, recursive, dry_run)
        __bucket_file_upload(upload_bucket_iter, bucket_id, metadata, retry, result_fp)
    except InvalidPathException as e:
        click.secho("[error] invalid path {}: ".format(
            e.path), err=True, fg='red')
        sys.exit(ERROR_EXITCODE)
    except Exception:
        click.secho("[error] cannot write result", err=True, fg='red')
        sys.exit(ERROR_EXITCODE)


def __generate_upload_bucket_iter(path, recursive, dry_run):
    upload_bucket_iter = generate_upload_bucket_iter(
        path=path, recursive=recursive)

    if dry_run:
        paths = []
        for upload_bucket in upload_bucket_iter:
            paths.append(upload_bucket.path)

        click.echo("[info] upload files:")
        click.echo('    ' + '\n    '.join(sorted(paths)))
        sys.exit(SUCCESS_EXITCODE)

    return upload_bucket_iter


def __bucket_file_upload(upload_bucket_iter, bucket_id, metadata, retry=None, result_fp=None):
    result_list = [] if result_fp else None

    while True:
        (success, errors) = upload_to_bucket(bucket_id, upload_bucket_iter, metadata)

        if result_list is not None:
            for info in success:
                result_list.append({
                    'bucket_id': bucket_id,
                    'source': info.source,
                    'file_id': info.file_id
                })

        # Retry if user confirmed
        if len(errors) > 0:
            prompt = 'Upload failed for {} file(s). Do you want to retry?'.format(
                len(errors))
            if __handle_bucket_retry_option(retry, prompt, default=True):
                upload_bucket_iter = iter(
                    [UploadBucketFile(key=e.file_id, path=e.source, metadata=e.metadata) for e in errors])
                continue

        break

    # Write results as JSON if needed
    if result_list is not None:
        assert result_fp
        json.dump(result_list, result_fp)


def __handle_bucket_retry_option(retry_option, prompt_msg, **confirm_opts):
    if retry_option == 'ask':
        return click.confirm(prompt_msg, confirm_opts)
    else:
        return (retry_option == 'force')


@bucket.command(name='create-and-upload', help='Create DataLake bucket and upload files')
@__click_create_datalake_bucket
@__click_bucket_file_upload
@click.pass_context
def create_datalake_bucket_upload_files(
        ctx, path, name, description, recursive, dry_run, metadata, retry=None, result_fp=None):
    __print_feature_new('This feature is an alpha stage. Invited members can use this feature. '
                        'This feature may be deprecated. Please use at your own risk.')
    upload_bucket_iter = __generate_upload_bucket_iter(path, recursive, dry_run)
    r = __create_datalake_bucket(name, description)
    click.echo(json_output_formatter(r))
    __bucket_file_upload(upload_bucket_iter, r['bucket']['bucket_id'], metadata, retry, result_fp)


@bucket.command(name='download', help='Download files')
@click.option('-b', '--bucket_id', '--bucket-id', 'bucket_id', type=str, help='Bucket identifier', required=True)
@click.option('-o', '--output_path', '--output-path', 'output_path', type=str, help='Output directory path',
              required=True)
@click.option('-f', '--file_id', '--file-id', 'file_id', type=str, help='File identifier', multiple=True)
@click.option('--dry-run', '--dry_run', 'dry_run', is_flag=True, help='Dry run, only shows upload candidate files')
@click.pass_context
def bucket_file_download(ctx, bucket_id, output_path, file_id, dry_run):
    __print_feature_new('This feature is an alpha stage. Invited members can use this feature. '
                        'This feature may be deprecated. Please use at your own risk.')
    if file_id:
        file_iter = generate_bucket_file_iter_by_id(bucket_id, *file_id)
    else:
        file_iter = generate_bucket_file_iter(bucket_id)

    if not Path(output_path).exists():
        Path(output_path).mkdir(parents=True)
    if dry_run:
        click.echo("[info] download files:")
        show_download_bucket_files(file_iter)
        sys.exit(SUCCESS_EXITCODE)

    download_from_bucket(bucket_id, file_iter, output_path)


def show_download_bucket_files(file_iter):
    def format_file_info(file_info):
        file_id = file_info.get('file_id')
        return file_id
    files = list(map(format_file_info, file_iter))
    click.echo('    ' + '\n    '.join(files))

# ---------------------------------------------------
# util
# ---------------------------------------------------


def _json_loads(r):
    try:
        r = json.loads(r)
    except JSONDecodeError as e:
        click.echo('{} {} {} {}'.format(
            "[error]", date, "error message =>", e), err=True)

    return r


def _json_file_load(path):
    with open(path, 'r') as f:
        json_data = json.load(f)
    return json_data


def __print_feature_deprecation(additional: str = None):
    message = 'This feature has been officially deprecated. ' \
              'The feature continues to be available for a while, ' \
              'but it is already scheduled for shutdown.'
    if additional:
        message = '{} {}'.format(message, additional)
    print(message, file=sys.stderr)


def __print_feature_renewal(additional: str = None):
    message = 'This feature has been renewed.'
    if additional:
        message = '{} {}'.format(message, additional)
    print(message, file=sys.stderr)


def __print_feature_new(additional: str = None):
    message = 'This feature has been newly added.'
    if additional:
        message = '{} {}'.format(message, additional)
    print(message, file=sys.stderr)


# add subcommands
main.add_command(training)
main.add_command(registry)
main.add_command(startapp)
main.add_command(dataset)
main.add_command(dx_template)
main.add_command(labs)


if __name__ == '__main__':
    main()
