import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/features/system/presentation/screens/system_screen.dart';

class SystemRoutes {
  static const String root = '/system';

  static StatefulShellBranch branch(GlobalKey<NavigatorState> navigatorKey) {
    return StatefulShellBranch(
      navigatorKey: navigatorKey,
      routes: [
        GoRoute(
          path: root,
          pageBuilder: (context, state) => const NoTransitionPage(child: SystemScreen()),
        ),
      ],
    );
  }
}
