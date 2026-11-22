import 'package:growatt_app/shared/theme/tokens/colors.dart';
import 'package:growatt_app/shared/theme/tokens/radii.dart';
import 'package:growatt_app/shared/theme/tokens/typography.dart';
import 'package:flutter/material.dart';

// ── Color Scheme Extension ────────────────────────────────────────────────────

class AppColorScheme extends ThemeExtension<AppColorScheme> {
  final Color surface;
  final Color surfaceAlt;
  final Color surfaceElevated;
  final Color surfaceMuted;
  final Color contentPrimary;
  final Color contentSecondary;
  final Color contentTertiary;
  final Color border;
  final Color borderMuted;
  final Color primary;
  final Color primaryMuted;
  final Color secondary;
  final Color accent1;
  final Color accent2;
  final Color error;
  final Color success;
  final Color warning;
  final Color errorBackground;
  final Color successBackground;

  const AppColorScheme({
    required this.surface,
    required this.surfaceAlt,
    required this.surfaceElevated,
    required this.surfaceMuted,
    required this.contentPrimary,
    required this.contentSecondary,
    required this.contentTertiary,
    required this.border,
    required this.borderMuted,
    required this.primary,
    required this.primaryMuted,
    required this.secondary,
    required this.accent1,
    required this.accent2,
    required this.error,
    required this.success,
    required this.warning,
    required this.errorBackground,
    required this.successBackground,
  });

  static const light = AppColorScheme(
    surface: AppColors.lightSurface, surfaceAlt: AppColors.lightSurfaceAlt,
    surfaceElevated: AppColors.lightSurfaceElevated, surfaceMuted: AppColors.lightSurfaceMuted,
    contentPrimary: AppColors.lightContentPrimary, contentSecondary: AppColors.lightContentSecondary,
    contentTertiary: AppColors.lightContentTertiary, border: AppColors.lightBorder,
    borderMuted: AppColors.lightBorderMuted, primary: AppColors.lightPrimary,
    primaryMuted: AppColors.lightPrimaryMuted, secondary: AppColors.secondary,
    accent1: AppColors.accent1, accent2: AppColors.accent2,
    error: AppColors.lightError, success: AppColors.lightSuccess, warning: AppColors.lightWarning,
    errorBackground: AppColors.lightErrorBackground, successBackground: AppColors.lightSuccessBackground,
  );

  static const dark = AppColorScheme(
    surface: AppColors.darkSurface, surfaceAlt: AppColors.darkSurfaceAlt,
    surfaceElevated: AppColors.darkSurfaceElevated, surfaceMuted: AppColors.darkSurfaceMuted,
    contentPrimary: AppColors.darkContentPrimary, contentSecondary: AppColors.darkContentSecondary,
    contentTertiary: AppColors.darkContentTertiary, border: AppColors.darkBorder,
    borderMuted: AppColors.darkBorderMuted, primary: AppColors.darkPrimary,
    primaryMuted: AppColors.darkPrimaryMuted, secondary: AppColors.secondary,
    accent1: AppColors.accent1, accent2: AppColors.accent2,
    error: AppColors.darkError, success: AppColors.darkSuccess, warning: AppColors.darkWarning,
    errorBackground: AppColors.darkErrorBackground, successBackground: AppColors.darkSuccessBackground,
  );

  @override
  AppColorScheme copyWith({
    Color? surface, Color? surfaceAlt, Color? surfaceElevated, Color? surfaceMuted,
    Color? contentPrimary, Color? contentSecondary, Color? contentTertiary,
    Color? border, Color? borderMuted, Color? primary, Color? primaryMuted,
    Color? secondary, Color? accent1, Color? accent2,
    Color? error, Color? success, Color? warning,
    Color? errorBackground, Color? successBackground,
  }) => AppColorScheme(
    surface: surface ?? this.surface, surfaceAlt: surfaceAlt ?? this.surfaceAlt,
    surfaceElevated: surfaceElevated ?? this.surfaceElevated, surfaceMuted: surfaceMuted ?? this.surfaceMuted,
    contentPrimary: contentPrimary ?? this.contentPrimary, contentSecondary: contentSecondary ?? this.contentSecondary,
    contentTertiary: contentTertiary ?? this.contentTertiary, border: border ?? this.border,
    borderMuted: borderMuted ?? this.borderMuted, primary: primary ?? this.primary,
    primaryMuted: primaryMuted ?? this.primaryMuted, secondary: secondary ?? this.secondary,
    accent1: accent1 ?? this.accent1, accent2: accent2 ?? this.accent2,
    error: error ?? this.error, success: success ?? this.success, warning: warning ?? this.warning,
    errorBackground: errorBackground ?? this.errorBackground, successBackground: successBackground ?? this.successBackground,
  );

