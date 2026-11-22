import 'package:growatt_app/app/router/routes/now_routes.dart';
import 'package:growatt_app/app/router/routes/energy_routes.dart';
import 'package:growatt_app/app/router/routes/charts_routes.dart';
import 'package:growatt_app/app/router/routes/activity_routes.dart';
import 'package:growatt_app/app/router/routes/system_routes.dart';
import 'package:growatt_app/app/shell/app_scaffold.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

GoRouter createRouter() {
  final rootNavigatorKey = GlobalKey<NavigatorState>(debugLabel: 'rootNav');
  return GoRouter(
    navigatorKey: rootNavigatorKey,
    initialLocation: NowRoutes.root,
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) =>
            AppShell(navigationShell: navigationShell),
        branches: [
          NowRoutes.branch(GlobalKey<NavigatorState>(debugLabel: 'nowNav')),
          EnergyRoutes.branch(GlobalKey<NavigatorState>(debugLabel: 'energyNav')),
          ChartsRoutes.branch(GlobalKey<NavigatorState>(debugLabel: 'chartsNav')),
          ActivityRoutes.branch(GlobalKey<NavigatorState>(debugLabel: 'activityNav')),
          SystemRoutes.branch(GlobalKey<NavigatorState>(debugLabel: 'systemNav')),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      appBar: AppBar(title: const Text('Not found')),
      body: Center(child: Text('No route for: ${state.uri}', textAlign: TextAlign.center)),
    ),
  );
}
