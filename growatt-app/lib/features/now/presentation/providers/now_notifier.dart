import 'dart:async';
import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:growatt_app/core/inverter/inverter_repository.dart';
import 'package:growatt_app/core/providers.dart';

class NowView {
  const NowView({required this.data, this.error});

  final NowData data;

  /// Set when the latest refresh failed and [data] is the cached copy.
  final String? error;
}

const _cacheKey = 'now_cache_v1';

final nowProvider = AsyncNotifierProvider<NowNotifier, NowView>(NowNotifier.new);

class NowNotifier extends AsyncNotifier<NowView> {
  @override
  Future<NowView> build() async {
    final interval = ref.watch(autoRefreshProvider);
    if (interval != null) {
      final timer = Timer.periodic(interval, (_) => refresh());
      final lifecycle = AppLifecycleListener(onResume: refresh);
      ref.onDispose(() {
        timer.cancel();
        lifecycle.dispose();
      });
    }
    return _load();
  }

  Future<void> refresh() async {
    final next = await AsyncValue.guard(_load);
    // Keep showing what we have if a refresh fails and there's no cache.
    if (next.hasError && state.hasValue) {
      state = AsyncData(NowView(data: state.requireValue.data, error: '${next.error}'));
    } else {
      state = next;
    }
  }

  Future<NowView> _load() async {
    final prefs = ref.read(sharedPreferencesProvider);
    try {
      final (data, row) = await ref.read(repositoryProvider).now();
      await prefs.setString(_cacheKey, jsonEncode(data.toJson(row)));
      return NowView(data: data);
    } catch (e) {
      final raw = prefs.getString(_cacheKey);
      if (raw == null) rethrow;
      final cached = InverterRepository.fromCache(jsonDecode(raw) as Map<String, dynamic>);
      if (cached == null) rethrow;
      return NowView(data: cached, error: '$e');
    }
  }
}
