import concurrent.futures
import queue
import typing
from typing import Any, Callable, Dict, Iterable, Optional, Union

# from builtins import range
import tqdm

from abejacli.config import JOB_WORKER_THREAD_NUM
from abejacli.fs_utils import UploadFile
from abejacli.logger import get_logger

INITIALIZE_REPORT = "INITIALIZE_REPORT"
PROGRESS_REPORT = "PROGRESS_REPORT"
RAISE_ERROR = "RAISE_ERROR"
SKIP_REPORT = "SKIP_REPORT"
FINISH_REPORT = "FINISH_REPORT"
EMPTY_REPORT = "EMPTY_REPORT"

logger = get_logger()


FileJobResultInfo = typing.NamedTuple('FileJobResultInfo', [
    ('source', str),
    ('destination', Optional[str]),
    ('metadata', Optional[Dict[str, Any]])
])
FileJobResultInfo.__doc__ = """
The namedTuple for objects in a tuple returned from ``process_file_jobs()``.
"""

FileJobResults = typing.NamedTuple('FileJobResults', [
    ('success', Iterable[FileJobResultInfo]),
    ('error', Iterable[FileJobResultInfo])
])
FileJobResults.__doc__ = """
The namedTuple for a tuple returned from ``process_file_jobs()``.
"""


def handle_command(container, publisher_container, command, publisher_id, diff, command_options):
    """
    handle published command to manipulate tqdm progress bar

    :param container: list of tqdm instances showing in display
    :param publisher_container: list of publisher id to manage tqdm container
    :param command: command to manipulate progress bar
    :param publisher_id: identifier of command publisher
    :param diff: size of progress
    :param command_options: extra options of commands
    :return:
    """
    if command == INITIALIZE_REPORT:
        index = publisher_container.index(None)
        tqdm_options = {
            'desc': '{:10.10}'.format(command_options.get('file_name')),
            'total': command_options.get('total'),
            'unit': 'B',
            'unit_scale': True,
            'position': index + 1
        }
        pbar = tqdm.tqdm(**tqdm_options)
        publisher_container[index] = publisher_id
        container[index] = pbar
    elif command == PROGRESS_REPORT:
        index = publisher_container.index(publisher_id)
        pbar = container[index]
        pbar.update(diff)
    elif command in (FINISH_REPORT, RAISE_ERROR, SKIP_REPORT):
        try:
            index = publisher_container.index(publisher_id)
            pbar = container[index]
            pbar.close()
            pbar.refresh()
            container[index] = None
            publisher_container[index] = None
        except ValueError:
            # In some circumstances, for example no Wi-Fi connection,
            # ``INITIALIZE_REPORT`` command never occurred, so there is
            # no ``publisher_id`` in  the list.
            pass


def process_file_jobs(
        channel_id: str,
        job: Callable[[str, Union[UploadFile, str], queue.Queue, Any], None],
        file_list: Iterable[Union[UploadFile, str]],
        type: str,
        total_size: int,
        worker_option: Any) -> FileJobResults:
    """
    execute specified job for all files in the queue

    :param channel_id: channel identifier
    :param job: file upload/download function
    :param file_list: list of upload/download file info
    :param type: type of global tqdm progress bar type (counter or size)
                   counter: progress when chunk of file content is processed
                   size: progress when each file is completed
    :param total_size: total size of queue
                   counter: total data size in all queued files
                   size: number of files in queue
    :param worker_option: options of worker
    :return: FileJobResults
    """
    # Setup for reporting
    report_queue = queue.Queue()
    container = [None for _ in range(JOB_WORKER_THREAD_NUM)]
    publisher_container = [None for _ in range(JOB_WORKER_THREAD_NUM)]
    # Setup for global tqdm options
    global_tqdm_options = {
        'position': 0,
        'total': total_size
    }
    type_options = {'unit': 'B', 'unit_scale': True} if type == 'size' else {}
    global_tqdm_options.update(type_options)
    # result container
    success_results = []
    error_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=JOB_WORKER_THREAD_NUM) as executor:
        # Setup workers
        job_futures = [
            executor.submit(job, channel_id, f, report_queue, worker_option) for f in file_list
        ]

        with tqdm.tqdm(**global_tqdm_options) as pbar:
            while True:
                try:
                    command, publisher_id, diff, command_options = report_queue.get(
                        timeout=3)
                except queue.Empty:
                    command, publisher_id, diff, command_options = EMPTY_REPORT, None, 0, None

                # update progress bar
                handle_command(container, publisher_container, command,
                               publisher_id, diff, command_options)
                # update global progress bar
                if type == 'size':
                    pbar.update(diff)
                elif type == 'counter' and command in (FINISH_REPORT, SKIP_REPORT):
                    pbar.update(1)
                # store job result
                if command in (FINISH_REPORT, SKIP_REPORT):
                    success_info = FileJobResultInfo(
                        source=command_options.get('source'),
                        destination=command_options.get('destination'),
                        metadata=command_options.get('metadata'))
                    success_results.append(success_info)
                # handle error from job worker
                if command == RAISE_ERROR:
                    error = command_options.get('error')
                    logger.error(str(error))
                    error_info = FileJobResultInfo(
                        source=command_options.get('source'),
                        destination=None,
                        metadata=command_options.get('metadata'))
                    error_results.append(error_info)
                # check if all worker thread is finished
                if command in (EMPTY_REPORT, FINISH_REPORT, RAISE_ERROR, SKIP_REPORT):
                    if report_queue.empty() and all([f.done() for f in job_futures]):
                        break
                if command != EMPTY_REPORT:
                    report_queue.task_done()

    return FileJobResults(
        success=success_results,
        error=error_results)
