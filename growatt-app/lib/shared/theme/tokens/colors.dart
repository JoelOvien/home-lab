import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // ── Brand ─────────────────────────────────────────────────────────────────
  static const Color accent1 = Color(0xFF10367D);
  static const Color accent2 = Color(0xFF168B7F);
  static const Color secondary = Color(0xFF0F172A);

  static const Color white = Colors.white;
  static const Color black = Colors.black;
  static const Color transparent = Colors.transparent;

  // ── Light Mode ────────────────────────────────────────────────────────────
  static const Color lightPrimary = Color(0xFFF59E0B);
  static const Color lightPrimaryMuted = Color(0x1AF59E0B);
  static const Color lightSuccess = Color(0xFF00A86B);
  static const Color lightError = Color(0xFFD92B0A);
  static const Color lightWarning = Color(0xFFD97706);

  // ── Dark Mode ─────────────────────────────────────────────────────────────
  static const Color darkPrimary = Color(0xFFF8C060);
  static const Color darkPrimaryMuted = Color(0x1FF8C060);
  static const Color darkSuccess = Color(0xFF00D68F);
  static const Color darkError = Color(0xFFF52207);
  static const Color darkWarning = Color(0xFFF79009);

  // ── Backward-compat aliases (dark values) ─────────────────────────────────
  static const Color primary = darkPrimary;
  static const Color primaryMuted = darkPrimaryMuted;
  static const Color success = darkSuccess;
  static const Color error = darkError;
  static const Color warning = darkWarning;

  // ── Light Surfaces ────────────────────────────────────────────────────────
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightSurfaceAlt = Color(0xFFF8F8FA);
  static const Color lightSurfaceElevated = Color(0xFFFFFFFF);
  static const Color lightSurfaceMuted = Color(0xFFF2F2F7);
  static const Color lightContentPrimary = Color(0xFF1A1A1A);
  static const Color lightContentSecondary = Color(0xFF6B6B6B);
  static const Color lightContentTertiary = Color(0xFF9B9B9B);
  static const Color lightBorder = Color(0xFFE5E5EA);
  static const Color lightBorderMuted = Color(0xFFF2F2F7);
  static const Color lightErrorBackground = Color(0xFFFEF3F2);
  static const Color lightSuccessBackground = Color(0xFFECFDF3);

  // ── Dark Surfaces ─────────────────────────────────────────────────────────
  static const Color darkSurface = Color(0xFF0A0A14);
  static const Color darkSurfaceAlt = Color(0xFF0F0F1E);
  static const Color darkSurfaceElevated = Color(0xFF141422);
  static const Color darkSurfaceMuted = Color(0xFF1A1A2C);
  static const Color darkContentPrimary = Color(0xFFF2F2F2);
  static const Color darkContentSecondary = Color(0xFF8C8C8C);
  static const Color darkContentTertiary = Color(0xFF4D4D4D);
  static const Color darkBorder = Color(0x2DFFFFFF);
  static const Color darkBorderMuted = Color(0x14FFFFFF);
  static const Color darkErrorBackground = Color(0xFF3A2020);
  static const Color darkSuccessBackground = Color(0xFF1E2E24);

}
