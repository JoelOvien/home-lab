import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/widgets/cards/section_card.dart';
import 'package:growatt_app/shared/widgets/feedback/app_loader.dart';
import 'package:growatt_app/shared/widgets/feedback/error_view.dart';

/// Scrollable, pull-to-refresh tab body.
class TabPage extends StatelessWidget {
  const TabPage({super.key, required this.title, required this.onRefresh, required this.children});

  final String title;
  final Future<void> Function() onRefresh;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: RefreshIndicator(
        onRefresh: onRefresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
          children: [
            for (final c in children) Padding(padding: const EdgeInsets.only(bottom: 12), child: c),
          ],
        ),
      ),
    );
  }
}

/// Loading and error states shared by the tabs.
class AsyncTab<T> extends StatelessWidget {
  const AsyncTab({
    super.key,
    required this.title,
    required this.value,
    required this.onRefresh,
    required this.builder,
  });

  final String title;
  final AsyncValue<T> value;
  final Future<void> Function() onRefresh;
  final List<Widget> Function(T data) builder;

  @override
  Widget build(BuildContext context) {
    final data = value.value;
    if (data != null) {
      return TabPage(title: title, onRefresh: onRefresh, children: [
        if (value.hasError)
          StatusBanner(
            icon: Icons.cloud_off,
            text: 'Refresh failed: ${value.error}',
            color: context.colors.onErrorContainer,
            background: context.colors.errorContainer,
          ),
        ...builder(data),
      ]);
    }
    if (value.hasError) {
      return TabPage(
        title: title,
        onRefresh: onRefresh,
        children: [ErrorView(message: '${value.error}', onRetry: onRefresh)],
      );
    }
    return Scaffold(appBar: AppBar(title: Text(title)), body: const Center(child: AppLoader()));
  }
}
