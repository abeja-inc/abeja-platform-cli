import json
import os
import tempfile
from abc import abstractmethod
from typing import Generator, Optional

import docker
from docker.models.images import Image

from abejacli.docker.utils import check_docker_installation, parse_image
from abejacli.model import md5digest, md5file
from abejacli.model.docker_handler import (
    BUILT_IMAGE_SUFFIX,
    DOCKERFILE_RUN_LOCAL_TEMPLATE
)
from abejacli.task import Run

REQUIREMENTS_TXT = 'requirements.txt'
PIPFILE = 'Pipfile'
LOCAL_MODEL_TYPE_KEY = 'abeja-platform-model-type'
LOCAL_MODEL_IMAGE_MD5_KEY = 'abeja-platform-image-md5'


class ContainerRun(Run):
    def __init__(
            self, handler, image, organization_id, datasets, environment, volume, no_cache,
            runtime=None, stdout=None, build_only=False, quiet=False,
            remove=True, platform_user_id=None, platform_personal_access_token=None):
        self.handler = handler
        self.image_name = image
        self.organization_id = organization_id
        self.datasets = datasets
        self.environment = environment
        self.volume = volume
        self.no_cache = no_cache
        self.runtime = runtime
        self.stdout = stdout    # click.echo
        self.build_only = build_only
        self.remove = remove

        self.platform_user_id = platform_user_id
        self.platform_personal_access_token = platform_personal_access_token

        self._setup_docker()

        self.command = None     # subclass of RunCommand
        self.image = None       # docker.models.images.Image
        self.container = None   # docker.models.containers.Container

        super().__init__(quiet=quiet)

    def _prepare(self):
        """prepare docker image and arguments for docker run command"""
        self.logger.info("preparing ...")
        self._prepare_image()
        self._prepare_command()

    def _prepare_image(self):
        """prepare docker image"""
        for line in self._docker_cli.pull(self.image_name, stream=True, decode=True):
            out = line.get('status', '')
            if line.get('progress'):
                out += ' ' + line['progress']
            if out:
                self.logger.raw(out)
        self.image = self._client.images.pull(self.image_name)

    @abstractmethod
    def _prepare_command(self):
        """prepare command args for docker run"""
        raise NotImplementedError()

    def _start(self):
        """start container"""
        self.logger.info("start training job")
        self.container = self._run_container()
        return self.container

    def _stop(self):
        """stop container and delete container if needed"""
        self.logger.info("stopping, please wait for a while")
        if self.container is None:
            return

        try:
            self.container.stop()
        except docker.errors.NotFound:
            pass    # ignore because container is already deleted

        if self.remove:
            try:
                self.container.remove()
            except (docker.errors.APIError, docker.errors.NotFound):
                pass    # ignore

    def _end(self):
        self._on_end()
        self._clean()

    def _clean(self):
        """clean all resources"""
        self.logger.info('start cleaning...')
        if self.container is not None:
            self._stop()

    def _setup_docker(self):
        if not check_docker_installation():
            self.logger.error("docker command is required")
            raise RuntimeError("docker command is required")

        self._client = docker.from_env()
        self._setup_docker_cli()

    def _setup_docker_cli(self) -> None:
        """setup cli

        docker client will default to connecting to the following respectively.
        unix://var/run/docker.sock : linux / osx
        tcp://127.0.0.1:2376       : windows

        judge operation system using by os.name
        cf. https://docs.python.org/3.9/library/os.html#os.name
        """
        if os.name == 'nt':
            base_url = 'tcp://127.0.0.1:2376'
        else:
            base_url = 'unix://var/run/docker.sock'
        self._docker_cli = docker.APIClient(base_url=base_url)

    def _get_container(self):
        try:
            return self._client.containers.get(self.container.id)
        except docker.errors.NotFound:
            return None

    def _run_container(self):
        if self.command is None:
            raise RuntimeError("command is not set")

        try:
            return self._client.containers.run(**self.command.to_dict())
        except Exception:
            self.logger.error('failed to create local runtime')
            raise RuntimeError('failed to create local runtime')


