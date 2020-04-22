from json import JSONDecodeError

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from abejacli.config import (
    ABEJA_PLATFORM_TOKEN,
    ABEJA_PLATFORM_USER_ID,
    PLATFORM_AUTH_TOKEN
)
from abejacli.logger import get_logger
from abejacli.version import VERSION


def generate_retry_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'abeja-platform-cli/{}'.format(VERSION)
    })
    retries = Retry(total=5,
                    backoff_factor=1,
                    method_whitelist=('GET', 'POST', 'PUT', 'DELETE', 'PATCH'),
                    status_forcelist=(500, 502, 503, 504),
                    raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session


def generate_user_session(json_content_type=True):
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'abeja-platform-cli/{}'.format(VERSION)
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


def api_get(url):
    try:
        session = generate_user_session()
        r = session.get(url)
        r.raise_for_status()
        r = r.json()

    except requests.exceptions.HTTPError as e:
        _error_message(e, r)
        raise

    return r


def api_get_data(url, params):
    try:
        session = generate_user_session()
        r = session.get(url, params=params)
        r.raise_for_status()
        try:
            r = r.json()
        except JSONDecodeError:
            r = r.text
    except requests.exceptions.HTTPError as e:
        _error_message(e, r)
        raise

    return r


def api_post(url, *args, **kwargs):
    try:
        # Don't set `Content-Type` manually.
        session = generate_user_session(
            json_content_type=(not kwargs.get('files')))
        r = session.post(url, *args, **kwargs)
        r.raise_for_status()
        try:
            r = r.json()
        except JSONDecodeError:
            r = r.text

    except requests.exceptions.HTTPError as e:
        _error_message(e, r)
        raise

    return r


def api_put(url, *args, **kwargs):
    try:
        # Don't set `Content-Type` manually.
        session = generate_user_session(
            json_content_type=(not kwargs.get('files')))
        r = session.put(url, *args, **kwargs)
        r.raise_for_status()
        try:
            r = r.json()
        except JSONDecodeError:
            r = r.text

    except requests.exceptions.HTTPError as e:
        _error_message(e, r)
        raise

    return r


def api_delete(url):
    try:
        session = generate_user_session()
        r = session.delete(url)
        r.raise_for_status()
        try:
            r = r.json()
        except JSONDecodeError:
            r = r.text

    except requests.exceptions.HTTPError as e:
        _error_message(e, r)
        raise

    return r


def api_patch(url, jsonData):
    try:
        session = generate_user_session()
        r = session.patch(url, jsonData)
        r.raise_for_status()
        try:
            r = r.json()
        except JSONDecodeError:
            r = r.text

    except requests.exceptions.HTTPError as e:
        _error_message(e, r)
        raise

    return r


def _error_message(e, r):
    logger = get_logger()
    logger.error('{} {} {} {} {}'.format("request.url      => ", str(r.request.method), str(r.request.url),
                                         str(e.response.status_code), str(e.response.reason)))
    logger.debug('{} {}'.format("request.headers  =>", str(r.request.headers)))
    logger.debug('{} {}'.format("request.body     =>", str(r.request.body)))
    logger.debug('{} {}'.format("response.headers =>", str(r.headers)))
    logger.error('{} {}'.format("response.body    =>", str(r.text)))
