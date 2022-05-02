# coding: utf-8

import json
from collections import defaultdict

from abejacli.config import DATASET_CHUNK_SIZE, ORGANIZATION_ENDPOINT
from abejacli.datalake import generate_channel_file_iter_by_period
from abejacli.logger import get_logger
from abejacli.session import api_post

logger = get_logger()


def create_request_element(channel_id, file_info, property_metadata_keys, category_id, _type):
    """
    create dataset item from datalake file

    :param channel_id:
    :param file_id:
    :param file_info:
    :param property_metadata_keys:
    :param category_id:
    :param _type:
    :return:
    """
    file_id = file_info.get('file_id')
    file_metadata = file_info.get('metadata')
    properties = {}
    for key in property_metadata_keys:
        metadata_name = 'x-abeja-meta-{}'.format(key)
        if metadata_name in file_metadata:
            properties[key] = file_metadata[metadata_name]
        else:
            print('[Warning] Metadata {} does not exist. Skipping'.format(metadata_name))

    data_uri = 'datalake://{}/{}'.format(channel_id, file_id)

    data = {
        'source_data': [
            {
                'data_uri': data_uri,
                'data_type': file_info['content_type']
            }
        ],
        'attributes': {
            _type: [
                {
                    "category_id": category_id,
                    **properties
                }
            ]
        }
    }
    return data


def filter_items_by_max_size(dataset_items, max_size_for_label):
    """
    trim dataset items by max size for each lable value

    :param dataset_items:
    :param max_size:
    :return:
    """
    items_by_labels = defaultdict(list)
    # group by label value
    for item in dataset_items:
        label = item['attributes']['classification'][0]['label']
        items_by_labels[label].append(item)
    filtered_items = []
    for k, v in items_by_labels.items():
        items_size = len(v)
        # trim by max_size
        upload_size = items_size if max_size_for_label is None else min(
            max_size_for_label, items_size)
        if upload_size < items_size:
            logger.info('[Warning] Skipping {} items for label:{} to register'.format(
                items_size - upload_size, k))
        filtered_items += v[:upload_size]
    return filtered_items


def register_dataset_items(dataset_id, items):
    """
    execute dataset api to registr dataset items

    :param dataset_id:
    :param items:
    :return:
    """
    url = '{}/datasets/{}/items'.format(ORGANIZATION_ENDPOINT, dataset_id)

    def _chunked(items, n):
        for i in range(0, len(items), n):
            yield items[i:i + n]

    # max number of items for add items should is 500 (by default)
    for chunked_items in _chunked(items, DATASET_CHUNK_SIZE):
        api_post(url, json.dumps(chunked_items))


def register_dataset_items_from_datalake(
    dataset_id, channel_id, property_metadata_keys, category_id, _type, max_size_for_label
):
    """
    register datasets from datalake channel

    :param dataset_id: target dataset id
    :param channel_id: target channel
    :param property_metadata_keys: metadata key which property value is stored
    :param category_id: category_id of dataset item to register
    :param _type: type of dataset item like classification.
    :param max_size_for_label: max size of dataset items for each label value
    :return:
    """
    print('Getting data from datalake....')
    file_iter = generate_channel_file_iter_by_period(channel_id)
    dataset_items = [
        create_request_element(channel_id, file_info, property_metadata_keys, category_id, _type)
        for file_info in file_iter
    ]
    print('Registering dataset items....')
    if max_size_for_label:
        dataset_items = filter_items_by_max_size(
            dataset_items, max_size_for_label)
    register_dataset_items(dataset_id, dataset_items)
    return {
        'result': 'success',
        'dataset_items': len(dataset_items),
        'dataset_id': dataset_id,
        'channel_id': channel_id
    }


def import_dataset_from_datalake(channel_id, dataset_id, property_metadata_keys, category_id, _type, _max):
    return register_dataset_items_from_datalake(
        dataset_id, channel_id, property_metadata_keys, category_id, _type, _max
    )
