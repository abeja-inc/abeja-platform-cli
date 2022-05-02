import os
import signal
import sys

import click


class ClickLogger:
    def __init__(self, disable: bool = False):
        self.disable = disable

    def raw(self, msg):
        if not self.disable:
            click.echo(msg)

    def debug(self, msg):
        if not self.disable and os.environ.get('DEBUG') is not None:
            click.echo(msg)

    def info(self, msg):
        if not self.disable:
            click.echo('[info] {}'.format(msg))

    def warn(self, msg):
        if not self.disable:
            click.secho('[warn] {}'.format(msg), fg='yellow')

    def error(self, msg):
        if not self.disable:
            click.secho('[error] {}'.format(msg), err=True, fg='red')


class Run:
    """
    Examples: subclass of this class can be used as follows.

    >>> with Run(quiet=False) as run:
    >>>     pass
    """

    def __init__(self, *args, **kwargs):
        disable = kwargs.get('quiet', False)
        self.logger = ClickLogger(disable=disable)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def __enter__(self):
        try:
            self._prepare()
            self._start()
            return self
        except Exception:
            self._clean()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._end()

    def _signal_handler(self, _signum, _frame):
        self._clean()
        sys.exit(1)

    def _prepare(self):
        """called when before started"""

    def _start(self):
        """called when started"""

    def _end(self):
        """called when finished"""
        self._on_end()
        self._clean()

    def _on_end(self):
        """called when after finished"""

    def _clean(self):
        """called when before exit"""
