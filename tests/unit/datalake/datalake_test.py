from unittest import TestCase

import requests
import requests_mock
from abejacli.config import ABEJA_API_URL, DATALAKE_ITEMS_PER_PAGE
from abejacli.datalake import (generate_channel_file_iter_by_id,
                               generate_channel_file_iter_by_period)

FILE = {
  "url_expires_on": "2017-11-21T02:18:16+00:00",
  "uploaded_at": "2017-11-16T07:10:56+00:00",
  "metadata": {
    "x-abeja-meta-filename": "file1.txt"
  },
  "file_id": "20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e",
  "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071056-b2168632-7aae-47ad-8339-9e6463607e6e?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
  "content_type": "text/plain"
}
FILES = [
  {
    "url_expires_on": "2017-11-21T02:18:16+00:00",
    "uploaded_at": "2017-11-16T07:10:56+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file1.txt"
    },
    "file_id": "20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e",
    "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071056-b2168632-7aae-47ad-8339-9e6463607e6e?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=Riaqm%2B4sJz9fc2J0GIsvIIAROG8%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
    "content_type": "text/plain"
  },
  {
    "url_expires_on": "2017-11-21T02:18:16+00:00",
    "uploaded_at": "2017-11-16T07:11:00+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file2.txt"
    },
    "file_id": "20171116T071100-6e82c7ef-ad2a-40ab-888b-3c2c5567de0f",
    "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071100-6e82c7ef-ad2a-40ab-888b-3c2c5567de0f?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=T1%2BcHb3A0D892Dfw5HYmY%2BIhROA%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
    "content_type": "text/plain"
  },
  {
    "url_expires_on": "2017-11-21T02:18:16+00:00",
    "uploaded_at": "2017-11-16T07:11:01+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file3.txt"
    },
    "file_id": "20171116T071101-959db0d1-e853-4dd0-9aa0-d81692d2d88b",
    "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071101-959db0d1-e853-4dd0-9aa0-d81692d2d88b?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=dE07nbdjtR08B0CzVLiwgap%2BK1E%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
    "content_type": "text/plain"
  },
  {
    "url_expires_on": "2017-11-21T02:18:16+00:00",
    "uploaded_at": "2017-11-16T07:11:02+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file4.txt"
    },
    "file_id": "20171116T071102-daa6078c-a0b9-4a02-a344-33c617667760",
    "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071102-daa6078c-a0b9-4a02-a344-33c617667760?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=lJrAckUoyCcYMIExn%2BEV6x93kyk%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
    "content_type": "text/plain"
  },
  {
    "url_expires_on": "2017-11-21T02:18:16+00:00",
    "uploaded_at": "2017-11-16T07:11:05+00:00",
    "metadata": {
      "x-abeja-meta-filename": "file5.txt"
    },
    "file_id": "20171116T071105-4a9b8400-2d56-49a9-aaf7-c07bc93489f1",
    "download_uri": "https://abeja-datalake-dev.s3.amazonaws.com/320e-1282495447337/20171116/071105-4a9b8400-2d56-49a9-aaf7-c07bc93489f1?AWSAccessKeyId=ASIAIS6VOBREHPTWAQDA&Signature=GzIz%2FA%2BlizK9dm%2FxKjXvQoUgm6M%3D&x-amz-security-token=FQoDYXdzEN7%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FwEaDGO9U9SxYJDxdzmbMyKCAnNauIDasGDp9mNIHaSbhG8PIXZWA193DiNcFqRvd4BlfA9VB2ZjohVJNnMLssOQBLkrK5Tgc7ixxgTuon2pkeew9IEiyxHjDm8T3jjLbUCUWqUDuy0JKdYjTqYGQ4SJBUSEGsFOfyUIDW1VqXPAdmgHC3p%2BMOOBI07uW6%2BThG50EjCttzrCYX9ka73R3Tj6Iqe4bnj3ogl909o9%2Fen1yRJ6uEGGkbfXCMJsAGrDrRY5bJxcjS4uCQLidqxQM1nbumNc%2F2WipjF7AK1wQQl50eEO%2FG9%2F%2Fc81Bjv767GazeCraSnukGggMTcqEOeUQEAlxgTo7lh6ykbl0JU%2BMs0Hks08DiiHhc3QBQ%3D%3D&Expires=1511230696",  # noqa
    "content_type": "text/plain"
  }
]


