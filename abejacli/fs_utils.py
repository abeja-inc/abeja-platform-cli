import json
import mimetypes
import os
import os.path
import tarfile
import zipfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cerberus import Validator

FILE_SPEC_ITEM_SCHEMA = {
    'file': {'type': 'string', 'required': True},
    'metadata': {
        'type': 'dict',
        'keysrules': {'type': 'string'},
        'valuesrules': {'nullable': False},
        'required': False
    }
}


class InvalidPathException(Exception):

    def __init__(self, path):
        self.path = path


class FileSpecFormatError(Exception):

    def __init__(self, path, message):
        self.path = path
        self.message = message


class UploadFile:

    def __init__(self, path, metadata=None):
        self.path = path
        self.metadata = metadata


class UploadFileSpec:

    def __init__(self):
        self.paths = set()
        self.__metadata_by_path = {}

    def add_metadata(self, path: str, metadata: Dict[str, Any]):
        full_path = os.path.realpath(path)
        self.__metadata_by_path[full_path] = metadata

    def get_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        full_path = os.path.realpath(path)
        return self.__metadata_by_path.get(full_path)

    @staticmethod
    def parse(file_list_path: str) -> 'UploadFileSpec':
        """Parses a spec file located at ``path``.

        Args:
            path: Spec file path. Spec file can be JSON.

        Returns:
            A ``UploadFileSpec`` object.

        Raises:
            FileNotFoundError: The file doesn't exist at ``file_list_path``.
            FileSpecFormatError: Validation error occurred.
        """
        try:
            with open(file_list_path, 'r', encoding='utf-8') as f:
                specs = json.load(f)
        except json.JSONDecodeError as error:
            raise FileSpecFormatError(
                file_list_path,
                'The file {} was malformed'.format(file_list_path)) from error

        specs_obj = UploadFileSpec()

        if not isinstance(specs, list):
            raise FileSpecFormatError(
                file_list_path, 'The top level must be an array.')

        for spec in specs:
            validator = Validator(FILE_SPEC_ITEM_SCHEMA)
            if not validator.validate(spec):
                raise FileSpecFormatError(
                    file_list_path,
                    'File spec item validation failed: {}.'.format(validator.errors))

            filepath = spec['file']
            specs_obj.paths.add(filepath)
            metadata = spec.get('metadata')
            if metadata:
                specs_obj.add_metadata(filepath, metadata)

        return specs_obj


def generate_upload_file_iter(
        paths: List[str],
        file_list_path: Optional[str] = None,
        recursive: bool = False,
        ignore_hidden_files: bool = True) -> Iterable[UploadFile]:
    """Returns a generator which yields ``UploadFile`` for specified paths and directories.

    Args:
        paths: Uploading file paths.
        file_list_path: JSON file specifies the list of upload files.
        recursive: ``True`` if this function search files under the directories.
        ignore_hidden_files: ``True`` if make this function skip hidden files which name
                             starts with ``'.'``.

    Returns:
        A generator which yields ``UploadFile``.
    """
    def build_spec(file_list_path, paths):
        spec = None

        if file_list_path:
            spec = UploadFileSpec.parse(file_list_path)

        if not spec:
            spec = UploadFileSpec()

        spec.paths.update(paths)
        return spec

    def walk_paths(paths):
        for path in paths:
            if os.path.isfile(path):
                yield path
            elif os.path.isdir(path):
                if not recursive:
                    raise InvalidPathException(path)
                for root, _, file_paths in os.walk(path):
                    for file_path in file_paths:
                        yield os.path.join(root, file_path)
            else:
                raise InvalidPathException(path)

    spec = build_spec(file_list_path, paths)

    for path in walk_paths(spec.paths):
        if not (ignore_hidden_files and os.path.basename(path).startswith('.')):
            yield UploadFile(path, spec.get_metadata(path))


class UploadBucketFile:

    def __init__(self, key, path, metadata=None):
        self.key = key
        self.path = path
        self.metadata = metadata


def generate_upload_bucket_iter(
        path: str,
        recursive: bool = False) -> Iterable[UploadBucketFile]:
    """Returns a generator which yields ``UploadBucketFile`` for specified paths and directories.

    Args:
        path: Uploading file paths.
        recursive: ``True`` if this function search files under the directories.

    Returns:
        A generator which yields ``UploadBucketFile``.
    """
    target_dir_path = '{}/'.format(str(Path(path).absolute()))
    for root, dirs, files in os.walk(path):
        for dirname in dirs[:]:
            if not recursive and str(Path(root, dirname).absolute()) != str(Path(path).absolute()):
                dirs.remove(dirname)
            if dirname.startswith('.'):
                dirs.remove(dirname)

        for filename in files:
            if filename.startswith('.'):
                continue
            filepath = Path(root, filename)
            file_location = str(filepath.absolute()).replace(target_dir_path, '', 1)
            content_type, _ = mimetypes.guess_type(str(filepath))
            metadata = {
                "x-abeja-meta-filename": file_location
            }
            yield UploadBucketFile(file_location, str(filepath), metadata)


class CompressedFile(ABC):
    mime_type = None
    extension_name = None

    @abstractmethod
    def is_matched_type(self, file_path):
        return None


class ZIPFile(CompressedFile):
    mime_type = 'application/zip'
    extension_name = '.zip'

    def is_matched_type(self, file_path):
        return zipfile.is_zipfile(file_path)


class TARFile(CompressedFile):
    mime_type = 'application/x-tar'
    extension_name = '.tar'

    def is_matched_type(self, file_path):
        if tarfile.is_tarfile(file_path):
            try:
                tarfile.open(file_path, "r:gz")
            except tarfile.ReadError:
                return True
        return False


class TGZFile(CompressedFile):
    mime_type = 'application/gzip'
    extension_name = '.tar.gz'

    def is_matched_type(self, file_path):
        if tarfile.is_tarfile(file_path):
            try:
                tarfile.open(file_path, "r:gz")
            except tarfile.ReadError:
                return False
        return True


def get_compressed_file(file_path):
    for cls in (ZIPFile, TGZFile, TARFile):
        if cls.is_matched_type(cls, file_path):
            return cls

    return None
