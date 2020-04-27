import copy
import json
import os
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from enum import Enum
from tempfile import TemporaryDirectory
from typing import Optional

from requests.exceptions import HTTPError

from abejacli.common import convert_to_local_image_name
from abejacli.config import (
    ABEJA_API_URL,
    LOG_FLUSH_INTERVAL,
    LOG_MAX_SIZE,
    ORGANIZATION_ENDPOINT,
    POLLING_INTERVAL,
    RESERVED_ENV_VAR,
    TAG_VERSION_SAMPV1,
    TRAIN_DEBUG_COMMAND_V1,
    TRAIN_DEBUG_COMMAND_V2,
    TRAIN_LOCAL_COMMAND_V1,
    TRAIN_LOCAL_COMMAND_V2
)
from abejacli.docker.commands.run import (
    DEFAULT_ARTIFACT_DIR,
    TrainRunCommand,
    build_volume,
    get_default_volume,
    get_storage_volume
)
from abejacli.docker.container_run import ContainerBuildAndRun, ContainerRun
from abejacli.docker.utils import parse_image
from abejacli.model.docker_handler import LOCAL_TRAIN_TYPE_VALUE  # deprecate
from abejacli.session import generate_retry_session, generate_user_session
from abejacli.training.client import (
    create_local_training_job,
    describe_training_version
)


class TrainingJobDebugRun(ContainerBuildAndRun):
    def __init__(self, *args, **kwargs):
        if 'v1flag' in kwargs:
            self.v1flag = kwargs.pop('v1flag')
        else:
            self.v1flag = False

        super().__init__(LOCAL_TRAIN_TYPE_VALUE, *args, **kwargs)

    def _prepare_command(self):
        run_command = self._get_run_command()
        self.volume.update(get_default_volume())
        self.command = TrainRunCommand.create(
            image=self.image.id, handler=self.handler,
            datasets=self.datasets, runtime=self.runtime,
            env_vars=self.environment, remove=self.remove, volume=self.volume,
            platform_user_id=self.platform_user_id,
            platform_personal_access_token=self.platform_personal_access_token,
            platform_organization_id=self.organization_id, command=run_command)

    def watch(self):
        if self.container is None:
            raise RuntimeError("container does not exist")

        for out in self.container.logs(stream=True):
            if self.stdout:
                self.stdout(out.decode('utf-8').rstrip())

    def _get_run_command(self):
        try:
            name, tag = parse_image(self.image_name)
        except RuntimeError as e:
            self.logger.error(e)
            raise e

        if self.v1flag:
            return TRAIN_DEBUG_COMMAND_V1
        if tag in TAG_VERSION_SAMPV1:
            return TRAIN_DEBUG_COMMAND_V1
        return TRAIN_DEBUG_COMMAND_V2


class TrainingJobStatus(Enum):
    PENDING = 'Pending'
    ACTIVE = 'Active'
    STOPPED = 'Stopped'
    COMPLETED = 'Complete'
    FAILED = 'Failed'


def truncate_log_line(
        log_line: dict, max_size: int, suffix: str = '...', encoding: str = 'utf-8') -> dict:
    """truncate message part of given log

    >>> truncate_log_line({"message": "1234567890abcdefg", "timestamp": 1566529144938}, 55)
    {"message": "123456789...", "timestamp": 1566529144938}
    """
    suffix_size = len(suffix.encode(encoding))

    if max_size < suffix_size:
        raise ValueError('max_size should be greater than size of suffix')

    if max_size < len(json.dumps({**log_line, 'message': suffix}, ensure_ascii=False).encode(encoding)):
        raise ValueError('max_size should be greater than size of payload without message')

    trimmed = False
    while len(json.dumps(log_line, ensure_ascii=False).encode(encoding)) > max_size:
        log_line['message'] = log_line['message'][:-1]
        trimmed = True

    if trimmed:
        log_line['message'] = log_line['message'][:-3] + suffix
    return log_line


