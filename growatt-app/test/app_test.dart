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

class _FailingSource implements D1Source {
  @override
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]) async =>
      throw const D1Exception('Authentication error');
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
    expect(find.textContaining('charging 420 W'), findsWidgets);
    expect(find.textContaining('Alerts muted until'), findsOneWidget);
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

  testWidgets('every tab builds', (tester) async {
    await pumpApp(tester, [
      isConfiguredProvider.overrideWithValue(true),
      d1SourceProvider.overrideWithValue(FakeD1Source()),
    ]);
    for (final icon in [Icons.show_chart, Icons.history, Icons.dns_outlined]) {
      await tester.tap(find.byIcon(icon));
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
