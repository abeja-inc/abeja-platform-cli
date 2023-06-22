
import click

from abejacli.configuration import __ensure_configuration_exists


@click.group(help='sample_cli operation commands')
@click.pass_context
def sample_cli(ctx):
    __ensure_configuration_exists(ctx)


@sample_cli.command(name='print-hellow-world', help='Print Hellow World')
@click.option('-n', '--name', type=str, help='Display name', required=True)
def print_hello_world(name):
    print(f"hello world!! {name}")
    return
