import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/app/shell/app_bottom_nav.dart';
import 'package:growatt_app/features/activity/presentation/providers/activity_provider.dart';
import 'package:growatt_app/features/charts/presentation/providers/charts_provider.dart';
import 'package:growatt_app/features/system/presentation/providers/system_provider.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';

class AppShell extends ConsumerStatefulWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  ConsumerState<AppShell> createState() => _AppShellState();
}

class _AppShellState extends ConsumerState<AppShell> {
  late final AppLifecycleListener _lifecycle;

  @override
  void initState() {
    super.initState();
    _lifecycle = AppLifecycleListener(onResume: _refreshTabs);
  }

  @override
  void dispose() {
    _lifecycle.dispose();
    super.dispose();
  }

  // The Now tab refreshes itself; the others fetch once, so refresh them
  // whenever they're shown again.
  void _refreshTabs() {
    ref.invalidate(chartsProvider);
    ref.invalidate(activityProvider);
    ref.invalidate(systemProvider);
  }

  void _onTap(int index) {
    final shell = widget.navigationShell;
    if (index != shell.currentIndex) {
      switch (index) {
        case 1:
          ref.invalidate(chartsProvider);
        case 2:
          ref.invalidate(activityProvider);
        case 3:
          ref.invalidate(systemProvider);
      }
    }
    shell.goBranch(index, initialLocation: index == shell.currentIndex);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBody: true,
      backgroundColor: context.colors.surface,
      body: widget.navigationShell,
      bottomNavigationBar: AppBottomNav(
        currentIndex: widget.navigationShell.currentIndex,
        onTap: _onTap,
        tabs: const [
          (icon: Icons.bolt, label: 'Now'),
          (icon: Icons.show_chart, label: 'Charts'),
          (icon: Icons.history, label: 'Activity'),
          (icon: Icons.dns_outlined, label: 'System'),
        ],
      ),
    );
  }
}
