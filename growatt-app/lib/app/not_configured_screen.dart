import 'package:flutter/material.dart';
import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';

class NotConfiguredScreen extends StatelessWidget {
  const NotConfiguredScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final typo = context.typography;
    final colors = context.colors;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.key_off_outlined, size: 48, color: context.status.warning),
              const SizedBox(height: 16),
              Text('Not configured', style: typo.displaySm),
              const SizedBox(height: 8),
              Text(
                'This build has no Cloudflare D1 credentials. Copy secrets.example.json '
                'to secrets.json, fill in accountId, databaseId and a D1 Read token, '
                'then rebuild with:',
                style: typo.bodyMd.copyWith(color: colors.onSurfaceVariant),
              ),
              const SizedBox(height: 12),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: colors.surfaceContainerHighest, borderRadius: BorderRadius.circular(10)),
                child: Text(
                  'flutter run --dart-define-from-file=secrets.json',
                  style: typo.bodySm.copyWith(fontFamily: 'monospace'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
