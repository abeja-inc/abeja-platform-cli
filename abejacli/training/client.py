import json
from typing import Optional

from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.session import api_get, api_post


def describe_training_version(name: str, version: int):
    return api_get("{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, name, version))


def create_local_training_job(
        name: str, version: int, description: str = None,
        user_parameters: Optional[dict] = None, datasets: Optional[dict] = None):
    url = "{}/training/definitions/{}/versions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, name, version)
    parameters = {'exec_env': 'local'}
    if description:
        parameters['description'] = description
    if user_parameters:
        parameters['user_parameters'] = user_parameters
    if datasets:
        parameters['datasets'] = datasets
    data = json.dumps(parameters)
    return api_post(url, data)
