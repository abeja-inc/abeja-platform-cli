
class InvalidDatalakeTimeInterval(Exception):
    pass


class BaseTrainingException(Exception):
    pass


class InvalidConfigException(BaseTrainingException):
    pass


class ConfigFileNotFoundError(BaseTrainingException):
    pass


class ResourceNotFound(Exception):
    pass
