import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    growatt_username: str
    growatt_password: str
    growatt_device_sn: str
    growatt_plant_id: str
    telegram_token: str
    telegram_chat_id: str
    battery_alert_levels: tuple[int, ...] = (30, 15)
    history_db_path: str = "data/history.db"
    cloudflare_account_id: str | None = None
    cloudflare_d1_database_id: str | None = None
    cloudflare_api_token: str | None = None

    @property
    def use_d1(self) -> bool:
        return self.cloudflare_api_token is not None

    @staticmethod
    def from_env() -> "Config":
        required = [
            "GROWATT_USERNAME",
            "GROWATT_PASSWORD",
            "GROWATT_DEVICE_SN",
            "GROWATT_PLANT_ID",
            "TELEGRAM_TOKEN",
            "TELEGRAM_CHAT_ID",
        ]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            raise ConfigError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
        d1_keys = ["CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_D1_DATABASE_ID", "CLOUDFLARE_API_TOKEN"]
        d1_set = [k for k in d1_keys if os.environ.get(k)]
        if d1_set and len(d1_set) != len(d1_keys):
            missing_d1 = [k for k in d1_keys if k not in d1_set]
            raise ConfigError(
                f"D1 history needs all of {', '.join(d1_keys)}; missing {', '.join(missing_d1)}"
            )
        try:
            int(os.environ["TELEGRAM_CHAT_ID"])
        except ValueError:
            raise ConfigError("TELEGRAM_CHAT_ID must be a numeric chat ID")
        return Config(
            growatt_username=os.environ["GROWATT_USERNAME"],
            growatt_password=os.environ["GROWATT_PASSWORD"],
            growatt_device_sn=os.environ["GROWATT_DEVICE_SN"],
            growatt_plant_id=os.environ["GROWATT_PLANT_ID"],
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            battery_alert_levels=_parse_levels(os.environ.get("BATTERY_ALERT_LEVELS", "30,15")),
            history_db_path=os.environ.get("HISTORY_DB_PATH", "data/history.db"),
            cloudflare_account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID") or None,
            cloudflare_d1_database_id=os.environ.get("CLOUDFLARE_D1_DATABASE_ID") or None,
            cloudflare_api_token=os.environ.get("CLOUDFLARE_API_TOKEN") or None,
        )


def _parse_levels(raw: str) -> tuple[int, ...]:
    try:
        levels = sorted({int(x) for x in raw.split(",") if x.strip()}, reverse=True)
    except ValueError:
        raise ConfigError(f"BATTERY_ALERT_LEVELS must be comma-separated integers, got {raw!r}")
    if any(not 0 < lvl < 100 for lvl in levels):
        raise ConfigError("BATTERY_ALERT_LEVELS values must be between 1 and 99")
    return tuple(levels)
