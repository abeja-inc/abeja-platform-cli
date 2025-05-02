import base64
import json
import sys
from typing import Optional

import click

from abejacli.common import get_organization_id, json_output_formatter
from abejacli.config import ABEJA_API_URL, ERROR_EXITCODE, SUCCESS_EXITCODE
from abejacli.configuration import __ensure_configuration_exists
from abejacli.logger import get_logger
from abejacli.session import api_delete, api_get_data, api_patch, api_post

logger = get_logger()


@click.group(help='Secret Version operation commands')
@click.pass_context
def secret_version(ctx):
    """Secret Version の操作を行うコマンドグループ"""
    __ensure_configuration_exists(ctx)


# ---------------------------------------------------
# secret version commands
# ---------------------------------------------------
@secret_version.command(name='list', help='List secret versions')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('-o', '--offset', 'offset', type=int, default=0,
              help='Offset for pagination. Default: 0', required=False)
@click.option('-l', '--limit', 'limit', type=int, default=50,
              help='Limit for pagination (1-100). Default: 50', required=False)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def list_secret_versions(secret_id: str, offset: int, limit: int, organization_id: Optional[str] = None):
    """シークレットのバージョン一覧を取得するコマンド

    Args:
        secret_id (str): シークレットID
        offset (int): ページング用のオフセット
        limit (int): ページング用のリミット（1～100）
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not secret_id:
            click.echo("Secret IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        # パラメータチェック
        if offset < 0:
            click.echo("Offsetは0以上である必要があります。")
            sys.exit(ERROR_EXITCODE)

        if limit < 1 or limit > 100:
            click.echo("Limitは1から100の範囲である必要があります。")
            sys.exit(ERROR_EXITCODE)

        # API呼び出しパラメータの設定
        params = {
            'offset': offset,
            'limit': limit,
            'return_secret_value': True
        }

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets/{}/versions".format(
            ABEJA_API_URL, org_id, secret_id)
        result = api_get_data(url, params)

        # シークレット値のデコード処理
        if 'versions' in result:
            for version in result['versions']:
                if 'value' in version and version['value']:
                    try:
                        version['value'] = base64.b64decode(version['value']).decode('utf-8')
                    except Exception:
                        pass

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットバージョン一覧の取得に失敗しました: {e}')
        click.echo(f'シークレットバージョン一覧の取得に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret_version.command(name='get', help='Get a specific secret version')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str,
              help='Version ID', required=True)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def get_secret_version(secret_id: str, version_id: str, organization_id: Optional[str] = None):
    """特定のシークレットバージョンを取得するコマンド

    Args:
        secret_id (str): シークレットID
        version_id (str): バージョンID
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not secret_id:
            click.echo("Secret IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if not version_id:
            click.echo("Version IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        # API呼び出しパラメータの設定
        params = {
            'return_secret_value': True
        }

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
            ABEJA_API_URL, org_id, secret_id, version_id)
        result = api_get_data(url, params)

        # シークレット値のデコード処理
        if 'value' in result and result['value']:
            try:
                result['value'] = base64.b64decode(result['value']).decode('utf-8')
            except Exception:
                pass

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットバージョンの取得に失敗しました: {e}')
        click.echo(f'シークレットバージョンの取得に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret_version.command(name='create', help='Create a new secret version')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('-v', '--value', 'value', type=str,
              help='Secret value', required=True)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def create_secret_version(secret_id: str, value: str, organization_id: Optional[str] = None):
    """新しいシークレットバージョンを作成するコマンド

    Args:
        secret_id (str): シークレットID
        value (str): シークレット値
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not secret_id:
            click.echo("Secret IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if value is None or value == '':
            click.echo("シークレット値が指定されていません。")
            sys.exit(ERROR_EXITCODE)

        # リクエストペイロードの構築
        payload = {
            'value': value,
        }

        # JSON形式に変換
        json_data = json.dumps(payload)

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets/{}/versions".format(
            ABEJA_API_URL, org_id, secret_id)
        result = api_post(url, json_data)

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットバージョンの作成に失敗しました: {e}')
        click.echo(f'シークレットバージョンの作成に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret_version.command(name='update', help='Update a secret version')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str,
              help='Version ID', required=True)
@click.option('--status', 'status', type=click.Choice(['active', 'inactive']),
              help='Version status (active or inactive)', required=True)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def update_secret_version(secret_id: str, version_id: str, status: str,
                          organization_id: Optional[str] = None):
    """シークレットバージョンを更新するコマンド

    Args:
        secret_id (str): シークレットID
        version_id (str): バージョンID
        status (str): バージョンのステータス（'active'または'inactive'）
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not secret_id:
            click.echo("Secret IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if not version_id:
            click.echo("Version IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if not status:
            click.echo("Status（ステータス）が指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if status not in ['active', 'inactive']:
            click.echo("Statusは'active'または'inactive'である必要があります。")
            sys.exit(ERROR_EXITCODE)

        # リクエストペイロードの構築
        payload = {
            'status': status,
        }

        # JSON形式に変換
        json_data = json.dumps(payload)

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
            ABEJA_API_URL, org_id, secret_id, version_id)
        result = api_patch(url, json_data)

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットバージョンの更新に失敗しました: {e}')
        click.echo(f'シークレットバージョンの更新に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret_version.command(name='delete', help='Delete a secret version')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('-v', '--version_id', '--version-id', 'version_id', type=str,
              help='Version ID', required=True)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
@click.option('-y', '--yes', 'yes', is_flag=True, default=False,
              help='Skip confirmation prompt', required=False)
def delete_secret_version(secret_id: str, version_id: str, organization_id: Optional[str] = None,
                          yes: bool = False):
    """シークレットバージョンを削除するコマンド

    Args:
        secret_id (str): シークレットID
        version_id (str): バージョンID
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
        yes (bool): 確認プロンプトをスキップするかどうか
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not secret_id:
            click.echo("Secret IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if not version_id:
            click.echo("Version IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        # 削除前にシークレットバージョン情報を取得して確認
        if not yes:
            try:
                # シークレットバージョン情報の取得
                url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
                    ABEJA_API_URL, org_id, secret_id, version_id)
                version_info = api_get_data(url, None)

                message = (
                    f'以下のシークレットバージョンを削除しますか？\n'
                    f'  - ID: {version_info["id"]}\n'
                    f'  - シークレットID: {version_info["secret_id"]}\n'
                    f'  - バージョン: {version_info["version"]}\n'
                    f'  - ステータス: {version_info.get("status", "不明")}\n'
                    f'  - 作成日時: {version_info["created_at"]}'
                )

                answer = click.prompt(
                    message,
                    type=click.Choice(['Y', 'n']),
                    default='Y'
                )

                if answer == 'n':
                    click.echo('操作を中止しました！')
                    sys.exit(SUCCESS_EXITCODE)
            except Exception as e:
                logger.warning(f'シークレットバージョン情報の取得に失敗しました: {e}')
                click.echo(f'シークレットバージョン情報の取得に失敗しました: {e}')
                if not click.confirm(f'シークレットバージョン (ID: {version_id}) を削除しますか？'):
                    click.echo('操作を中止しました！')
                    sys.exit(SUCCESS_EXITCODE)

        # 削除APIの呼び出し
        url = "{}/secret-manager/organizations/{}/secrets/{}/versions/{}".format(
            ABEJA_API_URL, org_id, secret_id, version_id)
        result = api_delete(url)

        click.echo('シークレットバージョンを削除しました')
        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットバージョンの削除に失敗しました: {e}')
        click.echo(f'シークレットバージョンの削除に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)
