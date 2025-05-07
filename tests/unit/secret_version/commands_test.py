import base64
import json
import re
from urllib.parse import urlparse

import pytest
import requests_mock
from click.testing import CliRunner

from abejacli.config import ABEJA_API_URL
from abejacli.secret_version.commands import (
    create_secret_version,
    delete_secret_version,
    get_secret_version,
    list_secret_versions,
    update_secret_version
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
MOCK_SECRET_NAME = 'test-secret'
MOCK_VERSION_ID = 'ver-1111111111111'
MOCK_VERSION_NUMBER = 1
MOCK_SECRET_VALUE = 'secret-value-123'
MOCK_SECRET_ENCODED_VALUE = base64.b64encode(MOCK_SECRET_VALUE.encode('utf-8')).decode('utf-8')
MOCK_SECRET_CREATED_AT = '2025-01-01T00:00:00Z'
MOCK_SECRET_UPDATED_AT = '2025-01-02T00:00:00Z'

MOCK_VERSION_RESPONSE = {
    'id': MOCK_VERSION_ID,
    'secret_id': MOCK_SECRET_ID,
    'version': MOCK_VERSION_NUMBER,
    'value': MOCK_SECRET_ENCODED_VALUE,
    'status': 'active',
    'created_at': MOCK_SECRET_CREATED_AT
}

MOCK_VERSION_LIST_RESPONSE = {
    'versions': [MOCK_VERSION_RESPONSE],
    'has_next': False,
    'offset': 0,
    'limit': 50,
    'total': 1
}

MOCK_VERSION_CREATE_RESPONSE = {
    'id': 'ver-2222222222222',
    'secret_id': MOCK_SECRET_ID,
    'version': 2,
    'value': MOCK_SECRET_ENCODED_VALUE,
    'status': 'active',
    'created_at': MOCK_SECRET_UPDATED_AT
}

MOCK_VERSION_UPDATE_RESPONSE = {
    'id': MOCK_VERSION_ID,
    'secret_id': MOCK_SECRET_ID,
    'version': MOCK_VERSION_NUMBER,
    'value': MOCK_SECRET_ENCODED_VALUE,
    'status': 'inactive',
    'created_at': MOCK_SECRET_CREATED_AT,
    'updated_at': MOCK_SECRET_UPDATED_AT
}

MOCK_VERSION_DELETE_RESPONSE = {
    'message': f'Secret version ({MOCK_VERSION_ID}) was deleted'
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
# list_secret_versions のテスト
# -----------------------------------------------
def test_list_secret_versions(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}/versions".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
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
        json=MOCK_VERSION_LIST_RESPONSE,
        additional_matcher=match_request_url)

    cmd = ['--organization_id', TEST_CONFIG_ORG_ID, '--secret_id', MOCK_SECRET_ID]
    r = runner.invoke(list_secret_versions, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_list_secret_versions_with_limit_offset(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}/versions".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)
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
        json=MOCK_VERSION_LIST_RESPONSE,
        additional_matcher=match_request_url)

    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--limit', '20',
        '--offset', '10'
    ]
    r = runner.invoke(list_secret_versions, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_list_secret_versions_missing_secret_id(runner):
    cmd = ['--organization_id', TEST_CONFIG_ORG_ID]
    r = runner.invoke(list_secret_versions, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_list_secret_versions_invalid_limit(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--limit', '0'
    ]
    r = runner.invoke(list_secret_versions, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_list_secret_versions_invalid_offset(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--offset', '-1'
    ]
    r = runner.invoke(list_secret_versions, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# get_secret_version のテスト
# -----------------------------------------------
def test_get_secret_version(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)
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
        json=MOCK_VERSION_RESPONSE,
        additional_matcher=match_request_url)

    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID
    ]
    r = runner.invoke(get_secret_version, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_get_secret_version_missing_secret_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--version_id', MOCK_VERSION_ID
    ]
    r = runner.invoke(get_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_get_secret_version_missing_version_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID
    ]
    r = runner.invoke(get_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# create_secret_version のテスト
# -----------------------------------------------
def test_create_secret_version(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}/versions".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID)

    def match_request_data(request):
        body = json.loads(request.text)
        assert body['value'] == MOCK_SECRET_ENCODED_VALUE
        return True

    req_mock.register_uri(
        'POST', url,
        json=MOCK_VERSION_CREATE_RESPONSE,
        additional_matcher=match_request_data)

    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--value', MOCK_SECRET_VALUE
    ]
    r = runner.invoke(create_secret_version, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_create_secret_version_missing_secret_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--value', MOCK_SECRET_VALUE
    ]
    r = runner.invoke(create_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_create_secret_version_missing_value(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID
    ]
    r = runner.invoke(create_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# update_secret_version のテスト
# -----------------------------------------------
def test_update_secret_version(req_mock, runner):
    url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)

    def match_request_data(request):
        body = json.loads(request.text)
        assert body['status'] == 'inactive'
        return True

    req_mock.register_uri(
        'PATCH', url,
        json=MOCK_VERSION_UPDATE_RESPONSE,
        additional_matcher=match_request_data)

    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID,
        '--status', 'inactive'
    ]
    r = runner.invoke(update_secret_version, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_update_secret_version_missing_secret_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--version_id', MOCK_VERSION_ID,
        '--status', 'inactive'
    ]
    r = runner.invoke(update_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_update_secret_version_missing_version_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--status', 'inactive'
    ]
    r = runner.invoke(update_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_update_secret_version_missing_status(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID
    ]
    r = runner.invoke(update_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_update_secret_version_invalid_status(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID,
        '--status', 'invalid-status'
    ]
    r = runner.invoke(update_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


# -----------------------------------------------
# delete_secret_version のテスト
# -----------------------------------------------
def test_delete_secret_version(req_mock, runner):
    # GET リクエストの設定（確認画面用の情報取得）
    get_url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)
    req_mock.register_uri('GET', get_url, json=MOCK_VERSION_RESPONSE)

    # DELETE リクエストの設定
    delete_url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)
    req_mock.register_uri('DELETE', delete_url, json=MOCK_VERSION_DELETE_RESPONSE)

    # 自動で確認に「Y」と答えるためのオプションを追加
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID,
        '--yes'
    ]
    r = runner.invoke(delete_secret_version, cmd)
    assert not r.exception
    assert r.exit_code == 0


def test_delete_secret_version_without_yes_flag(req_mock, runner):
    # GET リクエストの設定（確認画面用の情報取得）
    get_url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)
    req_mock.register_uri('GET', get_url, json=MOCK_VERSION_RESPONSE)

    # DELETE リクエストの設定
    delete_url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)
    req_mock.register_uri('DELETE', delete_url, json=MOCK_VERSION_DELETE_RESPONSE)

    # 確認プロンプトで「Y」と入力するシミュレーション
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID
    ]
    r = runner.invoke(delete_secret_version, cmd, input='Y\n')
    assert not r.exception
    assert r.exit_code == 0


def test_delete_secret_version_cancel(req_mock, runner):
    # GET リクエストの設定（確認画面用の情報取得）
    get_url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
        ABEJA_API_URL, TEST_CONFIG_ORG_ID, MOCK_SECRET_ID, MOCK_VERSION_ID)
    req_mock.register_uri('GET', get_url, json=MOCK_VERSION_RESPONSE)

    # 確認プロンプトで「n」と入力するシミュレーション
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID,
        '--version_id', MOCK_VERSION_ID
    ]
    r = runner.invoke(delete_secret_version, cmd, input='n\n')
    assert not r.exception
    assert r.exit_code == 0  # キャンセルの場合も正常終了
    assert '操作を中止しました' in r.output


def test_delete_secret_version_missing_secret_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--version_id', MOCK_VERSION_ID
    ]
    r = runner.invoke(delete_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0


def test_delete_secret_version_missing_version_id(runner):
    cmd = [
        '--organization_id', TEST_CONFIG_ORG_ID,
        '--secret_id', MOCK_SECRET_ID
    ]
    r = runner.invoke(delete_secret_version, cmd)
    assert r.exception
    assert r.exit_code != 0