  @override
  AppColorScheme lerp(AppColorScheme? other, double t) {
    if (other is! AppColorScheme) return this;
    return AppColorScheme(
      surface: Color.lerp(surface, other.surface, t)!, surfaceAlt: Color.lerp(surfaceAlt, other.surfaceAlt, t)!,
      surfaceElevated: Color.lerp(surfaceElevated, other.surfaceElevated, t)!, surfaceMuted: Color.lerp(surfaceMuted, other.surfaceMuted, t)!,
      contentPrimary: Color.lerp(contentPrimary, other.contentPrimary, t)!, contentSecondary: Color.lerp(contentSecondary, other.contentSecondary, t)!,
      contentTertiary: Color.lerp(contentTertiary, other.contentTertiary, t)!, border: Color.lerp(border, other.border, t)!,
      borderMuted: Color.lerp(borderMuted, other.borderMuted, t)!, primary: Color.lerp(primary, other.primary, t)!,
      primaryMuted: Color.lerp(primaryMuted, other.primaryMuted, t)!, secondary: Color.lerp(secondary, other.secondary, t)!,
      accent1: Color.lerp(accent1, other.accent1, t)!, accent2: Color.lerp(accent2, other.accent2, t)!,
      error: Color.lerp(error, other.error, t)!, success: Color.lerp(success, other.success, t)!,
      warning: Color.lerp(warning, other.warning, t)!, errorBackground: Color.lerp(errorBackground, other.errorBackground, t)!,
      successBackground: Color.lerp(successBackground, other.successBackground, t)!,
    );
  }
}

// ── Typography Extension ──────────────────────────────────────────────────────

class AppTypography extends ThemeExtension<AppTypography> {
  final TextStyle displayLg;
  final TextStyle displayMd;
  final TextStyle displaySm;
  final TextStyle headingLg;
  final TextStyle headingMd;
  final TextStyle headingSm;
  final TextStyle bodyLg;
  final TextStyle bodyMd;
  final TextStyle bodySm;
  final TextStyle caption;
  final TextStyle label;

  const AppTypography({
    required this.displayLg, required this.displayMd, required this.displaySm,
    required this.headingLg, required this.headingMd, required this.headingSm,
    required this.bodyLg, required this.bodyMd, required this.bodySm,
    required this.caption, required this.label,
  });

  factory AppTypography.fromColorScheme(AppColorScheme colors) {
    final base = colors.contentPrimary;
    return AppTypography(
      displayLg: AppTypographyTokens.displayLg.copyWith(color: base),
      displayMd: AppTypographyTokens.displayMd.copyWith(color: base),
      displaySm: AppTypographyTokens.displaySm.copyWith(color: base),
      headingLg: AppTypographyTokens.headingLg.copyWith(color: base),
      headingMd: AppTypographyTokens.headingMd.copyWith(color: base),
      headingSm: AppTypographyTokens.headingSm.copyWith(color: base),
      bodyLg: AppTypographyTokens.bodyLg.copyWith(color: base),
      bodyMd: AppTypographyTokens.bodyMd.copyWith(color: base),
      bodySm: AppTypographyTokens.bodySm.copyWith(color: base),
      caption: AppTypographyTokens.caption.copyWith(color: colors.contentSecondary),
      label: AppTypographyTokens.label.copyWith(color: colors.contentSecondary),
    );
  }

