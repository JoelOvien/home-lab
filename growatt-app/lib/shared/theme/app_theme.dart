import 'package:dynamic_color/dynamic_color.dart';
import 'package:flutter/material.dart';
import 'package:growatt_app/shared/theme/tokens/colors.dart';

/// Success and warning roles, which Material 3 doesn't define. Each is a tonal
/// palette harmonised towards the current primary colour.
class StatusColors extends ThemeExtension<StatusColors> {
  const StatusColors({
    required this.success,
    required this.successContainer,
    required this.onSuccessContainer,
    required this.warning,
    required this.warningContainer,
    required this.onWarningContainer,
  });

  factory StatusColors.from(ColorScheme scheme) {
    ColorScheme tonal(Color seed) => ColorScheme.fromSeed(
          seedColor: seed.harmonizeWith(scheme.primary),
          brightness: scheme.brightness,
        );
    final ok = tonal(AppColors.successSeed);
    final warn = tonal(AppColors.warningSeed);
    return StatusColors(
      success: ok.primary,
      successContainer: ok.primaryContainer,
      onSuccessContainer: ok.onPrimaryContainer,
      warning: warn.primary,
      warningContainer: warn.primaryContainer,
      onWarningContainer: warn.onPrimaryContainer,
    );
  }

  final Color success;
  final Color successContainer;
  final Color onSuccessContainer;
  final Color warning;
  final Color warningContainer;
  final Color onWarningContainer;

  @override
  StatusColors copyWith({
    Color? success,
    Color? successContainer,
    Color? onSuccessContainer,
    Color? warning,
    Color? warningContainer,
    Color? onWarningContainer,
  }) =>
      StatusColors(
        success: success ?? this.success,
        successContainer: successContainer ?? this.successContainer,
        onSuccessContainer: onSuccessContainer ?? this.onSuccessContainer,
        warning: warning ?? this.warning,
        warningContainer: warningContainer ?? this.warningContainer,
        onWarningContainer: onWarningContainer ?? this.onWarningContainer,
      );

  @override
  StatusColors lerp(StatusColors? other, double t) {
    if (other == null) return this;
    return StatusColors(
      success: Color.lerp(success, other.success, t)!,
      successContainer: Color.lerp(successContainer, other.successContainer, t)!,
      onSuccessContainer: Color.lerp(onSuccessContainer, other.onSuccessContainer, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningContainer: Color.lerp(warningContainer, other.warningContainer, t)!,
      onWarningContainer: Color.lerp(onWarningContainer, other.onWarningContainer, t)!,
    );
  }
}

/// Short names for the Material 3 type scale as this app uses it.
class AppTypography {
  const AppTypography(this._text, this._colors);

  final TextTheme _text;
  final ColorScheme _colors;

  TextStyle get displayLg => _text.headlineLarge!;
  TextStyle get displayMd => _text.headlineMedium!;
  TextStyle get displaySm => _text.headlineSmall!;
  TextStyle get headingLg => _text.titleLarge!;
  TextStyle get headingMd => _text.titleMedium!;
  TextStyle get headingSm => _text.titleSmall!;
  TextStyle get bodyLg => _text.bodyLarge!;
  TextStyle get bodyMd => _text.bodyMedium!;
  TextStyle get bodySm => _text.bodySmall!;
  TextStyle get caption => _text.bodySmall!.copyWith(color: _colors.onSurfaceVariant);
  TextStyle get label => _text.labelMedium!.copyWith(color: _colors.onSurfaceVariant);
}

ColorScheme fallbackScheme(Brightness brightness) =>
    ColorScheme.fromSeed(seedColor: AppColors.seed, brightness: brightness);

ThemeData buildTheme(ColorScheme scheme) {
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    cardTheme: CardThemeData(
      color: scheme.surfaceContainerHigh,
      elevation: 0,
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    navigationBarTheme: NavigationBarThemeData(backgroundColor: scheme.surfaceContainer),
    extensions: [StatusColors.from(scheme)],
  );
}
