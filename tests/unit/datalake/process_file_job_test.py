import uuid
from unittest import TestCase

from abejacli.datalake.process_file_job import (FINISH_REPORT,
                                                INITIALIZE_REPORT,
                                                PROGRESS_REPORT,
                                                handle_command)
from nose.tools import assert_is_none, assert_is_not_none

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch


class ProcessFileJobTest(TestCase):

    @patch('tqdm.tqdm')
    def test_handle_command(self, tqdm_mock):
        publisher_id = uuid.uuid4().hex
        progress_diff = 3
        container = [None for _ in range(5)]
        publisher_container = [None for _ in range(5)]
        tqdm_instance = tqdm_mock.return_value

        # assert tqdm is initialized with expected command_options
        initialize_options = {
            'file_name': 'dummy',
            'total': 30
        }
        expected_tqdm_options = {
            'desc': '{:10.10}'.format(initialize_options.get('file_name')),
            'total': initialize_options.get('total'),
            'unit': 'B',
            'unit_scale': True,
            'position': 1
        }
        handle_command(container, publisher_container,
                       INITIALIZE_REPORT, publisher_id, 0, initialize_options)
        tqdm_mock.assert_called_with(**expected_tqdm_options)
        index = publisher_container.index(publisher_id)
        assert_is_not_none(container[index])

        # assert tqdm is updated with expected args
        handle_command(container, publisher_container,
                       PROGRESS_REPORT, publisher_id, progress_diff, None)
        handle_command(container, publisher_container,
                       PROGRESS_REPORT, publisher_id, progress_diff, None)
        handle_command(container, publisher_container,
                       PROGRESS_REPORT, publisher_id, progress_diff, None)

        assert tqdm_instance.update.call_count == 3
        tqdm_instance.update.assert_called_with(progress_diff)

        # assert tqdm is cleaned up
        handle_command(container, publisher_container,
                       FINISH_REPORT, publisher_id, 0, None)
        assert tqdm_instance.refresh.call_count == 1
        assert tqdm_instance.close.call_count == 1
        assert_is_none(container[index])

    # @patch('abejacli.report_worker.handle_command')
    # @patch('tqdm.tqdm')
    # def test_run_size_type(self, tqdm_mock, handle_command_mock):
    #     publisher_id = uuid.uuid4().hex
    #     total_size = 30
    #     progress_diff = 3

    #     # mock tqdm
    #     tqdm_instance = tqdm_mock.return_value
    #     tqdm_instance.__enter__.return_value = tqdm_instance

    #     # mock report queue
    #     report_queue = MagicMock()
    #     options = {}
    #     report_queue.get.side_effect = [
    #         (INITIALIZE_REPORT, publisher_id, 0, options),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (FINISH_REPORT, publisher_id, 0, None),
    #         (FINISH_ALL_REPORTS, None, 0, None),
    #     ]
    #     report_job(report_queue, 'size', total_size)
    #     assert tqdm_instance.update.call_count == 6
    #     tqdm_instance.update.assert_any_call(progress_diff)

    # @patch('abejacli.report_worker.handle_command')
    # @patch('tqdm.tqdm')
    # def test_run_counter_type(self, tqdm_mock, handle_command_mock):
    #     publisher_id = uuid.uuid4().hex
    #     total_size = 30
    #     progress_diff = 3

    #     # mock tqdm
    #     tqdm_instance = tqdm_mock.return_value
    #     tqdm_instance.__enter__.return_value = tqdm_instance

    #     # mock report queue
    #     report_queue = MagicMock()
    #     options = {}
    #     report_queue.get.side_effect = [
    #         (INITIALIZE_REPORT, publisher_id, 0, options),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (FINISH_REPORT, publisher_id, 0, None),
    #         (FINISH_ALL_REPORTS, None, 0, None),
    #     ]
    #     report_job(report_queue, 'counter', total_size)
    #     # assert update method is called only once with 1
    #     assert tqdm_instance.update.call_count == 1
    #     tqdm_instance.update.assert_any_call(1)

    # @patch('abejacli.report_worker.handle_command')
    # @patch('tqdm.tqdm')
    # @patch('logging.Logger.error')
    # def test_run_raise_error(self, logging_error_mock, tqdm_mock, handle_command_mock):
    #     publisher_id = uuid.uuid4().hex
    #     total_size = 30
    #     progress_diff = 3

    #     # mock tqdm
    #     tqdm_instance = tqdm_mock.return_value
    #     tqdm_instance.__enter__.return_value = tqdm_instance

    #     # mock report queue
    #     report_queue = MagicMock()
    #     options = {}
    #     error_msg = 'some error'
    #     error_options = {
    #         'error': error_msg
    #     }
    #     report_queue.get.side_effect = [
    #         (INITIALIZE_REPORT, publisher_id, 0, options),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #         (PROGRESS_REPORT, publisher_id, progress_diff, None),
    #        (RAISE_ERROR, publisher_id, 0, error_options),
    #        (FINISH_ALL_REPORTS, None, 0, None),
    #    ]
    #    report_job(report_queue, 'size', total_size)
    #    assert tqdm_instance.update.call_count == 5
    #    tqdm_instance.update.assert_any_call(progress_diff)
    #    # assert logger.error is called with message
    #    logging_error_mock.assert_called_with(error_msg)
