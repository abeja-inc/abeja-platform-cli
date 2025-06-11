import base64
import json
import re
from urllib.parse import urlparse

import pytest
import requests_mock
from click.testing import CliRunner

from abejacli.config import ABEJA_API_URL
from abejacli.secret.commands import (
    create_secret,
    delete_secret,
    get_secret,
    list_secrets,
    update_secret
)

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_CONFIG_ORG_ID = '1234567890123'
TEST_CONFIG = {
    'abeja-platform-user': 'user-{}'.format(TEST_CONFIG_USER_ID),
    'personal-access-token': TEST_CONFIG_TOKEN,
    'organization-name': TEST_CONFIG_ORG_ID
}

# モックレスポンスデータ
MOCK_SECRET_ID = 'sec-1111111111111'
MOCK_SECRET_NAME = 'test-secret-name'
MOCK_SECRET_DESCRIPTION = 'テスト用シークレット'
MOCK_SECRET_VALUE = 'secret-value-123'
MOCK_SECRET_ENCODED_VALUE = base64.b64encode(MOCK_SECRET_VALUE.encode('utf-8')).decode('utf-8')
MOCK_SECRET_INTEGRATION_SERVICE_TYPE = 'abeja-platform-labs'
MOCK_SECRET_INTEGRATION_SERVICE_IDS = '1111111111111,2222222222222'
MOCK_SECRET_CREATED_AT = '2025-01-01T00:00:00Z'
MOCK_SECRET_UPDATED_AT = '2025-01-02T00:00:00Z'
MOCK_SECRET_EXPIRED_AT = '2026-01-01T00:00:00Z'

MOCK_SECRET_RESPONSE = {
    'id': MOCK_SECRET_ID,
    'name': MOCK_SECRET_NAME,
    'description': MOCK_SECRET_DESCRIPTION,
    'created_at': MOCK_SECRET_CREATED_AT,
    'updated_at': MOCK_SECRET_UPDATED_AT,
    'expired_at': MOCK_SECRET_EXPIRED_AT,
    'integration_service_type': MOCK_SECRET_INTEGRATION_SERVICE_TYPE,
    'integration_service_ids': MOCK_SECRET_INTEGRATION_SERVICE_IDS.split(','),
    'versions': [
        {
            'id': 'ver-1111111111111',
            'secret_id': MOCK_SECRET_ID,
            'version': 1,
            'value': MOCK_SECRET_ENCODED_VALUE,
            'status': 'active',
            'created_at': MOCK_SECRET_CREATED_AT
        }
    ]
}

MOCK_SECRET_LIST_RESPONSE = {
    'secrets': [MOCK_SECRET_RESPONSE],
    'has_next': False,
    'offset': 0,
    'limit': 50,
    'total': 1
}

MOCK_SECRET_CREATE_RESPONSE = {
    'id': MOCK_SECRET_ID,
    'name': MOCK_SECRET_NAME,
    'description': MOCK_SECRET_DESCRIPTION,
    'created_at': MOCK_SECRET_CREATED_AT,
    'updated_at': MOCK_SECRET_UPDATED_AT,
    'expired_at': MOCK_SECRET_EXPIRED_AT,
    'integration_service_type': MOCK_SECRET_INTEGRATION_SERVICE_TYPE,
    'integration_service_ids': MOCK_SECRET_INTEGRATION_SERVICE_IDS.split(','),
}

MOCK_SECRET_UPDATE_RESPONSE = {
    'id': MOCK_SECRET_ID,
    'name': MOCK_SECRET_NAME,
    'description': 'Updated description',
    'created_at': MOCK_SECRET_CREATED_AT,
    'updated_at': MOCK_SECRET_UPDATED_AT,
    'expired_at': '2027-01-01T00:00:00Z',
    'integration_service_type': MOCK_SECRET_INTEGRATION_SERVICE_TYPE,
    'integration_service_ids': MOCK_SECRET_INTEGRATION_SERVICE_IDS.split(','),
}

