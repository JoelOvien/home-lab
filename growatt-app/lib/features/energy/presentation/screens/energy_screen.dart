import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/features/energy/presentation/widgets/energy_section.dart';
import 'package:growatt_app/features/now/presentation/providers/now_notifier.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';
import 'package:growatt_app/shared/widgets/tab_page.dart';

/// Growatt's own kWh counters, from the same auto-refreshing data as Now.
class EnergyScreen extends ConsumerWidget {
  const EnergyScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return AsyncTab<NowView>(
      title: 'Energy',
      value: ref.watch(nowProvider),
      onRefresh: () => ref.read(nowProvider.notifier).refresh(),
      builder: (view) {
        final energy = view.data.snapshot?.energy;
        return [
          if (energy == null || energy.isEmpty)
            const InfoRow(label: 'Energy counters', value: 'Not recorded yet')
          else
            EnergySection(counters: energy),
        ];
      },
    );
  }
}
