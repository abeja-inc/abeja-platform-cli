import json
from unittest.mock import MagicMock, Mock, patch

from abejacli.docker.commands.run import ModelRunCommand
from abejacli.model import md5file
from abejacli.model.docker_handler import (BUILT_IMAGE_SUFFIX,
                                           DOCKERFILE_RUN_LOCAL_TEMPLATE,
                                           LOCAL_MODEL_REQUIREMENTS_MD5_KEY,
                                           LOCAL_MODEL_TYPE_VALUE,
                                           REQUIREMENTS_TXT, LocalModelHandler)
from pyfakefs.fake_filesystem_unittest import TestCase

IMAGE = 'abeja/test-model'
TAG = 'testing'


class LocalModelHandlerTest(TestCase):
    def setUp(self):
        self.setUpPyfakefs()
        self.local_model = LocalModelHandler()

    @patch('abejacli.model.docker_handler.docker')
    def test_generate_run_dockerfile(self, m):
        dockerfile = self.local_model._generate_run_dockerfile(IMAGE, TAG)
        self.assertIn('FROM {}:{}'.format(IMAGE, TAG), dockerfile)

    @patch('abejacli.model.docker_handler.docker')
    def test_check_rebuild_required_without_requirements_txt(self, m):
        not_exist_file_path = ''  # os.path.exists returns False with empty string
        self.local_model.requirements_file = not_exist_file_path
        self.assertFalse(self.local_model.check_rebuild_required())

    @patch('abejacli.model.docker_handler.docker')
    def test_check_rebuild_required_without_built_image(self, m):
        self.local_model._find_built_image = Mock(return_value=None)
        self.fs.create_file(REQUIREMENTS_TXT, contents='')
        self.assertTrue(self.local_model.check_rebuild_required())

    @patch('abejacli.model.docker_handler.docker')
    def test_check_rebuild_required_with_built_image_no_label(self, m):
        dummy_image = Mock()
        dummy_image.labels = {}
        self.local_model._find_built_image = Mock(return_value=dummy_image)
        self.fs.create_file(REQUIREMENTS_TXT, contents='')
        self.assertTrue(self.local_model.check_rebuild_required())

    @patch('abejacli.model.docker_handler.docker')
    def test_check_rebuild_required_with_built_image_different_prev_label(self, m):
        self.fs.create_file(REQUIREMENTS_TXT, contents='')

        dummy_image = Mock()
        dummy_image.labels = {
            LOCAL_MODEL_REQUIREMENTS_MD5_KEY: ''
        }
        self.local_model._find_built_image = Mock(return_value=dummy_image)
        self.assertTrue(self.local_model.check_rebuild_required())

    @patch('abejacli.model.docker_handler.docker')
    def test_check_rebuild_required_with_built_image_same_prev_label(self, m):
        self.fs.create_file(REQUIREMENTS_TXT, contents='')

        dummy_image = Mock()
        dummy_image.labels = {
            LOCAL_MODEL_REQUIREMENTS_MD5_KEY: md5file(REQUIREMENTS_TXT)
        }
        self.local_model._find_built_image = Mock(return_value=dummy_image)
        self.assertFalse(self.local_model.check_rebuild_required())

    @patch('abejacli.model.docker_handler.docker')
    def test_build_run_image_without_built_image(self, m):
        mock_build_image = Mock()
        self.local_model._find_built_image = Mock(return_value=None)
        self.local_model._build_image = mock_build_image

        self.local_model.build_run_image(IMAGE, TAG, LOCAL_MODEL_TYPE_VALUE)

        expected_image = '{}/{}/{}-{}'.format(
            IMAGE, TAG, LOCAL_MODEL_TYPE_VALUE, BUILT_IMAGE_SUFFIX)
        expected_dockerfile = DOCKERFILE_RUN_LOCAL_TEMPLATE.format(
            IMAGE='{}:{}'.format(IMAGE, TAG))
        mock_build_image.assert_called_once_with(
            expected_image, expected_dockerfile, LOCAL_MODEL_TYPE_VALUE, None)

    @patch('abejacli.model.docker_handler.docker')
    def test_build_run_image_with_built_image(self, m):
        self.local_model._find_built_image = Mock(return_value=Mock())

        self.local_model.check_rebuild_required = Mock(return_value=False)
        mock_build_image = Mock()
        self.local_model._build_image = mock_build_image

        self.local_model.build_run_image(IMAGE, TAG)

        mock_build_image.assert_not_called()

    @patch('abejacli.model.docker_handler.docker')
    def test_create_local_server(self, m):
        port = 50000
        self.local_model.run_container = MagicMock()
        command = ModelRunCommand.create(
            image='dummy', handler='dummy:handler', device_type='x86_cpu', port=port)
        local_server = self.local_model.create_local_server(command)

        self.assertEqual(local_server.endpoint,
                         'http://localhost:{}'.format(port))

    @patch('abejacli.model.docker_handler.docker')
    def test_parser_stream(self, m):
        dummy_logs = [{'test': 'dummy_{}'.format(i)} for i in range(10)]
        output_text = '\r\n'.join([json.dumps(l) for l in dummy_logs])
        log_gen = self.local_model._parse_stream(output_text.encode('utf-8'))
        self.assertListEqual(list(log_gen), dummy_logs)
