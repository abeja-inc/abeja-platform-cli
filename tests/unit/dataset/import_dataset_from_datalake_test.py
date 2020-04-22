"""Tests related to ``model`` and ``deployment``"""
import math
import random
from unittest import TestCase

import requests_mock
from click.testing import CliRunner

from abejacli.config import (ABEJA_API_URL, DATASET_CHUNK_SIZE,
                             ORGANIZATION_ENDPOINT)
from abejacli.dataset import (create_request_element, filter_items_by_max_size,
                              import_dataset_from_datalake,
                              register_dataset_items)

DATASET_ID = 1
CHANNEL_ID = '1111111111111'
FILE_ID = '20180306T062909-e5d12928-36b6-4b84-bb33-e3e298034550'
METADATA_LABEL_KEY = 'label'
METADATA_LABEL_VALUE = 'cat'
METADATA_LABEL_ID_KEY = 'label_id'
METADATA_LABEL_ID_VALUE = '1'
CATEGORY_ID = 1

DATALAKE_FILE_RESPONSE = {
    'url_expires_on': '2018-03-15T09:04:28+00:00',
    'uploaded_at': '2018-03-06T06:29:09+00:00',
    'metadata': {
        'x-abeja-meta-{}'.format(METADATA_LABEL_KEY): METADATA_LABEL_VALUE,
        'x-abeja-meta-{}'.format(METADATA_LABEL_ID_KEY): METADATA_LABEL_ID_VALUE,
        'x-abeja-meta-filename': '000000060482.jpg'
    },
    'file_id': FILE_ID,
    'download_uri': 'https://abeja-datalake-dev.s3.amazonaws.com/e498-1379786645868/20180306/'
                    '062909-e5d12928-36b6-4b84-bb33-e3e298034550?AWSAccessKeyId=ASIAJUSKQAOZ67OHU3NQ&Signature=xxxx',
    'content_type': 'image/jpeg'
}

DATASET_ITEM_RESPONSE = {
    'dataset_id': DATASET_ID,
    'source_data': [
        {
            'data_type': 'image/jpeg',
            'data_uri': 'datalake://1234567890123/20170815T044617-f20dde80-1e3b-4496-bc06-1b63b026b872'
        }
    ],
    'attributes': {
        'classification': [
            {
                'category_id': CATEGORY_ID,
                METADATA_LABEL_KEY: METADATA_LABEL_VALUE,
                METADATA_LABEL_ID_KEY: METADATA_LABEL_ID_VALUE
            }
        ]
    }
}


class DatasetImportFromDatalakeTest(TestCase):

    def setUp(self):
        self.runner = CliRunner()

    def test_create_request_element(self):
        expected = {
            'source_data': [{
                'data_uri': 'datalake://{}/{}'.format(CHANNEL_ID, FILE_ID),
                'data_type': 'image/jpeg'
            }],
            'attributes': {
                'classification': [
                    {
                        'category_id': CATEGORY_ID,
                        METADATA_LABEL_KEY: METADATA_LABEL_VALUE,
                        METADATA_LABEL_ID_KEY: METADATA_LABEL_ID_VALUE
                    }
                ]
            }
        }
        actual = create_request_element(
            CHANNEL_ID, DATALAKE_FILE_RESPONSE,
            [METADATA_LABEL_KEY, METADATA_LABEL_ID_KEY],
            CATEGORY_ID, 'classification'
        )
        self.assertEqual(actual, expected)

    @requests_mock.Mocker()
    def test_register_dataset_items(self, mock):
        url = '{}/datasets/{}/items'.format(ORGANIZATION_ENDPOINT, DATASET_ID)
        mock.register_uri('POST', url, json=DATASET_ITEM_RESPONSE)

        item_count = 1501
        dataset_items = [DATASET_ITEM_RESPONSE for _ in range(item_count)]
        register_dataset_items(DATASET_ID, dataset_items)

        expected_request_count = math.ceil(item_count / DATASET_CHUNK_SIZE)
        self.assertEqual(expected_request_count, len(mock.request_history))

    def test_filter_items_by_max_size(self):

        def generate_labeled_dataset_item(label):
            return {
                'source_data': [{
                    'data_uri': 'datalake://{}/{}'.format(CHANNEL_ID, FILE_ID),
                    'data_type': 'image/jpeg'
                }],
                'attributes': {
                    'classification': [
                        {
                            'label': label,
                        }
                    ]
                }
            }

        label1 = '1'
        label1_count = 10
        label1_items = [generate_labeled_dataset_item(
            label1) for _ in range(label1_count)]

        label2 = '2'
        label2_count = 11
        label2_items = [generate_labeled_dataset_item(
            label2) for _ in range(label2_count)]

        label3 = '3'
        label3_count = 9
        label3_items = [generate_labeled_dataset_item(
            label3) for _ in range(label3_count)]

        dataset_items = label1_items + label2_items + label3_items
        random.shuffle(dataset_items)
        filtered_dataset_items = filter_items_by_max_size(dataset_items, 10)

        self.assertEqual(10, sum(label1 == i['attributes']['classification'][0]['label']
                                 for i in filtered_dataset_items))
        self.assertEqual(10, sum(label2 == i['attributes']['classification'][0]['label']
                                 for i in filtered_dataset_items))
        self.assertEqual(9, sum(label3 == i['attributes']['classification'][0]['label']
                                for i in filtered_dataset_items))

    @requests_mock.Mocker()
    def test_register_dataset_items_from_datalake(self, mock):
        url = '{}/channels/{}'.format(ABEJA_API_URL, CHANNEL_ID)
        file_list_response = {
            'files': [
                DATALAKE_FILE_RESPONSE,
                DATALAKE_FILE_RESPONSE
            ]
        }
        mock.register_uri('GET', url, json=file_list_response)
        url = '{}/datasets/{}/items'.format(ORGANIZATION_ENDPOINT, DATASET_ID)
        mock.register_uri('POST', url, json=DATASET_ITEM_RESPONSE)

        result = import_dataset_from_datalake(
            CHANNEL_ID, DATASET_ID,
            [METADATA_LABEL_KEY, METADATA_LABEL_ID_KEY], CATEGORY_ID,
            'classification', 30
        )
        expected = {
            'result': 'success',
            'dataset_items': len(file_list_response['files']),
            'dataset_id': DATASET_ID,
            'channel_id': CHANNEL_ID
        }
        self.assertEqual(expected, result)
