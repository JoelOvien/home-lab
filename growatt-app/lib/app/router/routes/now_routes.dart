import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/features/now/presentation/screens/now_screen.dart';

class NowRoutes {
  static const String root = '/now';

  static StatefulShellBranch branch(GlobalKey<NavigatorState> navigatorKey) {
    return StatefulShellBranch(
      navigatorKey: navigatorKey,
      routes: [
        GoRoute(
          path: root,
          pageBuilder: (context, state) => const NoTransitionPage(child: NowScreen()),
        ),
      ],
    );
  }
}
