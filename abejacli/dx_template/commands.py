import json
import os
import re
import subprocess
import sys
import zipfile

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

DX_TEMPLATE_SKELETON_REPO = 'https://github.com/abeja-inc/platform-dx-template-skeleton-v1.git'
DX_TEMPLATE_THUMBNAIL_WIDTH_MAX = 800
DX_TEMPLATE_THUMBNAIL_HEIGHT_MAX = 600
DX_TEMPLATE_THUMBNAIL_SIZE_KB_MAX = 512

logger = get_logger()


@click.group(help='dx-template commands')
@click.pass_context
def dx_template(ctx):
    __ensure_configuration_exists(ctx)


# ---------------------------------------------------
# dx_template command
# ---------------------------------------------------
@dx_template.command(name='init', help='Prepare and create your own DX template definition files')
@click.option('-n', '--name', 'name', prompt='Please enter your DX template name', type=str, required=False,
              help='DX template name')
def init(name):
    """dx-template init コマンド
    DX テンプレート開発者に開発環境を提供するコマンド。
    git hub で管理しているDX テンプレート用のskeleton ファイルを元に各種定義ファイルを用意する。

    Args:
        name(str) : DX テンプレート名
    """
    click.echo('\n==== Your Settings ============================')

    # 入力されたDX テンプレート名でファイルやフォルダ名に入れない方が良い文字は削除する
    name = re.sub(r'[\\/:*?"<>|\.]+', '', name)
    click.echo(f'DX Template name: {name}')

    # DX テンプレートのサンプルファイル取得要否
    click.echo(f'Download the skeleton file from {DX_TEMPLATE_SKELETON_REPO}.')

    # Future Work: 公開/非公開設定
    click.echo('This DX template is used only inside your organization.')
    template_scope = 'private'

    # Future Work: ABEJA only　設定
    click.echo('This DX template is used only inside ABEJA inc.')
    abeja_user_only = True

    click.echo('================================')

    # ファイルの自動作成前にユーザに確認する
    answer = click.prompt('Are you sure you want to create the above?', type=click.Choice(['Y', 'n']))
    if answer == 'n':
        click.echo('Aborted!')
        sys.exit(ERROR_EXITCODE)

    git_clone_skeleton_files(DX_TEMPLATE_SKELETON_REPO, name)

    # git 履歴初期化
    init_git(name)

    # template.yaml の更新
    update_template_yaml(name, template_scope, abeja_user_only)

    # 処理正常終了
    click.echo('✨✨✨✨ It\'s done!! Happy DX! ✨✨✨✨\n')
    sys.exit(SUCCESS_EXITCODE)


# type 引数で渡しているclick.Path指定されたパスが実際に存在するかどうかを検証する
@dx_template.command(name='push', help='Upload your own DX template definition files')
@click.option('-d', '--directory_path', 'directory_path', type=click.Path(exists=True, file_okay=False),
              help='Directory path where your own DX template definition file is located. '
              f'The directory structure should be the same as {DX_TEMPLATE_SKELETON_REPO}',
              default=None, required=True)
