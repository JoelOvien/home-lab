import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:growatt_app/core/config/d1_config.dart';
import 'package:growatt_app/core/d1/d1_client.dart';
import 'package:growatt_app/core/d1/d1_source.dart';
import 'package:growatt_app/core/inverter/inverter_repository.dart';
import 'package:growatt_app/core/inverter/models.dart';

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
        {'key': 'battery_sign', 'value': 'charge_negative'},
      ]);
      expect(st.batteryCapacityKwh, 10.24);
      expect(st.startedTs, isNull);
      expect(st.batterySign, BatterySign.chargeNegative);
      expect(WorkerState.empty.batterySign, isNull);
    });

    test('battery direction needs a known sign', () {
      expect(batteryDirection(-400, null), isNull);
      expect(batteryDirection(-400, BatterySign.chargeNegative), BatteryDirection.charging);
      expect(batteryDirection(-400, BatterySign.chargePositive), BatteryDirection.discharging);
      expect(batteryDirection(3, BatterySign.chargePositive), BatteryDirection.idle);
      expect(batteryDirection(null, BatterySign.chargePositive), isNull);
    });

    test('status codes map to SPF names', () {
      expect(statusName(3), 'Fault');
      expect(statusName(8), 'PV + AC charging, grid bypass');
      expect(statusName(99), isNull);
      expect(statusName(null), isNull);
    });

    test('runtime needs SOC, capacity and a positive load', () {
      expect(runtimeHours(soc: 50, capacityKwh: 10, loadW: 1000), 5);
      expect(runtimeHours(soc: 50, capacityKwh: null, loadW: 1000), isNull);
      expect(runtimeHours(soc: 50, capacityKwh: 10, loadW: 0), isNull);
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
