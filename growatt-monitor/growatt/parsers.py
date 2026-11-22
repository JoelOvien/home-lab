"""Pure functions that extract metrics from Growatt API JSON responses.

Key names verified 2026-11-21 against live responses from
/panel/storage/getStorageStatusData and /panel/storage/getStorageEnergyDayChart
for the SPF 6000 ES PLUS (KHM9F990N7). See tests/fixtures/ for real payloads.

Status payload keys used: ppv1/ppv2 (PV W), vPv1/vPv2 (PV V), loadPower (W),
capacity (SOC %), vBat (V), vAcInput (grid V), gridPower (W drawn from grid).
"""
from typing import Any, Optional

# Voltage threshold below which the grid is considered down.
GRID_DOWN_VOLTAGE = 180.0


def _obj(payload: dict) -> dict:
    """Growatt typically nests device data under `obj` (sometimes `data`)."""
    if not isinstance(payload, dict):
        return {}
    if isinstance(payload.get("obj"), dict):
        return payload["obj"]
    if isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def _to_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def pv_watts(payload: dict) -> Optional[float]:
    obj = _obj(payload)
    p1 = _to_float(obj.get("ppv1"))
    p2 = _to_float(obj.get("ppv2"))
    if p1 is None and p2 is None:
        return _to_float(obj.get("panelPower"))
    return (p1 or 0.0) + (p2 or 0.0)


def pv_voltage(payload: dict) -> Optional[float]:
    """Highest PV string voltage. The SPF 6000 ES PLUS has one MPPT, so this
    is effectively vPv1; MPPT only activates around 120V and above."""
    obj = _obj(payload)
    values = [v for v in (_to_float(obj.get("vPv1")), _to_float(obj.get("vPv2"))) if v is not None]
    return max(values) if values else None


def load_watts(payload: dict) -> Optional[float]:
    return _to_float(_obj(payload).get("loadPower"))


def grid_watts(payload: dict) -> Optional[float]:
    return _to_float(_obj(payload).get("gridPower"))


def battery_watts(payload: dict) -> Optional[float]:
    """Raw batPower. The sign convention (charge vs discharge) is unverified."""
    return _to_float(_obj(payload).get("batPower"))


def battery_soc(payload: dict) -> Optional[float]:
    return _to_float(_obj(payload).get("capacity"))


def battery_voltage(payload: dict) -> Optional[float]:
    return _to_float(_obj(payload).get("vBat"))


def grid_voltage(payload: dict) -> Optional[float]:
    return _to_float(_obj(payload).get("vAcInput"))


def grid_present(payload: dict) -> Optional[bool]:
    v = grid_voltage(payload)
    if v is None:
        return None
    return v >= GRID_DOWN_VOLTAGE


# The day chart holds 288 samples (one per 5 minutes) of instantaneous watts.
SAMPLES_PER_HOUR = 12


def total_load_energy_kwh(payload: dict) -> Optional[float]:
    """Load energy (kWh) so far today from an energy-day chart response.

    Integrates charts.userLoad (W, 5-minute samples). Returns None when the
    chart has no samples yet.
    """
    charts = _obj(payload).get("charts")
    series = charts.get("userLoad") if isinstance(charts, dict) else None
    if not isinstance(series, list):
        return None
    watts = [f for f in (_to_float(x) for x in series) if f is not None]
    if not watts:
        return None
    return sum(watts) / SAMPLES_PER_HOUR / 1000


def _to_int(v: Any) -> Optional[int]:
    f = _to_float(v)
    return None if f is None else int(f)


def load_percent(payload: dict) -> Optional[float]:
    """Load as a % of the inverter's rating (Growatt spells it loadPrecent)."""
    return _to_float(_obj(payload).get("loadPrecent"))


def inv_status(payload: dict) -> Optional[int]:
    return _to_int(_obj(payload).get("invStatus"))


def status_code(payload: dict) -> Optional[int]:
    return _to_int(_obj(payload).get("status"))


def dtc(payload: dict) -> Optional[int]:
    return _to_int(_obj(payload).get("dtc"))


# SPF off-grid system status codes, from Growatt's SPF Modbus protocol. Not yet
# checked against the dashboard, so callers always show the raw code too.
STATUS_NAMES = {
    0: "standby",
    1: "no use",
    2: "discharging",
    3: "fault",
    4: "flash (firmware update)",
    5: "PV charging",
    6: "AC charging",
    7: "PV + AC charging",
    8: "PV + AC charging, grid bypass",
    9: "PV charging, grid bypass",
    10: "AC charging, grid bypass",
    11: "grid bypass",
    12: "PV charging and discharging",
}

FAULT_STATUS = 3


def status_name(code: Optional[int]) -> Optional[str]:
    return None if code is None else STATUS_NAMES.get(code)
