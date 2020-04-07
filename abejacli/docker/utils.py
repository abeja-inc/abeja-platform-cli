from pathlib import Path
from typing import Optional

import docker
import requests


def check_docker_installation() -> Optional[dict]:
    """return docker version info if docker is installed"""
    try:
        return docker.from_env().version()
    except requests.exceptions.ConnectionError:
        return None


def get_home_path() -> Optional[str]:
    """get home directory path, return None if failed"""
    try:
        return str(Path.home())
    except RuntimeError:
        return None


def parse_image(image: str) -> list:
    try:
        return image.split(':')
    except ValueError:
        msg = 'image and tag must be formatted in the "name:tag"' \
              ' format : {}'.format(image)
        raise RuntimeError(msg)
