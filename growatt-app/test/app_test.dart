import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:growatt_app/app/app.dart';
import 'dart:convert';

import 'package:growatt_app/core/d1/d1_source.dart';
import 'package:growatt_app/core/d1/fake_d1_source.dart';
import 'package:growatt_app/core/providers.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest.dart' as tzdata;

Future<void> pumpApp(WidgetTester tester, List overrides, {Map<String, Object> prefs = const {}}) async {
  SharedPreferences.setMockInitialValues(prefs);
  final store = await SharedPreferences.getInstance();
  await tester.pumpWidget(ProviderScope(
    retry: (_, _) => null,
    overrides: [
      sharedPreferencesProvider.overrideWithValue(store),
      autoRefreshProvider.overrideWithValue(null),
      ...overrides.cast(),
    ],
    child: const GrowattApp(),
  ));
  await tester.pumpAndSettle();
}

Finder navTab(String label) =>
    find.descendant(of: find.byType(NavigationBar), matching: find.text(label));

class _FailingSource implements D1Source {
  @override
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]) async =>
      throw const D1Exception('Authentication error');
}

class _DischargingSource implements D1Source {
  final _fake = FakeD1Source();

  @override
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]) async {
    final rows = await _fake.query(sql, params);
    if (!sql.startsWith('SELECT * FROM snapshots')) return rows;
    return [
      for (final r in rows) {...r, 'status': 2, 'battery_w': 318.0, 'pv_w': 0.0, 'load_w': 240.0, 'soc': 100.0},
    ];
  }
}

void main() {
  setUpAll(tzdata.initializeTimeZones);

  testWidgets('shows not configured without credentials', (tester) async {
    await pumpApp(tester, [isConfiguredProvider.overrideWithValue(false)]);
    expect(find.text('Not configured'), findsOneWidget);
  });

  testWidgets('Now tab renders fake data with direction and mute banner', (tester) async {
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source()),
    ]);
    expect(find.text('Grid on'), findsOneWidget);
    expect(find.text('1.24 kW'), findsWidgets);
    expect(find.textContaining('Charging 420 W'), findsWidgets);
    expect(find.textContaining('Alerts muted until'), findsOneWidget);
  });

  testWidgets('status 2 with a positive batPower reads as discharging', (tester) async {
    tester.view.physicalSize = const Size(1200, 4000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(_DischargingSource()),
    ]);
    expect(find.textContaining('Discharging 318 W'), findsWidgets);
    expect(find.textContaining('Battery discharging 318 W'), findsOneWidget);
    expect(find.textContaining(RegExp(r'^Charging \d')), findsNothing);
    expect(find.text('0 W'), findsWidgets);
    expect(find.text('20h 50m'), findsOneWidget);
  });

  testWidgets('old schema hides direction and shows the outage', (tester) async {
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source(oldSchema: true)),
    ]);
    expect(find.text('Grid down'), findsOneWidget);
    expect(find.textContaining('Outage for 2h'), findsOneWidget);
    expect(find.textContaining('charging'), findsNothing);
    expect(find.text('Inverter'.toUpperCase()), findsNothing);
    expect(find.textContaining('BATTERY_CAPACITY_KWH'), findsOneWidget);
  });

  testWidgets('Energy tab shows Growatt energy counters', (tester) async {
    tester.view.physicalSize = const Size(1200, 5000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source()),
    ]);
    expect(find.text('Photovoltaic output'), findsNothing);
    expect(find.text('Energy today'), findsOneWidget);
    expect(find.text('6.10 kWh'), findsOneWidget);
    expect(find.text('3.60 kWh'), findsOneWidget);
    expect(find.text('4.70 kWh'), findsOneWidget);
    await tester.tap(navTab('Energy'));
    await tester.pumpAndSettle();
    expect(find.text('Today and total'), findsOneWidget);
    expect(find.text('Photovoltaic output'), findsOneWidget);
    expect(find.text('6.1 kWh'), findsOneWidget);
    expect(find.text('Total 131.2 kWh'), findsOneWidget);
    expect(find.text('Total 7.0 kWh'), findsOneWidget);
  });

  testWidgets('Energy tab says so when every counter is null', (tester) async {
    tester.view.physicalSize = const Size(1200, 5000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source(oldSchema: true)),
    ]);
    expect(find.text('Energy today'), findsNothing);
    await tester.tap(navTab('Energy'));
    await tester.pumpAndSettle();
    expect(find.text('Not recorded yet'), findsOneWidget);
    expect(find.text('Photovoltaic output'), findsNothing);
  });

  testWidgets('Charts uses the exact counter for today', (tester) async {
    tester.view.physicalSize = const Size(1200, 5000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source()),
    ]);
    await tester.tap(navTab('Charts'));
    await tester.pumpAndSettle();
    expect(find.text('6.1'), findsOneWidget);
    expect(find.text('3.6'), findsOneWidget);
    expect(find.text('4.7'), findsOneWidget);
    expect(find.textContaining("Today is Growatt's own counter"), findsOneWidget);
  });

  testWidgets('every tab builds', (tester) async {
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source()),
    ]);
    for (final label in ['Energy', 'Charts', 'Activity', 'System']) {
      await tester.tap(navTab(label));
      await tester.pumpAndSettle();
    }
    expect(find.text('Uptime'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('failed refresh falls back to the cached status', (tester) async {
    final cache = jsonEncode({
      'snapshot': {'ts': 1700000000, 'soc': 64, 'pv_w': 300, 'grid_present': 1, 'grid_v': 229},
      'outage_start': null,
      'state': <String, String>{},
    });
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(_FailingSource()),
    ], prefs: {'now_cache_v1': cache});
    expect(find.textContaining('Refresh failed, showing saved data'), findsOneWidget);
    expect(find.textContaining('Authentication error'), findsOneWidget);
    expect(find.text('64%'), findsOneWidget);
    expect(find.textContaining('Stale'), findsOneWidget);
  });

  testWidgets('failure without a cache shows the error view', (tester) async {
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(_FailingSource()),
    ]);
    expect(find.text('Something went wrong'), findsOneWidget);
    expect(find.text('Authentication error'), findsOneWidget);
  });
}
