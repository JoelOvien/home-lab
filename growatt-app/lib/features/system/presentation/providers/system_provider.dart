import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/clock.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/core/providers.dart';

class SystemData {
  const SystemData({required this.clock, required this.state, required this.latestTs});
  final ZoneClock clock;
  final WorkerState state;
  final int? latestTs;
}

final systemProvider = FutureProvider<SystemData>((ref) async {
  final repo = ref.watch(repositoryProvider);
  final (state, latest) = await (repo.workerState(), repo.latestSnapshotTs()).wait;
  return SystemData(clock: ZoneClock.named(state.tz), state: state, latestTs: latest);
});
