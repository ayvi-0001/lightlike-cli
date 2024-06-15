from enum import Enum
from typing import Any, Sequence

__all__: Sequence[str] = (
    "CredentialsSource",
    "ClientConfigOptions",
    "ClientInitOptions",
    "ActiveCompleter",
)


class _ValueEnum(str, Enum):
    def __get__(self, instance: Any, owner: Any) -> str:
        return str(self.value)


class CredentialsSource(_ValueEnum):
    not_set = "not-set"
    from_environment = "from-environment"
    from_service_account_key = "from-service-account-key"

    def __get__(self, instance: Any, owner: Any) -> str:
        return str(self.value).replace("'", "")


class ClientConfigOptions(_ValueEnum):
    REINITIALIZE = "Re-initialize this configuration [%s] with new settings"
    CREATE_NEW = "Create a new configuration"
    SWITCH_AND_REINITIALIZE = "Switch to and re-initialize existing configuration: [%s]"


class ClientInitOptions(_ValueEnum):
    UPDATE_PROJECT = "Change projects with current auth [%s]."
    UPDATE_AUTH = "Switch auth method [current=%s]."


class ActiveCompleter(int, Enum):
    CMD = 1
    HISTORY = 2
    PATH = 3
