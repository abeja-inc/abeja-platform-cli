import json
import os
from unittest import mock

import pytest

from abejacli.configuration.config import Config
from abejacli.configuration.formatter import ConfigFormatter


@pytest.fixture
def config():
    return Config(user='1234567890123', token='1935793145984317957049835709', organization='abeja-inc')


class TestConfigFormatter(object):

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_build(self, config):
        formatter = ConfigFormatter.build(config)
        assert formatter
        formatter = ConfigFormatter.build(config, format='json')
        assert formatter

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_plain(self, config):
        formatter = ConfigFormatter.build(config)
        assert formatter.format() == \
            'abeja-platform-user:user-1234567890123\n' + \
            'personal-access-token:1935793145984317957049835709\n' + \
            'organization-name:abeja-inc'

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_plain_filters(self, config):
        formatter = ConfigFormatter.build(config)
        assert formatter.format(
            user=True) == 'abeja-platform-user:user-1234567890123'
        formatter = ConfigFormatter.build(config)
        assert formatter.format(
            token=True) == 'personal-access-token:1935793145984317957049835709'
        formatter = ConfigFormatter.build(config)
        assert formatter.format(
            organization=True) == 'organization-name:abeja-inc'

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_json(self, config):
        formatter = ConfigFormatter.build(config, format='json')
        assert json.loads(formatter.format()) == {
            'abeja-platform-user': config.user,
            'personal-access-token': config.token,
            'organization-name': config.organization,
        }
