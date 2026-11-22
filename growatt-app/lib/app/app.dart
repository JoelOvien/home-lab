import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/app/not_configured_screen.dart';
import 'package:growatt_app/core/providers.dart';
import 'package:growatt_app/core/push/push_setup.dart';
import 'package:growatt_app/shared/theme/app_theme.dart';

class GrowattApp extends ConsumerWidget {
  const GrowattApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (!ref.watch(isConfiguredProvider)) {
      return MaterialApp(
        title: 'Growatt',
        debugShowCheckedModeBanner: false,
        theme: buildLightTheme(),
        darkTheme: buildDarkTheme(),
        themeMode: ThemeMode.dark,
        home: const NotConfiguredScreen(),
      );
    }
    return MaterialApp.router(
      title: 'Growatt',
      debugShowCheckedModeBanner: false,
      theme: buildLightTheme(),
      darkTheme: buildDarkTheme(),
      themeMode: ThemeMode.dark,
      scaffoldMessengerKey: scaffoldMessengerKey,
      routerConfig: ref.watch(routerProvider),
    );
  }
}
