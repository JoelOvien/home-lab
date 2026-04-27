"""Pure functions that extract metrics from Growatt API JSON responses.

IMPORTANT: The exact JSON key names below are the conventional ones used by
Growatt's SPF endpoints (cross-referenced from open-source clients like the
`growattServer` PyPI package), but they have NOT been verified against a live
response from this specific account / firmware. Every field marked TODO must
be confirmed by logging a real response and adjusting the key if needed.

To verify, run once after deployment:
    log.info("status payload: %s", client.get_device_status())
and check the actual structure.
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
    # TODO verify key against live response. Common candidates: ppv, pv1Watt+pv2Watt.
    obj = _obj(payload)
    direct = _to_float(obj.get("ppv"))
    if direct is not None:
        return direct
    p1 = _to_float(obj.get("pv1Watt")) or 0.0
    p2 = _to_float(obj.get("pv2Watt")) or 0.0
    total = p1 + p2
    return total if total > 0 else None


def load_watts(payload: dict) -> Optional[float]:
    # TODO verify key. Common candidates: loadPower, pLocalLoad, useWatt.
    obj = _obj(payload)
    for k in ("loadPower", "pLocalLoad", "useWatt", "pac_to_user"):
        v = _to_float(obj.get(k))
        if v is not None:
            return v
    return None


def battery_soc(payload: dict) -> Optional[float]:
    # TODO verify key. Common: capacity, SOC, soc.
    obj = _obj(payload)
    for k in ("capacity", "SOC", "soc", "batSoc"):
        v = _to_float(obj.get(k))
        if v is not None:
            return v
    return None


def battery_voltage(payload: dict) -> Optional[float]:
    # TODO verify key. Common: vBat, batVolt.
    obj = _obj(payload)
    for k in ("vBat", "batVolt", "batteryVoltage"):
        v = _to_float(obj.get(k))
        if v is not None:
            return v
    return None


def grid_voltage(payload: dict) -> Optional[float]:
    # TODO verify key. Common: vAc1, gridVoltage, vac1.
    obj = _obj(payload)
    for k in ("vAc1", "gridVoltage", "vac1", "vGrid"):
        v = _to_float(obj.get(k))
        if v is not None:
            return v
    return None


def grid_present(payload: dict) -> Optional[bool]:
    v = grid_voltage(payload)
    if v is None:
        return None
    return v >= GRID_DOWN_VOLTAGE


def total_load_energy_kwh(payload: dict) -> Optional[float]:
    """Extract cumulative load energy (kWh) from an energy-day chart response.

    TODO verify shape. The chart endpoint typically returns something like
    {"obj": {"useEnergy": [...], "charts": {...}}} — we want the sum of the
    'use'/'load' series, OR the totalizer field if present.
    """
    obj = _obj(payload)
    for k in ("eUserToday", "loadEnergyToday", "useEnergyToday"):
        v = _to_float(obj.get(k))
        if v is not None:
            return v
    # Fallback: sum a series array
    charts = obj.get("charts") if isinstance(obj.get("charts"), dict) else obj
    for series_key in ("userLoad", "load", "useEnergy"):
        series = charts.get(series_key) if isinstance(charts, dict) else None
        if isinstance(series, list):
            total = 0.0
            any_value = False
            for x in series:
                f = _to_float(x)
                if f is not None:
                    total += f
                    any_value = True
            if any_value:
                return total
    return None
