import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:growatt_app/app/router/app_router.dart';
import 'package:growatt_app/core/config/d1_config.dart';
import 'package:growatt_app/core/d1/d1_client.dart';
import 'package:growatt_app/core/d1/d1_source.dart';
import 'package:growatt_app/core/d1/fake_d1_source.dart';
import 'package:growatt_app/core/inverter/inverter_repository.dart';
import 'package:shared_preferences/shared_preferences.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError('Override in main() via ProviderScope');
});

final d1ConfigProvider = Provider<D1Config>((ref) => D1Config.fromEnvironment);

final usingFakeDataProvider = Provider<bool>((ref) => fakeDataMode.isNotEmpty);

final isConfiguredProvider = Provider<bool>(
  (ref) => ref.watch(usingFakeDataProvider) || ref.watch(d1ConfigProvider).isConfigured,
);

final d1SourceProvider = Provider<D1Source>((ref) {
  if (ref.watch(usingFakeDataProvider)) {
    return FakeD1Source(oldSchema: fakeDataMode == 'old_schema');
  }
  return D1Client(ref.watch(d1ConfigProvider));
});

final repositoryProvider = Provider<InverterRepository>(
  (ref) => InverterRepository(ref.watch(d1SourceProvider)),
);

final nowClockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

final autoRefreshProvider = Provider<Duration?>((ref) => const Duration(seconds: 60));

final routerProvider = Provider<GoRouter>((ref) {
  final router = createRouter();
  ref.onDispose(router.dispose);
  return router;
});
