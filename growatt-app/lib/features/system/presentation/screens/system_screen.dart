import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/core/providers.dart';
import 'package:growatt_app/features/system/presentation/providers/system_provider.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';
import 'package:growatt_app/shared/widgets/tab_page.dart';

class SystemScreen extends ConsumerWidget {
  const SystemScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = ref.watch(nowClockProvider)();
    final fake = ref.watch(usingFakeDataProvider);
    return AsyncTab<SystemData>(
      title: 'System',
      value: ref.watch(systemProvider),
      onRefresh: () => ref.refresh(systemProvider.future),
      builder: (data) {
        final s = data.state;
        final clock = data.clock;
        String when(int? ts) => ts == null ? na : formatDateTime(clock.at(ts));
        String? ago(int? ts) => ts == null ? null : formatAgo(now.difference(_date(ts)));
        final latestStale = data.latestTs != null && now.difference(_date(data.latestTs!)) > staleAfter;

        return [
          SectionCard(
            title: 'Worker',
            child: Column(children: [
              InfoRow(
                label: 'Uptime',
                value: s.startedTs == null ? na : formatDuration(now.difference(_date(s.startedTs!))),
                sub: s.startedTs == null ? null : 'since ${when(s.startedTs)}',
              ),
              InfoRow(label: 'Last Growatt OK', value: ago(s.lastOkTs) ?? na, sub: s.lastOkTs == null ? null : when(s.lastOkTs)),
              InfoRow(
                label: 'Last error',
                value: s.lastError ?? na,
                sub: s.lastErrorTs == null ? null : when(s.lastErrorTs),
                valueColor: s.lastError == null ? null : context.colors.error,
              ),
              InfoRow(label: 'Alerts', value: s.isMuted(now) ? 'Muted until ${when(s.mutedUntilTs)}' : 'On'),
            ]),
          ),
          SectionCard(
            title: 'Data',
            child: Column(children: [
              InfoRow(
                label: 'Latest snapshot',
                value: ago(data.latestTs) ?? na,
                sub: data.latestTs == null ? null : when(data.latestTs),
                valueColor: latestStale ? context.status.warning : null,
              ),
              InfoRow(label: 'Source', value: fake ? 'Sample data' : 'Cloudflare D1 (read-only)'),
              InfoRow(label: 'Time zone', value: clock.label),
            ]),
          ),
          SectionCard(
            title: 'Battery settings',
            child: InfoRow(label: 'Capacity', value: formatKwh(s.batteryCapacityKwh)),
          ),
        ];
      },
    );
  }

  static DateTime _date(int ts) => DateTime.fromMillisecondsSinceEpoch(ts * 1000);
}
