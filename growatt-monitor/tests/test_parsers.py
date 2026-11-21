"""Parser tests against a real getStorageStatusData payload (captured 2026-11-21)."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from growatt import parsers  # noqa: E402

STATUS = json.loads((pathlib.Path(__file__).parent / "fixtures" / "storage_status.json").read_text())


def test_status_fields_from_real_payload():
    assert parsers.pv_watts(STATUS) == 21.0
    assert parsers.pv_voltage(STATUS) == 275.8
    assert parsers.load_watts(STATUS) == 824.0
    assert parsers.battery_soc(STATUS) == 75.0
    assert parsers.battery_voltage(STATUS) == 53.5
    assert parsers.grid_voltage(STATUS) == 218.4
    assert parsers.grid_present(STATUS) is True


def test_grid_absent_below_threshold():
    payload = {"result": 1, "obj": {**STATUS["obj"], "vAcInput": "0"}}
    assert parsers.grid_present(payload) is False


def test_missing_fields_are_none_not_zero():
    payload = {"result": 1, "obj": {}}
    assert parsers.pv_watts(payload) is None
    assert parsers.grid_present(payload) is None


def test_load_energy_integrates_5_minute_watts():
    # 12 samples of 1000 W = 1 hour at 1 kW = 1 kWh; nulls are ignored.
    payload = {"result": 1, "obj": {"charts": {"userLoad": [None] * 10 + [1000] * 12 + [None] * 266}}}
    assert parsers.total_load_energy_kwh(payload) == 1.0


def test_load_energy_none_when_no_samples():
    payload = {"result": 1, "obj": {"charts": {"userLoad": [None] * 288}}}
    assert parsers.total_load_energy_kwh(payload) is None
