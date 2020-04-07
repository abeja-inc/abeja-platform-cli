import pytest


# fixtures
@pytest.fixture
def plain_config():
    return {'abeja-platform-user': 'user-1234567890123',
            'personal-access-token': '1935793145984317957049835709',
            'organization-name': 'abeja-inc'}


@pytest.fixture
def plain_config_without_user_prefix():
    return {'abeja-platform-user': '1234567890123',
            'personal-access-token': '1935793145984317957049835709',
            'organization-name': 'abeja-inc'}


@pytest.fixture
def fake_environ():
    return {'ABEJA_CLI_USER': 'user-03948273409356',
            'ABEJA_CLI_TOKEN': '3b1b07dc9b2be49d8952c422a7528c671246f949',
            'ABEJA_CLI_ORGANIZATION': 'abeja-inc'}


@pytest.fixture
def fake_environ_deprecated():
    return {'ABEJA_PLATFORM_USER': 'user-9876543210123',
            'PERSONAL_ACCESS_TOKEN': 'ENVENVENVENVENVENVENV',
            'ORGANIZATION_NAME': 'demo-org'}


@pytest.fixture
def fake_environ_job():
    return {'ABEJA_PLATFORM_USER_ID': 'user-9999999999999',
            'ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN': 'TOKENTOKENTOKENTOKEN',
            'ABEJA_CLI_ORGANIZATION': 'job-org'}


@pytest.fixture
def fake_environ_auth_token():
    return {'PLATFORM_AUTH_TOKEN': 'AUTHTOKENAUTHTOKENAUTHTOKEN',
            'ABEJA_CLI_ORGANIZATION': 'auth-token-org'}
