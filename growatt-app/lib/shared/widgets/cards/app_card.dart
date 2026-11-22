import 'package:growatt_app/shared/theme/extensions/theme_extensions.dart';
import 'package:growatt_app/shared/theme/tokens/radii.dart';
import 'package:growatt_app/shared/theme/tokens/spacing.dart';
import 'package:flutter/material.dart';

class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding,
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    return Material(
      color: colors.surfaceElevated,
      borderRadius: AppRadii.mdBr,
      child: InkWell(
        borderRadius: AppRadii.mdBr,
        onTap: onTap,
        child: Container(
          padding: padding ?? AppSpacing.cardPadding,
          decoration: BoxDecoration(
            borderRadius: AppRadii.mdBr,
            border: Border.all(color: colors.borderMuted),
          ),
          child: child,
        ),
      ),
    );
  }
}
