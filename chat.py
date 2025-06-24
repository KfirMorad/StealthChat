# chat.py — StealthChat backend (final user-count model)

import os, asyncio, random, base64, aiohttp
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

import discord
from discord.ext import commands, tasks
from discord import Webhook
from dotenv import load_dotenv

import crypter

# ─── env ────────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN           = os.environ["BOT_TOKEN"]
WEBHOOK_URL         = os.environ["WEBHOOK_URL"]          # webhook that posts to SESSIONS_CHANNEL_ID
SESSIONS_CHANNEL_ID = int(os.environ["SESSIONS_CHANNEL_ID"])

# ─── discord client ─────────────────────────────────────────────────────
intents                 = discord.Intents.default()
intents.guilds          = True
intents.messages        = True
intents.message_content = True
bot                      = commands.Bot(command_prefix="!", intents=intents)

# ─── runtime state ──────────────────────────────────────────────────────
session_message_ids: Dict[str, int]              = {}  # SID → counter-message id
session_channel_ids: Dict[str, int]              = {}  # SID → text-channel id
session_counts:      Dict[str, int]              = {}  # SID → cached live count
session_last_seen:   Dict[str, datetime]         = {}  # SID → last payload time
receive_handlers:    Dict[str, List[Callable[[str], None]]] = {}

http_session: Optional[aiohttp.ClientSession] = None

# ────────────────────────── helpers ─────────────────────────────────────
async def _get_hook() -> Webhook:
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return Webhook.from_url(WEBHOOK_URL, session=http_session)

def _unique_sid(guild: discord.Guild) -> str:
    existing = {c.name for c in guild.channels}
    while True:
        sid = f"{random.randint(0, 999_999):06d}"
        if sid not in existing and sid not in session_channel_ids:
            return sid

# ───────────────────────── counter-message ops ──────────────────────────
async def _post_session_message(sid: str, count: int) -> int:
    hook = await _get_hook()
    msg  = await hook.send(content=f"{sid}|{count}", wait=True)
    return msg.id

async def _locate_counter_message(sid: str) -> Optional[discord.Message]:
    """Return the WebhookMessage object for <sid>|<n>, resyncing cache if needed."""
    hook = await _get_hook()
    # fast path: cached id
    msg_id = session_message_ids.get(sid)
    if msg_id:
        try:
            return await hook.fetch_message(msg_id)
        except discord.NotFound:
            pass
    # slow path: scan recent history once
    chan = bot.get_channel(SESSIONS_CHANNEL_ID) or await bot.fetch_channel(SESSIONS_CHANNEL_ID)
    if not isinstance(chan, discord.TextChannel):
        return None
    async for m in chan.history(limit=100):
        if m.webhook_id and m.content.startswith(f"{sid}|"):
            session_message_ids[sid] = m.id
            return m
    return None

async def _get_live_count(sid: str) -> Optional[int]:
    msg: Optional[discord.Message] = await _locate_counter_message(sid)
    if msg is None:
        return None
    try:
        _, n = msg.content.strip().split("|", 1)
        return int(n)
    except ValueError:
        return None

async def _edit_or_create_counter(sid: str, new_total: int) -> None:
    hook = await _get_hook()
    msg  = await _locate_counter_message(sid)
    if msg:
        await hook.edit_message(message_id=msg.id,
                                content=f"{sid}|{new_total}")
    else:
        session_message_ids[sid] = await _post_session_message(sid, new_total)

async def _delete_session_message(sid: str) -> None:
    hook = await _get_hook()
    msg_id = session_message_ids.pop(sid, None)
    if msg_id:
        try:
            await hook.delete_message(msg_id)
        except discord.NotFound:
            pass

# ───────────────────────── channel ops ──────────────────────────────────
async def _create_session_channel(sid: str, guild: discord.Guild) -> int:
    ch = await guild.create_text_channel(sid)
    return ch.id

async def _delete_session_channel(sid: str) -> None:
    ch_id = session_channel_ids.pop(sid, None)
    if ch_id:
        guild = bot.guilds[0]
        ch = guild.get_channel(ch_id)
        if isinstance(ch, discord.TextChannel):
            try: await ch.delete()
            except discord.NotFound: pass

# ───────────────────────── lifecycle helpers ────────────────────────────
async def _start_session(sid: str, guild: discord.Guild) -> None:
    ch_id = await _create_session_channel(sid, guild)
    session_channel_ids[sid] = ch_id
    msg_id = await _post_session_message(sid, 1)
    session_message_ids[sid] = msg_id
    session_counts[sid]      = 1
    session_last_seen[sid]   = datetime.now(timezone.utc)

async def _update_count(sid: str, delta: int) -> None:
    """Add +1 or -1 to live count; delete channel & message when hits 0."""
    live = await _get_live_count(sid)
    if live is None:
        live = 0
    new_total = live + delta
    print(f"[COUNT] {sid}: {live} → {new_total}")
    if new_total <= 0:
        await _delete_session_channel(sid)
        await _delete_session_message(sid)
        crypter.clear_session(sid)
        session_counts.pop(sid, None)
        session_last_seen.pop(sid, None)
        receive_handlers.pop(sid, None)
        return
    await _edit_or_create_counter(sid, new_total)
    session_counts[sid] = new_total

# ───────────────────────── API for GUI threads ──────────────────────────
def start_auto_session_from_thread(guild_id: int) -> str:
    guild = bot.get_guild(guild_id); assert guild
    sid = _unique_sid(guild)
    asyncio.run_coroutine_threadsafe(_start_session(sid, guild), bot.loop).result()
    return sid

def join_session_from_thread(sid: str) -> None:
    asyncio.run_coroutine_threadsafe(_update_count(sid, +1), bot.loop).result()

def leave_session_from_thread(sid: str) -> None:
    asyncio.run_coroutine_threadsafe(_update_count(sid, -1), bot.loop).result()

def send_session_message_from_thread(sid: str, content: str) -> None:
    asyncio.run_coroutine_threadsafe(_send_to_channel(sid, content), bot.loop)

def register_receive_callback(sid: str, cb: Callable[[str], None]) -> None:
    receive_handlers.setdefault(sid, []).append(cb)

def unregister_receive_callback(sid: str, cb: Callable[[str], None]) -> None:
    handlers = receive_handlers.get(sid, [])
    if cb in handlers: handlers.remove(cb)

# ───────────────────────── send helper ──────────────────────────────────
async def _send_to_channel(sid: str, content: str) -> None:
    ch_id = session_channel_ids.get(sid);
    if not ch_id: return
    guild = bot.guilds[0]
    ch = guild.get_channel(ch_id)
    if isinstance(ch, discord.TextChannel):
        await ch.send(content)

# ───────────────────────── boot-time sync ───────────────────────────────
async def sync_active_sessions() -> None:
    chan = bot.get_channel(SESSIONS_CHANNEL_ID) or await bot.fetch_channel(SESSIONS_CHANNEL_ID)
    if not isinstance(chan, discord.TextChannel): return
    session_message_ids.clear(); session_channel_ids.clear()
    session_counts.clear();      session_last_seen.clear()
    async for msg in chan.history(limit=None):
        if not msg.webhook_id: continue
        try: sid, n = msg.content.strip().split("|", 1); n = int(n)
        except ValueError: continue
        session_message_ids[sid] = msg.id
        session_counts[sid]      = n
        session_last_seen[sid]   = datetime.now(timezone.utc)
    # channels
    if bot.guilds:
        guild = bot.guilds[0]
        for sid in session_counts:
            ch = discord.utils.get(guild.channels, name=sid)
            if isinstance(ch, discord.TextChannel):
                session_channel_ids[sid] = ch.id

# ───────────────────────── bot events & idle cleanup ────────────────────
@bot.event
async def on_ready():
    await sync_active_sessions()
    cleanup.start()

@bot.event
async def on_message(msg: discord.Message):
    await bot.process_commands(msg)
    if msg.channel is None or bot.user is None: return
    if msg.author.id != bot.user.id:            return
    if not isinstance(msg.channel, discord.TextChannel): return
    # decrypt payload
    for sid, ch_id in session_channel_ids.items():
        if ch_id != msg.channel.id: continue
        pwd = crypter.session_passwords.get(sid)
        if not pwd: continue
        try:
            raw   = base64.urlsafe_b64decode(msg.content.encode())
            plain = crypter.decrypt_message(raw, pwd)
        except Exception: continue
        session_last_seen[sid] = datetime.now(timezone.utc)
        for cb in receive_handlers.get(sid, []): cb(plain)

@tasks.loop(minutes=5)
async def cleanup():
    now = datetime.now(timezone.utc)
    for sid, last in list(session_last_seen.items()):
        if now - last > timedelta(minutes=30):
            await _update_count(sid, -1)

@cleanup.before_loop
async def _wait_ready(): await bot.wait_until_ready()

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
