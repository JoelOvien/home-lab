import 'package:growatt_app/core/inverter/models.dart';
import 'package:intl/intl.dart';

const na = 'n/a';

String formatWatts(double? w) {
  if (w == null) return na;
  if (w.abs() >= 1000) return '${(w / 1000).toStringAsFixed(2)} kW';
  return '${w.round()} W';
}

String formatPercent(double? p) => p == null ? na : '${p.round()}%';

String formatVolts(double? v) => v == null ? na : '${v.toStringAsFixed(1)} V';

String formatKwh(double? kwh) => kwh == null ? na : '${kwh.toStringAsFixed(2)} kWh';

String formatDuration(Duration d) {
  if (d.isNegative) d = Duration.zero;
  final days = d.inDays;
  final hours = d.inHours % 24;
  final minutes = d.inMinutes % 60;
  if (days > 0) return '${days}d ${hours}h';
  if (d.inHours > 0) return '${d.inHours}h ${minutes}m';
  if (d.inMinutes > 0) return '${d.inMinutes}m';
  return '<1m';
}

String formatHours(double? hours) {
  if (hours == null || hours.isNaN || hours.isInfinite) return na;
  return formatDuration(Duration(minutes: (hours * 60).round()));
}

String formatAgo(Duration d) {
  if (d.inMinutes < 1) return 'just now';
  if (d.inHours < 1) return '${d.inMinutes} min ago';
  return '${formatDuration(d)} ago';
}

String formatClock(DateTime t) => DateFormat('HH:mm').format(t);

String formatDateTime(DateTime t) => DateFormat('d MMM HH:mm').format(t);

String formatDate(DateTime t) => DateFormat('d MMM').format(t);

String? formatBatteryFlow(BatteryFlow flow) => switch (flow.direction) {
      BatteryDirection.charging => 'Charging ${formatWatts(flow.chargeW)}',
      BatteryDirection.discharging => 'Discharging ${formatWatts(flow.dischargeW)}',
      null => null,
    };
