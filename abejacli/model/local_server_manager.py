import requests
from retrying import retry

HEALTH_CHECK_RETRY_INTERVAL = 1 * 1000  # one second
HEALTH_CHECK_RETRY_MAX_ATTEMPT = 60
HEALTH_CHECK_TIMEOUT = 1
SPOT_INSTANCE_INITIAL_HEALTH_CHECK = 60 * 2     # two minutes


# assert ((HEALTH_CHECK_RETRY_INTERVAL + HEALTH_CHECK_TIMEOUT)
#         * HEALTH_CHECK_RETRY_MAX_ATTEMPT) <= SPOT_INSTANCE_INITIAL_HEALTH_CHECK


class LocalServerManager:
    def __init__(self, local_server):
        self._server = local_server

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._server.stop()

    @retry(wait_fixed=HEALTH_CHECK_RETRY_INTERVAL,
           stop_max_attempt_number=HEALTH_CHECK_RETRY_MAX_ATTEMPT)
    def wait_until_running(self, health_check_url):
        """
        timeout * wait * stop must be within two minutes
        which is time that stop instance first receive health check.

        :param health_check_url:
        :return:
        """
        res = requests.get(health_check_url,
                           timeout=HEALTH_CHECK_TIMEOUT)
        res.raise_for_status()

    def send_request(self, method, endpoint, headers=None, data=None):
        if not headers:
            headers = {}

        # We intentionally make a request can wait forever by specifying
        # the `timeout` value is `None`.
        res = requests.request(
            method, endpoint, headers=headers, data=data, timeout=None)
        res.raise_for_status()
        return res

    def dump_logs(self):
        dumped_logs = self._server.logs(follow=False, stream=False)
        if type(dumped_logs) == bytes:
            # for py3
            dumped_logs = dumped_logs.decode('utf-8')
        return dumped_logs
