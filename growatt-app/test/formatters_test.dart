import 'package:flutter_test/flutter_test.dart';
import 'package:growatt_app/core/inverter/clock.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:timezone/data/latest.dart' as tzdata;

void main() {
  setUpAll(tzdata.initializeTimeZones);

  test('nulls render as n/a, never 0', () {
    expect(formatWatts(null), 'n/a');
    expect(formatPercent(null), 'n/a');
    expect(formatVolts(null), 'n/a');
    expect(formatKwh(null), 'n/a');
    expect(formatHours(null), 'n/a');
  });

  test('watts switch to kW at 1000', () {
    expect(formatWatts(0), '0 W');
    expect(formatWatts(820.4), '820 W');
    expect(formatWatts(1240), '1.24 kW');
    expect(formatWatts(-1500), '-1.50 kW');
  });

  test('values', () {
    expect(formatPercent(75.6), '76%');
    expect(formatVolts(52.84), '52.8 V');
    expect(formatKwh(3.456), '3.46 kWh');
  });

  test('durations', () {
    expect(formatDuration(const Duration(seconds: 30)), '<1m');
    expect(formatDuration(const Duration(minutes: 7)), '7m');
    expect(formatDuration(const Duration(hours: 2, minutes: 5)), '2h 5m');
    expect(formatDuration(const Duration(days: 3, hours: 4, minutes: 9)), '3d 4h');
    expect(formatDuration(const Duration(minutes: -5)), '<1m');
    expect(formatHours(12.5), '12h 30m');
  });

  test('ago', () {
    expect(formatAgo(const Duration(seconds: 20)), 'just now');
    expect(formatAgo(const Duration(minutes: 5)), '5 min ago');
    expect(formatAgo(const Duration(hours: 1, minutes: 3)), '1h 3m ago');
  });

  test('clock uses the worker zone and falls back when unknown', () {
    final berlin = ZoneClock.named('Europe/Berlin');
    // 2026-01-15 12:00 UTC is 13:00 in Berlin.
    expect(formatClock(berlin.at(1768478400)), '13:00');
    expect(berlin.startOfDay(DateTime.utc(2026, 1, 15, 23, 30)), DateTime.utc(2026, 1, 15, 23).millisecondsSinceEpoch ~/ 1000);
    expect(ZoneClock.named('Not/AZone').location, isNull);
    expect(ZoneClock.named(null).label, 'phone time');
  });
}
