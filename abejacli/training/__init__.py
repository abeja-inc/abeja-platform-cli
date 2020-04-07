from cerberus import Validator
from abejacli.exceptions import InvalidConfigException, ConfigFileNotFoundError
from ruamel.yaml import YAML

yaml = YAML()
HANDLER_REGEX = r'\A(([a-zA-Z_]\w+\.)+)?[a-zA-Z_]\w+(:[a-zA-Z_]\w+\Z)?'
CONFIGFILE_NAME = "training.yaml"

training_default_configuration = """\
name: training-1
# handler: train:handler
# image: abeja-inc/all-cpu:19.04
# environment:
#   key1: value1
#   key2: value2
# datasets:
#   dataset_name1: value1
#   dataset_name2: value2
# ignores:
#   - .gitignore
"""

default_schema = {
    'name': {'type': 'string', 'required': True},
    'handler': {'type': 'string', 'required': False, 'regex': HANDLER_REGEX},
    'image': {'type': 'string', 'required': False},
    'datasets': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {'type': 'string', 'coerce': str},
        'required': False,
        'nullable': True,
    },
    # DEPRECATED: params will be replaced with environment
    'params': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {
            'type': 'string',
            'coerce': lambda v: v if v is None else str(v),
            'nullable': True
        },
        'required': False,
        'nullable': True,
    },
    'environment': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {
            'type': 'string',
            'coerce': lambda v: v if v is None else str(v),
            'nullable': True
        },
        'required': False,
        'nullable': True,
    },
    'ignores': {
        'type': 'list',
        'required': False,
        'nullable': True,
        'schema': {
            'type': 'string'
        }
    }
}
create_version_schema = {
    'name': {'type': 'string', 'required': True},
    'handler': {'type': 'string', 'required': True, 'regex': HANDLER_REGEX},
    'image': {'type': 'string', 'required': True},
    'datasets': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {'type': 'string', 'coerce': str},
        'required': False,
        'nullable': True,
    },
    # DEPRECATED: params will be replaced with environment
    'params': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {
            'type': 'string',
            'coerce': lambda v: v if v is None else str(v),
            'nullable': True
        },
        'required': False,
        'nullable': True,
    },
    'environment': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {
            'type': 'string',
            'coerce': lambda v: v if v is None else str(v),
            'nullable': True
        },
        'required': False,
        'nullable': True,
    },
    'ignores': {
        'type': 'list',
        'required': False,
        'nullable': True,
        'schema': {
            'type': 'string'
        }
    }
}
create_notebook_schema = {
    'name': {'type': 'string', 'required': True},
    'image': {'type': 'string', 'required': True}
}


class TrainingConfig:
    def __init__(self):
        self.config_file = training_default_configuration
        self.default_schema = default_schema
        self.create_version_schema = create_version_schema
        self.create_notebook_schema = create_notebook_schema

    def write(self, name):
        data = yaml.load(self.config_file)
        data['name'] = name
        with open(CONFIGFILE_NAME, 'w') as configfile:
            yaml.dump(data, configfile)

    def read(self, schema):
        try:
            config_data = self._load_config()
            config = self._validate_and_normalize(config_data, schema)
            config['environment'] = config.get('environment', config.get('params', {}))
            if config.get('params'):
                config.pop('params', None)
            return config
        except FileNotFoundError:
            raise ConfigFileNotFoundError('configuration file not found')

    def _load_config(self):
        with open(CONFIGFILE_NAME, 'r') as configfile:
            return yaml.load(configfile.read())

    def _validate_and_normalize(self, config_data, schema):
        v = Validator(schema)
        if v.validate(config_data):
            return v.document
        else:
            raise InvalidConfigException('configuration file validation failed: {}.'.format(v.errors))


def read_training_config(yaml_path):
    try:
        # TODO: fix here to find `.abeja` directory and
        # use `training.yaml` in it if there is the directory.
        with open(yaml_path, 'r') as configfile:
            return yaml.load(configfile.read())
    except FileNotFoundError:
        raise ConfigFileNotFoundError('configuration file not found')


def is_valid_image_and_handler_pair(image: str, handler: str) -> bool:
    """FIXME: For "20.02" trial. "20.02" image does not require "method" in "handler".

    Args:
        image (str): Need to be ABEJA container image.
        handler (str): Need to be "file:method" format. But "20.02" image can specify "file" also.

    Returns:
        (bool): True if valid pair.
    """
    if not image.endswith("20.02a") and ":" not in handler:
        return False
    return True
