from unittest import TestCase

import requests
import requests_mock
from abejacli.config import ORGANIZATION_ENDPOINT, DATALAKE_ITEMS_PER_PAGE
from abejacli.bucket import (generate_bucket_file_iter_by_id,
                             generate_bucket_file_iter)
from nose.tools import assert_list_equal, assert_raises

FILE = {
  "expires": "2017-11-21T02:18:16+00:00",
  "metadata": {
    "x-abeja-meta-filename": "file2/file2-2.txt"
  },
  "file_id": "file2/file2-2.txt",
  "is_file": True,
  "size": 4,
  "etag": "etag",
  "download_uri": "https://abeja-storage-bucket-dev.s3.amazonaws.com/1122334455667/1981155819522/file2/file2-2.txt?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
}
FILES = [
  {
    "expires": "2017-11-21T02:18:16+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file2/file2-2.txt"
    },
    "file_id": "file2/file2-2.txt",
    "is_file": True,
    "size": 4,
    "etag": "etag",
    "download_uri": "https://abeja-storage-bucket-dev.s3.amazonaws.com/1122334455667/1981155819522/file2/file2-2.txt?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
  },
  {
    "expires": "2017-11-21T02:18:16+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file1.txt"
    },
    "file_id": "file1.txt",
    "is_file": True,
    "size": 4,
    "etag": "etag",
    "download_uri": "https://abeja-storage-bucket-dev.s3.amazonaws.com/1122334455667/1981155819522/file1.txt?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
  },
]


class GenerateFilePeriodIterTest(TestCase):

    @requests_mock.Mocker()
    def test_iter_file_period(self, mock):
        bucket_id = '1282495447337'
        res = {
            'files': FILES,
            'next_start_after': 'file1.txt',
        }
        url = '{}/buckets/{}/files?items_per_page={}'.format(
            ORGANIZATION_ENDPOINT, bucket_id, DATALAKE_ITEMS_PER_PAGE)
        mock.register_uri('GET', url, json=res)
        res2 = {
            'files': [],
            'next_start_after': 'file1.txt',
        }
        url = '{}/buckets/{}/files?items_per_page={}&start_after=file1.txt'.format(
            ORGANIZATION_ENDPOINT, bucket_id, DATALAKE_ITEMS_PER_PAGE)
        mock.register_uri('GET', url, json=res2)

        it = generate_bucket_file_iter(bucket_id)
        assert_list_equal(FILES, list(it))

    @requests_mock.Mocker()
    def test_iter_file_period_empty(self, mock):
        bucket_id = '1282495447337'
        res = {
            'files': [],
            'next_start_after': 'file1.txt',
        }
        url = '{}/buckets/{}/files?items_per_page={}'.format(
            ORGANIZATION_ENDPOINT, bucket_id, DATALAKE_ITEMS_PER_PAGE)
        mock.register_uri('GET', url, json=res)

        it = generate_bucket_file_iter(bucket_id)
        assert 0 == len(list(it))

    @requests_mock.Mocker()
    def test_iter_file_period_pagination(self, mock):
        bucket_id = '1282495447337'
        next_start_after = 'file1.txt'  # noqa
        first_res = {
            'files': FILES[:1],
            'next_start_after': next_start_after,
        }
        first_page_url = '{}/buckets/{}/files'.format(ORGANIZATION_ENDPOINT, bucket_id)
        next_start_after2 = 'file2/file2-2.txt'
        second_res = {
            'files': FILES[1:],
            'next_start_after': next_start_after2,
        }
        second_page_url = '{}/buckets/{}/files?start_after={}'.format(
            ORGANIZATION_ENDPOINT, bucket_id, next_start_after)
        third_res = {
            'files': [],
            'next_start_after': 'dummy',
        }
        third_page_url = '{}/buckets/{}/files?start_after={}'.format(
            ORGANIZATION_ENDPOINT, bucket_id, next_start_after2)

        mock.register_uri('GET', first_page_url, json=first_res)
        mock.register_uri('GET', second_page_url, json=second_res)
        mock.register_uri('GET', third_page_url, json=third_res)

        it = generate_bucket_file_iter(bucket_id)
        assert_list_equal(FILES, list(it))


class GenerateFileIdIterTest(TestCase):

    @requests_mock.Mocker()
    def test_iter_file_id(self, mock):
        bucket_id = '1282495447337'
        file_id = '20171116T071056/9e6463607e6e'
        url = '{}/buckets/{}/files/{}'.format(ORGANIZATION_ENDPOINT, bucket_id, file_id)
        mock.register_uri('GET', url, json=FILE)

        file_ids = [file_id]
        it = generate_bucket_file_iter_by_id(bucket_id, *file_ids)
        assert_list_equal([FILE], list(it))

    @requests_mock.Mocker()
    def test_iter_file_id_not_found(self, mock):
        bucket_id = '1282495447337'
        file_id = '20171116T071056/9e6463607e6e'
        url = '{}/buckets/{}/files/{}'.format(ORGANIZATION_ENDPOINT, bucket_id, file_id)
        mock.register_uri('GET', url, json=FILE, status_code=404)

        file_ids = [file_id]
        with assert_raises(requests.HTTPError):
            it = generate_bucket_file_iter_by_id(bucket_id, *file_ids)
            list(it)
