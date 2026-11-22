import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:growatt_app/core/config/d1_config.dart';
import 'package:growatt_app/core/d1/d1_client.dart';
import 'package:growatt_app/core/d1/d1_source.dart';
import 'package:growatt_app/core/inverter/inverter_repository.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/shared/functions/formatters.dart';

Map<String, dynamic> ok(List<Map<String, dynamic>> rows) => {
      'success': true,
      'errors': [],
      'result': [
        {'results': rows, 'success': true, 'meta': {}},
      ],
    };

Map<String, dynamic> failure(String message) => {
      'success': false,
      'errors': [
        {'code': 7500, 'message': message},
      ],
      'result': null,
    };

class _Adapter implements HttpClientAdapter {
  _Adapter(this.status, this.body);
  final int status;
  final Object body;
  RequestOptions? last;

  @override
  Future<ResponseBody> fetch(RequestOptions options, Stream<Uint8List>? requestStream, Future<void>? cancelFuture) async {
    last = options;
    return ResponseBody.fromString(jsonEncode(body), status, headers: {
      Headers.contentTypeHeader: [Headers.jsonContentType],
    });
  }

  @override
  void close({bool force = false}) {}
}

class _MapSource implements D1Source {
  _MapSource(this.handler);
  final List<D1Row> Function(String sql) handler;

  @override
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]) async => handler(sql);
}

