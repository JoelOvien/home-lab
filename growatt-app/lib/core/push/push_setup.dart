import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:growatt_app/core/config/d1_config.dart';

const _apiKey = String.fromEnvironment('fcmApiKey');
const _appId = String.fromEnvironment('fcmAppId');
const _senderId = String.fromEnvironment('fcmSenderId');
const _projectId = String.fromEnvironment('fcmProjectId');

/// Must match TOPIC in growatt-monitor/bot/push.py.
const alertsTopic = 'alerts';

final scaffoldMessengerKey = GlobalKey<ScaffoldMessengerState>();

bool get pushConfigured =>
    _apiKey.isNotEmpty && _appId.isNotEmpty && _senderId.isNotEmpty && _projectId.isNotEmpty;

/// Android only. The system shows alerts while the app is in the background
/// or closed; in the foreground they appear as a snack bar instead.
Future<void> setupPush() async {
  if (kIsWeb || !Platform.isAndroid || fakeDataMode.isNotEmpty || !pushConfigured) return;
  try {
    await Firebase.initializeApp(
      options: const FirebaseOptions(
        apiKey: _apiKey,
        appId: _appId,
        messagingSenderId: _senderId,
        projectId: _projectId,
      ),
    );
    final messaging = FirebaseMessaging.instance;
    await messaging.requestPermission();
    await messaging.subscribeToTopic(alertsTopic);
    FirebaseMessaging.onMessage.listen((message) {
      final n = message.notification;
      if (n == null) return;
      scaffoldMessengerKey.currentState?.showSnackBar(
        SnackBar(content: Text([n.title, n.body].whereType<String>().join(': '))),
      );
    });
  } catch (e) {
    debugPrint('Push setup failed: $e');
  }
}
