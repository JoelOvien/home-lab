import 'package:flutter/material.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/widgets/cards/app_card.dart';

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.title, required this.child, this.trailing});

  final String title;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(title, style: context.typography.headingSm.copyWith(color: context.colors.primary))),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }
}

class InfoRow extends StatelessWidget {
  const InfoRow({super.key, required this.label, required this.value, this.valueColor, this.sub});

  final String label;
  final String value;
  final String? sub;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final typo = context.typography;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label, style: typo.bodyMd.copyWith(color: context.colors.onSurfaceVariant))),
          const SizedBox(width: 12),
          Flexible(
            child: Align(
              alignment: Alignment.centerRight,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(value, textAlign: TextAlign.end, style: typo.bodyMd.copyWith(fontWeight: FontWeight.w600, color: valueColor)),
                  if (sub != null) Text(sub!, textAlign: TextAlign.end, style: typo.caption),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class MetricTile extends StatelessWidget {
  const MetricTile({super.key, required this.icon, required this.label, required this.value, this.sub, this.color});

  final IconData icon;
  final String label;
  final String value;
  final String? sub;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final typo = context.typography;
    final on = colors.onSecondaryContainer;
    return AppCard(
      color: colors.secondaryContainer,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 18, color: color ?? on),
            const SizedBox(width: 6),
            Text(label, style: typo.label.copyWith(color: on)),
          ]),
          const SizedBox(height: 8),
          Text(value, style: typo.displaySm.copyWith(color: on), maxLines: 1, overflow: TextOverflow.ellipsis),
          Text(sub ?? ' ', style: typo.caption.copyWith(color: on.withValues(alpha: 0.8)), maxLines: 2),
        ],
      ),
    );
  }
}

class StatusBanner extends StatelessWidget {
  const StatusBanner({super.key, required this.icon, required this.text, required this.color, required this.background});

  final IconData icon;
  final String text;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(12)),
      child: Row(children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: context.typography.bodySm.copyWith(color: color))),
      ]),
    );
  }
}