class GenerateFilePeriodIterTest(TestCase):

    @requests_mock.Mocker()
    def test_iter_file_period(self, mock):
        channel_id = '1282495447337'
        start = '20171114'
        end = '20171116'
        res = {
            'files': FILES,
            'next_page_token': None,
        }
        url = '{}/channels/{}?start={}&end={}&items_per_page={}'.format(ABEJA_API_URL, channel_id,
                                                                        start, end, DATALAKE_ITEMS_PER_PAGE)
        mock.register_uri('GET', url, json=res)

        it = generate_channel_file_iter_by_period(channel_id, start, end)
        assert FILES == list(it)

    @requests_mock.Mocker()
    def test_iter_file_period_empty(self, mock):
        channel_id = '1282495447337'
        start = '20171114'
        end = '20171116'
        res = {
            'files': [],
            'next_page_token': None,
        }
        url = '{}/channels/{}?start={}&end={}&items_per_page={}'.format(ABEJA_API_URL, channel_id,
                                                                        start, end, DATALAKE_ITEMS_PER_PAGE)
        mock.register_uri('GET', url, json=res)

        it = generate_channel_file_iter_by_period(channel_id, start, end)
        assert 0 == len(list(it))

    @requests_mock.Mocker()
    def test_iter_file_period_pagination(self, mock):
        channel_id = '1282495447337'
        start = '20171114'
        end = '20171116'
        next_page_token = 'eyJpdGVtc19wZXJfcGFnZSI6ICI3IiwgInRpbWV6b25lIjogIlVUQyIsICJsYXN0X2ZpbGVfaWQiOiAiMjAxNzExMTZUMDcxMTA1LTRhOWI4NDAwLTJkNTYtNDlhOS1hYWY3LWMwN2JjOTM0ODlmMSJ9'  # noqa
        first_res = {
            'files': FILES[0:3],
            'next_page_token': next_page_token,
        }
        first_page_url = '{}/channels/{}?start={}&end={}&items_per_page={}'.format(ABEJA_API_URL, channel_id,
                                                                                   start, end, DATALAKE_ITEMS_PER_PAGE)
        second_res = {
            'files': FILES[3:],
            'next_page_token': None,
        }
        second_page_url = '{}/channels/{}?next_page_token={}'.format(
            ABEJA_API_URL, channel_id, next_page_token)

        mock.register_uri('GET', first_page_url, json=first_res)
        mock.register_uri('GET', second_page_url, json=second_res)

        it = generate_channel_file_iter_by_period(channel_id, start, end)
        assert FILES == list(it)


class GenerateFileIdIterTest(TestCase):

    @requests_mock.Mocker()
    def test_iter_file_id(self, mock):
        channel_id = '1282495447337'
        file_id = '20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e'
        url = '{}/channels/{}/{}'.format(ABEJA_API_URL, channel_id, file_id)
        mock.register_uri('GET', url, json=FILE)

        file_ids = [file_id]
        it = generate_channel_file_iter_by_id(channel_id, *file_ids)
        assert [FILE] == list(it)

    @requests_mock.Mocker()
    def test_iter_file_id_not_found(self, mock):
        channel_id = '1282495447337'
        file_id = '20171116T071056-b2168632-7aae-47ad-8339-9e6463607e6e'
        url = '{}/channels/{}/{}'.format(ABEJA_API_URL, channel_id, file_id)
        mock.register_uri('GET', url, json=FILE, status_code=404)

        file_ids = [file_id]
        with self.assertRaises(requests.HTTPError):
            it = generate_channel_file_iter_by_id(channel_id, *file_ids)
            list(it)
