import json
import os
import re
import subprocess
import sys

import click
import ruamel.yaml
import yamale
from PIL import Image

from abejacli.config import (
    ERROR_EXITCODE,
    ORGANIZATION_ENDPOINT,
    SUCCESS_EXITCODE
)
from abejacli.configuration import __ensure_configuration_exists
from abejacli.logger import get_logger
from abejacli.session import generate_user_session

LABS_APP_SKELETON_REPO = 'https://github.com/abeja-inc/platform-labs-app-skeleton-v1.git'
LABS_APP_THUMBNAIL_WIDTH_MAX = 800
LABS_APP_THUMBNAIL_HEIGHT_MAX = 600
LABS_APP_THUMBNAIL_SIZE_KB_MAX = 512

logger = get_logger()


@click.group(help='labs commands')
@click.pass_context
def labs(ctx):
    __ensure_configuration_exists(ctx)


# ---------------------------------------------------
# labs command
# ---------------------------------------------------
@labs.command(name='init', help='Prepare and create your own Labs App definition files')
@click.option('--name', 'name', prompt='Please enter your Labs App name', type=str, required=False, help='labs app name')
@click.option(
    '--app_type', 'app_type',
    prompt='Please enter your Labs App type',
    type=click.Choice(choices=['streamlit']), default='streamlit',
    required=False, help='labs app type'
)
# TODO: scope は現状 private のみ対応
# @click.option(
#     '--scope', 'scope',
#     prompt='Please enter your Labs App scope',
#     type=click.Choice(choices=['private', 'public']), default='private',
#     required=False, help='labs app scope'
# )
@click.option(
    '--scope', 'scope',
    prompt='Please enter your Labs App scope',
    type=click.Choice(choices=['private']), default='private',
    required=False, help='labs app scope'
)
@click.option(
    '--abeja_user_only', 'abeja_user_only',
    prompt='Please enter your Labs App can only access abejainc user',
    type=click.Choice(['Y', 'n']), default='Y',
    required=False, help='labs app only access abejainc user'
)
# TODO: auth_type は現状 abeja のみ対応
# @click.option(
#     '--auth_type', 'auth_type',
#     prompt='Please enter your Labs App auth type',
#     type=click.Choice(choices=['none', 'abeja']), default='abeja',
#     required=False, help='labs app auth type'
# )
@click.option(
    '--auth_type', 'auth_type',
    prompt='Please enter your Labs App auth type',
    type=click.Choice(choices=['abeja']), default='abeja',
    required=False, help='labs app auth type'
)
@click.option(
    '--author', 'author',
    prompt='Please enter your email',
    type=str, required=False, help='labs app auther email'
)
def init(name, app_type, scope, abeja_user_only, auth_type, author):
    """labs init コマンド
    Labs アプリ開発者に開発環境を提供するコマンド。
    GitHub で管理している Labs アプリ用 skeleton レポジトリを元に各種定義ファイルを用意する。

    Args:
        name(str) : Labs アプリ名
    """
    # 入力内容表示
    click.echo('\n==== Your Settings ============================')
    name = re.sub(r'[\\/:*?"<>|\.]+', '', name)
    click.echo(f'Download the skeleton file from {LABS_APP_SKELETON_REPO}.')
    click.echo(f'LabsApp name: {name}')
    click.echo(f'LabsApp appType: {app_type}')
    click.echo(f'LabsApp scope: {scope}')
    if(abeja_user_only == 'Y'):
        abeja_user_only = True
    else:
        abeja_user_only = False
    click.echo(f'LabsApp abejaUserOnly: {abeja_user_only}')
    click.echo(f'LabsApp authType: {auth_type}')
    click.echo(f'LabsApp author: {author}')
    click.echo('================================')

    # ファイルの自動作成前にユーザに確認する
    answer = click.prompt('Are you sure you want to create the above?', type=click.Choice(['Y', 'n']), default='Y')
    if answer == 'n':
        click.echo('Aborted!')
        sys.exit(ERROR_EXITCODE)

    git_clone_skeleton_files(
        repository_url=LABS_APP_SKELETON_REPO,
        destination_path=name,
        git_branch=app_type
    )

    # git 履歴初期化
    init_git(name)

    # setting.yaml の更新
    update_setting_yaml(name, scope, abeja_user_only, auth_type, author)

    # 処理正常終了
    click.echo('✨✨✨✨ It\'s done!! Happy Labs App! ✨✨✨✨\n')
    sys.exit(SUCCESS_EXITCODE)


# type 引数で渡しているclick.Path指定されたパスが実際に存在するかどうかを検証する
@labs.command(name='push', help='Upload your own Labs App definition files')
@click.option('-d', '--directory_path', 'directory_path', type=click.Path(exists=True, file_okay=False),
              help='Directory path where your own Labs App definition file is located. '
              f'The directory structure should be the same as {LABS_APP_SKELETON_REPO}',
              default=None, required=True)
