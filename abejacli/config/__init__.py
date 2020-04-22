"""
isort:skip_file
"""
import os

# Make callers be able to `from abejacli.config import Config`
from abejacli.configuration import CONFIG_FILE_PATH, ROOT_DIRECTORY  # noqa: F401
from abejacli.configuration.loader import ConfigSetLoader
from abejacli.exceptions import InvalidConfigException

SUCCESS_EXITCODE = 0
ERROR_EXITCODE = 1
INVALID_PARAMETER_EXITCODE = 2

LOG_DIRECTORY = os.path.join(os.path.expanduser('~'), '.abeja', 'log')
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, 'abejacli.log')

SAMPLE_MODEL_PATH = os.environ.get(
    'SAMPLE_MODEL_PATH',
    'https://s3-ap-northeast-1.amazonaws.com/abeja-platform-config-prod'
)
STDERROR_LOG_LEVEL = os.environ.get('LOG_LEVEL', 'ERROR')
DATALAKE_ITEMS_PER_PAGE = int(os.environ.get('DATALAKE_ITEMS_PER_PAGE', 100))
HTTP_READ_CHUNK_SIZE = int(os.environ.get('HTTP_READ_CHUNK_SIZE', 1024))
FILE_READ_CHUNK_SIZE = int(os.environ.get('FILE_READ_CHUNK_SIZE', 8192))
JOB_WORKER_THREAD_NUM = int(os.environ.get('JOB_WORKER_THREAD_NUM', 10))
PLATFORM_REQUEST_TIMEOUT_SECONDS = int(
    os.environ.get('PLATFORM_REQUEST_TIMEOUT_SECONDS', 300))

SERVICE_API_TIMEOUT = 90

DATASET_CHUNK_SIZE = 500

ENV_VAR_KEY_FORMAT = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
VOLUME_FORMAT = r'^(/)?([^/\0]+(/)?)+$'
DATASET_VAR_KEY_FORMAT = r'^[a-zA-Z_][a-zA-Z0-9_-]*$'

TRIGGER_DEFAULT_RETRY_COUNT = 5
RUN_DEFAULT_RETRY_COUNT = 5

DEFAULT_EXCLUDE_FILES = ['.git']

DOCKER_REPOSITORIES = ['abeja', 'abeja-inc']
TAG_VERSION_SAMPV1 = ['18.10', '0.1.0', '0.1.0-arm64v8', '0.1.0-arm32v7']
RUN_LOCAL_COMMAND_V1 = ['/bin/sh', '-c', 'abeja-model run']
RUN_LOCAL_COMMAND_V2 = ['/bin/sh', '-c', 'platform-model-proxy run']
TRAIN_DEBUG_COMMAND_V1 = ['/bin/sh', '-c', 'abeja-model train']
TRAIN_DEBUG_COMMAND_V2 = ['/bin/sh', '-c', 'abeja-train train']
TRAIN_LOCAL_COMMAND_V1 = [
    '/bin/sh', '-c',
    'abeja-model download_training_source_code && abeja-model train'
]
TRAIN_LOCAL_COMMAND_V2 = ['/bin/sh', '-c', 'abeja-train']

# Configurations
CONFIG = None
ABEJA_PLATFORM_USER_ID = None
ABEJA_PLATFORM_TOKEN = None
ORGANIZATION_NAME = None
PLATFORM_AUTH_TOKEN = None
ORGANIZATION_ENDPOINT = None
ABEJA_API_URL = 'https://api.abeja.io'

# For backward compatibility, CONFIG must be a plain dictionary.
try:
    config = ConfigSetLoader().load().active_config

    # Because we want load configuration from environment variables too,
    # we don't use asdict().
    CONFIG = {
        'abeja-platform-user': config.user,
        'personal-access-token': config.token,
        'organization-name': config.organization
    }
    ABEJA_PLATFORM_USER_ID = CONFIG['abeja-platform-user']
    ABEJA_PLATFORM_TOKEN = CONFIG['personal-access-token']
    ORGANIZATION_NAME = CONFIG['organization-name']
    PLATFORM_AUTH_TOKEN = config.platform_auth_token
    if config.api_url:
        ABEJA_API_URL = config.api_url
except InvalidConfigException:
    pass

ORGANIZATION_ENDPOINT = "{}/organizations/{}".format(
    ABEJA_API_URL, ORGANIZATION_NAME)
protocol, fqdn = ABEJA_API_URL.split('://')
WEB_API_ENDPOINT = '{}://{}.{}'.format(protocol, ORGANIZATION_NAME, fqdn)

# Values are the reserved environment variables
RESERVED_ENV_VAR = {
    'handler': 'HANDLER',
    'datasets': 'DATASETS',
    'platform_auth_token': 'PLATFORM_AUTH_TOKEN',
    'abeja_api_url': 'ABEJA_API_URL',
    'service_type': 'SERVICE_TYPE',
    'python_unbufferd': 'PYTHONUNBUFFERED',
    'organization_id': 'ABEJA_ORGANIZATION_ID',
    'training_job_definition_name': 'TRAINING_JOB_DEFINITION_NAME',
    'training_job_definition_version': 'TRAINING_JOB_DEFINITION_VERSION',
    'training_job_id': 'TRAINING_JOB_ID',
    'training_notebook_id': 'TRAINING_NOTEBOOK_ID',
    'abeja_storage_dir_path': 'ABEJA_STORAGE_DIR_PATH',
    'abeja_training_result_dir': 'ABEJA_TRAINING_RESULT_DIR'
}


def get_env_var(key, _type, default=None):
    if os.environ.get(key):
        return _type(os.environ[key])
    return default


# train-local config
LOG_FLUSH_INTERVAL = get_env_var('LOG_FLUSH_INTERVAL', int, 5)
assert LOG_FLUSH_INTERVAL > 0, 'LOG_FLUSH_INTERVAL should be greater than 0'

LOG_MAX_SIZE = get_env_var('LOG_MAX_SIZE', int, 1 * 1024 * 1024)
_BUFFER = 1024  # 1kB of buffer
assert LOG_MAX_SIZE > _BUFFER, 'LOG_MAX_SIZE should be greater than {}'.format(
    _BUFFER)

LOG_MAX_SIZE -= _BUFFER

POLLING_INTERVAL = get_env_var('POLLING_INTERVAL', int, 10)
