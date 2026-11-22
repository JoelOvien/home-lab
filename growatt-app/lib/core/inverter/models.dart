import 'package:growatt_app/core/d1/d1_source.dart';

double? asDouble(Object? v) => switch (v) {
      num n => n.toDouble(),
      String s => double.tryParse(s),
      _ => null,
    };

int? asInt(Object? v) => switch (v) {
      int n => n,
      num n => n.toInt(),
      String s => int.tryParse(s),
      _ => null,
    };

/// The recorder writes every 5 minutes, so older data can't be trusted.
const staleAfter = Duration(minutes: 15);

class Snapshot {
  const Snapshot({
    required this.ts,
    this.pvW,
    this.loadW,
    this.gridW,
    this.batteryW,
    this.soc,
    this.batteryV,
    this.gridV,
    this.gridPresent,
    this.loadPct,
    this.invStatus,
    this.status,
    this.dtc,
    this.energy = EnergyCounters.empty,
  });

  final int ts;
  final double? pvW, loadW, gridW, batteryW, soc, batteryV, gridV, loadPct;
  final bool? gridPresent;
  final int? invStatus, status, dtc;
  final EnergyCounters energy;

  static Snapshot? fromRow(D1Row r) {
    final ts = asInt(r['ts']);
    if (ts == null) return null;
    final gp = asInt(r['grid_present']);
    return Snapshot(
      ts: ts,
      pvW: asDouble(r['pv_w']),
      loadW: asDouble(r['load_w']),
      gridW: asDouble(r['grid_w']),
      batteryW: asDouble(r['battery_w']),
      soc: asDouble(r['soc']),
      batteryV: asDouble(r['battery_v']),
      gridV: asDouble(r['grid_v']),
      gridPresent: gp == null ? null : gp != 0,
      loadPct: asDouble(r['load_pct']),
      invStatus: asInt(r['inv_status']),
      status: asInt(r['status']),
      dtc: asInt(r['dtc']),
      energy: EnergyCounters.fromRow(r),
    );
  }

  bool isStale(DateTime now) =>
      now.difference(DateTime.fromMillisecondsSinceEpoch(ts * 1000)) > staleAfter;
}

class TodayTotal {
  const TodayTotal(this.today, this.total);
  final double? today, total;
  bool get isEmpty => today == null && total == null;
}

/// Growatt's own kWh counters (getStorageTotalData), recorded on each snapshot.
class EnergyCounters {
  const EnergyCounters({
    this.pv = const TodayTotal(null, null),
    this.discharge = const TodayTotal(null, null),
    this.charge = const TodayTotal(null, null),
    this.import = const TodayTotal(null, null),
    this.load = const TodayTotal(null, null),
  });
  static const empty = EnergyCounters();

  final TodayTotal pv, discharge, charge, import, load;

  factory EnergyCounters.fromRow(D1Row r) {
    TodayTotal pair(String name) =>
        TodayTotal(asDouble(r['${name}_today_kwh']), asDouble(r['${name}_total_kwh']));
    return EnergyCounters(
      pv: pair('pv'),
      discharge: pair('discharge'),
      charge: pair('charge'),
      import: pair('import'),
      load: pair('load'),
    );
  }

  bool get isEmpty => [pv, discharge, charge, import, load].every((c) => c.isEmpty);
}

class Outage {
  const Outage(this.startTs, this.endTs);
  final int startTs;
  final int? endTs;

  static Outage? fromRow(D1Row r) {
    final start = asInt(r['start_ts']);
    return start == null ? null : Outage(start, asInt(r['end_ts']));
  }

  Duration duration(DateTime now) => Duration(
      seconds: (endTs ?? now.millisecondsSinceEpoch ~/ 1000) - startTs);
}

class InverterEvent {
  const InverterEvent({required this.ts, required this.kind, this.detail});
  final int ts;
  final String kind;
  final String? detail;

  static InverterEvent? fromRow(D1Row r) {
    final ts = asInt(r['ts']);
    final kind = r['kind'];
    if (ts == null || kind is! String) return null;
    final detail = r['detail'];
    return InverterEvent(ts: ts, kind: kind, detail: detail is String ? detail : null);
  }
}

