def test_import_config_variables():
    # In some old code (e.g. samples), there are importing ABEJA_PLATFORM_USER_ID,
    # ABEJA_PLATFORM_TOKEN directly from `abejacli.config` module.
    temp = __import__('abejacli.config', globals(), locals(), [
                      'ABEJA_PLATFORM_USER_ID', 'ABEJA_PLATFORM_TOKEN'], 0)

    assert hasattr(temp, 'ABEJA_PLATFORM_USER_ID')
    assert hasattr(temp, 'ABEJA_PLATFORM_TOKEN')


def test_import_config_auth_token():
    temp = __import__('abejacli.config', globals(), locals(), [
        'PLATFORM_AUTH_TOKEN'], 0)

    assert hasattr(temp, 'PLATFORM_AUTH_TOKEN')
