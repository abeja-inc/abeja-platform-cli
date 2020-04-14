import requests
from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import os
import re
token = os.environ.get('CIRCLE_CI_TOKEN')


def get_request_session():
    s = requests.Session()
    retries = Retry(total=5,
                    backoff_factor=1,
                    status_forcelist=[ 500, 502, 503, 504 ])

    s.mount('https://', HTTPAdapter(max_retries=retries))
    s.mount('http://', HTTPAdapter(max_retries=retries))
    return s


def get_stage():
    sdk_branch_name = os.environ.get('CIRCLE_BRANCH')
    if re.match(r'^release\/.+$', sdk_branch_name):
        stage = 'staging'
    elif sdk_branch_name == 'master':
        stage = 'production'
    else:
        return None
    return stage


def trigger_build_by_branch(stage):
    """https://circleci.com/docs/api/v2/#trigger-a-new-pipeline
    """
    url = 'https://circleci.com/api/v2/project/gh/abeja-inc/platform-system-test/pipeline'
    url = '{}?circle-token={}'.format(url, token)
    branch_name = 'deployment/{}'.format(stage)
    params = {
        'branch': branch_name
    }
    session = get_request_session()
    r = session.post(url, json=params)
    r.raise_for_status()


def main():
    stage = get_stage()
    if stage is None:
        exit(1)
    trigger_build_by_branch(stage)

if __name__ == '__main__':
    main()
