import 'package:dynamic_color/dynamic_color.dart';
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
    final configured = ref.watch(isConfiguredProvider);
    return DynamicColorBuilder(builder: (lightDynamic, darkDynamic) {
      final theme = buildTheme(lightDynamic?.harmonized() ?? fallbackScheme(Brightness.light));
      final darkTheme = buildTheme(darkDynamic?.harmonized() ?? fallbackScheme(Brightness.dark));
      if (!configured) {
        return MaterialApp(
          title: 'Growatt',
          debugShowCheckedModeBanner: false,
          theme: theme,
          darkTheme: darkTheme,
          home: const NotConfiguredScreen(),
        );
      }
      return MaterialApp.router(
        title: 'Growatt',
        debugShowCheckedModeBanner: false,
        theme: theme,
        darkTheme: darkTheme,
        scaffoldMessengerKey: scaffoldMessengerKey,
        routerConfig: ref.watch(routerProvider),
      );
    });
  }
}
