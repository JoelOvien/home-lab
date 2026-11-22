import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:growatt_app/core/config/d1_config.dart';
import 'package:growatt_app/core/d1/d1_client.dart';
import 'package:growatt_app/core/d1/d1_source.dart';
import 'package:growatt_app/core/d1/fake_d1_source.dart';
import 'package:growatt_app/core/inverter/inverter_repository.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:home_widget/home_widget.dart';
import 'package:workmanager/workmanager.dart';

const _androidProvider = 'com.homelab.growatt_app.StatusWidgetProvider';
const _refreshTask = 'widget-refresh';

class WidgetTile {
  const WidgetTile(this.value, [this.detail = '']);
  final String value, detail;
}

class WidgetLines {
  const WidgetLines({required this.pv, required this.load, required this.battery, required this.grid, this.gridOn});
  final WidgetTile pv, load, battery, grid;
  final bool? gridOn;
}

String _today(double? kwh) => kwh == null ? '' : '${formatKwh(kwh)} today';

WidgetLines widgetLines(Snapshot? s) {
  final direction = switch (batteryDirection(s?.status)) {
    BatteryDirection.charging => 'Charging',
    BatteryDirection.discharging => 'Discharging',
    null => null,
  };
  return WidgetLines(
    pv: WidgetTile(formatWatts(s?.pvW), _today(s?.energy.pv.today)),
    load: WidgetTile(formatWatts(s?.loadW), _today(s?.energy.load.today)),
    battery: WidgetTile(
      formatPercent(s?.soc),
      [formatVolts(s?.batteryV), if (direction != null) direction].join(' · '),
    ),
    grid: WidgetTile(
      switch (s?.gridPresent) {
        true => 'On',
        false => 'Off',
        null => na,
      },
      formatVolts(s?.gridV),
    ),
    gridOn: s?.gridPresent,
  );
}

bool get _supported => !kIsWeb && Platform.isAndroid;

/// Hands the latest snapshot to the Android home screen widget. Failures are
/// swallowed: the widget is a convenience and must never break the app.
Future<void> pushToHomeWidget(Snapshot? s) async {
  if (!_supported) return;
  try {
    final lines = widgetLines(s);
    final tiles = {'pv': lines.pv, 'load': lines.load, 'battery': lines.battery, 'grid': lines.grid};
    await Future.wait([
      for (final MapEntry(:key, :value) in tiles.entries) ...[
        HomeWidget.saveWidgetData(key, value.value),
        HomeWidget.saveWidgetData('${key}_detail', value.detail),
      ],
      HomeWidget.saveWidgetData('grid_on', lines.gridOn),
      HomeWidget.saveWidgetData('ts', s == null ? null : '${s.ts}'),
    ]);
    await HomeWidget.updateWidget(qualifiedAndroidName: _androidProvider);
  } catch (e) {
    debugPrint('Home widget update failed: $e');
  }
}

D1Source _backgroundSource() => fakeDataMode.isNotEmpty
    ? FakeD1Source(oldSchema: fakeDataMode == 'old_schema')
    : D1Client(D1Config.fromEnvironment);

@pragma('vm:entry-point')
void widgetRefreshDispatcher() {
  Workmanager().executeTask((_, _) async {
    try {
      final snapshot = await InverterRepository(_backgroundSource()).latestSnapshot();
      await pushToHomeWidget(snapshot);
      return true;
    } catch (e) {
      debugPrint('Background widget refresh failed: $e');
      // Keep the last good data on the widget; WorkManager retries next period.
      return true;
    }
  });
}

/// Refreshes the widget every 15 minutes (Android's minimum) while the app is
/// closed, reading D1 only, like the rest of the app.
Future<void> setupHomeWidgetRefresh() async {
  if (!_supported) return;
  try {
    await Workmanager().initialize(widgetRefreshDispatcher);
    await Workmanager().registerPeriodicTask(
      _refreshTask,
      _refreshTask,
      frequency: const Duration(minutes: 15),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingPeriodicWorkPolicy.update,
    );
  } catch (e) {
    debugPrint('Home widget refresh setup failed: $e');
  }
}
