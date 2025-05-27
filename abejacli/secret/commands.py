import base64
import json
import re
import sys
from typing import Optional

import click

from abejacli.common import get_organization_id, json_output_formatter
from abejacli.config import ABEJA_API_URL, ERROR_EXITCODE, SUCCESS_EXITCODE
from abejacli.configuration import __ensure_configuration_exists
from abejacli.logger import get_logger
from abejacli.session import api_delete, api_get_data, api_patch, api_post
from abejacli.secret.integration_service_type import IntegrationServiceType

logger = get_logger()


@click.group(help='Secret Manager operation commands')
@click.pass_context
def secret(ctx):
    """Secret Manager の操作を行うコマンドグループ"""
    __ensure_configuration_exists(ctx)


# ---------------------------------------------------
# secret commands
# ---------------------------------------------------
@secret.command(name='list', help='List secrets in organization')
@click.option('-o', '--offset', 'offset', type=int, default=0,
              help='Offset for pagination. Default: 0', required=False)
@click.option('-l', '--limit', 'limit', type=int, default=50,
              help='Limit for pagination (1-100). Default: 50', required=False)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def list_secrets(offset: int, limit: int, organization_id: Optional[str] = None):
    """組織内のシークレット一覧を取得するコマンド

    Args:
        offset (int): ページング用のオフセット
        limit (int): ページング用のリミット（1～100）
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
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
        url = "{}/secret-manager/organizations/{}/secrets".format(ABEJA_API_URL, org_id)
        result = api_get_data(url, params)

        # シークレット値のデコード処理
        for secret in result.get('secrets', []):
            for version in secret.get('versions', []):
                if 'value' in version and version['value']:
                    try:
                        version['value'] = base64.b64decode(version['value']).decode('utf-8')
                    except Exception:
                        pass

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレット一覧の取得に失敗しました: {e}')
        click.echo(f'シークレット一覧の取得に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret.command(name='get', help='Get a specific secret')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def get_secret(secret_id: str, organization_id: Optional[str] = None):
    """特定のシークレットを取得するコマンド

    Args:
        secret_id (str): シークレットID
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

        # API呼び出しパラメータの設定
        params = {
            'return_secret_value': True
        }

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets/{}".format(
            ABEJA_API_URL, org_id, secret_id)
        result = api_get_data(url, params)

        # シークレット値のデコード処理
        for version in result.get('versions', []):
            if 'value' in version and version['value']:
                try:
                    version['value'] = base64.b64decode(version['value']).decode('utf-8')
                except Exception:
                    pass

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットの取得に失敗しました: {e}')
        click.echo(f'シークレットの取得に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret.command(name='create', help='Create a new secret')
@click.option('--integration_service_ids', 'integration_service_ids', type=str,
              help='Integration service IDs', required=False)
@click.option('--integration_service_type', 'integration_service_type', type=str,
              help='Integration service type', required=False)
@click.option('-n', '--name', 'name', type=str,
              help='Secret name The secret name can contain ASCII letters, numbers, and the following characters: `_-` '
                   'Do not end your secret name with a hyphen followed by six characters. '
                   'The secret name must be unique within the same organization.', required=True)
@click.option('-v', '--value', 'value', type=str,
              help='Secret value', required=True)
@click.option('-d', '--description', 'description', type=str,
              help='Secret description', required=False)
@click.option('-e', '--expired-at', 'expired_at', type=str,
              help='Expiration date in ISO 8601 format (e.g. 2025-12-31T23:59:59+09:00)', required=False)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def create_secret(name: str, value: str, description: Optional[str] = None,
                  expired_at: Optional[str] = None, organization_id: Optional[str] = None):
    """新しいシークレットを作成するコマンド

    Args:
        name (str): シークレット名 ASCII文字、数字、および _- の文字を含めることができます
            シークレット名の最後にハイフンを入れ、その後に6文字を続けないこと
            シークレット名は同じ組織内で一意でなければなりません
        value (str): シークレット値
        description (str, optional): シークレットの説明
        expired_at (str, optional): 有効期限（ISO 8601形式）
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
        integration_service_ids (str, optional): 連携サービスIDリスト
        integration_service_type (str, optional): 連携サービスタイプ
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not name:
            click.echo("シークレット名が指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            click.echo('"name" must contain only ASCII letters, numbers, and the following characters: _-')
            sys.exit(ERROR_EXITCODE)

        if re.match(r'.*-......$', name):
            click.echo('"name" must not end with a hyphen followed by six characters')
            sys.exit(ERROR_EXITCODE)

        if value is None or value == '':
            click.echo("シークレット値が指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if integration_service_type:
            if not IntegrationServiceType.has_value(integration_service_type):
                click.echo('"integration_service_type" must be one of the following: {}'.format(
                    ', '.join(IntegrationServiceType._value2member_map_.keys())
                ))
                sys.exit(ERROR_EXITCODE)

        # Base64エンコードされた値を作成
        encoded_value = base64.b64encode(value.encode('utf-8')).decode('utf-8')

        # リクエストペイロードの構築
        payload = {
            'name': name,
            'value': encoded_value,
        }

        if expired_at:
            payload['expired_at'] = expired_at

        if description:
            payload['description'] = description

        if integration_service_type:
            payload['integration_service_type'] = integration_service_type

        if integration_service_ids:
            payload['integration_service_ids'] = integration_service_ids

        # JSON形式に変換
        json_data = json.dumps(payload)

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets".format(
            ABEJA_API_URL, org_id)
        result = api_post(url, json_data)

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットの作成に失敗しました: {e}')
        click.echo(f'シークレットの作成に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret.command(name='update', help='Update an existing secret')
@click.option('--integration_service_ids', 'integration_service_ids', type=str,
              help='Integration service IDs', required=False)
@click.option('--integration_service_type', 'integration_service_type', type=str,
              help='Integration service type', required=False)
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('-d', '--description', 'description', type=str,
              help='Secret description', required=False)
@click.option('-e', '--expired-at', 'expired_at', type=str,
              help='Expiration date in ISO 8601 format (e.g. 2025-12-31T23:59:59+09:00)', required=False)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
def update_secret(secret_id: str, description: Optional[str] = None,
                  expired_at: Optional[str] = None, organization_id: Optional[str] = None):
    """既存のシークレットを更新するコマンド

    Args:
        secret_id (str): シークレットID
        description (str, optional): シークレットの説明
        expired_at (str, optional): 有効期限（ISO 8601形式）
        organization_id (str, optional): 組織ID（指定しない場合は現在の組織IDを使用）
        integration_service_ids (str, optional): 連携サービスIDリスト
        integration_service_type (str, optional): 連携サービスタイプ
    """
    try:
        org_id = organization_id or get_organization_id()
        if not org_id:
            click.echo("Organization IDが取得できませんでした。--organization-idオプションで指定してください。")
            sys.exit(ERROR_EXITCODE)

        if not secret_id:
            click.echo("Secret IDが指定されていません。")
            sys.exit(ERROR_EXITCODE)

        if integration_service_type:
            if not IntegrationServiceType.has_value(integration_service_type):
                click.echo('"integration_service_type" must be one of the following: {}'.format(
                    ', '.join(IntegrationServiceType._value2member_map_.keys())
                ))
                sys.exit(ERROR_EXITCODE)

        # リクエストペイロードの構築
        payload = {}

        if description:
            payload['description'] = description

        if expired_at:
            payload['expired_at'] = expired_at

        if integration_service_ids:
            payload['integration_service_ids'] = integration_service_ids

        if integration_service_type:
            payload['integration_service_type'] = integration_service_type

        # JSON形式に変換
        json_data = json.dumps(payload)

        # APIリクエスト
        url = "{}/secret-manager/organizations/{}/secrets/{}".format(
            ABEJA_API_URL, org_id, secret_id)
        result = api_patch(url, json_data)

        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットの更新に失敗しました: {e}')
        click.echo(f'シークレットの更新に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)


@secret.command(name='delete', help='Delete a secret')
@click.option('-s', '--secret_id', '--secret-id', 'secret_id', type=str,
              help='Secret ID', required=True)
@click.option('--organization_id', '--organization-id', 'organization_id', type=str,
              help='Organization ID. If not specified, the current organization ID is used.', required=False)
@click.option('-y', '--yes', 'yes', is_flag=True, default=False,
              help='Skip confirmation prompt', required=False)
def delete_secret(secret_id: str, organization_id: Optional[str] = None, yes: bool = False):
    """シークレットを削除するコマンド

    Args:
        secret_id (str): シークレットID
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

        # 削除前にシークレット情報を取得して確認
        if not yes:
            try:
                # シークレット情報の取得
                url = "{}/secret-manager/organizations/{}/secrets/{}".format(
                    ABEJA_API_URL, org_id, secret_id)
                secret_info = api_get_data(url, None)

                message = (
                    f'以下のシークレットを削除しますか？\n'
                    f'  - ID: {secret_info["id"]}\n'
                    f'  - 名前: {secret_info["name"]}\n'
                    f'  - 説明: {secret_info.get("description", "なし")}\n'
                    f'  - 作成日時: {secret_info["created_at"]}\n'
                    f'  - 更新日時: {secret_info["updated_at"]}'
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
                logger.warning(f'シークレット情報の取得に失敗しました: {e}')
                click.echo(f'シークレット情報の取得に失敗しました: {e}')
                if not click.confirm(f'シークレット (ID: {secret_id}) を削除しますか？'):
                    click.echo('操作を中止しました！')
                    sys.exit(SUCCESS_EXITCODE)

        # 削除APIの呼び出し
        url = "{}/secret-manager/organizations/{}/secrets/{}".format(
            ABEJA_API_URL, org_id, secret_id)
        result = api_delete(url)

        click.echo('シークレットを削除しました')
        click.echo(json_output_formatter(result))
        sys.exit(SUCCESS_EXITCODE)
    except Exception as e:
        logger.error(f'シークレットの削除に失敗しました: {e}')
        click.echo(f'シークレットの削除に失敗しました: {e}')
        sys.exit(ERROR_EXITCODE)
