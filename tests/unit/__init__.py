from mock import patch
from abejacli.configuration.config import Config, ConfigSet


class ConfigPatcher():
    def __init__(self):
        self.config_set = ConfigSet()
        self.config_patcher = None

    def add(self, *args, **kwargs):
        self.config_set.add(Config(*args, **kwargs))
        return self

    def any(self):
        return self.add(user='x', token='x', organization='x')

    def start(self):
        self.config_patcher = patch('abejacli.configuration.loader.ConfigSetLoader.load',
                                    return_value=self.config_set)
        self.config_patcher.start()
        return self

    def stop(self):
        self.config_patcher.stop()
        return self
