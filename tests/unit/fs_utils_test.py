import os
import random
import tarfile
import zipfile
from unittest import TestCase

from abejacli.fs_utils import (FileSpecFormatError, InvalidPathException,
                               TARFile, TGZFile, UploadFileSpec, ZIPFile,
                               generate_upload_file_iter, generate_upload_bucket_iter,
                               get_compressed_file)
from pyfakefs.fake_filesystem_unittest import Patcher

HIDDEN_FILE = '/dummy/.IgnoreMe'
ALL_FILES = {
    HIDDEN_FILE,
    '/dummy/file1.txt',
    '/dummy/file2.txt',
    '/dummy/file3.txt',
    '/dummy/file4.txt',
    '/dummy/sub/file5.txt',
    '/dummy/sub/file6.txt',
}

REGULAR_FILE_SET = ALL_FILES - {HIDDEN_FILE}
TOPLAYER_FILE_SET = REGULAR_FILE_SET - {
    '/dummy/sub/file5.txt',
    '/dummy/sub/file6.txt',
}


class GenerateUploadFileIterTest(TestCase):

    def setUp(self):
        self.patcher = Patcher()
        self.patcher.setUp()

        for file in ALL_FILES:
            self.patcher.fs.create_file(file, contents='test')

    def upload_files_to_path_set(self, file_iter):
        return set([upload_file.path for upload_file in file_iter])

    def test_iter_dir(self):
        file_iter = generate_upload_file_iter(['/dummy'], recursive=True)
        file_set = self.upload_files_to_path_set(file_iter)
        self.assertSetEqual(file_set, REGULAR_FILE_SET)

    def test_iter_dir_hidden(self):
        file_iter = generate_upload_file_iter(
            ['/dummy'], recursive=True, ignore_hidden_files=False)
        file_set = self.upload_files_to_path_set(file_iter)
        self.assertSetEqual(file_set, ALL_FILES)

    def test_iter_file(self):
        file = '/dummy/file1.txt'
        file_iter = generate_upload_file_iter([file])
        file_set = self.upload_files_to_path_set(file_iter)
        self.assertSetEqual(file_set, set([file]))

    def test_iter_dir_with_reject(self):
        dir_path = '/dummy'
        file_iter = generate_upload_file_iter([dir_path], recursive=False)
        with self.assertRaises(InvalidPathException) as context:
            list(file_iter)
        assert context.exception.path == dir_path

    def test_iter_dir_with_invalid_path(self):
        invalid_path = '/invalid'
        file_iter = generate_upload_file_iter([invalid_path])
        with self.assertRaises(InvalidPathException) as context:
            list(file_iter)
        assert context.exception.path == invalid_path

    def tearDown(self):
        self.patcher.tearDown()


class GenerateUploadBucketIterTest(TestCase):

    def setUp(self):
        self.patcher = Patcher()
        self.patcher.setUp()

        for file in ALL_FILES:
            self.patcher.fs.create_file(file, contents='test')

    def upload_files_to_path_set(self, file_iter):
        return set([upload_file.path for upload_file in file_iter])

    def test_iter_dir(self):
        file_iter = generate_upload_bucket_iter('/dummy', recursive=True)
        file_set = self.upload_files_to_path_set(file_iter)
        self.assertSetEqual(file_set, REGULAR_FILE_SET)

    def test_iter_dir_without_recursive(self):
        dir_path = '/dummy'
        file_iter = generate_upload_bucket_iter(dir_path, recursive=False)
        file_set = self.upload_files_to_path_set(file_iter)
        self.assertSetEqual(file_set, TOPLAYER_FILE_SET)

    def test_iter_dir_with_invalid_path(self):
        invalid_path = '/invalid'
        file_iter = generate_upload_bucket_iter(invalid_path)
        file_set = self.upload_files_to_path_set(file_iter)
        self.assertEqual(len(file_set), 0)

    def tearDown(self):
        self.patcher.tearDown()


class UploadFileSpecTest(TestCase):

    def setUp(self):
        self.fakefs_patcher = Patcher()
        self.fakefs_patcher.setUp()

    def tearDown(self):
        self.fakefs_patcher.tearDown()

    def test_parse_file_not_found(self):
        self.assertRaises(FileNotFoundError,
                          lambda: UploadFileSpec.parse("unknown file"))

    def test_parse_file_invalid_json(self):
        self.assertRaises(FileSpecFormatError,
                          lambda: self.parse_string('{'))

    def test_parse_file_contents_must_be_array(self):
        self.assertRaises(FileSpecFormatError,
                          lambda: self.parse_string('{}'))

    def test_parse_file_item_validation(self):
        self.assertRaises(FileSpecFormatError,
                          lambda: self.parse_string('{1}'))

    def test_empty(self):
        spec = self.parse_string('[]')
        self.assertSetEqual(spec.paths, set())

    def test_file_no_metadata(self):
        spec = self.parse_string(r"""[
            {"file":"test.txt"}
        ]""")
        self.assertSetEqual(spec.paths, {'test.txt'})

    def test_file_metadata(self):
        spec = self.parse_string(r"""[
            {
                "file":"test.csv",
                "metadata": {
                    "a": "b",
                    "c": 1
                }
            }
        ]""")
        self.assertSetEqual(spec.paths, {'test.csv'})
        self.assertDictEqual(spec.get_metadata('test.csv'), {
            'a': 'b',
            'c': 1
        })

    def parse_string(self, contents):
        name = '/file_spec/test_{}.json'.format(random.randrange(100))
        self.fakefs_patcher.fs.create_file(name, contents=contents)
        return UploadFileSpec.parse(name)


class GetCompressedFileTest(TestCase):
    def setUp(self):
        self.patcher = Patcher()
        self.patcher.setUp()

    def tearDown(self):
        self.patcher.tearDown()

    def test_zip_file(self):
        self.patcher.fs.create_file('zip_file.txt', contents='test')
        with zipfile.ZipFile('zip_file.zip', 'w') as zip_file:
            zip_file.write('zip_file.txt')
        self.assertFileExists('zip_file.zip')

        cf = get_compressed_file('zip_file.zip')
        self.assertIsNotNone(cf, msg='test_zip_file faild: cf is none')
        self.assertEqual(cf.extension_name, ZIPFile.extension_name,
                         msg='test_zip_file faild: ext={}'.format(cf.extension_name))

    def test_tgz_file(self):
        self.patcher.fs.create_file('tar_file.tar.gz')
        with tarfile.open('tar_file.tar.gz', 'w:gz') as f:
            f.close()
        self.assertFileExists('tar_file.tar.gz')

        cf = get_compressed_file('tar_file.tar.gz')
        self.assertIsNotNone(cf, msg='test_tar_file faild: cf is none')
        self.assertEqual(cf.extension_name, TGZFile.extension_name,
                         msg='test_tar_file faild: ext={}'.format(cf.extension_name))

    def test_tar_file(self):
        self.patcher.fs.create_file('tar_file.tar')
        with tarfile.open('tar_file.tar', 'w:') as f:
            f.close()
        self.assertFileExists('tar_file.tar')

        cf = get_compressed_file('tar_file.tar')
        self.assertIsNotNone(cf, msg='test_tar_file faild: cf is none')
        self.assertEqual(cf.extension_name, TARFile.extension_name,
                         msg='test_tar_file faild: ext={}'.format(cf.extension_name))

    def assertFileExists(self, file_path):
        self.assertTrue(os.path.exists(file_path),
                        msg='File {0} does not exist'.format(file_path))
