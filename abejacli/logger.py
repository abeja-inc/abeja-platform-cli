import logging
import os

from abejacli.config import LOG_DIRECTORY, LOG_FILE_PATH, STDERROR_LOG_LEVEL


def get_logger():
    """
    Return a logger to output to stderr and logging file

    :return: (Logger) Logger.
    """
    # Initialize if this function is called at first.
    if not get_logger.initialized:
        if not os.path.exists(LOG_DIRECTORY):
            os.makedirs(LOG_DIRECTORY)

        logger = logging.getLogger("abejacli")
        logger.setLevel(logging.DEBUG)

        # stderr
        echo = logging.StreamHandler()
        echo.setLevel(logging.getLevelName(STDERROR_LOG_LEVEL))
        echo.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)8s %(message)s"))

        # file error
        file_logging = logging.FileHandler(filename=LOG_FILE_PATH)
        file_logging.setLevel(logging.DEBUG)
        file_logging.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)8s %(message)s"))

        logger.addHandler(echo)
        logger.addHandler(file_logging)

        # Finish initialize.
        get_logger.initialized = True

    # Return existent logger if it has been already created.
    return logging.getLogger("abejacli")


get_logger.initialized = False
