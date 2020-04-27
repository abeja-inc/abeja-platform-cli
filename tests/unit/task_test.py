import pytest
from mock import MagicMock

from abejacli.task import Run

run = pytest.fixture(lambda: Run())


def test_run(run):
    run._prepare = mock_prepare = MagicMock()
    run._start = mock_start = MagicMock()
    run._end = mock_end = MagicMock()

    with run:
        pass

    mock_prepare.assert_called_once_with()
    mock_start.assert_called_once_with()
    mock_end.assert_called_once_with()


def test_run_with_error_in_enter(run):
    run._prepare = mock_prepare = MagicMock(side_effect=Exception('dummy'))
    run._end = mock_end = MagicMock()
    run._clean = mock_clean = MagicMock()

    with pytest.raises(Exception):
        with run:
            pass

    mock_prepare.assert_called_once_with()
    mock_end.assert_not_called()
    mock_clean.assert_called_once_with()
