import json
import os
import tempfile
from typing import Callable, Generator, Optional

import docker
from docker.models.containers import Container
from docker.models.images import Image

from abejacli.docker.commands.run import RunCommand
from abejacli.model import md5file

DOCKERFILE_RUN_LOCAL_TEMPLATE = '''
FROM {IMAGE}

ADD . /srv/app
WORKDIR /srv/app
RUN if test -r requirements.txt; then pip install --no-cache-dir -r requirements.txt; fi
'''

REQUIREMENTS_TXT = 'requirements.txt'
BUILT_IMAGE_SUFFIX = 'local-model'
LOCAL_MODEL_TYPE_KEY = 'abeja-platform-model-type'
LOCAL_MODEL_REQUIREMENTS_MD5_KEY = 'abeja-platform-requirement-md5'

LOCAL_MODEL_TYPE_VALUE = 'inference'
LOCAL_TRAIN_TYPE_VALUE = 'train'


class LocalServer:
    def __init__(self, container: Container, port: Optional[int] = None) -> None:
        self._container = container
        self.endpoint = 'http://localhost:{}'.format(port)

    def stop(self) -> None:
        # much faster to use kill, because stop container takes about 10 sec.
        # self._container.stop()
        try:
            self._container.kill()
        except docker.errors.NotFound:
            # ignore because the container does not exist anymore.
            return

    def logs(
            self, follow: bool = True, stream: bool = True,
            since: str = None) -> Generator[bytes, None, None]:
        return self._container.logs(follow=follow, stream=stream, since=since)


class LocalModelHandler:
    def __init__(self) -> None:
        self._client = docker.from_env()
        self._setup_docker_cli()
        self.requirements_file = REQUIREMENTS_TXT

    def _setup_docker_cli(self) -> None:
        """
        setup cli

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

    def check_rebuild_required(self) -> bool:
        """
        return true if requirements.txt exists and
        the last update is later than that of the specified image.
        target_last_modified and image_last_modified are time in utc.

        :param image:
        :param tag:
        :return:
        """
        # no need to rebuild if requirements.txt does not exist
        if not os.path.exists(self.requirements_file):
            return False

        image = self._find_built_image()
        if image is None:
            return True

        # check md5 of requirements.txt using label
        prev_md5 = image.labels.get(LOCAL_MODEL_REQUIREMENTS_MD5_KEY)
        if not prev_md5:
            return True

        if prev_md5 != md5file(self.requirements_file):
            return True

        return False

    def build_run_image(
            self, image: str, tag: str, model_type: str = None,
            no_cache: bool = False, stdout=None) -> Image:
        """
        build docker image adding label to be able to find it

        :param image:
        :param tag:
        :param no_cache:
        :param stdout:
        :return: built docker image
        """
        if not no_cache:
            # when rebuild is required, don't use cache
            no_cache = self.check_rebuild_required()

        # skip build if use cache is enabled and built image exists.
        built_image = self._find_built_image()
        if built_image and not no_cache:
            return built_image

        dockerfile = self._generate_run_dockerfile(image, tag)

        # ex. abeja/platform-minimal/0.1.0/local-inference-model
        image_name = '{}/{}/{}-{}'.format(image,
                                          tag, model_type, BUILT_IMAGE_SUFFIX)

        self._build_image(image_name, dockerfile, model_type, stdout)
        return self._find_built_image()

    def _build_image(self, name: str, dockerfile: str, type_value: str, stdout: Callable = None) -> None:
        with tempfile.NamedTemporaryFile(mode='w+t') as f:
            f.write(dockerfile)
            f.seek(0)  # put file pointer back the initial position for being read
            requirements_md5 = md5file(self.requirements_file) if os.path.exists(
                self.requirements_file) else None
            labels = {
                LOCAL_MODEL_TYPE_KEY: type_value,
                LOCAL_MODEL_REQUIREMENTS_MD5_KEY: requirements_md5
            }
            for output in self._docker_cli.build(tag=name, dockerfile=f.name, path=os.getcwd(), labels=labels):
                if not stdout:
                    continue
                try:
                    for line in self._parse_stream(output):
                        line = line['stream'].rstrip()
                        stdout(str(line))
                except Exception:
                    continue

    def run_container(self, run_command: RunCommand) -> Container:
        return self._client.containers.run(**run_command.to_dict())

    def stop_container(self, container) -> None:
        container.stop()

    def create_local_server(self, run_command: RunCommand) -> LocalServer:
        """
        run container in background as local api server
        assign dynamic port number for host port.

        :return:
        """
        container = self.run_container(run_command=run_command)
        port = run_command.get_port()
        return LocalServer(container, port=port)

    def _generate_run_dockerfile(self, image: str, tag: str) -> str:
        from_image = '{}:{}'.format(image, tag)
        return DOCKERFILE_RUN_LOCAL_TEMPLATE.format(IMAGE=from_image)

    def _find_built_image(self) -> Optional[Image]:
        images = self._client.images.list(
            filters={'label': LOCAL_MODEL_TYPE_KEY})
        if not images:
            return None
        # pick the first because images is descending order list
        return images[0]

    def _parse_stream(self, output) -> Generator[dict, None, None]:
        if type(output) == bytes:
            # for py3
            output = output.decode('utf-8')
        lines = output.rstrip().split('\r\n')
        for line in lines:
            yield json.loads(line)
