
from click.testing import CliRunner
import pytest
import requests_mock

from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.run import describe_datalake_channels

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_CONFIG_ORG_NAME = 'test-inc'
TEST_CONFIG = {
    'abeja-platform-user': 'user-{}'.format(TEST_CONFIG_USER_ID),
    'personal-access-token': TEST_CONFIG_TOKEN,
    'organization-name': TEST_CONFIG_ORG_NAME
}


MOCK_DATALAKE_CHANNELS_RESPONSE = {
    "updated_at": "2019-12-05T01:55:39Z",
    "organization_name": "xxx-inc",
    "organization_id": "99999",
    "created_at": "2017-04-27T08:26:11Z",
    "channels": [
        {
            "channel_id": "1102917837827",
            "name": "example-channel",
            "description": "test channel",
            "storage_type": "datalake",
            "security_method": "organization",
            "created_at": "2017-04-27T07:49:30Z",
            "updated_at": "2018-02-14T03:14:05Z"
        }
    ]
}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def req_mock(request):
    m = requests_mock.Mocker()
    m.start()
    request.addfinalizer(m.stop)
    return m


# Channels

def test_describe_channels(req_mock, runner):
    url = "{}/channels?limit=1000&filter_archived=exclude_archived".format(ORGANIZATION_ENDPOINT)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json=MOCK_DATALAKE_CHANNELS_RESPONSE,
        additional_matcher=match_request_url)

    cmd = []
    r = runner.invoke(describe_datalake_channels, cmd)
    assert not r.exception


def test_describe_channels_include_archived(req_mock, runner):
    url = "{}/channels?limit=1000&filter_archived=include_archived".format(ORGANIZATION_ENDPOINT)

    def match_request_url(request):
        return request.url == url

    req_mock.register_uri(
        'GET', url,
        json=MOCK_DATALAKE_CHANNELS_RESPONSE,
        additional_matcher=match_request_url)

    cmd = ['--include-archived']
    r = runner.invoke(describe_datalake_channels, cmd)
    print(r.output)
    assert not r.exception


def test_describe_jobs_invalid_options(req_mock, runner):
    cmd = ['--filter-archived', '--include-archived']
    r = runner.invoke(describe_datalake_channels, cmd)
    assert r.exception
