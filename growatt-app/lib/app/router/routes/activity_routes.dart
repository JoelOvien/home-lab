import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/features/activity/presentation/screens/activity_screen.dart';

class ActivityRoutes {
  static const String root = '/activity';

  static StatefulShellBranch branch(GlobalKey<NavigatorState> navigatorKey) {
    return StatefulShellBranch(
      navigatorKey: navigatorKey,
      routes: [
        GoRoute(
          path: root,
          pageBuilder: (context, state) => const NoTransitionPage(child: ActivityScreen()),
        ),
      ],
    );
  }
}
