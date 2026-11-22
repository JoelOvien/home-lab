import asyncio
import logging
import signal
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from config import Config, ConfigError
from growatt.client import GrowattClient
from bot import commands as bot_commands
from bot.notifications import Notifier
from bot.push import FcmPusher
from scheduler import Scheduler
from jobs.grid_monitor import make_grid_monitor
from jobs.energy_report import make_energy_report
from jobs.battery_monitor import make_battery_monitor
from jobs.recorder import make_recorder
from jobs.status_alerts import make_status_alerts
from history import History, LocalBackend, D1Backend
from health import WorkerHealth


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stdout,
    )
    # httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


log = logging.getLogger("growatt-monitor")


async def write_startup_state(history: History, cfg: Config, started_ts: float) -> None:
    """Publish settings the app needs. Unset ones are deleted, so a value
    removed from Railway doesn't linger as if it were still configured."""
    values = {
        "started_ts": int(started_ts),
        "tz": cfg.tz_name,
        "battery_capacity_kwh": cfg.battery_capacity_kwh,
        # Retired: batPower turned out to be unsigned. Deleting it stops older
        # app builds from labelling discharge as charge.
        "battery_sign": None,
    }
    try:
        for key, value in values.items():
            if value is None:
                await history.delete_state(key)
            else:
                await history.set_state(key, value)
    except Exception:
        log.exception("Could not write worker state to history")


async def amain() -> None:
    setup_logging()

    try:
        cfg = Config.from_env()
    except ConfigError as e:
        log.error("Configuration error: %s", e)
        sys.exit(1)

    # ---- Growatt ----
    client = GrowattClient(
        cfg.growatt_username,
        cfg.growatt_password,
        cfg.growatt_device_sn,
        cfg.growatt_plant_id,
    )
    bot_commands.bind_client(client)

    if cfg.use_d1:
        backend = D1Backend(
            cfg.cloudflare_account_id, cfg.cloudflare_d1_database_id, cfg.cloudflare_api_token
        )
        log.info("History stored in Cloudflare D1")
    else:
        backend = LocalBackend(cfg.history_db_path)
        log.info("History stored in local SQLite at %s", cfg.history_db_path)
    history = History(backend)
    bot_commands.bind_history(history)

    health = WorkerHealth(history)
    client.call_listener = health.on_call
    await write_startup_state(history, cfg, health.started_ts)

    # ---- Telegram application ----
    application = (
        ApplicationBuilder()
        .token(cfg.telegram_token)
        .build()
    )

    # Updates from any other chat are dropped without a reply.
    owner_only = filters.Chat(chat_id=int(cfg.telegram_chat_id))
    for cmd in bot_commands.COMMANDS:
        application.add_handler(CommandHandler(cmd.name, cmd.handler, filters=owner_only))
    application.add_handler(MessageHandler(filters.COMMAND & owner_only, bot_commands.cmd_unknown))

    pusher = None
    if cfg.fcm_service_account_json:
        pusher = FcmPusher(cfg.fcm_service_account_json)
        log.info("Push alerts enabled for FCM project %s", pusher.project_id)
    notifier = Notifier(application.bot, cfg.telegram_chat_id, history, pusher=pusher)
    bot_commands.bind(
        notifier=notifier,
        health=health,
        settings=bot_commands.Settings(cfg.tz, cfg.battery_capacity_kwh),
    )

    async def unreachable_alert() -> None:
        await notifier.alert("unreachable", "⚠️ Cannot reach Growatt API. Will keep retrying.")
    client.unreachable_callback = unreachable_alert

    async def fatal_auth_alert(msg: str) -> None:
        await notifier.send(
            "🚫 Growatt login rejected (bad credentials). "
            "Stopping API calls until env vars are fixed and the worker is restarted."
        )
    client.fatal_auth_callback = fatal_auth_alert

    # ---- Scheduled jobs registry ----
    scheduler = Scheduler()
    scheduler.register(
        "grid_monitor",
        interval_seconds=120,
        fn=make_grid_monitor(client, notifier, history),
    )
    scheduler.register(
        "battery_monitor",
        interval_seconds=300,
        fn=make_battery_monitor(client, notifier, cfg.battery_alert_levels),
    )
    scheduler.register(
        "status_alerts",
        interval_seconds=300,
        fn=make_status_alerts(
            client, notifier, cfg.load_alert_pct, cfg.solar_check_hours, cfg.tz
        ),
    )
    scheduler.register(
        "recorder",
        interval_seconds=300,
        fn=make_recorder(client, history),
    )
    scheduler.register_daily(
        "energy_report",
        cfg.daily_report_time,
        cfg.tz,
        make_energy_report(client, notifier, cfg.tz, history=history),
    )

    # ---- Lifecycle ----
    await application.initialize()
    await application.start()
    assert application.updater is not None
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    await notifier.send("🟢 Growatt Monitor is online")

    scheduler_task = asyncio.create_task(scheduler.run_forever(), name="scheduler")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass  # not supported on some platforms

    try:
        await stop_event.wait()
    finally:
        log.info("Shutting down…")
        scheduler_task.cancel()
        try:
            await notifier.send("🔴 Growatt Monitor is shutting down")
        except Exception:
            pass
        try:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        except Exception:
            log.exception("Error during shutdown")


def main() -> None:
    try:
        asyncio.run(amain())
    except Exception:
        # Last-ditch logging; Railway will restart the worker.
        logging.exception("Fatal error in growatt-monitor; exiting")
        sys.exit(1)


if __name__ == "__main__":
    main()
