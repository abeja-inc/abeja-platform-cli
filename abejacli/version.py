import tomlkit
import os


def _get_project_meta():
    toml_path = os.path.join(os.path.dirname(__file__), '../pyproject.toml')
    with open(toml_path) as pyproject:
        file_contents = pyproject.read()

    return tomlkit.parse(file_contents)['tool']['poetry']


pkg_meta = _get_project_meta()
VERSION = pkg_meta['version']
