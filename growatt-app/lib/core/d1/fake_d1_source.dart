import 'dart:math';

import 'package:growatt_app/core/d1/d1_source.dart';

/// Generated data for the Simulator and widget tests. With [oldSchema] it
/// behaves like D1 before the worker migration: no worker_state, no events,
/// no new snapshot columns, and an outage in progress.
class FakeD1Source implements D1Source {
  FakeD1Source({this.oldSchema = false, DateTime? now}) : _now = now;

  final bool oldSchema;
  final DateTime? _now;

  int get _nowTs => (_now ?? DateTime.now()).millisecondsSinceEpoch ~/ 1000;

  @override
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]) async {
    final now = _nowTs;
    if (sql.contains('FROM worker_state')) return oldSchema ? [] : _state(now);
    if (sql.contains('FROM events')) return oldSchema ? [] : _events(now);
    if (sql.contains('FROM outages WHERE end_ts IS NULL')) {
      return oldSchema ? [{'start_ts': now - 8000, 'end_ts': null}] : [];
    }
    if (sql.contains('FROM outages')) return _outages(now);
    if (sql.contains('MAX(ts)')) return [{'ts': _latestTs(now)}];
    if (sql.contains('AVG(battery_v)')) return _health(now);
    if (sql.contains('ORDER BY ts DESC LIMIT 1')) return [_latest(now)];
    if (sql.contains('FROM snapshots WHERE ts >= ?')) {
      return _series(params.first as int, now);
    }
    return [];
  }

  int _latestTs(int now) => now - 140;

  D1Row _latest(int now) {
    final row = <String, dynamic>{
      'ts': _latestTs(now),
      'pv_w': 1240.0,
      'load_w': 820,
      'grid_w': oldSchema ? 0 : 0.0,
      'battery_w': 420.0,
      'soc': 76.0,
      'battery_v': 52.8,
      'grid_v': oldSchema ? 0.0 : 231.4,
      'grid_present': oldSchema ? 0 : 1,
    };
    if (!oldSchema) {
      row.addAll({
        'load_pct': 13.7,
        'inv_status': -10,
        'status': 8,
        'dtc': 20006,
        'pv_today_kwh': 3.6,
        'pv_total_kwh': 3.7,
        'discharge_today_kwh': 1.4,
        'discharge_total_kwh': 7.0,
        'charge_today_kwh': 3.7,
        'charge_total_kwh': 65.5,
        'import_today_kwh': 4.7,
        'import_total_kwh': 131.2,
        'load_today_kwh': 6.1,
        'load_total_kwh': 73.8,
      });
    }
    return row;
  }

  List<D1Row> _state(int now) => [
        {'key': 'started_ts', 'value': '${now - 3 * 86400 - 4 * 3600}'},
        {'key': 'last_ok_ts', 'value': '${now - 140}'},
        {'key': 'last_error', 'value': 'ReadTimeout'},
        {'key': 'last_error_ts', 'value': '${now - 26 * 3600}'},
        {'key': 'muted_until_ts', 'value': '${now + 90 * 60}'},
        {'key': 'battery_capacity_kwh', 'value': '5'},
        {'key': 'tz', 'value': 'Africa/Lagos'},
      ];

  List<D1Row> _events(int now) => [
        {'ts': now - 3 * 3600, 'kind': 'grid_up', 'detail': '🔌 Grid RESTORED after 1h 12m (229.0V)'},
        {'ts': now - 4 * 3600 - 720, 'kind': 'grid_down', 'detail': '⚠️ Grid LOST (0.0V)'},
        {'ts': now - 9 * 3600, 'kind': 'battery_full', 'detail': 'SOC 100%'},
        {'ts': now - 30 * 3600, 'kind': 'overload', 'detail': 'Load 91%'},
        {'ts': now - 50 * 3600, 'kind': 'battery_low', 'detail': 'SOC 28%'},
        {'ts': now - 72 * 3600, 'kind': 'unreachable', 'detail': null},
      ];

  List<D1Row> _outages(int now) => [
        if (oldSchema) {'start_ts': now - 8000, 'end_ts': null},
        {'start_ts': now - 4 * 3600 - 720, 'end_ts': now - 3 * 3600},
        {'start_ts': now - 28 * 3600, 'end_ts': now - 25 * 3600 - 600},
        {'start_ts': now - 75 * 3600, 'end_ts': now - 74 * 3600},
      ];

  List<D1Row> _health(int now) {
    final wk = now ~/ 604800;
    return [
      for (var i = 7; i >= 0; i--)
        {'wk': wk - i, 'v': 51.6 - i * 0.04 + (i.isEven ? 0.05 : 0), 'n': 30 + i},
    ];
  }

  List<D1Row> _series(int since, int now) {
    final rows = <D1Row>[];
    final rand = Random(7);
    final end = _latestTs(now);
    var soc = 60.0;
    for (var t = since - since % 300; t <= end; t += 300) {
      // A two-hour hole a day ago shows the gap handling.
      if (t > end - 26 * 3600 && t < end - 24 * 3600) continue;
      final hour = ((t + 3600) % 86400) / 3600;
      final sun = hour > 6.5 && hour < 18.5 ? sin((hour - 6.5) / 12 * pi) : 0.0;
      final pv = sun * 3200 * (0.85 + rand.nextDouble() * 0.15);
      final load = 550 + 300 * sin(hour / 24 * 2 * pi + 1) + rand.nextDouble() * 120;
      soc = (soc + (pv - load) / 10240 * 100 / 12).clamp(20, 100);
      final grid = soc <= 21 ? load : 0.0;
      rows.add({'ts': t, 'pv_w': pv, 'load_w': load, 'grid_w': grid, 'soc': soc});
    }
    return rows;
  }
}
