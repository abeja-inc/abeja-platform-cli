import json

from abejacli.config import (
    DOCKER_REPOSITORIES,
    RUN_LOCAL_COMMAND_V1,
    RUN_LOCAL_COMMAND_V2,
    TAG_VERSION_SAMPV1
)


def get_runtime_command(image: str, tag: str, v1_flag: bool):
    if image.split('/')[0] not in DOCKER_REPOSITORIES:
        return RUN_LOCAL_COMMAND_V2
    if v1_flag:
        return RUN_LOCAL_COMMAND_V1

    if tag in TAG_VERSION_SAMPV1:
        return RUN_LOCAL_COMMAND_V1

    return RUN_LOCAL_COMMAND_V2


def format_container_log(log: str):
    formatted_message = log.decode('utf-8').rstrip('\n')
    try:
        msg = json.loads(formatted_message)["message"]
        return msg
    except json.decoder.JSONDecodeError:
        # When log is not json
        return formatted_message
    except KeyError:
        # When message is not in json
        return formatted_message
