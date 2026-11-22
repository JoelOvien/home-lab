import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:flutter/material.dart';

class ErrorView extends StatelessWidget {
  const ErrorView({
    super.key,
    required this.message,
    this.onRetry,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final typo = context.typography;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: colors.error),
            const SizedBox(height: 16),
            Text('Something went wrong', style: typo.headingSm, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(message, style: typo.bodyMd.copyWith(color: colors.onSurfaceVariant), textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 24),
              TextButton(onPressed: onRetry, child: const Text('Try again')),
            ],
          ],
        ),
      ),
    );
  }
}