void main() {
  group('parseD1Response', () {
    test('returns rows on success', () {
      final rows = parseD1Response(ok([{'ts': 1, 'pv_w': 2}]), 200);
      expect(rows, [{'ts': 1, 'pv_w': 2}]);
    });

    test('success with no result is empty', () {
      expect(parseD1Response({'success': true, 'result': null}, 200), isEmpty);
    });

    test('missing table or column counts as empty', () {
      expect(parseD1Response(failure('no such table: worker_state: SQLITE_ERROR'), 400), isEmpty);
      expect(parseD1Response(failure('No such column: load_pct'), 400), isEmpty);
    });

    test('other API errors surface the first message', () {
      expect(
        () => parseD1Response(failure('Authentication error'), 403),
        throwsA(isA<D1Exception>().having((e) => e.message, 'message', 'Authentication error')),
      );
    });

    test('falls back to the HTTP status without a message', () {
      expect(
        () => parseD1Response('<html>bad gateway</html>', 502),
        throwsA(isA<D1Exception>().having((e) => e.message, 'message', 'D1 returned HTTP 502')),
      );
    });
  });

  group('D1Client', () {
    const config = D1Config(accountId: 'acct', databaseId: 'db', apiToken: 'tok');

    test('posts sql and params with the bearer token', () async {
      final adapter = _Adapter(200, ok([{'key': 'tz', 'value': 'UTC'}]));
      final client = D1Client(config, dio: Dio()..httpClientAdapter = adapter);
      final rows = await client.query('SELECT key, value FROM worker_state WHERE key = ?', ['tz']);
      expect(rows.single['value'], 'UTC');
      expect(adapter.last!.uri.toString(),
          'https://api.cloudflare.com/client/v4/accounts/acct/d1/database/db/query');
      expect(adapter.last!.headers['Authorization'], 'Bearer tok');
      expect(adapter.last!.data, {'sql': 'SELECT key, value FROM worker_state WHERE key = ?', 'params': ['tz']});
    });

    test('reads the error body of a 4xx instead of throwing a Dio error', () async {
      final client = D1Client(config, dio: Dio()..httpClientAdapter = _Adapter(400, failure('no such table: events')));
      expect(await client.query('SELECT ts, kind, detail FROM events'), isEmpty);

      final bad = D1Client(config, dio: Dio()..httpClientAdapter = _Adapter(401, failure('Invalid token')));
      expect(bad.query('SELECT 1'), throwsA(isA<D1Exception>()));
    });
  });

  group('models', () {
    test('old-schema snapshot leaves new columns null and coerces ints', () {
      final s = Snapshot.fromRow({
        'ts': 1700000000, 'pv_w': 1200, 'load_w': 820.5, 'grid_w': null,
        'battery_w': -300, 'soc': 76, 'battery_v': 52.8, 'grid_v': 231, 'grid_present': 1,
      })!;
      expect(s.pvW, 1200.0);
      expect(s.gridW, isNull);
      expect(s.gridPresent, isTrue);
      expect(s.loadPct, isNull);
      expect(s.invStatus, isNull);
      expect(s.dtc, isNull);
      expect(s.energy.isEmpty, isTrue);
    });

    test('energy counters are read and stay null when missing', () {
      final s = Snapshot.fromRow({
        'ts': 1,
        'pv_today_kwh': 3.6, 'pv_total_kwh': '3.7',
        'discharge_today_kwh': 1.4, 'discharge_total_kwh': 7,
        'charge_today_kwh': 3.7, 'charge_total_kwh': 65.5,
        'import_today_kwh': 4.7, 'import_total_kwh': 131.2,
        'load_today_kwh': null, 'load_total_kwh': 73.8,
      })!;
      final e = s.energy;
      expect(e.isEmpty, isFalse);
      expect((e.pv.today, e.pv.total), (3.6, 3.7));
      expect((e.discharge.today, e.discharge.total), (1.4, 7.0));
      expect((e.charge.today, e.charge.total), (3.7, 65.5));
      expect((e.import.today, e.import.total), (4.7, 131.2));
      expect(e.load.today, isNull);
      expect(e.load.total, 73.8);

      final allNull = Snapshot.fromRow({'ts': 1, 'pv_today_kwh': null, 'load_total_kwh': null})!;
      expect(allNull.energy.isEmpty, isTrue);
    });

    test('new snapshot columns are read', () {
      final s = Snapshot.fromRow({'ts': 1, 'load_pct': 14.8, 'inv_status': -10, 'status': 8, 'dtc': 20006})!;
      expect(s.loadPct, 14.8);
      expect(s.invStatus, -10);
      expect(s.status, 8);
      expect(s.dtc, 20006);
      expect(s.gridPresent, isNull);
    });

    test('worker_state values are parsed from text', () {
      final st = WorkerState.fromRows([
        {'key': 'battery_capacity_kwh', 'value': '10.24'},
        {'key': 'started_ts', 'value': 'garbage'},
      ]);
      expect(st.batteryCapacityKwh, 10.24);
      expect(st.startedTs, isNull);
    });

    test('battery direction comes from the status code, not the batPower sign', () {
      Snapshot snap(int? status, double? w) => Snapshot(ts: 0, status: status, batteryW: w);

      final discharging = BatteryFlow.of(snap(2, 318));
      expect(discharging.direction, BatteryDirection.discharging);
      expect(discharging.dischargeW, 318);
      expect(discharging.chargeW, 0);
      expect(formatBatteryFlow(discharging), 'Discharging 318 W');

      final charging = BatteryFlow.of(snap(10, 120));
      expect(charging.direction, BatteryDirection.charging);
      expect(charging.chargeW, 120);
      expect(charging.dischargeW, 0);
      expect(formatBatteryFlow(charging), 'Charging 120 W');

      for (final code in [5, 6, 7, 8, 9, 10]) {
        expect(batteryDirection(code), BatteryDirection.charging);
      }
      for (final code in [0, 1, 3, 4, 11, 12, 99]) {
        expect(batteryDirection(code), isNull);
      }
      expect(BatteryFlow.of(snap(2, -318)).dischargeW, 318);

      final unknown = BatteryFlow.of(snap(null, 318));
      expect(unknown.direction, isNull);
      expect(unknown.chargeW, isNull);
      expect(unknown.dischargeW, isNull);
      expect(formatBatteryFlow(unknown), isNull);
      expect(BatteryFlow.of(null).direction, isNull);
    });

    test('status codes map to SPF names', () {
      expect(statusName(3), 'Fault');
      expect(statusName(8), 'PV + AC charging, grid bypass');
      expect(statusName(99), isNull);
      expect(statusName(null), isNull);
    });

    test('runtime needs SOC, capacity, a positive load and a battery that is not charging', () {
      const d = BatteryDirection.discharging;
      expect(runtimeHours(soc: 50, capacityKwh: 10, loadW: 1000, direction: d), 5);
      expect(runtimeHours(soc: 50, capacityKwh: 10, loadW: 1000, direction: BatteryDirection.charging), isNull);
      expect(runtimeHours(soc: 50, capacityKwh: 10, loadW: 1000), isNull);
      expect(runtimeHours(soc: 50, capacityKwh: null, loadW: 1000, direction: d), isNull);
      expect(runtimeHours(soc: 50, capacityKwh: 10, loadW: 0, direction: d), isNull);
    });
  });

  test('repository tolerates the old schema', () async {
    final repo = InverterRepository(_MapSource((sql) {
      if (sql.contains('FROM snapshots')) return [{'ts': 100, 'soc': 50}];
      return [];
    }));
    final (now, row) = await repo.now();
    expect(now.snapshot!.soc, 50);
    expect(now.state.values, isEmpty);
    expect(now.openOutage, isNull);
    expect(await repo.events(), isEmpty);

    final cached = InverterRepository.fromCache(jsonDecode(jsonEncode(now.toJson(row))) as Map<String, dynamic>)!;
    expect(cached.snapshot!.ts, 100);
  });
}
