import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/clock.dart';
import 'package:growatt_app/core/inverter/energy.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/core/providers.dart';

class ChartsData {
  const ChartsData({
    required this.clock,
    required this.nowTs,
    required this.startOfToday,
    required this.points,
    required this.today,
    required this.week,
    required this.month,
    required this.health,
    this.exactToday = EnergyCounters.empty,
  });

  final ZoneClock clock;
  final int nowTs;
  final int startOfToday;
  final List<SeriesPoint> points;
  final EnergySplit today, week, month;
  final List<WeeklyVoltage> health;

  /// Growatt's own counters for today, when the latest snapshot is from today.
  final EnergyCounters exactToday;

  List<SeriesPoint> since(int ts) => points.where((p) => p.ts >= ts).toList();
}

final chartsProvider = FutureProvider<ChartsData>((ref) async {
  final repo = ref.watch(repositoryProvider);
  final now = ref.watch(nowClockProvider)();
  final nowTs = now.millisecondsSinceEpoch ~/ 1000;
  final state = await repo.workerState();
  final clock = ZoneClock.named(state.tz);
  final startOfToday = clock.startOfDay(now);
  const day = 86400;

  final (points, health, latest) = await (
    repo.series(nowTs - 30 * day),
    repo.batteryHealth(nowTs - 8 * 7 * day),
    repo.latestSnapshot(),
  ).wait;

  List<SeriesPoint> since(int ts) => points.where((p) => p.ts >= ts).toList();
  return ChartsData(
    clock: clock,
    nowTs: nowTs,
    startOfToday: startOfToday,
    points: points,
    today: EnergySplit.of(since(startOfToday), Duration(seconds: nowTs - startOfToday)),
    week: EnergySplit.of(since(nowTs - 7 * day), const Duration(days: 7)),
    month: EnergySplit.of(points, const Duration(days: 30)),
    health: health,
    exactToday: latest != null && latest.ts >= startOfToday ? latest.energy : EnergyCounters.empty,
  );
});
