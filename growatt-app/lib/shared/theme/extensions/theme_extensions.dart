import 'package:growatt_app/shared/theme/app_theme.dart';
import 'package:flutter/material.dart';

extension ThemeExtensions on BuildContext {
  ColorScheme get colors => Theme.of(this).colorScheme;
  StatusColors get status => Theme.of(this).extension<StatusColors>()!;
  AppTypography get typography => AppTypography(Theme.of(this).textTheme, colors);
  ThemeData get theme => Theme.of(this);
  bool get isDark => Theme.of(this).brightness == Brightness.dark;
}