class TrainingJobLocalContainerRun(ContainerRun):

    def __init__(
            self,
            organization_id: str, job_definition_name: str,
            job_definition_version: int, datasets: dict,
            environment: dict, volume: dict = None, description: str = None,
            runtime=None, stdout=None, remove=True,
            platform_user_id=None, platform_personal_access_token=None,
            v1flag=False, log_flush_interval=LOG_FLUSH_INTERVAL,
            log_max_size=LOG_MAX_SIZE, polling_interval=POLLING_INTERVAL):
        self.job_definition_name = job_definition_name
        self.job_definition_version = job_definition_version
        self.description = description
        self.platform_auth_token = None
        self.training_job_id = None
        self.temporary_archive_dir = None
        self.v1flag = v1flag
        self.log_max_size = log_max_size
        self.log_flush_interval = log_flush_interval
        self.polling_interval = polling_interval
        self.executor = None
        self.is_finished = False

        super().__init__(
            None, None, organization_id, datasets, environment, volume,
            no_cache=True, runtime=runtime, stdout=stdout, build_only=False,
            quiet=False, platform_user_id=platform_user_id, remove=remove,
            platform_personal_access_token=platform_personal_access_token)

    def watch(self):
        # update container info
        self.container = self._get_container()
        if self.container is None:
            raise RuntimeError("container does not exist")

        # periodically check remote status
        # and stop container if remote status is STOPPED
        self.executor = ThreadPoolExecutor()
        self.executor.submit(self._check_remote_status_and_stop_if_canceled)

        # flush every LOG_FLUSH_INTERVAL seconds or
        # if log buffer exceeds LOG_BUFFER_SIZE.
        logs = []
        log_size = 0
        start = time.monotonic()

        for out in self.container.logs(stream=True):
            line = out.decode('utf-8').rstrip()
            if self.stdout:
                self.stdout(line)

            # 43 bytes of overhead
            log_line = {'message': line, 'timestamp': int(time.time() * 1000)}

            # trim log line if one log line exceeds limit
            log_line_size = len(json.dumps(log_line, ensure_ascii=False).encode('utf-8'))
            if log_line_size > self.log_max_size:
                log_line = truncate_log_line(
                    log_line, max_size=self.log_max_size)
                log_size += self.log_max_size
            else:
                log_size += log_line_size

            logs.append(log_line)

            # flush logs if logs exceeds buffer limit
            if (log_size >= self.log_max_size) or \
                    (time.monotonic() - start) >= self.log_flush_interval:
                self._send_logs(logs)

                # reset conditions
                logs = []
                log_size = 0
                start = time.monotonic()

        if len(logs) > 0:
            self._send_logs(logs)

        self.is_finished = True
        self.executor.shutdown(wait=False)

    def _prepare(self):
        version = describe_training_version(
            self.job_definition_name, self.job_definition_version)
        self.handler = version['handler']

        # NOTE: as of datasets and environment,
        # values in version is merged with ones given as command args.
        if not self.datasets:
            self.datasets = version.get('datasets', {})
        else:
            datasets = version.get('datasets', {})
            datasets.update(copy.deepcopy(self.datasets))
            self.datasets = datasets

        if not self.environment:
            self.environment = version.get('environment', {})
        else:
            environment = version.get('user_parameters', {})
            environment.update(copy.deepcopy(self.environment))
            self.environment = environment

        self.image_name = convert_to_local_image_name(version['image'])

        job = create_local_training_job(
            self.job_definition_name, self.job_definition_version,
            description=self.description, datasets=self.datasets,
            user_parameters=self.environment)

        self.platform_auth_token = job['token']
        self.training_job_id = job['training_job_id']
        self.temporary_archive_dir = TemporaryDirectory(prefix=os.getcwd() + '/')

        super()._prepare()

    def _prepare_command(self):
        env_vars = {
            RESERVED_ENV_VAR['handler']: self.handler,
            RESERVED_ENV_VAR['datasets']: json.dumps(self.datasets),
            RESERVED_ENV_VAR['platform_auth_token']: self.platform_auth_token,
            RESERVED_ENV_VAR['python_unbufferd']: 'x',  # do not buffer stdout
            RESERVED_ENV_VAR['abeja_api_url']: ABEJA_API_URL,
            RESERVED_ENV_VAR['organization_id']: self.organization_id,
            RESERVED_ENV_VAR['training_job_definition_name']: self.job_definition_name,
            RESERVED_ENV_VAR['training_job_definition_version']: str(self.job_definition_version),
            RESERVED_ENV_VAR['training_job_id']: self.training_job_id,
            RESERVED_ENV_VAR['abeja_training_result_dir']: DEFAULT_ARTIFACT_DIR
        }

        env_vars.update(self.environment)

        volume_options = {}
        volume_options.update(get_storage_volume())

        if self.volume:
            volume_options.update(self.volume)

        tempdir_name = self.temporary_archive_dir.name
        volume_options.update(build_volume(tempdir_name, DEFAULT_ARTIFACT_DIR))

        run_command = self._get_run_command()

        self.command = TrainRunCommand.create(
            image=self.image.id, handler=self.handler,
            datasets=self.datasets, runtime=self.runtime, env_vars=env_vars,
            platform_user_id=self.platform_user_id,
            platform_personal_access_token=self.platform_personal_access_token,
            platform_organization_id=self.organization_id,
            command=run_command,
            volume=volume_options,
            remove=False    # do not remove container to check the status
        )

    def _start(self):
        self._update_status({
            'status': 'Active',
            'start_time': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        })
        super()._start()

    def _on_end(self):
        # TODO: better to allow upload artifact in Active status,
        # and change status to Complete if succeeded in uploading artifact.
        self._update_status({
            'status': self._get_container_status(),
            'completion_time': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        })

        # upload artifact when remote status is complete or failed.
        job = self._get_training_job()
        if job.get('status') in (TrainingJobStatus.COMPLETED.value, TrainingJobStatus.FAILED.value):
            self._upload_artifact()

    def _get_container_status(self):
        container = self._get_container()
        if container is None:
            return TrainingJobStatus.FAILED.value
        if container.status == 'running':
            return TrainingJobStatus.ACTIVE.value
        if container.attrs.get('State', {}).get('ExitCode') == 0:
            return TrainingJobStatus.COMPLETED.value
        return TrainingJobStatus.FAILED.value

    def _upload_artifact(self):
        """upload training job artifact to platform.

        TODO: retry as many times as possible not to lose the artifact file,
        or consider to save artifact file in local if fail in uploading.
        """
        archived_file_path = self._archive_artifact()

        # do not upload if artifact does not exist
        if archived_file_path is None:
            return

        with generate_retry_session() as session:
            session.headers.update({
                'Authorization': 'Bearer {}'.format(self.platform_auth_token)
            })
            url = '{}/training/definitions/{}/jobs/{}/result'.format(
                ORGANIZATION_ENDPOINT, self.job_definition_name, self.training_job_id)
            res = session.post(url)
            res.raise_for_status()
            res = res.json()

        presigned_upload_url = res['uri']

        with generate_retry_session() as session:
            with open(archived_file_path, 'rb') as f:
                headers = {'Content-Type': 'application/zip'}
                res = session.put(presigned_upload_url, headers=headers, data=f)
                res.raise_for_status()

    def _archive_artifact(self):
        archive_filename = '{}.zip'.format(self.training_job_id)
        archive_dir_path = self.temporary_archive_dir.name
        archive_filepath = os.path.join(archive_dir_path, archive_filename)

        target_files = []
        for root, dirs, files in os.walk(archive_dir_path):
            for file in files:
                abs_file_path = os.path.join(root, file)
                if os.path.exists(abs_file_path):
                    target_files.append(abs_file_path)

        if not target_files:
            return None

        with zipfile.ZipFile(archive_filepath, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for target_file in target_files:
                file = os.path.basename(target_file)
                z.write(target_file, arcname=os.path.join(self.training_job_id, file))

        return archive_filepath

    def _update_status(self, status: dict):
        """update training job status recorded in platform.
        if failed in updating status, keep retrying forever
        so as not to keep platform-recorded training job in incomplete status.

        Args:
            status:
                {"status": "Complete", "completion_time": [unix epochtime in millisec : integer]}
        """
        with generate_retry_session() as session:
            session.headers.update({
                'Authorization': 'Bearer {}'.format(self.platform_auth_token)
            })
            url = '{}/training/definitions/{}/jobs/{}/status'.format(
                ORGANIZATION_ENDPOINT, self.job_definition_name, self.training_job_id)
            res = session.put(url, json=status)
            res.raise_for_status()

    def _get_remote_status(self) -> Optional[str]:
        with generate_retry_session() as session:
            session.headers.update({
                'Authorization': 'Bearer {}'.format(self.platform_auth_token)
            })
            url = '{}/training/definitions/{}/jobs/{}'.format(
                ORGANIZATION_ENDPOINT, self.job_definition_name, self.training_job_id)
            res = session.get(url)
            res.raise_for_status()
            res = res.json()
            return res.get('status')

    def _check_remote_status_and_stop_if_canceled(self):
        self.logger.debug('checking training job {} remote status'.format(self.training_job_id))
        current_status = self._get_remote_status()
        while current_status != TrainingJobStatus.STOPPED.value:
            time.sleep(self.polling_interval)
            self.logger.debug('checking training job {} remote status'.format(self.training_job_id))
            current_status = self._get_remote_status()
            if self.is_finished:
                return
        self.logger.info('stop training job {} because remote status is stopped'.format(self.training_job_id))
        self._stop()

    def _clean(self):
        super()._clean()

        if self.executor:
            # NOTE: allow to call shutdown even if it is already so.
            self.executor.shutdown(wait=False)

        # NOTE: no need to flush container logs
        # because sending logs when they are emitted.

        if self.temporary_archive_dir is not None:
            # not raise exception when this method is called more than once.
            self.temporary_archive_dir.cleanup()

        # if job is canceled for some reasons, update status with `Stopped`.
        self._stop_if_active()

    def _stop_if_active(self):
        """check current status in platform, update with stopped if needed"""
        if self.training_job_id is None:
            return

        job = self._get_training_job()
        if job.get('status') not in (
            TrainingJobStatus.STOPPED.value,
            TrainingJobStatus.COMPLETED.value,
            TrainingJobStatus.FAILED.value
        ):
            self._update_status({
                'status': 'Stopped',
                'completion_time': datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
            })
            self.logger.info('stop training job {}'.format(self.training_job_id))

    def _get_training_job(self):
        with generate_user_session() as session:
            url = "{}/training/definitions/{}/jobs/{}".format(
                ORGANIZATION_ENDPOINT, self.job_definition_name, self.training_job_id)
            res = session.get(url)
            res.raise_for_status()
            return res.json()

    def _send_logs(self, logs):
        """
        NOTE: designed to allow missing logs,
        not to stop training job.
        """
        with generate_retry_session() as session:
            session.headers.update({
                'Authorization': 'Bearer {}'.format(self.platform_auth_token)
            })
            url = '{}/training/definitions/{}/jobs/{}/logs'.format(
                ORGANIZATION_ENDPOINT, self.job_definition_name, self.training_job_id)
            res = session.post(url, json={'logs': logs})
            try:
                res.raise_for_status()
            except HTTPError as e:
                self.logger.warn('failed to send logs, error : {}'.format(e))

    def _get_run_command(self):
        try:
            name, tag = parse_image(self.image_name)
        except RuntimeError as e:
            self.logger.error(e)
            raise e

        if self.v1flag:
            return TRAIN_LOCAL_COMMAND_V1
        if tag in TAG_VERSION_SAMPV1:
            return TRAIN_LOCAL_COMMAND_V1
        return TRAIN_LOCAL_COMMAND_V2