  @override
  AppTypography copyWith({
    TextStyle? displayLg, TextStyle? displayMd, TextStyle? displaySm,
    TextStyle? headingLg, TextStyle? headingMd, TextStyle? headingSm,
    TextStyle? bodyLg, TextStyle? bodyMd, TextStyle? bodySm,
    TextStyle? caption, TextStyle? label,
  }) => AppTypography(
    displayLg: displayLg ?? this.displayLg, displayMd: displayMd ?? this.displayMd,
    displaySm: displaySm ?? this.displaySm, headingLg: headingLg ?? this.headingLg,
    headingMd: headingMd ?? this.headingMd, headingSm: headingSm ?? this.headingSm,
    bodyLg: bodyLg ?? this.bodyLg, bodyMd: bodyMd ?? this.bodyMd,
    bodySm: bodySm ?? this.bodySm, caption: caption ?? this.caption, label: label ?? this.label,
  );

  @override
  AppTypography lerp(AppTypography? other, double t) {
    if (other is! AppTypography) return this;
    return AppTypography(
      displayLg: TextStyle.lerp(displayLg, other.displayLg, t)!,
      displayMd: TextStyle.lerp(displayMd, other.displayMd, t)!,
      displaySm: TextStyle.lerp(displaySm, other.displaySm, t)!,
      headingLg: TextStyle.lerp(headingLg, other.headingLg, t)!,
      headingMd: TextStyle.lerp(headingMd, other.headingMd, t)!,
      headingSm: TextStyle.lerp(headingSm, other.headingSm, t)!,
      bodyLg: TextStyle.lerp(bodyLg, other.bodyLg, t)!,
      bodyMd: TextStyle.lerp(bodyMd, other.bodyMd, t)!,
      bodySm: TextStyle.lerp(bodySm, other.bodySm, t)!,
      caption: TextStyle.lerp(caption, other.caption, t)!,
      label: TextStyle.lerp(label, other.label, t)!,
    );
  }
}

// ── Theme Factories ───────────────────────────────────────────────────────────

ThemeData buildLightTheme() {
  const colors = AppColorScheme.light;
  final typography = AppTypography.fromColorScheme(colors);
  return ThemeData(
    brightness: Brightness.light,
    scaffoldBackgroundColor: colors.surface,
    colorScheme: ColorScheme.light(
      primary: colors.primary, secondary: colors.secondary,
      surface: colors.surface, error: colors.error,
      onPrimary: AppColors.white, onSecondary: AppColors.white,
      onSurface: colors.contentPrimary, onError: AppColors.white,
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: colors.surface, foregroundColor: colors.contentPrimary,
      elevation: 0, scrolledUnderElevation: 0, centerTitle: true,
      titleTextStyle: typography.headingSm,
    ),
    dividerTheme: DividerThemeData(color: colors.border, thickness: 1, space: 0),
    cardTheme: CardThemeData(
      color: colors.surfaceElevated, elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: AppRadii.mdBr, side: BorderSide(color: colors.borderMuted)),
    ),
    bottomNavigationBarTheme: BottomNavigationBarThemeData(
      backgroundColor: colors.surface, selectedItemColor: colors.primary,
      unselectedItemColor: colors.contentTertiary, type: BottomNavigationBarType.fixed, elevation: 0,
    ),
    extensions: [colors, typography],
  );
}

ThemeData buildDarkTheme() {
  const colors = AppColorScheme.dark;
  final typography = AppTypography.fromColorScheme(colors);
  return ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: colors.surface,
    colorScheme: ColorScheme.dark(
      primary: colors.primary, secondary: colors.secondary,
      surface: colors.surface, error: colors.error,
      onPrimary: AppColors.white, onSecondary: AppColors.white,
      onSurface: colors.contentPrimary, onError: AppColors.white,
    ),
    appBarTheme: AppBarTheme(
      backgroundColor: colors.surface, foregroundColor: colors.contentPrimary,
      elevation: 0, scrolledUnderElevation: 0, centerTitle: true,
      titleTextStyle: typography.headingSm,
    ),
    dividerTheme: DividerThemeData(color: colors.border, thickness: 1, space: 0),
    cardTheme: CardThemeData(
      color: colors.surfaceElevated, elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: AppRadii.mdBr, side: BorderSide(color: colors.borderMuted)),
    ),
    bottomNavigationBarTheme: BottomNavigationBarThemeData(
      backgroundColor: colors.surface, selectedItemColor: colors.primary,
      unselectedItemColor: colors.contentTertiary, type: BottomNavigationBarType.fixed, elevation: 0,
    ),
    extensions: [colors, typography],
  );
}
