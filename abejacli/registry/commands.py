import datetime
import json
import sys

import click

import abejacli.configuration
import abejacli.version
from abejacli.common import json_output_formatter
from abejacli.config import CONFIG, ERROR_EXITCODE, ORGANIZATION_ENDPOINT
from abejacli.logger import get_logger
from abejacli.session import api_delete, api_get, api_get_data, api_post

__version__ = abejacli.version.VERSION
date = datetime.datetime.today()
logger = get_logger()


@click.group(help='Registry repository commands')
@click.pass_context
def registry(ctx):
    if not CONFIG:
        click.echo(
            "[error] there is no configuration, execute 'abeja config init'")
        ctx.abort()
        return


# ---------------------------------------------------
# registry repository command
# ---------------------------------------------------
@registry.command(name='create-repository', help='Create registry repository')
@click.option('-n', '--name', type=str, help='Registry repository name', required=True)
@click.option('-d', '--description', 'description', type=str,
              help='Repository repository details', default=None, required=False)
def create_repository(name, description):
    try:
        r = _create_repository(name, description)
    except Exception as e:
        logger.error('create-repository failed: {}'.format(e))
        click.echo('create-repository failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _create_repository(name, description):
    parameters = {
        'name': name,
        'description': description
    }

    json_data = json.dumps(parameters)
    url = "{}/registry/repositories".format(ORGANIZATION_ENDPOINT)
    r = api_post(url, json_data)
    return r


@registry.command(name='delete-repository', help='Delete registry repository')
@click.option('-d', '--repository_id', '--repository-id', 'repository_id', type=str, help='Repository id',
              required=True)
def delete_repository(repository_id):
    try:
        r = _delete_repository(repository_id)
    except Exception as e:
        logger.error('delete-repository failed: {}'.format(e))
        click.echo('delete-repository failed.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


def _delete_repository(repository_id):
    url = '{}/registry/repositories/{}'.format(ORGANIZATION_ENDPOINT, repository_id)
    r = api_delete(url)
    return r


@registry.command(name='describe-repositories', help='Describe registry repository')
@click.option('-l', '--limit', 'limit', type=int,
              help='Number of pagings', default=None, required=False)
@click.option('-o', '--offset', 'offset', type=int,
              help='Paging start index', default=None, required=False)
def describe_repositories(limit, offset):
    try:
        r = _describe_repositories(limit, offset)
    except Exception as e:
        logger.error('describe-repositories failed: {}'.format(e))
        click.echo('describe-repositories failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_repositories(limit, offset):
    if limit is not None and offset is not None:
        params = {
            'limit': limit,
            'offset': offset
        }
    elif limit is not None and offset is None:
        params = {
            'limit': limit
        }
    elif limit is None and offset is not None:
        params = {
            'offset': offset
        }
    else:
        params = {}
    url = "{}/registry/repositories".format(ORGANIZATION_ENDPOINT)
    r = api_get_data(url, params)
    return r


@registry.command(name='describe-repository', help='Describe specified repository')
@click.option('-d', '--repository_id', '--repository-id', 'repository_id', type=str,
              help='Repository id', required=True)
def describe_repository(repository_id):
    try:
        r = _describe_repository(repository_id)
    except Exception as e:
        logger.error('describe-repository failed: {}'.format(e))
        click.echo('describe-repository failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_repository(repository_id):
    url = "{}/registry/repositories/{}".format(ORGANIZATION_ENDPOINT, repository_id)
    r = api_get(url)
    return r


@registry.command(name='describe-repository-tags', help='Describe specified repository tags')
@click.option('-d', '--repository_id', '--repository-id', 'repository_id', type=str,
              help='Repository id', required=True)
@click.option('-l', '--limit', 'limit', type=int,
              help='Number of pagings', default=None, required=False)
@click.option('-o', '--offset', 'offset', type=int,
              help='Paging start index', default=None, required=False)
def describe_repository_tags(repository_id, limit, offset):
    try:
        r = _describe_repository_tags(repository_id, limit, offset)
    except Exception as e:
        logger.error('describe-repository-tags failed: {}'.format(e))
        click.echo('describe-repository-tags failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _describe_repository_tags(repository_id, limit, offset):
    if limit is not None and offset is not None:
        params = {
            'limit': limit,
            'offset': offset
        }
    elif limit is not None and offset is None:
        params = {
            'limit': limit
        }
    elif limit is None and offset is not None:
        params = {
            'offset': offset
        }
    else:
        params = {}
    url = "{}/registry/repositories/{}/tags".format(ORGANIZATION_ENDPOINT, repository_id)
    r = api_get_data(url, params)
    return r
