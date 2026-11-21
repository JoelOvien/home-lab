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
