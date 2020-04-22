import json
import os
import sys

import click
from ruamel.yaml import YAML

from abejacli.common import json_output_formatter
from abejacli.config import ERROR_EXITCODE, ORGANIZATION_ENDPOINT
from abejacli.configuration import __ensure_configuration_exists
from abejacli.dataset import import_dataset_from_datalake
from abejacli.logger import get_logger
from abejacli.session import api_delete, api_get, api_post, api_put

logger = get_logger()
yaml = YAML()


@click.group(help='Dataset operation commands')
@click.pass_context
def dataset(ctx):
    __ensure_configuration_exists(ctx)


@dataset.command(name='create-dataset', help='Create dataset channel')
@click.option('-n', '--name', type=str, help='Display name', required=True)
@click.option('-t', '--type', 'dataset_type', type=str,
              help='Type of dataset ex. classification, detection', required=True)
@click.option('-p', '--props', type=click.File('r'),
              help='Path to the json file of property to validate annotation attributes', required=True)
def create_dataset(name, dataset_type, props):
    try:
        props = props.read()
        props = json.loads(props)
        parameters = {
            'name': name,
            'type': dataset_type,
            'props': props
        }
        json_data = json.dumps(parameters)
        url = "{}/datasets".format(ORGANIZATION_ENDPOINT)
        r = api_post(url, json_data)
    except Exception as e:
        logger.error('create-dataset failed: {}'.format(e))
        click.echo('create-dataset failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@dataset.command(name='delete-dataset', help='Delete dataset')
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str, help='Dataset id', required=True)
def delete_dataset(dataset_id):
    try:
        url = '{}/datasets/{}'.format(ORGANIZATION_ENDPOINT, dataset_id)
        r = api_delete(url)
    except Exception as e:
        logger.error('delete-dataset failed: {}'.format(e))
        click.echo('delete-dataset failed.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


@dataset.command(name='describe-datasets', help='Describe dataset')
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str,
              help='Dataset id', default='all', required=False)
def describe_datasets(dataset_id):
    try:
        url = "{}/datasets".format(ORGANIZATION_ENDPOINT) if dataset_id == 'all' \
            else "{}/datasets/{}".format(ORGANIZATION_ENDPOINT, dataset_id)
        r = api_get(url)
    except Exception as e:
        logger.error('describe-dataset failed: {}'.format(e))
        click.echo('describe-dataset failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


def _get_all_dataset_items(base_url, q):
    next_page_token = None
    items = []
    while True:
        if q is not None and next_page_token is None:
            url = "{}?q={}".format(base_url, q)
        elif next_page_token:
            url = "{}?next_page_token={}".format(base_url, next_page_token)
        else:
            url = base_url
        r = api_get(url)
        items += r['items']
        if r['next_page_token'] is None:
            return {
                "items": items,
                "total_count": r['total_count']
            }
        next_page_token = r['next_page_token']


@dataset.command(name='describe-dataset-items', help='Describe dataset items')
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str,
              help='Dataset id', required=True)
@click.option('-i', '--dataset_item_id', '--dataset-item-id', 'dataset_item_id', type=str,
              help='Dataset item id', default=None, required=False)
@click.option('-q', 'q', type=str,
              help='query to filter the result. i.e. q=label_id:1 AND tag:v1', default=None, required=False)
def describe_dataset_items(dataset_id, dataset_item_id, q):
    if dataset_item_id and q:
        click.echo('describe-dataset-items failed: q cannot be specified when dataset-item-id is specified')
        sys.exit(ERROR_EXITCODE)
    try:
        if dataset_item_id is None:
            url = "{}/datasets/{}/items".format(ORGANIZATION_ENDPOINT, dataset_id)
            res = _get_all_dataset_items(url, q)
        else:
            url = "{}/datasets/{}/items/{}".format(ORGANIZATION_ENDPOINT, dataset_id, dataset_item_id)
            res = api_get(url)
    except Exception as e:
        logger.error('describe-dataset-items failed: {}'.format(e))
        click.echo('describe-dataset-items failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(res))


@dataset.command(name='delete-dataset-item', help='Delete dataset item')
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str, help='Dataset id', required=True)
@click.option('-i', '--dataset_item_id', '--dataset-item-id', 'dataset_item_id', type=str,
              help='Dataset item id', required=True)
