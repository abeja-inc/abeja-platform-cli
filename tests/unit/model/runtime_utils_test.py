import pytest

from abejacli.config import RUN_LOCAL_COMMAND_V1, RUN_LOCAL_COMMAND_V2
from abejacli.model.runtime_utils import get_runtime_command


@pytest.mark.parametrize(
    '_, params, expect', [
        ('18.10', {'image': 'abeja/all-cpu', 'tag': '18.10', 'v1': False}, RUN_LOCAL_COMMAND_V1),
        ('19.04', {'image': 'abeja/all-cpu', 'tag': '19.04', 'v1': False}, RUN_LOCAL_COMMAND_V2),
        ('18.10', {'image': 'abeja-inc/all-cpu', 'tag': '18.10', 'v1': False}, RUN_LOCAL_COMMAND_V1),
        ('19.04', {'image': 'abeja-inc/all-cpu', 'tag': '19.04', 'v1': False}, RUN_LOCAL_COMMAND_V2),
        ('Local:0.1.0', {'image': 'my-image', 'tag': '0.1.0', 'v1': False}, RUN_LOCAL_COMMAND_V2),
        ('Local:18.10', {'image': 'my-image', 'tag': '18.10', 'v1': False}, RUN_LOCAL_COMMAND_V2),
        ('Custom:v1flag:True', {'image': 'abeja/all-cpu', 'tag': 'custom', 'v1': True}, RUN_LOCAL_COMMAND_V1),
        ('Custom:v1flag:False', {'image': 'abeja/all-cpu', 'tag': 'custom', 'v1': False}, RUN_LOCAL_COMMAND_V2),
    ]
)
def test_get_runtime_command(_, params, expect):
    actual = get_runtime_command(params['image'], params['tag'], params['v1'])
    assert actual == expect
