import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/features/energy/presentation/screens/energy_screen.dart';

class EnergyRoutes {
  static const String root = '/energy';

  static StatefulShellBranch branch(GlobalKey<NavigatorState> navigatorKey) {
    return StatefulShellBranch(
      navigatorKey: navigatorKey,
      routes: [
        GoRoute(
          path: root,
          pageBuilder: (context, state) => const NoTransitionPage(child: EnergyScreen()),
        ),
      ],
    );
  }
}
