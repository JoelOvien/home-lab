import 'package:flutter/material.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/theme/tokens/colors.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';

String formatKwh1(double? kwh) => kwh == null ? na : '${kwh.toStringAsFixed(1)} kWh';

class EnergySection extends StatelessWidget {
  const EnergySection({super.key, required this.counters});
  final EnergyCounters counters;

  @override
  Widget build(BuildContext context) {
    final c = counters;
    final tiles = [
      _EnergyTile(icon: Icons.wb_sunny_outlined, color: AppColors.energyPv, label: 'Photovoltaic output', value: c.pv),
      _EnergyTile(icon: Icons.battery_alert_outlined, color: AppColors.energyDischarge, label: 'Discharging', value: c.discharge),
      _EnergyTile(icon: Icons.battery_charging_full, color: AppColors.energyCharge, label: 'Charging', value: c.charge),
      _EnergyTile(icon: Icons.electrical_services, color: AppColors.energyImport, label: 'Imported from grid', value: c.import),
      _EnergyTile(icon: Icons.home_outlined, color: AppColors.energyLoad, label: 'Load consumption', value: c.load),
    ];
    return SectionCard(
      title: 'Today and total',
      child: Column(children: [
        for (var i = 0; i < tiles.length; i += 2) ...[
          if (i > 0) const SizedBox(height: 10),
          IntrinsicHeight(
            child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Expanded(child: tiles[i]),
              const SizedBox(width: 10),
              Expanded(child: i + 1 < tiles.length ? tiles[i + 1] : const SizedBox()),
            ]),
          ),
        ],
      ]),
    );
  }
}

class _EnergyTile extends StatelessWidget {
  const _EnergyTile({required this.icon, required this.color, required this.label, required this.value});
  final IconData icon;
  final Color color;
  final String label;
  final TodayTotal value;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final typo = context.typography;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: colors.surfaceContainerLow, borderRadius: BorderRadius.circular(12)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(color: color.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(8)),
            child: Icon(icon, size: 18, color: color),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(label, style: typo.bodySm.copyWith(color: colors.onSurfaceVariant))),
        ]),
        const SizedBox(height: 10),
        Text(formatKwh1(value.today), style: typo.headingMd.copyWith(color: color)),
        Text('Today', style: typo.caption),
        const SizedBox(height: 6),
        Text('Total ${formatKwh1(value.total)}', style: typo.bodySm.copyWith(fontWeight: FontWeight.w600)),
      ]),
    );
  }
}
