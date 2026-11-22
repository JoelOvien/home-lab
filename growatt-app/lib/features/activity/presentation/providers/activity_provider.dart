import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/clock.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/core/providers.dart';

class ActivityData {
  const ActivityData({required this.clock, required this.events, required this.outages});
  final ZoneClock clock;
  final List<InverterEvent> events;
  final List<Outage> outages;
}

final activityProvider = FutureProvider<ActivityData>((ref) async {
  final repo = ref.watch(repositoryProvider);
  final (state, events, outages) = await (repo.workerState(), repo.events(), repo.outages()).wait;
  return ActivityData(clock: ZoneClock.named(state.tz), events: events, outages: outages);
});