MOCK_SECRET_DELETE_RESPONSE = {
    'message': f'Secret ({MOCK_SECRET_ID}) was deleted'
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


# -----------------------------------------------
# list_secrets のテスト
# -----------------------------------------------
def test_list_secrets(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets".format(ABEJA_API_URL, TEST_CONFIG_ORG_ID)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        'limit': ['50'],
        'offset': ['0'],
        'return_secret_value': ['true']
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json=MOCK_SECRET_LIST_RESPONSE,
        additional_matcher=match_request_url)

    cmd = ['--organization_id', TEST_CONFIG_ORG_ID]
    r = runner.invoke(list_secrets, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_list_secrets_with_limit_offset(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets".format(ABEJA_API_URL, TEST_CONFIG_ORG_ID)
    re_url = r"^{}.+".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        'limit': ['20'],
        'offset': ['10'],
        'return_secret_value': ['true']
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json=MOCK_SECRET_LIST_RESPONSE,
        additional_matcher=match_request_url)

    cmd = ['--organization_id', TEST_CONFIG_ORG_ID, '--limit', '20', '--offset', '10']
    r = runner.invoke(list_secrets, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_list_secrets_invalid_limit(req_mock, runner):
    cmd = ['--organization_id', TEST_CONFIG_ORG_ID, '--limit', '0']
    r = runner.invoke(list_secrets, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_list_secrets_invalid_offset(req_mock, runner):
    cmd = ['--organization_id', TEST_CONFIG_ORG_ID, '--offset', '-1']
    r = runner.invoke(list_secrets, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# get_secret のテスト
# -----------------------------------------------
def test_get_secret(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
    re_url = r"^{}\??.*".format(url)
    matcher = re.compile(re_url)

    expected_params = {
        'return_secret_value': ['true']
    }

    def match_request_url(request):
        assert request.qs == expected_params
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'GET', matcher,
        json=MOCK_SECRET_RESPONSE,
        additional_matcher=match_request_url)

    cmd = ['--organization_id', TEST_CONFIG_ORG_ID, '--secret_id', MOCK_SECRET_ID]
    r = runner.invoke(get_secret, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_get_secret_missing_secret_id(runner):
    cmd = ['--organization_id', TEST_CONFIG_ORG_ID]
    r = runner.invoke(get_secret, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# create_secret のテスト
# -----------------------------------------------
def test_create_secret(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID)

    def match_request_data(request):
        body = json.loads(request.text)
        assert body['name'] == MOCK_SECRET_NAME
        assert body['value'] == MOCK_SECRET_ENCODED_VALUE
        assert body['description'] == MOCK_SECRET_DESCRIPTION
        assert body['expired_at'] == MOCK_SECRET_EXPIRED_AT
        assert body['integration_service_type'] == MOCK_SECRET_INTEGRATION_SERVICE_TYPE
        assert body['integration_service_ids'] == MOCK_SECRET_INTEGRATION_SERVICE_IDS.split(',')
        return True

    req_mock.register_uri(
        'POST', url,
        json=MOCK_SECRET_CREATE_RESPONSE,
        additional_matcher=match_request_data)

    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--name', MOCK_SECRET_NAME,
        '--value', MOCK_SECRET_VALUE,
        '--description', MOCK_SECRET_DESCRIPTION,
        '--expired-at', MOCK_SECRET_EXPIRED_AT,
        '--integration-service-type', MOCK_SECRET_INTEGRATION_SERVICE_TYPE,
        '--integration-service-ids', MOCK_SECRET_INTEGRATION_SERVICE_IDS
    ]
    r = runner.invoke(create_secret, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_create_secret_missing_name(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--value', MOCK_SECRET_VALUE
    ]
    r = runner.invoke(create_secret, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_create_secret_missing_value(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--name', MOCK_SECRET_NAME
    ]
    r = runner.invoke(create_secret, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# update_secret のテスト
# -----------------------------------------------
def test_update_secret(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)

    updated_description = "Updated description"
    updated_expired_at = "2027-01-01T00:00:00Z"

    def match_request_data(request):
        body = json.loads(request.text)
        assert body['description'] == updated_description
        assert body['expired_at'] == updated_expired_at
        assert body['integration_service_type'] == MOCK_SECRET_INTEGRATION_SERVICE_TYPE
        assert body['integration_service_ids'] == MOCK_SECRET_INTEGRATION_SERVICE_IDS
        return True

    req_mock.register_uri(
        'PATCH', url,
        json=MOCK_SECRET_UPDATE_RESPONSE,
        additional_matcher=match_request_data)

    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--description', updated_description,
        '--expired-at', updated_expired_at,
        '--integration-service-type', MOCK_SECRET_INTEGRATION_SERVICE_TYPE,
        '--integration-service-ids', MOCK_SECRET_INTEGRATION_SERVICE_IDS
    ]
    r = runner.invoke(update_secret, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_update_secret_missing_secret_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--description', 'Updated description'
    ]
    r = runner.invoke(update_secret, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# delete_secret のテスト
# -----------------------------------------------
def test_delete_secret(req_mock, runner):
    # GET リクエストの設定（確認画面用の情報取得）
    get_url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
    req_mock.register_uri('GET', get_url, json=MOCK_SECRET_RESPONSE)

    # DELETE リクエストの設定
    delete_url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
    req_mock.register_uri('DELETE', delete_url, json=MOCK_SECRET_DELETE_RESPONSE)

    # 自動で確認に「Y」と答えるためのオプションを追加
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--yes'
    ]
    r = runner.invoke(delete_secret, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_delete_secret_without_yes_flag(req_mock, runner):
    # GET リクエストの設定（確認画面用の情報取得）
    get_url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
    req_mock.register_uri('GET', get_url, json=MOCK_SECRET_RESPONSE)

    # DELETE リクエストの設定
    delete_url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
    req_mock.register_uri('DELETE', delete_url, json=MOCK_SECRET_DELETE_RESPONSE)

    # 確認プロンプトで「Y」と入力するシミュレーション
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID
    ]
    r = runner.invoke(delete_secret, cmd, input='Y\n')
    assert not r.exception
    assert r.exit_code == 0


def test_delete_secret_cancel(req_mock, runner):
    # GET リクエストの設定（確認画面用の情報取得）
    get_url = "{}/secret-manager/organizations/{}/secrets/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
    req_mock.register_uri('GET', get_url, json=MOCK_SECRET_RESPONSE)

    # 確認プロンプトで「n」と入力するシミュレーション
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID
    ]
    r = runner.invoke(delete_secret, cmd, input='n\n')
    assert not r.exception
    assert r.exit_code == 0  # キャンセルの場合も正常終了
    assert '操作を中止しました' in r.output


def test_delete_secret_missing_secret_id(runner):
    cmd = ['--organization_id', TEST_CONFIG_ORG_ID]
    r = runner.invoke(delete_secret, cmd)
    assert r.exception
    assert r.exit_code != 0
