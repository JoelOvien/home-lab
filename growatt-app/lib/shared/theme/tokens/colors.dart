import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  /// Material 3 baseline purple, the same fallback the home screen widget uses
  /// when the device has no dynamic colour (Android < 12, iOS).
  static const Color seed = Color(0xFF6750A4);

  static const Color successSeed = Color(0xFF2E7D32);
  static const Color warningSeed = Color(0xFFF59E0B);

  // Data series, fixed so charts read the same whatever the wallpaper.
  static const Color energyPv = Color(0xFF14B8A6);
  static const Color energyDischarge = Color(0xFF3B82F6);
  static const Color energyCharge = Color(0xFF8B5CF6);
  static const Color energyImport = Color(0xFFF59E0B);
  static const Color energyLoad = Color(0xFFF97316);
}
