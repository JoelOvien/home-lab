import 'package:growatt_app/shared/theme/app_theme.dart';
import 'package:flutter/material.dart';

extension ThemeExtensions on BuildContext {
  AppColorScheme get colors => Theme.of(this).extension<AppColorScheme>()!;
  AppTypography get typography => Theme.of(this).extension<AppTypography>()!;
  ThemeData get theme => Theme.of(this);
  Brightness get brightness => Theme.of(this).brightness;
  bool get isDark => brightness == Brightness.dark;
}
