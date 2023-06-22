import json
import os

import pytest
from mock import MagicMock, patch

from abejacli.docker.container_run import ContainerBuildAndRun


@pytest.fixture
def container_build_and_run():
    with patch.object(ContainerBuildAndRun, '_setup_docker'):
        return ContainerBuildAndRun(
            image_type='train',
            handler='train:handler',
            image='abeja/all-cpu:18.10',
            organization_id='1234567890123',
            datasets={}, environment={},
            volume={}, no_cache=False)


class TestContainerBuildAndRun:

    def test_find_or_build_image(self, container_build_and_run):
        container_build_and_run._find_built_image = MagicMock(
            return_value=None)
        container_build_and_run._build_image = MagicMock()

        with pytest.raises(RuntimeError):
            container_build_and_run._find_or_build_image()

    @pytest.mark.parametrize("test_dir, expected", [
        ('tests/unit/resources/container_run_test/exist_pipfile', 'a7251a3b0a5586a6301d450b9bab8501'),
        ('tests/unit/resources/container_run_test/exist_requirements', 'abdc069736ab4b295de3d8581dc050bd'),
        ('tests/unit/resources/container_run_test/no_requirements', 'a83daf73508de5f3294cd744dc2b06f1'),
    ])
    def test_calc_md5(self, test_dir, expected, container_build_and_run):
        base_dir = os.getcwd()
        os.chdir(os.path.join(base_dir, test_dir))
        actual = container_build_and_run._calc_md5()
        os.chdir(base_dir)
        assert expected == actual

    def test_stdout_build_output(self, container_build_and_run):
        output_1 = "Step 1/6 : FROM abeja-inc/all-cpu:18.10"
        output_2 = "pull access denied for abeja-inc/all-cpu, repository does not exist or may require 'docker login'"    # noqa
        output_lines = [
            json.dumps({
                "stream": output_1
            }).encode('utf-8'),
            json.dumps({
                "errorDetail": {
                    "message": "pull access denied for abeja-inc/all-cpu, repository does not exist or may require 'docker login'"  # noqa
                },
                "error": output_2
            }).encode('utf-8')
        ]
        container_build_and_run.stdout = mock_stdout = MagicMock()
        for output in output_lines:
            container_build_and_run._stdout_build_output(output)

        assert mock_stdout.call_count == 2
        call_arg_1 = mock_stdout.call_args_list[0][0][0]
        call_arg_2 = mock_stdout.call_args_list[1][0][0]

        for actual, expected in zip([call_arg_1, call_arg_2], [output_1, output_2]):
            assert actual == expected
