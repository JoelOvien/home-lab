package com.homelab.growatt_app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Bundle
import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // High importance so alerts pop up on screen. The worker sends to this
        // channel id (CHANNEL_ID in growatt-monitor/bot/push.py).
        val channel = NotificationChannel("alerts", "Alerts", NotificationManager.IMPORTANCE_HIGH)
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }
}
