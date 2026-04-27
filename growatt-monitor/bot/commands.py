"""Telegram command handlers.

To add a new command: write an async handler `async def my_handler(update, context)`
and append it to COMMANDS at the bottom. main.py wires them into the Application.
"""
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, List

from telegram import Update
from telegram.ext import ContextTypes

from growatt.client import GrowattClient
from growatt import parsers

log = logging.getLogger(__name__)

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


@dataclass
class Command:
    name: str            # without leading slash
    description: str
    handler: Handler


# The client is injected by main.py at startup.
_client: GrowattClient | None = None


def bind_client(client: GrowattClient) -> None:
    global _client
    _client = client


def _require_client() -> GrowattClient:
    if _client is None:
        raise RuntimeError("Growatt client not bound — call bind_client() at startup")
    return _client


async def _safe_reply(update: Update, text: str) -> None:
    if update.message is not None:
        await update.message.reply_text(text)


async def _fetch_status() -> dict:
    client = _require_client()
    return await client.acall("get_device_status")


def _fmt_w(v: float | None) -> str:
    return f"{v:.0f} W" if v is not None else "n/a"


def _fmt_v(v: float | None) -> str:
    return f"{v:.1f} V" if v is not None else "n/a"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.0f}%" if v is not None else "n/a"


# ---------- handlers ----------

async def cmd_pv(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await _fetch_status()
        await _safe_reply(update, f"☀️ PV output: {_fmt_w(parsers.pv_watts(data))}")
    except Exception:
        log.exception("/pv failed")
        await _safe_reply(update, "⚠️ Could not reach Growatt API. Try again shortly.")


async def cmd_load(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await _fetch_status()
        await _safe_reply(update, f"🔋 Load: {_fmt_w(parsers.load_watts(data))}")
    except Exception:
        log.exception("/load failed")
        await _safe_reply(update, "⚠️ Could not reach Growatt API. Try again shortly.")


async def cmd_battery(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await _fetch_status()
        soc = parsers.battery_soc(data)
        v = parsers.battery_voltage(data)
        await _safe_reply(update, f"🔋 Battery: SOC {_fmt_pct(soc)} | {_fmt_v(v)}")
    except Exception:
        log.exception("/battery failed")
        await _safe_reply(update, "⚠️ Could not reach Growatt API. Try again shortly.")


async def cmd_grid(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await _fetch_status()
        v = parsers.grid_voltage(data)
        present = parsers.grid_present(data)
        state = "ON" if present else ("OFF" if present is False else "unknown")
        await _safe_reply(update, f"🔌 Grid: {state} ({_fmt_v(v)})")
    except Exception:
        log.exception("/grid failed")
        await _safe_reply(update, "⚠️ Could not reach Growatt API. Try again shortly.")


async def cmd_status(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = await _fetch_status()
        pv = parsers.pv_watts(data)
        load = parsers.load_watts(data)
        soc = parsers.battery_soc(data)
        bv = parsers.battery_voltage(data)
        gv = parsers.grid_voltage(data)
        present = parsers.grid_present(data)
        grid_state = "ON" if present else ("OFF" if present is False else "unknown")
        msg = (
            "📟 Growatt status\n"
            f"☀️ PV:      {_fmt_w(pv)}\n"
            f"🔋 Load:    {_fmt_w(load)}\n"
            f"🔋 Battery: {_fmt_pct(soc)} ({_fmt_v(bv)})\n"
            f"🔌 Grid:    {grid_state} ({_fmt_v(gv)})"
        )
        await _safe_reply(update, msg)
    except Exception:
        log.exception("/status failed")
        await _safe_reply(update, "⚠️ Could not reach Growatt API. Try again shortly.")


COMMANDS: List[Command] = [
    Command("pv",      "Current PV (solar) output in watts",        cmd_pv),
    Command("load",    "Current load consumption in watts",         cmd_load),
    Command("battery", "Battery SOC % and voltage",                 cmd_battery),
    Command("grid",    "Grid voltage and on/off state",             cmd_grid),
    Command("status",  "Full summary",                              cmd_status),
]


async def cmd_unknown(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["Unknown command. Available:"]
    for c in COMMANDS:
        lines.append(f"  /{c.name} — {c.description}")
    await _safe_reply(update, "\n".join(lines))
