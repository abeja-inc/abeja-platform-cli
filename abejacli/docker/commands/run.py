import json
import os
import socket
from typing import List, Optional

from abejacli import config
from abejacli.config import RESERVED_ENV_VAR, RUN_LOCAL_COMMAND_V1
from abejacli.docker.utils import get_home_path

# ==========================
# Environment Variable Keys
# ==========================
SERVICE_TYPE_HTTP = 'HTTP'
ABEJA_PLATFORM_USER_ID = 'ABEJA_PLATFORM_USER_ID'
ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN = 'ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN'

# ==========================
# Defined Default Path
# ==========================
DEFAULT_STORAGE_BASE_DIR = '/cache'
DEFAULT_STORAGE_DIR = '{}/.abeja/.cache'.format(DEFAULT_STORAGE_BASE_DIR)
DEFAULT_WORKING_DIR = '/srv/app'
DEFAULT_ARTIFACT_DIR = '/output'
PYTHONUNBUFFERED_OPTION = 'x'

# ==========================
# Defined Docker Parmaertes
# ==========================
DOCKER_PARAMETER_SETTING = {
    'x86_cpu': {
        'privileged': False,
        'volume': [],
        'runtime': None
    },
    'x86_gpu': {
        'privileged': False,
        'volume': [],
        'runtime': 'nvidia'
    },
    'jetson_tx2': {
        'privileged': True,
        'volume': [
            {
                'host': '/usr/lib/aarch64-linux-gnu/tegra',
                'guest': {'bind': '/usr/lib/aarch64-linux-gnu/tegra', 'mode': 'ro'}
            }],
        'runtime': None
    },
    'raspberry3': {
        'privileged': False,
        'volume': [{'host': '/opt', 'guest': {'bind': '/opt', 'mode': 'ro'}}],
        'runtime': None
    }
}