def push(directory_path):
    """dx-template push コマンド
    ローカルで作成したDX テンプレート定義ファイルを ABEJA Platform にアップロードする

    Args:
        directory_path(click.Path) : アップロードしたいDX テンプレート定義ファイルが格納されているディレクトリ
    """
    url = '{}/dx-templates'.format(ORGANIZATION_ENDPOINT)

    # 必要なファイルの存在を確認する
    upload_files = {
        'template_yaml': os.path.join(directory_path, 'template.yaml'),
        'handler': os.path.join(directory_path, 'src/abeja_platform/deployments/run/handler.py'),
        'thumbnail': os.path.join(directory_path, 'Thumbnail.jpg'),
        'how_to_use': os.path.join(directory_path, 'DxTemplate.md'),
        'how_to_use_jp': os.path.join(directory_path, 'DxTemplate_JP.md'),
    }
    for path in upload_files.values():
        if not os.path.isfile(path):
            click.echo(f'A required file is missing: {path}')
            sys.exit(ERROR_EXITCODE)

    # template.yaml のフォーマットを確認する
    template_schema = os.path.join(directory_path, 'template_schema.yaml')
    verify_dxtemplate_yaml(upload_files["template_yaml"], template_schema)

    # Thumbnail.jpg の解像度を確認する
    thumbnail_img = Image.open(upload_files["thumbnail"])
    if thumbnail_img.width > DX_TEMPLATE_THUMBNAIL_WIDTH_MAX or thumbnail_img.height > DX_TEMPLATE_THUMBNAIL_HEIGHT_MAX:
        click.echo('Resolution of "{}" is {}x{}. Please fix thumbnail resolution under {}x{}.'.format(
            upload_files["thumbnail"],
            thumbnail_img.width, thumbnail_img.height,
            DX_TEMPLATE_THUMBNAIL_WIDTH_MAX, DX_TEMPLATE_THUMBNAIL_HEIGHT_MAX
        ))
        sys.exit(ERROR_EXITCODE)

    # Thumbnail.jpg のファイルサイズを確認する
    thumbnail_size_kb = int(round(os.path.getsize(upload_files["thumbnail"]) / 1024, 0))
    if thumbnail_size_kb > DX_TEMPLATE_THUMBNAIL_SIZE_KB_MAX:
        click.echo('File size of "{}" is {}KB. Please fix thumbnail file size under {}KB.'.format(
            upload_files["thumbnail"],
            thumbnail_size_kb,
            DX_TEMPLATE_THUMBNAIL_SIZE_KB_MAX
        ))
        sys.exit(ERROR_EXITCODE)

    # handler.py をrun ディレクトリごとzip で固める
    handler_dire_path = os.path.join(directory_path, 'src/abeja_platform/deployments/run')
    zip_path = os.path.join(directory_path, 'src/abeja_platform/deployments/handler.zip')
    try:
        files_and_directorys_to_zip(handler_dire_path, zip_path)
    except Exception as e:
        print(f"Failed to create zip file: {zip_path}\nError: {str(e)}")
        sys.exit(ERROR_EXITCODE)
    upload_files['handler'] = zip_path

    try:
        # アップロード対象のファイルをリスト化してAPI に送信する
        files = []
        for file_name, file_path in upload_files.items():
            file = open(file_path, 'rb')
            if file_name == "template_yaml":
                files.append((file_name, (os.path.basename(file_path), file, 'application/yaml')))
            elif file_name == "handler":
                files.append((file_name, (os.path.basename(file_path), file, 'application/zip')))
            elif file_name == "thumbnail":
                files.append((file_name, (os.path.basename(file_path), file, 'image/jpeg')))
            else:
                files.append((file_name, (os.path.basename(file_path), file, 'text/markdown')))
        with generate_user_session(False) as session:
            response = session.post(url, files=files, timeout=None)

        response.raise_for_status()
        content = response.json()

        click.echo('Upload succeeded')
        click.echo(json.dumps(content, indent=4))

    except Exception as e:
        click.echo('Error: Failed to upload files {} to DX template repository (Reason: {})'.format(upload_files, e))
        sys.exit(ERROR_EXITCODE)
    finally:
        # io.BufferedReader を全てclose する
        for _, file in files:
            file[1].close()
        # 一時的に作成したZIPファイルの削除
        if os.path.exists(zip_path):
            os.remove(zip_path)

    # 処理正常終了
    click.echo('✨✨✨✨ It\'s done!! Happy DX! ✨✨✨✨\n')
    sys.exit(SUCCESS_EXITCODE)


def update_template_yaml(name, template_scope='private', abeja_user_only=True):
    """引数で渡された内容をもとにtemplate.yaml を更新する
    template.yaml は`./{name}/template.yaml` に配置されていることを想定している

    Args:
        name (str): DX テンプレート名
        template_scope (str): DX テンプレートの公開設定 'public' or 'private'
        abeja_user_only (bool): ABEJA Only か否か
    """

    template_yaml_path = f'./{name}/template.yaml'

    try:
        # YAML ファイルを読み込み
        yaml = ruamel.yaml.YAML()
        with open(template_yaml_path, 'r') as file:
            data = yaml.load(file)

        # 内容を編集
        data['metadata']['templateName'] = name
        data['metadata']['templateScope'] = template_scope
        data['metadata']['abejaUserOnly'] = abeja_user_only

        # 編集後の内容をYAMLファイルに書き込み
        with open(template_yaml_path, 'w') as file:
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


def files_and_directorys_to_zip(directory_path, zip_path):
    """引数で渡されたディレクトリパス配下のファイルを一つのzip ファイルに圧縮する
    Args:
        directory_path (str): 圧縮する対象のファイルが格納されているディレクトリのパス
        zip_path (str): 圧縮後のzip ファイルパス
    """
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory_path):
            for f in files:
                file_path = os.path.join(root, f)
                rel_path = os.path.relpath(file_path, directory_path)
                zipf.write(file_path, rel_path)
            for d in dirs:
                dir_path = os.path.join(root, d)
                rel_path = os.path.relpath(dir_path, directory_path)
                zipf.write(dir_path, rel_path)


def verify_dxtemplate_yaml(template_yaml, template_schema):
    try:
        schema = yamale.make_schema(template_schema)
        data = yamale.make_data(template_yaml)
        yamale.validate(schema, data, strict=False)
    except ValueError as e:
        click.echo(f'Validation failed of template.yaml!: {e}\n')
        sys.exit(ERROR_EXITCODE)
    except Exception as e:
        click.echo(f'Exception was occurred!: {e}\n')
        sys.exit(ERROR_EXITCODE)
    return
