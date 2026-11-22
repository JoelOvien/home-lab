package com.homelab.growatt_app

import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.SharedPreferences
import android.text.format.DateFormat
import android.view.View
import android.widget.RemoteViews
import es.antonborri.home_widget.HomeWidgetLaunchIntent
import es.antonborri.home_widget.HomeWidgetProvider
import java.util.Date

private const val STALE_AFTER_MS = 15 * 60 * 1000L

class StatusWidgetProvider : HomeWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
        widgetData: SharedPreferences,
    ) {
        val ts = widgetData.getString("ts", null)?.toLongOrNull()
        val updated = when (ts) {
            null -> "No data"
            else -> {
                val ms = ts * 1000
                val clock = DateFormat.getTimeFormat(context).format(Date(ms))
                if (System.currentTimeMillis() - ms > STALE_AFTER_MS) "Stale · $clock" else clock
            }
        }
        val gridOff = widgetData.contains("grid_on") && !widgetData.getBoolean("grid_on", true)

        for (id in appWidgetIds) {
            val views = RemoteViews(context.packageName, R.layout.status_widget).apply {
                setTextViewText(R.id.updated, updated)
                tile(widgetData, R.id.pv, R.id.pv_detail, "pv")
                tile(widgetData, R.id.load, R.id.load_detail, "load")
                tile(widgetData, R.id.battery, R.id.battery_detail, "battery")
                tile(widgetData, R.id.grid, R.id.grid_detail, "grid")
                setTextColor(
                    R.id.grid,
                    context.getColor(if (gridOff) R.color.widget_alert else R.color.widget_value),
                )
                setOnClickPendingIntent(
                    android.R.id.background,
                    HomeWidgetLaunchIntent.getActivity(context, MainActivity::class.java),
                )
            }
            appWidgetManager.updateAppWidget(id, views)
        }
    }

    private fun RemoteViews.tile(data: SharedPreferences, valueId: Int, detailId: Int, key: String) {
        setTextViewText(valueId, data.getString(key, null) ?: "n/a")
        val detail = data.getString("${key}_detail", null).orEmpty()
        setTextViewText(detailId, detail)
        setViewVisibility(detailId, if (detail.isEmpty()) View.GONE else View.VISIBLE)
    }
}
