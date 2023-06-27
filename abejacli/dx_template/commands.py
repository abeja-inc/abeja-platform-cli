import os
import re
import subprocess
import sys
import zipfile

import click
import requests
import yaml

from abejacli.common import __try_get_organization_id
from abejacli.config import (
    ABEJA_PLATFORM_TOKEN,
    ABEJA_PLATFORM_USER_ID,
    ERROR_EXITCODE,
    ORGANIZATION_ENDPOINT,
    SUCCESS_EXITCODE
)
from abejacli.configuration import __ensure_configuration_exists
from abejacli.logger import get_logger
from abejacli.session import generate_user_session

# for Debug
# import http
# http.client.HTTPConnection.debuglevel=1


DX_TEMPLATE_SKELETON_REPO = 'https://github.com/abeja-inc/platform-dx-template-samples.git'

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
    click.echo(f'url is {url}')
    click.echo(f'ABEJA_PLATFORM_TOKEN is {ABEJA_PLATFORM_TOKEN}')
    click.echo(f'ABEJA_PLATFORM_USER_ID is {ABEJA_PLATFORM_USER_ID}')

    # 必要ファイルの存在確認
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

    # handler.py をrun ディレクトリごとzip で固める
    # TODO: ネスト深すぎるので後で直す
    try:
        handler_dire_path = os.path.join(directory_path, 'src/abeja_platform/deployments/run')
        zip_path = os.path.join(directory_path, 'src/abeja_platform/deployments/handler.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(handler_dire_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.relpath(file_path, directory_path))
        upload_files['handler'] = zip_path
    except Exception as e:
        print(f"Failed to create zip file: {zip_path}\nError: {str(e)}")

    try:
        # upload_files をまとめてアップロードする
        # TODO:
        files = []
        for file_name, file_path in upload_files.items():
            file = open(file_path, 'rb')
            # files.append(('files', (file_name, file, 'multipart/form-data')))
            files.append((file_name, (f'{file_name}.md', file, 'application/octet-stream')))

        # TODO: デバッグ用後で削除
        for f in files:
            click.echo(f)

        """
        $ curl -X POST -u "user-2778435122950":cbfec955d67dd231c95b4a9d8d083a98f162823d \
        >   -F template_yaml=@/home/ogawa/platform/abeja-platform-cli/ogawa-template/template.yaml \
        >   -F handler=@/home/ogawa/platform/abeja-platform-cli/ogawa-template/src/abeja_platform/deployments/handler.zip \
        >   -F thumbnail=@/home/ogawa/platform/abeja-platform-cli/ogawa-template/Thumbnail.jpg \
        >   -F how_to_use=@/home/ogawa/platform/abeja-platform-cli/ogawa-template/DxTemplate.md \
        >   -F how_to_use_jp=@/home/ogawa/platform/abeja-platform-cli/ogawa-template/DxTemplate_JP.md \
        >   "https://api.dev.abeja.io/organizations/2964344169041/dx-templates" | jq .
        """

        with generate_user_session(False) as session:
            # session.auth = HTTPBasicAuth(ABEJA_PLATFORM_USER_ID, ABEJA_PLATFORM_TOKEN)
            session.headers.update({
                "Content-Type": "multipart/form-data",
            })
            click.echo(session.headers)
            response = session.post(url, files=files, timeout=None)

        if response.status_code == 200:
            click.echo('Files uploaded successfully.')
            click.echo(response.json())
        else:
            click.echo(f'Failed to upload files. Status code: {response.status_code}')
            click.echo(response.text)

    except FileNotFoundError:
        click.echo('File not found.')
    except requests.exceptions.RequestException as e:
        click.echo(f'An error occurred during the request: {e}')
    finally:
        # io.BufferedReader を全てclose する
        for _, file in files:
            # click.echo(file[1])
            file[1].close()


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