def delete_dataset_item(dataset_id, dataset_item_id):
    try:
        url = '{}/datasets/{}/items/{}'.format(ORGANIZATION_ENDPOINT, dataset_id, dataset_item_id)
        r = api_delete(url)
    except Exception as e:
        logger.error('delete-dataset-item failed: {}'.format(e))
        click.echo('delete-dataset-item failed.')
        sys.exit(ERROR_EXITCODE)

    click.echo(json_output_formatter(r))


@dataset.command(name='create-dataset-item', help='Create dataset item')
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str, help='Dataset id', required=True)
@click.option('-p', '--payload', '_payload', type=click.File('r'),
              help='Path to the json or yaml file for property that validates annotation attribute', required=True)
def create_dataset_item(dataset_id, _payload):
    ext = os.path.splitext(_payload.name)[-1]
    try:
        if ext in ['.json']:
            payload = json.loads(_payload.read())
        elif ext in ['.yml', '.yaml']:
            payload = yaml.load(_payload.read())
        else:
            click.echo('Invalid payload file format. .json .yml .yaml is acceptable')
            sys.exit(ERROR_EXITCODE)
        url = "{}/datasets/{}/items".format(ORGANIZATION_ENDPOINT, dataset_id)
        r = api_post(url, json.dumps(payload))
    except Exception as e:
        logger.error('create-dataset-item failed: {}'.format(e))
        click.echo('create-dataset-item failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@dataset.command(name='update-dataset-item', help='Update dataset item')
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str, help='Dataset id', required=True)
@click.option('-i', '--dataset_item_id', '--dataset-item-id', 'dataset_item_id', type=str,
              help='Dataset item id', required=True)
@click.option('-p', '--payload', '_payload', type=click.File('r'),
              help='Path to the json or yaml file for property that validates annotation attribute', required=True)
def update_dataset_item(dataset_id, dataset_item_id, _payload):
    ext = os.path.splitext(_payload.name)[-1]
    try:
        if ext in ['.json']:
            payload = json.loads(_payload.read())
        elif ext in ['.yml', '.yaml']:
            payload = yaml.load(_payload.read())
        else:
            click.echo('Invalid payload file format. .json .yml .yaml is acceptable')
            sys.exit(ERROR_EXITCODE)
        url = "{}/datasets/{}/items/{}".format(ORGANIZATION_ENDPOINT, dataset_id, dataset_item_id)
        r = api_put(url, json.dumps(payload))
    except Exception as e:
        logger.error('update-dataset-item failed: {}'.format(e))
        click.echo('update-dataset-item failed.')
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))


@dataset.command(name='import-from-datalake')
@click.option('-c', '--channel_id', '--channel-id', 'channel_id', type=str, help='DataLake channel id', required=True)
@click.option('-d', '--dataset_id', '--dataset-id', 'dataset_id', type=str, help='Dataset id', required=True)
@click.option('--property-metadata-key', 'property_metadata_keys', type=str, multiple=True,
              help='DataLake metadata that is used as property of dataset. label and label_id is used as default',
              default=['label', 'label_id'])
@click.option('--category_id', '--category-id', 'category_id', type=str,
              help='category id of the property. default is 1', default=1)
@click.option('--type', '_type', type=str, help='dataset type. default is classification', default="classification")
@click.option('--max-size-for-label', '_max', type=int, required=False,
              help='Max number of items for each labels that is uploaded to dataset API', default=None)
def dataset_import_from_datalake(channel_id, dataset_id, property_metadata_keys, category_id, _type, _max):
    """Imports dataset items from datalake.
    You can import dataset items from a datalake channel with properties.
    You have to prepare a datalake channel that has files you want to use as dataset.
    `x-abeja-meta-label` and `x-abeja-meta-label_id` is used as properties by default.
    For example, `cat00001.jpg` with `x-abeja-meta-label:cat`
    and `x-abeja-meta-label_id:1` is registered to a dataset with label `cat` and label_id 1.
    You can specify the multiple metadata names for properties with `--property-metadata-key` option.
    """
    try:
        r = import_dataset_from_datalake(
            channel_id, dataset_id, property_metadata_keys,
            category_id, _type, _max
        )
    except Exception as e:
        logger.exception(e)
        sys.exit(ERROR_EXITCODE)
    click.echo(json_output_formatter(r))