def push(directory_path):
    """labs push コマンド
    ローカルで作成した Labs アプリ定義ファイルを ABEJA Platform にアップロードする

    Args:
        directory_path(click.Path) : アップロードしたい Labs アプリ定義ファイルが格納されているディレクトリ
    """
    url = f"{ORGANIZATION_ENDPOINT.replace('organizations', 'labs/organizations')}/apps"

    # 必要なファイルの存在を確認する
    upload_files = {
        'setting_yaml': os.path.join(directory_path, 'setting.yaml'),
        'thumbnail': os.path.join(directory_path, 'Thumbnail.jpg'),
        'how_to_use': os.path.join(directory_path, 'HowToUse.md'),
        'how_to_use_jp': os.path.join(directory_path, 'HowToUse_JP.md'),
    }
    for path in upload_files.values():
        if not os.path.isfile(path):
            click.echo(f'A required file is missing: {path}')
            sys.exit(ERROR_EXITCODE)

    # setting.yaml のフォーマットを確認する
    setting_schema = os.path.join(directory_path, 'setting_schema.yaml')
    verify_setting_yaml(upload_files["setting_yaml"], setting_schema)

    # Thumbnail.jpg の解像度を確認する
    thumbnail_img = Image.open(upload_files["thumbnail"])
    if thumbnail_img.width > LABS_APP_THUMBNAIL_WIDTH_MAX or thumbnail_img.height > LABS_APP_THUMBNAIL_HEIGHT_MAX:
        click.echo('Resolution of "{}" is {}x{}. Please fix thumbnail resolution under {}x{}.'.format(
            upload_files["thumbnail"],
            thumbnail_img.width, thumbnail_img.height,
            LABS_APP_THUMBNAIL_WIDTH_MAX, LABS_APP_THUMBNAIL_HEIGHT_MAX
        ))
        sys.exit(ERROR_EXITCODE)

    # Thumbnail.jpg のファイルサイズを確認する
    thumbnail_size_kb = int(round(os.path.getsize(upload_files["thumbnail"]) / 1024, 0))
    if thumbnail_size_kb > LABS_APP_THUMBNAIL_SIZE_KB_MAX:
        click.echo('File size of "{}" is {}KB. Please fix thumbnail file size under {}KB.'.format(
            upload_files["thumbnail"],
            thumbnail_size_kb,
            LABS_APP_THUMBNAIL_SIZE_KB_MAX
        ))
        sys.exit(ERROR_EXITCODE)

    try:
        # アップロード対象のファイルをリスト化してAPI に送信する
        files = []
        for file_name, file_path in upload_files.items():
            file = open(file_path, 'rb')
            if file_name == "setting_yaml":
                files.append((file_name, (os.path.basename(file_path), file, 'application/yaml')))
            elif file_name == "thumbnail":
                files.append((file_name, (os.path.basename(file_path), file, 'image/jpeg')))
            else:
                files.append((file_name, (os.path.basename(file_path), file, 'text/markdown')))
        with generate_user_session(False) as session:
            response = session.post(url, files=files, timeout=None)

        response.raise_for_status()
        content = response.json()

        content.pop('setting_yaml_base64', None)
        content.pop('thumbnail_base64', None)
        content.pop('how_to_use_base64', None)
        content.pop('how_to_use_jp_base64', None)

        click.echo('Upload succeeded')
        click.echo(json.dumps(content, indent=4))

    except Exception as e:
        click.echo('Error: Failed to upload files {} to LabsApp repository (Reason: {})'.format(upload_files, e))
        sys.exit(ERROR_EXITCODE)
    finally:
        # io.BufferedReader を全てclose する
        for _, file in files:
            file[1].close()

    # 処理正常終了
    click.echo('✨✨✨✨ It\'s done!! Happy Labs App! ✨✨✨✨\n')
    sys.exit(SUCCESS_EXITCODE)


def update_setting_yaml(name, scope='private', abeja_user_only=True, auth_type='abeja', author=''):
    """引数で渡された内容をもとにsetting.yaml を更新する
    setting.yaml は`./{name}/setting.yaml` に配置されていることを想定している

    Args:
        name (str): Labs アプリ名
        scope (str): Labs アプリの公開設定 'public' or 'private'
        abeja_user_only (bool): ABEJA Only か否か
    """

    setting_yaml_path = f'./{name}/setting.yaml'

    try:
        # YAML ファイルを読み込み
        yaml = ruamel.yaml.YAML()
        with open(setting_yaml_path, 'r') as file:
            data = yaml.load(file)

        # 内容を編集
        data['metadata']['name'] = name
        data['metadata']['scope'] = scope
        data['metadata']['abejaUserOnly'] = abeja_user_only
        data['metadata']['authType'] = auth_type
        data['metadata']['author'] = author
        data['spec']['image'] = f'{name}:latest'

        # 編集後の内容をYAMLファイルに書き込み
        with open(setting_yaml_path, 'w') as file:
            yaml.dump(data, stream=file)

    except yaml.YAMLError as e:
        click.echo(f"YAML Error: {str(e)}")
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        click.echo(f"An unexpected error has occurred.: {str(e)}")
        sys.exit(ERROR_EXITCODE)


def git_clone_skeleton_files(repository_url, destination_path, git_branch='main'):
    """引数で指定されたリポジトリからgit clone で宛先のパスにファイルをダウンロードする
    Args:
        repository_url (str): git hub リポジトリ のhttps のURL
        destination_path (str): git clone するローカルのパス
        git_branch (str): 取得先のリポジトリのブランチ名（指定がなければmain）
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


def init_git(name):
    try:
        subprocess.run(['rm', '-rf', f'{name}/.git'], check=True)
        subprocess.run(['git', 'init', name], check=True)
    except Exception as e:
        click.echo(f'Failed to init git: {e}\n')


def verify_setting_yaml(setting_yaml, setting_schema):
    try:
        schema = yamale.make_schema(setting_schema)
        data = yamale.make_data(setting_yaml)
        yamale.validate(schema, data, strict=False)
    except ValueError as e:
        click.echo(f'Validation failed of setting.yaml!: {e}\n')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        click.echo(f'Exception was occurred!: {e}\n')
        sys.exit(ERROR_EXITCODE)
    return