enum BatteryDirection { charging, discharging }

class WorkerState {
  const WorkerState(this.values);
  static const empty = WorkerState({});

  final Map<String, String> values;

  factory WorkerState.fromRows(List<D1Row> rows) => WorkerState({
        for (final r in rows)
          if (r['key'] is String && r['value'] != null) r['key'] as String: '${r['value']}',
      });

  int? get startedTs => asInt(values['started_ts']);
  int? get lastOkTs => asInt(values['last_ok_ts']);
  String? get lastError => values['last_error'];
  int? get lastErrorTs => asInt(values['last_error_ts']);
  int? get mutedUntilTs => asInt(values['muted_until_ts']);
  double? get batteryCapacityKwh => asDouble(values['battery_capacity_kwh']);
  String? get tz => values['tz'];

  bool isMuted(DateTime now) {
    final until = mutedUntilTs;
    return until != null && until * 1000 > now.millisecondsSinceEpoch;
  }
}

const _dischargingStatus = 2;
const _chargingStatuses = {5, 6, 7, 8, 9, 10};

/// `batPower` is a magnitude in both directions on this inverter, so the
/// direction comes from the SPF `status` code, the same mapping as the bot's
/// /flow. Any other code (standby, bypass, fault, 12 = both) is unknown.
BatteryDirection? batteryDirection(int? status) {
  if (status == _dischargingStatus) return BatteryDirection.discharging;
  if (_chargingStatuses.contains(status)) return BatteryDirection.charging;
  return null;
}

class BatteryFlow {
  const BatteryFlow(this.direction, this.chargeW, this.dischargeW);
  final BatteryDirection? direction;
  final double? chargeW, dischargeW;

  factory BatteryFlow.of(Snapshot? s) {
    final direction = batteryDirection(s?.status);
    final w = s?.batteryW?.abs() ?? 0;
    return switch (direction) {
      BatteryDirection.charging => BatteryFlow(direction, w, 0),
      BatteryDirection.discharging => BatteryFlow(direction, 0, w),
      null => const BatteryFlow(null, null, null),
    };
  }
}

/// Hours left at the current load, from SOC × capacity ÷ load. Only while the
/// battery is discharging, since otherwise it isn't running down.
double? runtimeHours({double? soc, double? capacityKwh, double? loadW, BatteryDirection? direction}) {
  if (direction != BatteryDirection.discharging) return null;
  if (soc == null || capacityKwh == null || loadW == null || loadW <= 0) return null;
  return soc / 100 * capacityKwh / (loadW / 1000);
}

class SeriesPoint {
  const SeriesPoint({required this.ts, this.pvW, this.loadW, this.gridW, this.soc});
  final int ts;
  final double? pvW, loadW, gridW, soc;

  static SeriesPoint? fromRow(D1Row r) {
    final ts = asInt(r['ts']);
    if (ts == null) return null;
    return SeriesPoint(
      ts: ts,
      pvW: asDouble(r['pv_w']),
      loadW: asDouble(r['load_w']),
      gridW: asDouble(r['grid_w']),
      soc: asDouble(r['soc']),
    );
  }
}

class WeeklyVoltage {
  const WeeklyVoltage({required this.weekStartTs, required this.volts, required this.samples});
  final int weekStartTs;
  final double volts;
  final int samples;
}

/// Growatt's SPF Modbus status table, as the worker maps it. Unverified on
/// this inverter, so the raw code is always shown alongside.
const _statusNames = {
  0: 'Standby',
  1: 'No use',
  2: 'Discharging',
  3: 'Fault',
  4: 'Firmware update',
  5: 'PV charging',
  6: 'AC charging',
  7: 'PV + AC charging',
  8: 'PV + AC charging, grid bypass',
  9: 'PV charging, grid bypass',
  10: 'AC charging, grid bypass',
  11: 'Grid bypass',
  12: 'PV charging and discharging',
};

String? statusName(int? code) => code == null ? null : _statusNames[code];
