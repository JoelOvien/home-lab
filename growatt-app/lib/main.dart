import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/app/app.dart';
import 'package:growatt_app/core/providers.dart';
import 'package:growatt_app/core/push/push_setup.dart';
import 'package:growatt_app/core/widget/home_widget_sync.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest.dart' as tzdata;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  tzdata.initializeTimeZones();
  final prefs = await SharedPreferences.getInstance();
  runApp(
    ProviderScope(
      // Show D1 errors straight away; the user can pull to refresh.
      retry: (_, _) => null,
      overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      child: const GrowattApp(),
    ),
  );
  unawaited(setupPush());
  unawaited(setupHomeWidgetRefresh());
}
