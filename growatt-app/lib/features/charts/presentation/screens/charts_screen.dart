import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/clock.dart';
import 'package:growatt_app/core/inverter/energy.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/features/charts/presentation/providers/charts_provider.dart';
import 'package:growatt_app/shared/functions/formatters.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';
import 'package:growatt_app/shared/widgets/tab_page.dart';

enum _Range { today, last24h }

class ChartsScreen extends ConsumerStatefulWidget {
  const ChartsScreen({super.key});

  @override
  ConsumerState<ChartsScreen> createState() => _ChartsScreenState();
}

class _ChartsScreenState extends ConsumerState<ChartsScreen> {
  var _range = _Range.today;

  @override
  Widget build(BuildContext context) {
    return AsyncTab<ChartsData>(
      title: 'Charts',
      value: ref.watch(chartsProvider),
      onRefresh: () => ref.refresh(chartsProvider.future),
      builder: (data) {
        final start = _range == _Range.today ? data.startOfToday : data.nowTs - 86400;
        final points = data.since(start);
        final colors = context.colors;
        return [
          SegmentedButton<_Range>(
            segments: const [
              ButtonSegment(value: _Range.today, label: Text('Today')),
              ButtonSegment(value: _Range.last24h, label: Text('Last 24h')),
            ],
            selected: {_range},
            style: SegmentedButton.styleFrom(
              selectedBackgroundColor: colors.primary,
              selectedForegroundColor: Colors.black,
            ),
            onSelectionChanged: (s) => setState(() => _range = s.first),
          ),
          SectionCard(
            title: 'Load vs solar',
            trailing: _Legend(items: [('Load', colors.accent2), ('Solar', colors.primary)]),
            child: _TimeChart(
              clock: data.clock,
              start: start,
              end: data.nowTs,
              series: [
                (points.map((p) => (p.ts, p.loadW)).toList(), colors.accent2),
                (points.map((p) => (p.ts, p.pvW)).toList(), colors.primary),
              ],
              formatY: (v) => v >= 1000 ? '${(v / 1000).toStringAsFixed(1)}k' : v.round().toString(),
            ),
          ),
          SectionCard(
            title: 'Battery SOC',
            child: _TimeChart(
              clock: data.clock,
              start: start,
              end: data.nowTs,
              minY: 0,
              maxY: 100,
              series: [(points.map((p) => (p.ts, p.soc)).toList(), colors.success)],
              formatY: (v) => '${v.round()}%',
            ),
          ),
          SectionCard(
            title: 'Energy',
            child: _EnergyTable(rows: [('Today', data.today), ('7 days', data.week), ('30 days', data.month)]),
          ),
          SectionCard(title: 'Battery health', child: _HealthChart(weeks: data.health, clock: data.clock)),
        ];
      },
    );
  }
}

class _Legend extends StatelessWidget {
  const _Legend({required this.items});
  final List<(String, Color)> items;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        for (final (label, color) in items) ...[
          Container(width: 10, height: 3, color: color),
          const SizedBox(width: 4),
          Text(label, style: context.typography.caption),
          const SizedBox(width: 10),
        ],
      ]);
}

List<FlSpot> spotsWithGaps(List<(int, double?)> samples, int start) {
  final spots = <FlSpot>[];
  int? prevTs;
  for (final (ts, w) in samples) {
    final gap = prevTs != null && ts - prevTs > maxGapSeconds;
    if (w == null || gap) {
      if (spots.isNotEmpty && spots.last != FlSpot.nullSpot) spots.add(FlSpot.nullSpot);
    }
    if (w != null) spots.add(FlSpot((ts - start) / 3600, w));
    prevTs = ts;
  }
  return spots;
}

class _TimeChart extends StatelessWidget {
  const _TimeChart({
    required this.clock,
    required this.start,
    required this.end,
    required this.series,
    required this.formatY,
    this.minY,
    this.maxY,
  });

