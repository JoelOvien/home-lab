import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/clock.dart';
import 'package:growatt_app/core/inverter/inverter_repository.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/core/providers.dart';
import 'package:growatt_app/features/now/presentation/providers/now_notifier.dart';
import 'package:growatt_app/features/now/presentation/widgets/energy_section.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';
import 'package:growatt_app/shared/widgets/tab_page.dart';

class NowScreen extends ConsumerWidget {
  const NowScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = ref.watch(nowClockProvider)();
    return AsyncTab<NowView>(
      title: 'Now',
      value: ref.watch(nowProvider),
      onRefresh: () => ref.read(nowProvider.notifier).refresh(),
      builder: (view) => _content(context, view, now),
    );
  }

  List<Widget> _content(BuildContext context, NowView view, DateTime now) {
    final colors = context.colors;
    final NowData(:snapshot, :openOutage, :state) = view.data;
    final clock = ZoneClock.named(state.tz);
    final s = snapshot;
    final flow = BatteryFlow.of(s);

    return [
      if (s == null)
        const InfoRow(label: 'Latest data', value: 'No snapshots recorded yet')
      else
        _UpdatedLine(snapshot: s, now: now),
      if (view.error != null)
        StatusBanner(
          icon: Icons.cloud_off,
          text: 'Refresh failed, showing saved data. ${view.error}',
          color: colors.error,
          background: colors.errorBackground,
        ),
      if (state.isMuted(now))
        StatusBanner(
          icon: Icons.notifications_off_outlined,
          text: 'Alerts muted until ${formatClock(clock.at(state.mutedUntilTs!))}',
          color: colors.warning,
          background: colors.primaryMuted,
        ),
      _GridCard(snapshot: s, outage: openOutage, now: now),
      _MetricGrid(snapshot: s, flow: flow),
      SectionCard(title: 'Flow', child: Text(_flowLine(s, flow), style: context.typography.bodyMd)),
      SectionCard(
        title: 'Battery',
        child: Column(children: [
          InfoRow(label: 'Charge power', value: formatWatts(flow.chargeW)),
          InfoRow(label: 'Discharge power', value: formatWatts(flow.dischargeW)),
          InfoRow(
            label: 'Runtime at current load',
            value: flow.direction == BatteryDirection.charging
                ? 'Charging'
                : formatHours(runtimeHours(
                    soc: s?.soc,
                    capacityKwh: state.batteryCapacityKwh,
                    loadW: s?.loadW,
                    direction: flow.direction,
                  )),
            sub: state.batteryCapacityKwh == null ? 'Set BATTERY_CAPACITY_KWH on the worker' : null,
          ),
        ]),
      ),
      if (s != null && !s.energy.isEmpty) EnergySection(counters: s.energy),
      if (s != null && (s.invStatus != null || s.status != null || s.dtc != null))
        SectionCard(
          title: 'Inverter',
          child: Column(children: [
            InfoRow(
              label: 'Status',
              value: switch ((s.status, statusName(s.status))) {
                (null, _) => na,
                (final code?, null) => 'Code $code',
                (final code?, final name?) => '$name ($code)',
              },
              valueColor: s.status == 3 ? colors.error : null,
            ),
            InfoRow(label: 'invStatus', value: s.invStatus?.toString() ?? na),
            InfoRow(label: 'dtc', value: s.dtc?.toString() ?? na),
          ]),
        ),
    ];
  }
}

String _flowLine(Snapshot? s, BatteryFlow flow) {
  final parts = [
    'Solar ${formatWatts(s?.pvW)}',
    'Load ${formatWatts(s?.loadW)}',
    'Grid ${formatWatts(s?.gridW)}',
  ];
  final battery = formatBatteryFlow(flow);
  if (battery != null) parts.add('Battery ${battery[0].toLowerCase()}${battery.substring(1)}');
  return parts.join('  ·  ');
}

class _UpdatedLine extends StatelessWidget {
  const _UpdatedLine({required this.snapshot, required this.now});
  final Snapshot snapshot;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final stale = snapshot.isStale(now);
    final age = now.difference(DateTime.fromMillisecondsSinceEpoch(snapshot.ts * 1000));
    final color = stale ? context.colors.warning : context.colors.contentSecondary;
    return Row(children: [
      Icon(stale ? Icons.warning_amber_rounded : Icons.schedule, size: 16, color: color),
      const SizedBox(width: 6),
      Text(
        stale ? 'Stale: updated ${formatAgo(age)}' : 'Updated ${formatAgo(age)}',
        style: context.typography.bodySm.copyWith(color: color, fontWeight: stale ? FontWeight.w600 : null),
      ),
    ]);
  }
}

class _GridCard extends StatelessWidget {
  const _GridCard({required this.snapshot, required this.outage, required this.now});
  final Snapshot? snapshot;
  final Outage? outage;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final present = snapshot?.gridPresent;
    final (icon, title, color, bg) = switch (present) {
      true => (Icons.power, 'Grid on', colors.success, colors.successBackground),
      false => (Icons.power_off, 'Grid down', colors.error, colors.errorBackground),
      null => (Icons.help_outline, 'Grid $na', colors.contentSecondary, colors.surfaceMuted),
    };
    final sub = switch (present) {
      true => formatVolts(snapshot?.gridV),
      false when outage != null => 'Outage for ${formatDuration(outage!.duration(now))}',
      _ => null,
    };
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(16)),
      child: Row(children: [
        Icon(icon, size: 32, color: color),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: context.typography.headingLg.copyWith(color: color)),
            if (sub != null) Text(sub, style: context.typography.bodyMd),
          ]),
        ),
      ]),
    );
  }
}

class _MetricGrid extends StatelessWidget {
  const _MetricGrid({required this.snapshot, required this.flow});
  final Snapshot? snapshot;
  final BatteryFlow flow;

  @override
  Widget build(BuildContext context) {
    final s = snapshot;
    final battery = formatBatteryFlow(flow);
    final tiles = [
      MetricTile(icon: Icons.wb_sunny_outlined, label: 'SOLAR', value: formatWatts(s?.pvW)),
      MetricTile(
        icon: Icons.bolt,
        label: 'LOAD',
        value: formatWatts(s?.loadW),
        sub: s?.loadPct == null ? null : '${formatPercent(s!.loadPct)} of rated',
      ),
      MetricTile(
        icon: Icons.battery_charging_full,
        label: 'BATTERY',
        value: formatPercent(s?.soc),
        sub: [formatVolts(s?.batteryV), if (battery != null) battery].join(' · '),
      ),
      MetricTile(
        icon: Icons.electrical_services,
        label: 'GRID',
        value: formatVolts(s?.gridV),
        sub: s?.gridW == null ? null : formatWatts(s!.gridW),
      ),
    ];
    return Column(children: [
      Row(children: [Expanded(child: tiles[0]), const SizedBox(width: 12), Expanded(child: tiles[1])]),
      const SizedBox(height: 12),
      Row(children: [Expanded(child: tiles[2]), const SizedBox(width: 12), Expanded(child: tiles[3])]),
    ]);
  }
}