def get_free_tcp_port() -> int:
    """
    get free tcp port in dynamic port range
    which is defined by IANA
    cf. https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml

    :returns: free port number
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        _address, port = s.getsockname()
        return port


def build_volumes(volume_params):
    volumes = {}
    for host_path, container_path in volume_params:
        volumes.update(build_volume(host_path, container_path))
    return volumes


def build_volume(host_path, container_path, mode='rw'):
    return {
        host_path: {
            'bind': container_path,
            'mode': mode
        }
    }


def get_storage_volume() -> Optional[dict]:
    home_dir = get_home_path()
    if home_dir:
        return build_volume(home_dir, DEFAULT_STORAGE_BASE_DIR)
    return None


def get_default_volume() -> dict:
    current_dir = '{}'.format(os.getcwd())
    volume = build_volume(current_dir, DEFAULT_WORKING_DIR)
    storage_volume = get_storage_volume()
    if storage_volume:
        volume.update(storage_volume)
    return volume


def add_default_env_vars(env_vars: dict) -> dict:
    """add default environment variables commonly used in both model and train"""
    # deep copy to make argument immutable
    update_env_vars = {**env_vars}
    PYTHONUNBUFFERED = RESERVED_ENV_VAR['python_unbufferd']
    if PYTHONUNBUFFERED not in update_env_vars:
        update_env_vars[PYTHONUNBUFFERED] = PYTHONUNBUFFERED_OPTION
    ABEJA_STORAGE_DIR_PATH = RESERVED_ENV_VAR['abeja_storage_dir_path']
    if ABEJA_STORAGE_DIR_PATH not in update_env_vars:
        update_env_vars[ABEJA_STORAGE_DIR_PATH] = DEFAULT_STORAGE_DIR
    return update_env_vars


class RunCommand:
    def __init__(
            self, image: str, working_dir: str = None,
            environment: List[str] = None, volumes: dict = None, ports: dict = None,
            command: List[str] = None, remove: bool = True, detach: bool = True,
            privileged: bool = False,
            stderr: bool = True, runtime: str = None) -> None:
        self.image = image
        self.working_dir = working_dir
        self.environment = environment
        if ports is None:
            ports = {}
        self.ports = ports
        self.volumes = volumes
        self.command = command
        self.remove = remove
        self.detach = detach
        self.stderr = stderr
        self.runtime = runtime
        self.privileged = privileged

    def get_port(self) -> Optional[dict]:
        ports = list(self.ports.values())
        return ports[0] if ports else None

    def to_dict(self) -> dict:
        d = {
            'image': self.image,
            'remove': self.remove,
            'detach': self.detach,
            'stderr': self.stderr
        }
        if self.working_dir:
            d['working_dir'] = self.working_dir
        if self.environment:
            d['environment'] = self.environment
        if self.ports:
            d['ports'] = self.ports
        if self.volumes:
            d['volumes'] = self.volumes
        if self.command:
            d['command'] = self.command
        if self.runtime:
            d['runtime'] = self.runtime
        if self.privileged:
            d['privileged'] = self.privileged
        return d


class TrainRunCommand(RunCommand):
    @classmethod
    def create(
            cls, image: str, handler: str, datasets: dict = None,
            runtime: str = None, env_vars: dict = None, volume: dict = None,
            platform_user_id: str = None, platform_personal_access_token: str = None,
            platform_organization_id: str = None, command: list = None,
            remove=True) -> 'TrainRunCommand':
        if volume is None:
            volume = {}

        if env_vars is None:
            env_vars = {}
        env_vars = add_default_env_vars(env_vars)

        environment = ['{}={}'.format(k, v) for k, v in env_vars.items()]

        if handler:
            environment.append('{}={}'.format(RESERVED_ENV_VAR['handler'], handler))
        if datasets:
            environment.append('{}={}'.format(
                RESERVED_ENV_VAR['datasets'], str(json.dumps(datasets))))
        if platform_user_id:
            environment.append('{}={}'.format(
                ABEJA_PLATFORM_USER_ID, platform_user_id))
        if platform_personal_access_token:
            environment.append('{}={}'.format(
                ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN, platform_personal_access_token))
        if platform_organization_id:
            environment.append('{}={}'.format(
                RESERVED_ENV_VAR['organization_id'], platform_organization_id))

        if command is None:
            command = ['/bin/sh', '-c', 'abeja-model train']

        return TrainRunCommand(
            image=image, working_dir=DEFAULT_WORKING_DIR, environment=environment,
            command=command, volumes=volume, runtime=runtime, remove=remove)


class ModelRunCommand(RunCommand):
    @classmethod
    def create(
            cls, image: str, handler: str, device_type: str, port: int = None,
            command: List[str] = None, env_vars: dict = None,
            organization_id: str = None) -> 'ModelRunCommand':

        volume = get_default_volume()

        privileged = DOCKER_PARAMETER_SETTING[device_type]['privileged']
        runtime = DOCKER_PARAMETER_SETTING[device_type]['runtime']
        for v in DOCKER_PARAMETER_SETTING[device_type]['volume']:
            volume[v['host']] = v['guest']

        if port is None:
            port = get_free_tcp_port()
        ports = {'5000/tcp': port}

        if env_vars is None:
            env_vars = {}
        env_vars = add_default_env_vars(env_vars)
        if RESERVED_ENV_VAR['abeja_training_result_dir'] not in env_vars:
            env_vars[RESERVED_ENV_VAR['abeja_training_result_dir']] = '.'

        env_vars[RESERVED_ENV_VAR['service_type']] = SERVICE_TYPE_HTTP

        if ABEJA_PLATFORM_USER_ID not in env_vars:
            env_vars[ABEJA_PLATFORM_USER_ID] = config.ABEJA_PLATFORM_USER_ID
        if ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN not in env_vars:
            env_vars[ABEJA_PLATFORM_PERSONAL_ACCESS_TOKEN] = config.ABEJA_PLATFORM_TOKEN

        if handler:
            env_vars[RESERVED_ENV_VAR['handler']] = handler
        if organization_id:
            # NOTE: organization_id from arg takes priority over one passed as env.
            env_vars[RESERVED_ENV_VAR['organization_id']] = organization_id

        environment = ['{}={}'.format(k, v) for k, v in env_vars.items()]

        if command is None:
            command = RUN_LOCAL_COMMAND_V1

        return ModelRunCommand(
            image=image, working_dir=DEFAULT_WORKING_DIR, ports=ports,
            environment=environment, volumes=volume, privileged=privileged,
            runtime=runtime, command=command)
