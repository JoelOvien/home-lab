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
from scheduler import Scheduler
from jobs.grid_monitor import make_grid_monitor
from jobs.energy_report import make_energy_report


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stdout,
    )


log = logging.getLogger("growatt-monitor")


async def amain() -> None:
    setup_logging()

    try:
        cfg = Config.from_env()
    except ConfigError as e:
        log.error("Configuration error: %s", e)
        sys.exit(1)

    # ---- Growatt ----
    client = GrowattClient(cfg.growatt_username, cfg.growatt_password, cfg.growatt_device_sn)
    bot_commands.bind_client(client)

    # ---- Telegram application ----
    application = (
        ApplicationBuilder()
        .token(cfg.telegram_token)
        .build()
    )

    for cmd in bot_commands.COMMANDS:
        application.add_handler(CommandHandler(cmd.name, cmd.handler))
    application.add_handler(MessageHandler(filters.COMMAND, bot_commands.cmd_unknown))

    notifier = Notifier(application.bot, cfg.telegram_chat_id)

    async def unreachable_alert() -> None:
        await notifier.send("⚠️ Cannot reach Growatt API. Will keep retrying.")
    client.unreachable_callback = unreachable_alert

    # ---- Scheduled jobs registry ----
    scheduler = Scheduler()
    scheduler.register(
        "grid_monitor",
        interval_seconds=60,
        fn=make_grid_monitor(client, notifier),
    )
    scheduler.register(
        "energy_report",
        interval_seconds=12 * 3600,
        fn=make_energy_report(client, notifier, hours=12),
        run_immediately=False,
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
