import os
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

BATTERY_SIGNS = ("charge_positive", "charge_negative")


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
    tz_name: str = "UTC"
    daily_report_time: str = "21:00"
    battery_capacity_kwh: float | None = None
    load_alert_pct: float = 85.0
    solar_check_hours: tuple[int, int] = (10, 15)
    battery_sign: str | None = None

    @property
    def use_d1(self) -> bool:
        return self.cloudflare_api_token is not None

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)

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
            tz_name=_parse_tz(os.environ.get("TZ") or "UTC"),
            daily_report_time=_parse_hhmm(os.environ.get("DAILY_REPORT_TIME") or "21:00"),
            battery_capacity_kwh=_parse_positive(
                "BATTERY_CAPACITY_KWH", os.environ.get("BATTERY_CAPACITY_KWH")
            ),
            load_alert_pct=_parse_positive("LOAD_ALERT_PCT", os.environ.get("LOAD_ALERT_PCT") or "85"),
            solar_check_hours=_parse_hours(os.environ.get("SOLAR_CHECK_HOURS") or "10-15"),
            battery_sign=_parse_sign(os.environ.get("BATTERY_SIGN")),
        )


def _parse_levels(raw: str) -> tuple[int, ...]:
    try:
        levels = sorted({int(x) for x in raw.split(",") if x.strip()}, reverse=True)
    except ValueError:
        raise ConfigError(f"BATTERY_ALERT_LEVELS must be comma-separated integers, got {raw!r}")
    if any(not 0 < lvl < 100 for lvl in levels):
        raise ConfigError("BATTERY_ALERT_LEVELS values must be between 1 and 99")
    return tuple(levels)


def _parse_tz(raw: str) -> str:
    try:
        ZoneInfo(raw)
    except (ZoneInfoNotFoundError, ValueError):
        raise ConfigError(f"TZ must be an IANA time zone like Africa/Lagos, got {raw!r}")
    return raw


def _parse_hhmm(raw: str) -> str:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", raw.strip())
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        raise ConfigError(f"DAILY_REPORT_TIME must be HH:MM, got {raw!r}")
    return f"{int(m[1]):02d}:{m[2]}"


def _parse_positive(name: str, raw: str | None) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number, got {raw!r}")
    if value <= 0:
        raise ConfigError(f"{name} must be above 0")
    return value


def _parse_hours(raw: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", raw.strip())
    if not m or not 0 <= int(m[1]) < int(m[2]) <= 24:
        raise ConfigError(f"SOLAR_CHECK_HOURS must look like 10-15, got {raw!r}")
    return int(m[1]), int(m[2])


def _parse_sign(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    if raw.strip() not in BATTERY_SIGNS:
        raise ConfigError(f"BATTERY_SIGN must be one of {', '.join(BATTERY_SIGNS)}")
    return raw.strip()
