from unittest.mock import MagicMock

import pytest

from abejacli.training import TrainingConfig, create_version_schema


@pytest.fixture
def training_configuration():
    return {
        'name': 'cats_and_dogs',
        'handler': 'train:handler',
        'image': 'abeja-inc/all-gpu:18.10',
        'params': {
            'NUM_EPOCHS': 10,
            'ARTIFACT_FILE_NAME': 'model.h5',
            'MAX_ITEM': None
        },
        'environment': {
            'NUM_EPOCHS': 10,
            'ARTIFACT_FILE_NAME': 'model.h5',
            'MAX_ITEM': None
        },
        'datasets': {
            'train': 1234567890123
        }
    }


class TestTrainingConfig:
    def test_read_str_params_values(self, training_configuration):
        config = TrainingConfig()
        config._load_config = MagicMock(
            return_value=training_configuration)
        res = config.read(create_version_schema)
        assert 'environment' in res
        for param in res['environment'].values():
            assert param is None or type(param) == str
