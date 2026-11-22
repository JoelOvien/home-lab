import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/providers.dart';
import 'package:growatt_app/features/activity/presentation/providers/activity_provider.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';
import 'package:growatt_app/shared/widgets/tab_page.dart';

const _eventInfo = <String, (IconData, String)>{
  'grid_down': (Icons.power_off, 'Grid down'),
  'grid_up': (Icons.power, 'Grid back'),
  'battery_low': (Icons.battery_alert, 'Battery low'),
  'battery_full': (Icons.battery_full, 'Battery full'),
  'overload': (Icons.warning_amber_rounded, 'Overload'),
  'fault': (Icons.error_outline, 'Inverter fault'),
  'solar_stopped': (Icons.wb_cloudy_outlined, 'Solar stopped'),
  'unreachable': (Icons.cloud_off, 'Growatt unreachable'),
};

class ActivityScreen extends ConsumerWidget {
  const ActivityScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = ref.watch(nowClockProvider)();
    return AsyncTab<ActivityData>(
      title: 'Activity',
      value: ref.watch(activityProvider),
      onRefresh: () => ref.refresh(activityProvider.future),
      builder: (data) {
        final typo = context.typography;
        final colors = context.colors;
        return [
          SectionCard(
            title: 'Events',
            child: data.events.isEmpty
                ? Text('No events recorded yet.', style: typo.caption)
                : Column(children: [
                    for (final e in data.events)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        dense: true,
                        leading: Icon(_eventInfo[e.kind]?.$1 ?? Icons.info_outline, color: _eventColor(context, e.kind)),
                        title: Text(_eventInfo[e.kind]?.$2 ?? e.kind, style: typo.bodyMd.copyWith(fontWeight: FontWeight.w600)),
                        subtitle: e.detail == null ? null : Text(e.detail!, style: typo.caption),
                        trailing: Text(formatDateTime(data.clock.at(e.ts)), style: typo.caption),
                      ),
                  ]),
          ),
          SectionCard(
            title: 'Outages',
            child: data.outages.isEmpty
                ? Text('No outages recorded.', style: typo.caption)
                : Column(children: [
                    for (final o in data.outages)
                      InfoRow(
                        label: formatDateTime(data.clock.at(o.startTs)),
                        value: o.endTs == null ? 'Ongoing, ${formatDuration(o.duration(now))}' : formatDuration(o.duration(now)),
                        valueColor: o.endTs == null ? colors.error : null,
                        sub: o.endTs == null ? null : 'until ${formatClock(data.clock.at(o.endTs!))}',
                      ),
                  ]),
          ),
        ];
      },
    );
  }

  Color _eventColor(BuildContext context, String kind) {
    final c = context.colors;
    final s = context.status;
    return switch (kind) {
      'grid_up' || 'battery_full' => s.success,
      'grid_down' || 'fault' || 'unreachable' => c.error,
      'battery_low' || 'overload' || 'solar_stopped' => s.warning,
      _ => c.tertiary,
    };
  }
}
