import 'package:flutter_test/flutter_test.dart';
import 'package:growatt_app/core/inverter/models.dart';
import 'package:growatt_app/core/widget/home_widget_sync.dart';

void main() {
  test('splits each status into a value and a detail', () {
    final lines = widgetLines(const Snapshot(
      ts: 0,
      pvW: 0,
      loadW: 240,
      soc: 100,
      batteryV: 53.1,
      gridV: 0,
      gridPresent: false,
      status: 2,
      energy: EnergyCounters(pv: TodayTotal(3.4, null), load: TodayTotal(5.25, null)),
    ));
    expect((lines.pv.value, lines.pv.detail), ('0 W', '3.40 kWh today'));
    expect((lines.load.value, lines.load.detail), ('240 W', '5.25 kWh today'));
    expect((lines.battery.value, lines.battery.detail), ('100%', '53.1 V · Discharging'));
    expect((lines.grid.value, lines.grid.detail), ('Off', '0.0 V'));
    expect(lines.gridOn, false);
  });

  test('missing fields show n/a and drop empty details', () {
    final lines = widgetLines(null);
    expect((lines.pv.value, lines.pv.detail), ('n/a', ''));
    expect((lines.battery.value, lines.battery.detail), ('n/a', 'n/a'));
    expect(lines.grid.value, 'n/a');
    expect(lines.gridOn, isNull);
  });

  test('grid on', () {
    final grid = widgetLines(const Snapshot(ts: 0, gridPresent: true, gridV: 231.4)).grid;
    expect((grid.value, grid.detail), ('On', '231.4 V'));
  });
}
