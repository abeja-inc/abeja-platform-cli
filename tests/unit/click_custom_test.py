from unittest import TestCase

import click
import pytest
from click.testing import CliRunner
from parameterized import parameterized

from abejacli.click_custom import (
    DatasetParamType,
    EnvParamType,
    PortNumberType,
    UserParamType,
    VolumeParamType,
    convert_to_local_image_callback
)


class TestPortNumberType(TestCase):
    def setUp(self):
        self.param_type = PortNumberType()

    def test_convert(self):
        port = self.param_type.convert("3000", None, None)
        self.assertEqual(port, 3000)

    def test_convert_not_number(self):
        with self.assertRaises(click.exceptions.BadParameter):
            self.param_type.convert("test", None, None)

    def test_convert_out_of_range(self):
        with self.assertRaises(click.exceptions.BadParameter):
            self.param_type.convert("70000", None, None)


class TestMetadataParamType(TestCase):
    def setUp(self):
        self.param_type = UserParamType()

    def test_convert(self):
        m1, m2 = self.param_type.convert("key:value", None, None)
        self.assertEqual(m1, "key")
        self.assertEqual(m2, "value")


class TestEnvParamType(TestCase):
    def setUp(self):
        self.param_type = EnvParamType()

    @parameterized.expand([
        ("key:value", "key", "value"),
        ("key", "key", ""),
        ("key:.value", "key", ".value"),
        ("key:value1:value2", "key", "value1:value2"),
        ("key:value value", "key", "value value"),
        ("key:value\nvalue", "key", "value\nvalue"),
        ("key:", "key", "")
    ])
    def test_convert(self, value, expected_key, expected_value):
        m1, m2 = self.param_type.convert(value, None, None)
        self.assertEqual(m1, expected_key)
        self.assertEqual(m2, expected_value)

    def test_convert_without_key(self):
        with self.assertRaises(click.exceptions.BadParameter):
            self.param_type.convert(':value', None, None)


class TestUserParamType(TestCase):
    def setUp(self):
        self.param_type = UserParamType()

    def test_convert(self):
        m1, m2 = self.param_type.convert("key:value", None, None)
        self.assertEqual(m1, "key")
        self.assertEqual(m2, "value")


@pytest.fixture
def dataset_param_type():
    return DatasetParamType()


class TestDatasetParamType:
    def test_convert(self, dataset_param_type):
        m1, m2 = dataset_param_type.convert("flower-classification:1234567890123", None, None)
        assert m1 == "flower-classification"
        assert m2 == "1234567890123"


@pytest.fixture
def volume_param_type():
    return VolumeParamType()


class TestVolumeParamType:
    @pytest.mark.parametrize("given,expected_key,expected_value", [
        ("/hoge/moge:/foo", "/hoge/moge", "/foo"),
        ("myvol2:/app", "myvol2", "/app"),
        ("/a/b/c:/a-b-c", "/a/b/c", "/a-b-c"),
        ("/1:/foo$/bar#/@aa", "/1", "/foo$/bar#/@aa")
    ])
    def test_convert(self, volume_param_type, given, expected_key, expected_value):
        m1, m2 = volume_param_type.convert(given, None, None)
        assert m1 == expected_key
        assert m2 == expected_value


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.parametrize(
    'given,expected', [
        ('abeja-inc/all-cpu:19.04', 'abeja/all-cpu:19.04'),
        ('abeja/all-cpu:19.04', 'abeja/all-cpu:19.04'),
        ('custom/1230000000000/sample_repository_1:e599',
         'custom/1230000000000/sample_repository_1:e599'),
        ('custom/1230000000000/abeja-inc/all-cpu:18.10',
         'custom/1230000000000/abeja-inc/all-cpu:18.10'),
        ('abeja-inc-hoge/abeja-inc-fuga:latest',
         'abeja-inc-hoge/abeja-inc-fuga:latest')
    ])
def test_convert_to_local_image_callback(given, expected, runner):
    @click.command()
    @click.option('--image', 'image', type=str, required=True,
                  callback=convert_to_local_image_callback)
    def dummy_command(image):
        assert image == expected

    r = runner.invoke(dummy_command, ['--image', given])
    assert r.exit_code == 0
