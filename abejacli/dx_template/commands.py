import os
import re
import subprocess
import sys

import click
import yaml

from abejacli.common import __try_get_organization_id
from abejacli.config import ERROR_EXITCODE, SUCCESS_EXITCODE
from abejacli.configuration import __ensure_configuration_exists
from abejacli.logger import get_logger

DX_TEMPLATE_SKELETON_REPO = 'https://github.com/abeja-inc/platform-dx-template-samples.git'

logger = get_logger()


@click.group(help='dx-template commands')
@click.pass_context
def dx_template(ctx):
    __ensure_configuration_exists(ctx)


# ---------------------------------------------------
# dx_template command
# ---------------------------------------------------
@dx_template.command(name='init', help='DX template difinition files create commands')
@click.option('-n', '--name', 'name', prompt='Please enter your DX template name', type=str, required=False,
              help='DX template name')
@click.option('-o', '--organization_id', '--organization-id', 'organization_id', type=str, required=False,
              help='Organization ID, organization_id of current credential organization is used by default. '
                   'This value is set as an environment variable named `ABEJA_ORGANIZATION_ID`. '
                   '`ABEJA_ORGANIZATION_ID` from this arg takes priority over one in `--environment`.',
              callback=__try_get_organization_id)
@click.option('-s', '--skeleton_file', '--skeleton-file', 'skeleton_file', type=click.Choice(['Y', 'n']), default='Y',
              prompt='want DX template definition skeleton files?',
              help='get (or not get) skeleton files')
def init(name, organization_id, skeleton_file):
    """dx-template init コマンド
    Args:
        name(str) : DX テンプレート名
        organization_id(str) : オーガニゼーションID
        skeleton_file(str) : skeleton ファイルの要否（Y or n）
    """
    click.echo('\n==== Your Settings ============================')

    # 入力されたDX テンプレート名でファイルやフォルダ名に入れない方が良い文字は削除する
    name = re.sub(r'[\\/:*?"<>|\.]+', '', name)
    click.echo(f'DX Template name: {name}')

    # DX テンプレートのサンプルファイル取得要否
    if skeleton_file == 'Y':
        click.echo(f'Download the skeleton file from {DX_TEMPLATE_SKELETON_REPO}.')
    else:
        click.echo('Skeleton files will not be downloaded.')

    # Future Work: 公開/非公開設定
    click.echo('This DX template is used only inside your organization.')
    publish_type = 'private'

    # Future Work: ABEJA only　設定
    click.echo('This DX template is used only inside ABEJA inc.')
    abeja_user_only = True

    click.echo('================================')

    # ファイルの自動作成前にユーザに確認する
    answer = click.prompt('Are you sure you want to create the above?', type=click.Choice(['Y', 'n']))
    if answer == 'n':
        click.echo('Aborted!')
        sys.exit(ERROR_EXITCODE)

    # skeleton ファイルの取得と保存
    if skeleton_file == 'Y':
        git_clone_skeleton_files(DX_TEMPLATE_SKELETON_REPO, name)

    # template.yaml の作成
    create_and_save_template_yaml(organization_id, name, publish_type, abeja_user_only)

    # 処理正常終了
    click.echo('✨✨✨✨ It\'s done!! Happy DX! ✨✨✨✨\n')
    sys.exit(SUCCESS_EXITCODE)


def create_and_save_template_yaml(organization_id, name, publish_type, abeja_user_only):
    """引数で渡された内容をもとにtemplate.yaml を作成して保存する
    Args:
        organization_id (str): オーガニゼーションID
        name (str): DX テンプレート名
        publish_type (str): DX テンプレートの公開設定 'public' or 'private'
        abeja_user_only (bool): ABEJA Only か否か
    """

    # YAML 生成に使う辞書作成
    yaml_data = {
        'organization_id': organization_id,
        'name': name,
        'descripton': '',
        'type': publish_type,
        'abeja_user_only': abeja_user_only
    }

    # ディレクトリ作成しYAML ファイルを保存する（既に同名ディレクトリ、ファイルがある場合は上書き）
    output_dir = f'./{name}'
    os.makedirs(output_dir, exist_ok=True)
    output_file = f'./{name}/template.yaml'
    try:
        with open(output_file, 'w') as file:
            yaml.dump(yaml_data, file)
    except FileNotFoundError:
        click.echo('failed to create the directory or yaml file. check DX template name you input.\n')
        sys.exit(ERROR_EXITCODE)

    click.echo(f'YAML file saved as: {output_file}\n')


def git_clone_skeleton_files(repository_url, destination_path, git_branch='main'):
    """引数で指定されたリポジトリからgit clone で宛先のパスにファイルをダウンロードする
    Args:
        repository_url (str): git hub リポジトリ のhttps のURL
        destination_path (str): git clone するローカルのパス
        git_branch (str): 取得先のリポジトリのブランチ名（していなければmain）
    """
    try:
        click.echo('================================')
        click.echo(f'Cloning repository: {repository_url} to {destination_path}')
        # check=Trueを指定することで、git cloneがエラーを返した場合にCalledProcessError が発生
        subprocess.run(['git', 'clone', '-b', git_branch, repository_url, destination_path], check=True)
        click.echo('\nRepository cloned successfully!\n')
        click.echo('================================\n')

    except subprocess.CalledProcessError as e:
        click.echo(f'Error occurred while cloning repository: {e}\n')
        sys.exit(ERROR_EXITCODE)

    except Exception as e:
        click.echo(f'An error occurred: {e}\n')
        sys.exit(ERROR_EXITCODE)
