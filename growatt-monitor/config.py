import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    growatt_username: str
    growatt_password: str
    growatt_device_sn: str
    telegram_token: str
    telegram_chat_id: str

    @staticmethod
    def from_env() -> "Config":
        required = [
            "GROWATT_USERNAME",
            "GROWATT_PASSWORD",
            "GROWATT_DEVICE_SN",
            "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        return Config(
            growatt_username=os.environ["GROWATT_USERNAME"],
            growatt_password=os.environ["GROWATT_PASSWORD"],
            growatt_device_sn=os.environ["GROWATT_DEVICE_SN"],
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        )