def _generate_run_dockerfile(image: str, tag: str) -> str:
    from_image = '{}:{}'.format(image, tag)
    return DOCKERFILE_RUN_LOCAL_TEMPLATE.format(IMAGE=from_image)


def _parse_stream(output) -> Generator[dict, None, None]:
    lines = output.decode('utf-8').rstrip().split('\r\n')
    for line in lines:
        yield json.loads(line)


class ContainerBuildAndRun(ContainerRun):
    def __init__(self, image_type, *args, **kwargs):
        self.image_type = image_type
        super().__init__(*args, **kwargs)

    def _prepare_image(self):
        self.image = self._find_or_build_image()

    @abstractmethod
    def _prepare_command(self):
        """prepare command args for docker run"""
        raise NotImplementedError()

    def _find_or_build_image(self) -> Image:
        """build docker image adding label to be able to find it"""
        no_cache = self.no_cache
        if not no_cache:
            # when rebuild is required, don't use cache
            no_cache = self._check_rebuild_required()

        # skip build if use cache is enabled and built image exists.
        built_image = self._find_built_image()
        if built_image and not no_cache:
            return built_image

        self.logger.info("building image")
        try:
            self._build_image()
        except Exception:
            self.logger.error("failed to build image")
            raise RuntimeError("failed to build image")
        built_image = self._find_built_image()
        if built_image is None:
            raise RuntimeError("failed to find built image")
        return built_image

    def _check_rebuild_required(self) -> bool:
        """
        return true if requirements.txt exists and
        the last update is later than that of the specified image.
        target_last_modified and image_last_modified are time in utc.
        """
        image = self._find_built_image()
        if image is None:
            return True

        # check md5 of requirements.txt using label
        prev_md5 = image.labels.get(LOCAL_MODEL_IMAGE_MD5_KEY)
        if not prev_md5 or prev_md5 != self._calc_md5():
            return True
        return False

    def _find_built_image(self) -> Optional[Image]:
        images = self._client.images.list(
            filters={'label': LOCAL_MODEL_TYPE_KEY})
        if not images:
            return None
        # pick the first because images is descending order list
        return images[0]

    def _build_image(self) -> None:
        # ex. abeja/platform-minimal/0.1.0/local-inference-model
        try:
            image_name, image_tag = parse_image(self.image_name)
        except RuntimeError as e:
            self.logger.error(e)
            raise e

        name = '{}/{}/{}-{}'.format(
            image_name, image_tag, self.image_type, BUILT_IMAGE_SUFFIX)

        dockerfile = _generate_run_dockerfile(image_name, image_tag)

        with tempfile.NamedTemporaryFile(mode='w+t') as f:
            f.write(dockerfile)
            f.seek(0)  # put file pointer back the initial position for being read
            image_md5 = self._calc_md5()
            labels = {
                LOCAL_MODEL_TYPE_KEY: self.image_type,
                LOCAL_MODEL_IMAGE_MD5_KEY: image_md5
            }
            for output in self._docker_cli.build(tag=name, dockerfile=f.name, path=os.getcwd(), labels=labels):
                self._stdout_build_output(output)

    def _calc_md5(self):
        requirements_md5 = md5file(REQUIREMENTS_TXT) if os.path.exists(REQUIREMENTS_TXT) else ''
        pipfile_md5 = md5file(PIPFILE) if os.path.exists(PIPFILE) else ''
        image_name_md5 = md5digest(self.image_name.encode('utf-8'))
        return md5digest((requirements_md5 + pipfile_md5 + image_name_md5).encode('utf-8'))

    def _stdout_build_output(self, output):
        if not self.stdout:
            return
        try:
            for chunk in _parse_stream(output):
                for line in chunk.get('stream', '').split('\r\n'):
                    line = line.rstrip()
                    if line:
                        self.stdout(line)
                # NOTE: error message is not contained in `stream` key.
                if 'error' in chunk:
                    for line in chunk.get('error', '').split('\r\n'):
                        line = line.rstrip()
                        if line:
                            self.stdout(line)
        except Exception:
            pass
