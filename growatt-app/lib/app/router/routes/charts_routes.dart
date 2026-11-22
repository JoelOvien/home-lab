import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/features/charts/presentation/screens/charts_screen.dart';

class ChartsRoutes {
  static const String root = '/charts';

  static StatefulShellBranch branch(GlobalKey<NavigatorState> navigatorKey) {
    return StatefulShellBranch(
      navigatorKey: navigatorKey,
      routes: [
        GoRoute(
          path: root,
          pageBuilder: (context, state) => const NoTransitionPage(child: ChartsScreen()),
        ),
      ],
    );
  }
}
