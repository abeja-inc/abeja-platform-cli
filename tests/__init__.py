import requests
from abejacli.config import ABEJA_PLATFORM_USER_ID, ABEJA_PLATFORM_TOKEN, PLATFORM_AUTH_TOKEN
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import uuid
import os
from unittest.mock import patch


def _test_generate_retry_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'abeja-system-test'
    })

    retries = Retry(total=5,
                    backoff_factor=1,
                    method_whitelist=('GET', 'POST', 'PUT', 'DELETE', 'PATCH'),
                    status_forcelist=(500, 502, 503, 504),
                    raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def _test_generate_user_session(json_content_type=True):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'abeja-system-test'
    })
    if ABEJA_PLATFORM_USER_ID and ABEJA_PLATFORM_TOKEN:
        session.auth = (ABEJA_PLATFORM_USER_ID, ABEJA_PLATFORM_TOKEN)
    elif PLATFORM_AUTH_TOKEN:
        session.headers.update({
            'Authorization': 'Bearer {}'.format(PLATFORM_AUTH_TOKEN)
        })

    # Actually, we don't need to set `Content-Type` manually, If we use
    # `requests.request(url, json=json)`...
    if json_content_type:
        session.headers.update({
            'Content-Type': 'application/json'
        })

    retries = Retry(total=5,
                    backoff_factor=1,
                    method_whitelist=('GET', 'POST', 'PUT', 'DELETE', 'PATCH'),
                    status_forcelist=(500, 502, 503, 504),
                    raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def session_decorator(func):
    def wrapper(*args, **kwargs):
        with patch('abejacli.session.generate_retry_session') as mock_generate_retry_session, \
                patch('abejacli.session.generate_user_session') as mock_generate_user_session:
            mock_generate_retry_session.side_effect = _test_generate_retry_session
            mock_generate_user_session.side_effect = _test_generate_user_session
            return func(*args, **kwargs)
    return wrapper


def get_tmp_training_file_name():
    """Putting temporary file in /tmp dir.
    Hopefully want to use tempfile but can't close tempfile, so using tmp dir
    """
    filename = '{}.yaml'.format(uuid.uuid4())
    return os.path.join('/tmp', filename)