import 'package:timezone/timezone.dart' as tz;

/// Converts epoch seconds to wall time in the worker's IANA zone, falling
/// back to the phone's zone when the worker hasn't published one.
class ZoneClock {
  ZoneClock._(this.location);

  factory ZoneClock.named(String? name) {
    if (name == null || name.isEmpty) return ZoneClock._(null);
    try {
      return ZoneClock._(tz.getLocation(name));
    } catch (_) {
      return ZoneClock._(null);
    }
  }

  final tz.Location? location;

  String get label => location?.name ?? 'phone time';

  DateTime at(int epochSeconds) {
    final ms = epochSeconds * 1000;
    final loc = location;
    return loc == null
        ? DateTime.fromMillisecondsSinceEpoch(ms)
        : tz.TZDateTime.fromMillisecondsSinceEpoch(loc, ms);
  }

  int startOfDay(DateTime now) {
    final loc = location;
    if (loc == null) {
      final l = now.toLocal();
      return DateTime(l.year, l.month, l.day).millisecondsSinceEpoch ~/ 1000;
    }
    final l = tz.TZDateTime.from(now, loc);
    return tz.TZDateTime(loc, l.year, l.month, l.day).millisecondsSinceEpoch ~/ 1000;
  }
}
