import 'package:growatt_app/core/inverter/models.dart';

/// Sample pairs further apart than this are a gap (worker down, inverter
/// offline) and aren't integrated across. Matches `MAX_GAP_SECONDS` in history.py.
const maxGapSeconds = 15 * 60;

class Energy {
  const Energy({required this.kwh, required this.coveredSeconds});
  final double kwh;
  final double coveredSeconds;

  double coverage(Duration window) =>
      window.inSeconds <= 0 ? 0 : (coveredSeconds / window.inSeconds).clamp(0, 1);
}

/// Trapezoidal integration of watts over time-ordered samples, a port of
/// `History.load_energy`.
Energy integrate(Iterable<(int, double?)> samples) {
  var wh = 0.0;
  var covered = 0.0;
  (int, double?)? prev;
  for (final cur in samples) {
    final p = prev;
    prev = cur;
    if (p == null) continue;
    final (t0, w0) = p;
    final (t1, w1) = cur;
    final dt = t1 - t0;
    if (w0 == null || w1 == null || dt <= 0 || dt > maxGapSeconds) continue;
    wh += (w0 + w1) / 2 * dt / 3600;
    covered += dt;
  }
  return Energy(kwh: wh / 1000, coveredSeconds: covered);
}

class EnergySplit {
  const EnergySplit({required this.window, required this.load, required this.pv, required this.grid});
  final Duration window;
  final Energy load, pv, grid;

  factory EnergySplit.of(List<SeriesPoint> points, Duration window) => EnergySplit(
        window: window,
        load: integrate(points.map((p) => (p.ts, p.loadW))),
        pv: integrate(points.map((p) => (p.ts, p.pvW))),
        grid: integrate(points.map((p) => (p.ts, p.gridW))),
      );
}
