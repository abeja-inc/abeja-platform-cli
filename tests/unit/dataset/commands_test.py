import json

from click.testing import CliRunner
import pytest
import requests_mock
from ruamel.yaml import YAML

from abejacli.config import ORGANIZATION_ENDPOINT, ABEJA_API_URL
from abejacli.dataset.commands import (
    create_dataset,
    delete_dataset,
    describe_datasets,
    dataset_import_from_datalake,
    describe_dataset_items,
    delete_dataset_item,
    create_dataset_item,
    update_dataset_item
)

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_CONFIG_ORG_NAME = 'test-inc'
TEST_CONFIG = {
    'abeja-platform-user': 'user-{}'.format(TEST_CONFIG_USER_ID),
    'personal-access-token': TEST_CONFIG_TOKEN,
    'organization-name': TEST_CONFIG_ORG_NAME
}
import tempfile

yaml = YAML()


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def req_mock(request):
    m = requests_mock.Mocker()
    m.start()
    request.addfinalizer(m.stop)
    return m


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--name', 'dummy_dataset', '--type', 'classification'],
         {},
         {
             'name': 'dummy_dataset',
             'type': 'classification',

        }),
    ]
)
def test_create_dataset(req_mock, runner, cmd, additional_config, expected_payload):
    url = "{}/datasets".format(ORGANIZATION_ENDPOINT)
    props = {
        "categories": [
            {
                "labels": [
                    {
                        "label_id": 1,
                        "label": "dog"
                    },
                    {
                        "label_id": 2,
                        "label": "cat"
                    },
                    {
                        "label_id": 3,
                        "label": "others"
                    }
                ],
                "category_id": 1,
                "name": "cats_dogs"
            }
        ]
    }
    expected_payload = {**expected_payload, "props": props}

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    with tempfile.NamedTemporaryFile('w') as fp:
        filename = fp.name
        cmd += ['--props', filename]
        fp.write(json.dumps(props))
        fp.seek(0)
        r = runner.invoke(create_dataset, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789'],
         {},
         {}
         ),
    ]
)
def test_delete_dataset(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    url = "{}/datasets/{}".format(ORGANIZATION_ENDPOINT, testing_dataset_id)

    def match_request_text(request):
        return request.url == url

    req_mock.register_uri(
        'DELETE', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    r = runner.invoke(delete_dataset, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789'],
         {},
         {}),
        ([],
         {},
         {}),
    ]
)
def test_descripe_dataset(req_mock, runner, cmd, additional_config, expected_payload):
    if len(cmd) == 0:
        url = "{}/datasets".format(ORGANIZATION_ENDPOINT)
    else:
        testing_dataset_id = '123456789'
        url = "{}/datasets/{}".format(ORGANIZATION_ENDPOINT, testing_dataset_id)

    def match_request_text(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    r = runner.invoke(describe_datasets, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789', '--channel_id', '987654321'],
         {},
         {}
         ),
        (['--dataset_id', '123456789', '--channel_id', '987654321', '--max-size-for-label', '100'],
         {},
         {}
         ),
    ]
)
def test_dataset_import_from_datalake(req_mock, runner, cmd, additional_config, expected_payload):
    # TODO: Need fix after cli is fixed.
    testing_dataset_id = '123456789'
    testing_channel_id = '987654321'
    url = '{}/datasets/{}/items'.format(ORGANIZATION_ENDPOINT, testing_dataset_id)
    datalake_url = '{}/channels/{}?items_per_page=100'.format(ABEJA_API_URL, testing_channel_id)

    expected_payload_datalake = {
        "files": [
            {
                "file_id": "20180510T065023-5875ca81-59cc-47bd-9b82-38f5ce15fd68",
                "download_url": "https://abeja-datalake.s3.amazonaws.com/xxxx-xxxxxxxx/20180510/XXXXYYYYZZZZ",
                "url_expires_on": "2018-05-10T07:50:23+00:00",
                "uploaded_at": "2018-05-10T07:27:46+00:00",
                "metadata": {
                    "x-abeja-meta-label": "dog",
                    "x-abeja-meta-label_id": "1",
                    "x-abeja-meta-filename": "test.jpg",
                    "x-abeja-sys-meta-validation-status": "FAILURE",
                    "x-abeja-sys-meta-validation-schema-version": "2",
                    "x-abeja-sys-meta-validation-schema-id": "1466430869682",
                    "x-abeja-sys-meta-validation-error": []
                },
                "content_type": "image/jpeg"
            }
        ]
    }

    def match_request_text_datalake(request):
        return request.url == datalake_url

    def match_request_text(request):
        req = request.json()
        assert req[0]['source_data'][0]['data_type'] == expected_payload_datalake['files'][0]['content_type']
        assert req[0]['attributes']['classification'][0]['label'] == \
            expected_payload_datalake['files'][0]['metadata']['x-abeja-meta-label']
        return request.url == url

    req_mock.register_uri(
        'GET', datalake_url,
        json=expected_payload_datalake,
        additional_matcher=match_request_text_datalake
    )
    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text
    )
    r = runner.invoke(dataset_import_from_datalake, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789'],
         {},
         {}),
    ]
)
def test_descripe_dataset_items(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    url = "{}/datasets/{}/items".format(ORGANIZATION_ENDPOINT, testing_dataset_id)
    token_url = "{}/datasets/{}/items?next_page_token=nnnn".format(ORGANIZATION_ENDPOINT, testing_dataset_id)

    first_response = {
        "items": [{"name": "xxx"}, {"name": "yyy"}],
        "next_page_token": "nnnn",
        "total_count": 3
    }

    second_response = {
        "items": [{"name": "zzz"}],
        "next_page_token": None,
        "total_count": 3
    }

    def match_request_text_first(request):
        return request.url == url

    def match_request_text_second(request):
        return request.url == token_url

    req_mock.register_uri(
        'GET', url,
        json=first_response,
        additional_matcher=match_request_text_first)

    req_mock.register_uri(
        'GET', token_url,
        json=second_response,
        additional_matcher=match_request_text_second)

    r = runner.invoke(describe_dataset_items, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789', '-q', 'label:test'],
         {},
         {}),
    ]
)
def test_descripe_dataset_items_with_query(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    test_q = 'label:test'
    url = "{}/datasets/{}/items?q={}".format(ORGANIZATION_ENDPOINT, testing_dataset_id, test_q)
    token_url = "{}/datasets/{}/items?next_page_token=nnnn".format(ORGANIZATION_ENDPOINT, testing_dataset_id)

    first_response = {
        "items": [{"name": "xxx"}, {"name": "yyy"}],
        "next_page_token": "nnnn",
        "total_count": 3
    }

    second_response = {
        "items": [{"name": "zzz"}],
        "next_page_token": None,
        "total_count": 3
    }

    def match_request_text_first(request):
        return request.url == url

    def match_request_text_second(request):
        return request.url == token_url

    req_mock.register_uri(
        'GET', url,
        json=first_response,
        additional_matcher=match_request_text_first)

    req_mock.register_uri(
        'GET', token_url,
        json=second_response,
        additional_matcher=match_request_text_second)

    r = runner.invoke(describe_dataset_items, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789', '--dataset_item_id', '987654321'],
         {},
         {}),
    ]
)
def test_descripe_dataset_item(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    testing_dataset_item_id = '987654321'
    url = "{}/datasets/{}/items/{}".format(ORGANIZATION_ENDPOINT, testing_dataset_id, testing_dataset_item_id)

    response = {"name": "xxx"}

    def match_request_text(request):
        return True
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json=response,
        additional_matcher=match_request_text)

    r = runner.invoke(describe_dataset_items, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789', '--dataset_item_id', '987654321'],
         {},
         {}
         ),
    ]
)
def test_delete_dataset_item(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    testing_dataset_item_id = '987654321'
    url = "{}/datasets/{}/items/{}".format(ORGANIZATION_ENDPOINT, testing_dataset_id, testing_dataset_item_id)

    def match_request_text(request):
        return request.url == url

    req_mock.register_uri(
        'DELETE', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    r = runner.invoke(delete_dataset_item, cmd)
    print(r.output)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789'],
         {},
         {}
         ),
    ]
)
def test_create_dataset_item(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    url = "{}/datasets/{}/items".format(ORGANIZATION_ENDPOINT, testing_dataset_id)
    payload = {
        "source_data": [
            {
                "data_type": "images/jpeg",
                "data_uri": "datalake://1200000000000/20170815T044617-f20dde80-1e3b-4496-bc06-1b63b026b872",
                "height": 500,
                "width": 200
            },
            {
                "data_type": "images/jpeg",
                "data_uri": "datalake://1200000000000/20170815T044617-f20dde80-1e3b-4496-bc06-cccccccccccc",
                "height": 1000,
                "width": 500
            }
        ],
        "attributes": {
            "classification": [
                {
                    "category_id": 1,
                    "label_id": 1
                }
            ],
            "detection": [
                {
                    "category_id": 1,
                    "label_id": 2,
                    "rect": {
                        "xmin": 22,
                        "ymin": 145,
                        "xmax": 140,
                        "ymax": 220
                    }
                }
            ]
        },
        "custom_format": {
            "anything": "something"
        }
    }
    expected_payload = payload

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'POST', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    with tempfile.NamedTemporaryFile('w', suffix=".json") as fp:
        filename = fp.name
        cmd += ['--payload', filename]
        fp.write(json.dumps(payload))
        fp.seek(0)
        r = runner.invoke(create_dataset_item, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception

    with tempfile.NamedTemporaryFile('w', suffix=".yml") as fp:
        filename = fp.name
        cmd += ['--payload', filename]
        yaml.dump(payload, stream=fp)
        fp.seek(0)
        r = runner.invoke(create_dataset_item, cmd)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception


@pytest.mark.parametrize(
    'cmd,additional_config,expected_payload',
    [
        (['--dataset_id', '123456789', '--dataset_item_id', '987654321'],
         {},
         {}
         ),
    ]
)
def test_update_dataset_item(req_mock, runner, cmd, additional_config, expected_payload):
    testing_dataset_id = '123456789'
    testing_dataset_item_id = '987654321'
    url = "{}/datasets/{}/items/{}".format(ORGANIZATION_ENDPOINT, testing_dataset_id, testing_dataset_item_id)
    payload = {
        "attributes": {
            "classification": [
                {
                    "category_id": 1,
                    "label_id": 1
                }
            ]
        }
    }
    expected_payload = payload

    def match_request_text(request):
        return json.loads(request.text) == expected_payload

    req_mock.register_uri(
        'PUT', url,
        json=expected_payload,
        additional_matcher=match_request_text)

    with tempfile.NamedTemporaryFile('w', suffix=".json") as fp:
        filename = fp.name
        cmd += ['--payload', filename]
        fp.write(json.dumps(payload))
        fp.seek(0)
        r = runner.invoke(update_dataset_item, cmd)
    print(r.output)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception

    with tempfile.NamedTemporaryFile('w', suffix=".yml") as fp:
        filename = fp.name
        cmd += ['--payload', filename]
        yaml.dump(payload, stream=fp)
        fp.seek(0)
        r = runner.invoke(update_dataset_item, cmd)
    print(r.output)
    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception
