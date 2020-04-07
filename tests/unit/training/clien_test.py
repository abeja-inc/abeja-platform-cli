import json
import requests_mock
from abejacli.config import ORGANIZATION_ENDPOINT
from abejacli.training.client import create_local_training_job
from abejacli.training.client import describe_training_version


def test_describe_training_version():
    name = 'training-job-definition-1'
    version = 1
    url = "{}/training/definitions/{}/versions/{}".format(
        ORGANIZATION_ENDPOINT, name, version)
    expected = {
        "job_definition_id": "1010101010101",
        "job_definition_version": 1,
        "handler": "train:handler",
        "datasets": {
            "mnist": "1111111111111"
        },
        "image": "abeja-inc/deepgpu:0.1.0",
        "source_code_base64": "",
        "user_parameters": {}
    }
    with requests_mock.Mocker() as mock:
        mock.register_uri('GET', url, text=json.dumps(expected))
        res = describe_training_version(name, version)
        assert res == expected


def test_create_local_training_job():
    name = 'training-job-definition-1'
    version = 1
    training_job_id = "1417943358413"
    description = "initial training job"
    user_parameters = {"BATCH_SIZE": 100}
    datasets = {"train": "3333333333333"}
    url = "{}/training/definitions/{}/versions/{}/jobs".format(
        ORGANIZATION_ENDPOINT, name, version)
    expected = {
        "job_definition_id": training_job_id,
        "name": name,
        "exec_env": "local",
        "description": description,
        "user_parameters": user_parameters,
        "datasets": datasets
    }

    def match_request_body(request):
        return request.text == json.dumps({
            'exec_env': 'local',
            'description': 'initial training job',
            'user_parameters': {'BATCH_SIZE': 100},
            'datasets': {'train': '3333333333333'}
        })

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            'POST', url, additional_matcher=match_request_body, text=json.dumps(expected))
        res = create_local_training_job(
            name, version, description=description,
            user_parameters=user_parameters, datasets=datasets)
        assert res == expected
