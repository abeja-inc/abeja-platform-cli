from enum import Enum
from typing import Any


class IntegrationServiceType(Enum):
    ABEJA_PLATFORM_LABS = "abeja-platform-labs"
    # NOTE: Not supported yet
    # ABEJA_PLATFORM_TRAINING_JOBS = "abeja-platform-training-jobs"
    # ABEJA_PLATFORM_DEPLOYMENT_HTTPS_SERVICES = "abeja-platform-deployment-https-services"
    # ABEJA_PLATFORM_DEPLOYMENT_TRIGGERS = "abeja-platform-deployment-triggers"

    @classmethod
    def has_value(cls, value: Any) -> bool:
        return value in cls._value2member_map_
