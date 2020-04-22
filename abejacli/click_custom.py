import re
from datetime import date

from click import Option, ParamType, UsageError

from abejacli.common import convert_to_local_image_name
from abejacli.config import (
    DATASET_VAR_KEY_FORMAT,
    ENV_VAR_KEY_FORMAT,
    VOLUME_FORMAT
)


class MutuallyExclusiveAndRequireOption(Option):
    """
    Mutually exclude other specified options

    Note: this implementation refers to https://gist.github.com/jacobtolar/fb80d5552a9a9dfc32b12a829fa21c0c
    """

    def __init__(self, *args, **kwargs):
        self.mutually_exclusive = set(kwargs.pop('mutually_exclusive', []))
        self.requires = set(kwargs.pop('requires', []))
        help = kwargs.get('help', '')
        if self.mutually_exclusive:
            ex_str = ', '.join(self.mutually_exclusive)
            kwargs['help'] = help + (
                ' NOTE: This argument is mutually exclusive with '
                ' arguments: [' + ex_str + '].'
            )
        super(MutuallyExclusiveAndRequireOption,
              self).__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        if self.name in opts and self.mutually_exclusive and self.mutually_exclusive.intersection(opts):
            raise UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(
                    self.name,
                    ', '.join(self.mutually_exclusive)
                )
            )

        if self.name in opts and self.requires and not self.requires.intersection(opts):
            raise UsageError(
                "Illegal usage: `{}` requires "
                "arguments `{}`.".format(
                    self.name,
                    ', '.join(self.requires)
                )
            )

        return super(MutuallyExclusiveAndRequireOption, self).handle_parse_result(
            ctx,
            opts,
            args
        )


class PortNumberType(ParamType):
    name = 'PortNumber'

    def convert(self, value, param, ctx):
        if value is None:
            return value
        try:
            port = int(value)
            if 0 < port and port <= 65535:
                return port
            self.fail('{} must be number in 1 - 65535'.format(value), param, ctx)
        except ValueError:
            self.fail('{} is not valid port number'.format(value), param, ctx)


class DateStrParamType(ParamType):
    name = 'DateString'

    def convert(self, value, param, ctx):
        try:
            if len(value) != 8:
                raise ValueError('invalid date string length')
            year, month, day = value[:4], value[4:6], value[6:]
            date(int(year), int(month), int(day))
            return value
        except (TypeError, ValueError):
            self.fail('{} is not a valid date string, date string should be YYYYMMDD'.format(
                value), param, ctx)


class EnvParamType(ParamType):
    name = 'EnvironmentString'

    def convert(self, value, param, ctx):
        # names shall not contain the character '='
        # values consists of portable character set
        # portable character set
        # http://pubs.opengroup.org/onlinepubs/000095399/basedefs/xbd_chap06.html#tagtcjh_3
        key = value.split(':')[0]
        if not re.match(ENV_VAR_KEY_FORMAT, key):
            self.fail('{} is not a valid environment variable, environment variable name should be {}'
                      .format(value, ENV_VAR_KEY_FORMAT), param, ctx)
        return key, ':'.join(value.split(':')[1:])


class MetadataParamType(EnvParamType):
    name = 'MetadataString'


class UserParamType(EnvParamType):
    name = 'UserParamString'


class VolumeParamType(ParamType):
    name = 'VolumeParamString'

    def convert(self, value, param, ctx):
        """
        Returns:
            ex. ('/tmp', '/user')
        """
        try:
            k, v = value.split(':')
        except ValueError:
            self.fail('{} is not a valid volume, volume name should include `:`'
                      .format(value), param, ctx)
        if (not re.match(VOLUME_FORMAT, k)) or (not re.match(VOLUME_FORMAT, v)):
            self.fail('{} is not a valid volume, volume option should be {}'
                      .format(value, VOLUME_FORMAT), param, ctx)
        return k, v


class DatasetParamType(EnvParamType):
    name = 'DatasetParamString'

    def convert(self, value, param, ctx):
        # names shall not contain the character '='
        # values consists of portable character set
        # portable character set
        # http://pubs.opengroup.org/onlinepubs/000095399/basedefs/xbd_chap06.html#tagtcjh_3
        key = value.split(':')[0]
        if not re.match(DATASET_VAR_KEY_FORMAT, key):
            self.fail('{} is not a valid dataset variable, dataset variable name should be {}'
                      .format(value, DATASET_VAR_KEY_FORMAT), param, ctx)
        return key, ':'.join(value.split(':')[1:])


DATE_STR = DateStrParamType()
PORT_NUMBER = PortNumberType()
METADATA_STR = MetadataParamType()
ENVIRONMENT_STR = EnvParamType()
USER_PARAM_STR = UserParamType()
VOLUME_PARAM_STR = VolumeParamType()
DATASET_PARAM_STR = DatasetParamType()


def convert_to_local_image_callback(ctx, _param, value):
    if not value or ctx.resilient_parsing:
        return
    return convert_to_local_image_name(value)
