import 'package:growatt_app/core/d1/d1_source.dart';
import 'package:growatt_app/core/inverter/models.dart';

class NowData {
  const NowData({required this.snapshot, required this.openOutage, required this.state});

  final Snapshot? snapshot;
  final Outage? openOutage;
  final WorkerState state;

  Map<String, Object?> toJson(D1Row? snapshotRow) => {
        'snapshot': snapshotRow,
        'outage_start': openOutage?.startTs,
        'state': state.values,
      };
}

/// Read-only access to the worker's D1 history. SELECTs only; the app never
/// talks to Growatt.
class InverterRepository {
  InverterRepository(this.db);
  final D1Source db;

  Future<(NowData, D1Row?)> now() async {
    final results = await Future.wait([
      db.query('SELECT * FROM snapshots ORDER BY ts DESC LIMIT 1'),
      db.query('SELECT start_ts, end_ts FROM outages WHERE end_ts IS NULL ORDER BY start_ts DESC LIMIT 1'),
      db.query('SELECT key, value FROM worker_state'),
    ]);
    final row = results[0].firstOrNull;
    return (
      NowData(
        snapshot: row == null ? null : Snapshot.fromRow(row),
        openOutage: results[1].map(Outage.fromRow).nonNulls.firstOrNull,
        state: WorkerState.fromRows(results[2]),
      ),
      row,
    );
  }

  static NowData? fromCache(Map<String, dynamic> json) {
    final snap = json['snapshot'];
    final start = json['outage_start'];
    final state = json['state'];
    return NowData(
      snapshot: snap is Map ? Snapshot.fromRow(Map<String, dynamic>.from(snap)) : null,
      openOutage: start is int ? Outage(start, null) : null,
      state: state is Map
          ? WorkerState({for (final e in state.entries) '${e.key}': '${e.value}'})
          : WorkerState.empty,
    );
  }

  Future<Snapshot?> latestSnapshot() async {
    final row = (await db.query('SELECT * FROM snapshots ORDER BY ts DESC LIMIT 1')).firstOrNull;
    return row == null ? null : Snapshot.fromRow(row);
  }

  Future<WorkerState> workerState() async =>
      WorkerState.fromRows(await db.query('SELECT key, value FROM worker_state'));

  Future<int?> latestSnapshotTs() async =>
      asInt((await db.query('SELECT MAX(ts) AS ts FROM snapshots')).firstOrNull?['ts']);

  Future<List<SeriesPoint>> series(int sinceTs) async {
    final rows = await db.query(
      'SELECT ts, pv_w, load_w, grid_w, soc FROM snapshots WHERE ts >= ? ORDER BY ts',
      [sinceTs],
    );
    return rows.map(SeriesPoint.fromRow).nonNulls.toList();
  }

  /// Mean battery voltage per week at 45–55 % SOC, a rough health trend.
  Future<List<WeeklyVoltage>> batteryHealth(int sinceTs) async {
    final rows = await db.query(
      'SELECT ts / 604800 AS wk, AVG(battery_v) AS v, COUNT(*) AS n FROM snapshots '
      'WHERE ts >= ? AND soc BETWEEN 45 AND 55 AND battery_v IS NOT NULL '
      'GROUP BY wk ORDER BY wk',
      [sinceTs],
    );
    final weeks = <WeeklyVoltage>[];
    for (final r in rows) {
      final wk = asInt(r['wk']);
      final v = asDouble(r['v']);
      if (wk == null || v == null) continue;
      weeks.add(WeeklyVoltage(weekStartTs: wk * 604800, volts: v, samples: asInt(r['n']) ?? 0));
    }
    return weeks;
  }

  Future<List<InverterEvent>> events({int limit = 100}) async {
    final rows = await db.query('SELECT ts, kind, detail FROM events ORDER BY ts DESC, id DESC LIMIT ?', [limit]);
    return rows.map(InverterEvent.fromRow).nonNulls.toList();
  }

  Future<List<Outage>> outages({int limit = 50}) async {
    final rows = await db.query('SELECT start_ts, end_ts FROM outages ORDER BY start_ts DESC LIMIT ?', [limit]);
    return rows.map(Outage.fromRow).nonNulls.toList();
  }
}