  final ZoneClock clock;
  final int start, end;
  final List<(List<(int, double?)>, Color)> series;
  final String Function(double) formatY;
  final double? minY, maxY;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final bars = [
      for (final (samples, color) in series)
        LineChartBarData(
          spots: spotsWithGaps(samples, start),
          color: color,
          barWidth: 2,
          isCurved: false,
          dotData: const FlDotData(show: false),
        ),
    ];
    if (bars.every((b) => b.spots.isEmpty)) {
      return SizedBox(height: 60, child: Center(child: Text('No data in this range', style: context.typography.caption)));
    }
    final spanHours = (end - start) / 3600;
    final labelStyle = context.typography.caption;
    return SizedBox(
      height: 180,
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: spanHours,
          minY: minY ?? 0,
          maxY: maxY,
          lineBarsData: bars,
          lineTouchData: const LineTouchData(enabled: false),
          borderData: FlBorderData(show: false),
          gridData: FlGridData(
            drawVerticalLine: false,
            getDrawingHorizontalLine: (_) => FlLine(color: colors.borderMuted, strokeWidth: 1),
          ),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 36,
                getTitlesWidget: (v, meta) => v == meta.max || v == meta.min
                    ? const SizedBox.shrink()
                    : Text(formatY(v), style: labelStyle),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: spanHours > 12 ? 6 : 3,
                reservedSize: 22,
                getTitlesWidget: (v, meta) => v == meta.max
                    ? const SizedBox.shrink()
                    : Text(formatClock(clock.at(start + (v * 3600).round())), style: labelStyle),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

String _kwh(Energy e) => e.coveredSeconds == 0 ? na : e.kwh.toStringAsFixed(1);

class _EnergyTable extends StatelessWidget {
  const _EnergyTable({required this.rows});
  final List<(String, EnergySplit)> rows;

  @override
  Widget build(BuildContext context) {
    final typo = context.typography;
    final head = typo.caption;
    final cell = typo.bodyMd.copyWith(fontWeight: FontWeight.w600);
    Widget num(String s, TextStyle style) => Text(s, textAlign: TextAlign.end, style: style);
    return Column(children: [
      Table(
        columnWidths: const {0: FlexColumnWidth(1.2)},
        children: [
          TableRow(children: [
            Text('', style: head),
            num('Load', head),
            num('Solar', head),
            num('Grid', head),
          ]),
          for (final (label, e) in rows)
            TableRow(children: [
              Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(label, style: typo.bodyMd)),
              Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: num(_kwh(e.load), cell)),
              Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: num(_kwh(e.pv), cell)),
              Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: num(_kwh(e.grid), cell)),
            ]),
        ],
      ),
      const SizedBox(height: 6),
      Align(
        alignment: Alignment.centerLeft,
        child: Text(
          'kWh. Data covers ${[for (final (l, e) in rows) '${(e.load.coverage(e.window) * 100).round()}% of $l'].join(', ')}. '
          'Gaps over 15 min are skipped.',
          style: typo.caption,
        ),
      ),
    ]);
  }
}

class _HealthChart extends StatelessWidget {
  const _HealthChart({required this.weeks, required this.clock});
  final List<WeeklyVoltage> weeks;
  final ZoneClock clock;

  @override
  Widget build(BuildContext context) {
    final typo = context.typography;
    if (weeks.isEmpty) {
      return Text('No snapshots at 45–55% SOC yet.', style: typo.caption);
    }
    final colors = context.colors;
    final lo = weeks.map((w) => w.volts).reduce((a, b) => a < b ? a : b);
    final hi = weeks.map((w) => w.volts).reduce((a, b) => a > b ? a : b);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(
        height: 140,
        child: LineChart(LineChartData(
          minY: (lo - 0.3).floorToDouble(),
          maxY: (hi + 0.3).ceilToDouble(),
          lineTouchData: const LineTouchData(enabled: false),
          borderData: FlBorderData(show: false),
          gridData: FlGridData(
            drawVerticalLine: false,
            getDrawingHorizontalLine: (_) => FlLine(color: colors.borderMuted, strokeWidth: 1),
          ),
          lineBarsData: [
            LineChartBarData(
              spots: [for (final (i, w) in weeks.indexed) FlSpot(i.toDouble(), w.volts)],
              color: colors.success,
              barWidth: 2,
            ),
          ],
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 36,
                interval: 0.5,
                getTitlesWidget: (v, meta) => v == meta.min || v == meta.max
                    ? const SizedBox.shrink()
                    : Text(v.toStringAsFixed(1), style: typo.caption),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: 2,
                reservedSize: 22,
                getTitlesWidget: (v, meta) {
                  final i = v.round();
                  if (i < 0 || i >= weeks.length || i.isOdd) return const SizedBox.shrink();
                  return Text(formatDate(clock.at(weeks[i].weekStartTs)), style: typo.caption);
                },
              ),
            ),
          ),
        )),
      ),
      const SizedBox(height: 6),
      Text('Weekly mean voltage at 45–55% SOC. Latest ${formatVolts(weeks.last.volts)}.', style: typo.caption),
    ]);
  }
}
