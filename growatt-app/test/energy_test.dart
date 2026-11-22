import 'package:flutter_test/flutter_test.dart';
import 'package:growatt_app/core/inverter/energy.dart';
import 'package:growatt_app/core/inverter/models.dart';

void main() {
  test('trapezoid over evenly spaced samples', () {
    final e = integrate([(0, 1000.0), (300, 1000.0), (600, 2000.0)]);
    // 1000 W for 5 min + avg 1500 W for 5 min = 83.33 + 125 Wh
    expect(e.kwh, closeTo(0.20833, 1e-5));
    expect(e.coveredSeconds, 600);
  });

  test('skips gaps over 15 minutes but integrates exactly 15', () {
    final e = integrate([(0, 600.0), (900, 600.0), (900 + 901, 600.0)]);
    expect(e.coveredSeconds, 900);
    expect(e.kwh, closeTo(0.15, 1e-9));
  });

  test('skips pairs with a null on either side', () {
    final e = integrate([(0, 1000.0), (300, null), (600, 1000.0), (900, 1000.0)]);
    expect(e.coveredSeconds, 300);
    expect(e.kwh, closeTo(1000 * 300 / 3600 / 1000, 1e-9));
  });

  test('ignores duplicate and out-of-order timestamps', () {
    final e = integrate([(300, 500.0), (300, 500.0), (200, 500.0)]);
    expect(e.kwh, 0);
    expect(e.coveredSeconds, 0);
  });

  test('empty and single samples are zero', () {
    expect(integrate(const []).kwh, 0);
    expect(integrate([(0, 900.0)]).coveredSeconds, 0);
  });

  test('split integrates load, PV and grid separately', () {
    final points = [
      const SeriesPoint(ts: 0, loadW: 1000, pvW: 2000, gridW: null),
      const SeriesPoint(ts: 3600 ~/ 12, loadW: 1000, pvW: 2000, gridW: 0),
    ];
    final split = EnergySplit.of(points, const Duration(seconds: 600));
    expect(split.load.kwh, closeTo(1000 * 300 / 3600 / 1000, 1e-9));
    expect(split.pv.kwh, closeTo(2 * split.load.kwh, 1e-9));
    expect(split.grid.coveredSeconds, 0);
    expect(split.load.coverage(split.window), 0.5);
  });
}
