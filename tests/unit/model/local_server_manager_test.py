from unittest.mock import Mock

import requests_mock

from abejacli.model.local_server_manager import LocalServerManager


def test_exit_is_called_when_exception_raised():
    mock_local_server = Mock()
    try:
        with LocalServerManager(mock_local_server):
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    mock_local_server.stop.assert_called_once_with()


def test_send_request_timeout():
    endpoint = 'https://httpbin.org/get'
    mock_local_server = Mock()
    with requests_mock.Mocker() as mock:
        mock.get(endpoint, json={'url': endpoint})
        with LocalServerManager(mock_local_server) as server:
            res = server.send_request('GET', endpoint)
            assert res.status_code == 200

        assert mock.called
        assert mock.last_request.timeout is None
