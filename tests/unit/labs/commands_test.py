import os
import shutil
from urllib.parse import urlparse

import pytest
import requests_mock
from click.testing import CliRunner
from ruamel.yaml import YAML

from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.labs.commands import init, push

TEST_CONFIG_USER_ID = '12345'
TEST_CONFIG_TOKEN = 'ntoken12345'
TEST_CONFIG_ORG_NAME = 'test-inc'
TEST_CONFIG = {
    'abeja-platform-user': 'user-{}'.format(TEST_CONFIG_USER_ID),
    'personal-access-token': TEST_CONFIG_TOKEN,
    'organization-name': TEST_CONFIG_ORG_NAME
}

LABS_APP_NAME_INIT = 'labs-app-test-init'
LABS_APP_NAME_PUSH = 'labs-app-test-push'
LABS_APP_DESCRIPTION = 'test labs app'
LABS_APP_TYPE = 'streamlit'
LABS_APP_SCOPE = 'private'
LABS_APP_ABEJA_USER_ONLY = True
LABS_APP_AUTH_TYPE = 'abeja'
LABS_APP_AUTHOR = 'test@abejainc.com'
LABS_APP_GITHUB_URL = 'https://github.com/abeja-inc/platform-labs-app-skeleton-v1'

MOCK_LABS_APP_RESPONSE = {
    "labs_app_id": "1111111111111",
    "organization_id": "1111111111111",
    "status": "pending",
    "name": LABS_APP_NAME_PUSH,
    "description": LABS_APP_DESCRIPTION,
    "version": "0.0.1",
    "scope": LABS_APP_SCOPE,
    "abeja_user_only": LABS_APP_ABEJA_USER_ONLY,
    "author": LABS_APP_AUTHOR,
    "auth_type": LABS_APP_AUTH_TYPE,
    "github_url": LABS_APP_GITHUB_URL,
    "image": f"custom/1111111111111/${LABS_APP_NAME_PUSH}:latest",
    "instance_type": "cpu-0.25",
    "command": "python3 -m http.server 8501 -d /app/src",
    "setting_yaml_base64": "dummy",
    "thumbnail_base64": "dummy",
    "how_to_use_base64": "dummy",
    "how_to_use_jp_base64": "dummy",
    "created_at": "2024-06-19T03:05:44.062621Z",
    "modified_at": "2024-06-19T09:14:05.650001Z",
}

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


def test_labs_app_init(runner):
    # delete labs-app-repo if exists
    if os.path.exists(LABS_APP_NAME_INIT):
        shutil.rmtree(LABS_APP_NAME_INIT)

    # run init command
    cmd = [
        '--name', LABS_APP_NAME_INIT,
        '--app_type', LABS_APP_TYPE,
        '--scope', LABS_APP_SCOPE,
        '--abeja_user_only', 'Y' if LABS_APP_ABEJA_USER_ONLY else 'N',
        '--auth_type', LABS_APP_AUTH_TYPE,
        '--author', LABS_APP_AUTHOR,
    ]
    r = runner.invoke(init, cmd)
    # print("r.output:\n", r.output)
    assert not r.exception

    # delete labs-app-repo if exists
    if os.path.exists(LABS_APP_NAME_INIT):
        shutil.rmtree(LABS_APP_NAME_INIT)


def test_labs_app_init_invalid_cmd(runner):
    # run init command with invalid app_type
    cmd = [
        '--name', LABS_APP_NAME_INIT,
        '--app_type', 'dummy',
        '--scope', LABS_APP_SCOPE,
        '--abeja_user_only', 'Y' if LABS_APP_ABEJA_USER_ONLY else 'N',
        '--auth_type', LABS_APP_AUTH_TYPE,
        '--author', LABS_APP_AUTHOR,
    ]
    r = runner.invoke(init, cmd)
    assert r.exception

    # run init command with invalid scope
    cmd = [
        '--name', LABS_APP_NAME_INIT,
        '--app_type', LABS_APP_TYPE,
        '--scope', 'dummy',
        '--abeja_user_only', 'Y' if LABS_APP_ABEJA_USER_ONLY else 'N',
        '--auth_type', LABS_APP_AUTH_TYPE,
        '--author', LABS_APP_AUTHOR,
    ]
    r = runner.invoke(init, cmd)
    assert r.exception

    # run init command with invalid abeja_user_only
    cmd = [
        '--name', LABS_APP_NAME_INIT,
        '--app_type', LABS_APP_TYPE,
        '--scope', LABS_APP_SCOPE,
        '--abeja_user_only', 'dummy',
        '--auth_type', LABS_APP_AUTH_TYPE,
        '--author', LABS_APP_AUTHOR,
    ]
    r = runner.invoke(init, cmd)
    assert r.exception

    # run init command with invalid auth_type
    cmd = [
        '--name', LABS_APP_NAME_INIT,
        '--app_type', LABS_APP_TYPE,
        '--scope', LABS_APP_SCOPE,
        '--abeja_user_only', 'Y' if LABS_APP_ABEJA_USER_ONLY else 'N',
        '--auth_type', 'dummy',
        '--author', LABS_APP_AUTHOR,
    ]
    r = runner.invoke(init, cmd)
    assert r.exception


def test_labs_app_push(req_mock, runner):
    # delete labs-app-repo if exists
    if os.path.exists(LABS_APP_NAME_PUSH):
        shutil.rmtree(LABS_APP_NAME_PUSH)

    # run init command and create labs-app directory
    cmd = [
        '--name', LABS_APP_NAME_PUSH,
        '--app_type', LABS_APP_TYPE,
        '--scope', LABS_APP_SCOPE,
        '--abeja_user_only', 'Y' if LABS_APP_ABEJA_USER_ONLY else 'N',
        '--auth_type', LABS_APP_AUTH_TYPE,
        '--author', LABS_APP_AUTHOR,
    ]
    r = runner.invoke(init, cmd)
    # print("[test_labs_app_push] r.output:\n", r.output)
    assert not r.exception

    # run push command
    url = f"{ORGANIZATION_ENDPOINT.replace('organizations', 'labs/organizations')}/apps"

    def match_request_url(request):
        return request.path == urlparse(url).path

    req_mock.register_uri(
        'POST', url,
        json=MOCK_LABS_APP_RESPONSE,
        additional_matcher=match_request_url)

    cmd = ['--directory_path', LABS_APP_NAME_PUSH]
    r = runner.invoke(push, cmd)
    # print("[test_labs_app_push] r.output:\n", r.output)

    assert req_mock.called
    assert r.exit_code == 0
    assert not r.exception

    # delete labs-app-repo if exists
    if os.path.exists(LABS_APP_NAME_PUSH):
        shutil.rmtree(LABS_APP_NAME_PUSH)
