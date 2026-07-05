import asyncio
import random
import os
import json
import re
import sqlite3
import time
import threading
from datetime import datetime
from urllib.parse import quote
import httpx
from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.messages import SearchGlobalRequest
from telethon.tl.types import InputMessagesFilterEmpty, InputPeerEmpty

JOIN_MAP_FILE = "join_map.json"

# ─── Gemini integration ────────────────────────────────────────────────────────

GEMINI_ENDPOINT = "http://localhost:8081/v1/chat/completions"
GEMINI_SYSTEM_PROMPT = (
    "Ты обычный пользователь в Telegram-чате. Отвечай естественно, кратко, как живой человек.\n"
    "Правила:\n"
    "- Только русский язык, 1-3 коротких предложения\n"
    "- Если хочешь сказать несколько мыслей — раздели их пустой строкой (бот отправит как отдельные сообщения)\n"
    "- Без эмодзи, без звёздочек, без форматирования\n"
    "- Если тема разговора — игры, досуг, свободное время — ненавязчиво упомяни "
    "'Synthesis game bot' (текстовый крафт-бот в Telegram)\n"
    "- Иначе просто поддержи разговор нейтрально\n"
    "- Не звучи как реклама, не повторяйся, не используй шаблонные фразы"
)

GEMINI_CONTEXT_PROMPT = (
    "Вот последние сообщения в чате (\"пользователь\" — другие люди, \"я\" — это ты). "
    "Ответь одним сообщением на ситуацию естественно."
)

async def generate_gemini_response(last_messages_text: str) -> str | None:
    """Generate a contextual reply using the local Gemini proxy. Returns None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(GEMINI_ENDPOINT, json={
                "model": "gemini-3.5-flash",
                "messages": [
                    {"role": "system", "content": GEMINI_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{GEMINI_CONTEXT_PROMPT}\n\n---\n{last_messages_text}"}
                ],
                "temperature": 0.9,
                "max_tokens": 120
            })
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"].strip()
                # Remove quotes if Gemini wrapped the answer
                text = text.strip('"\'»«').strip()
                return text if text else None
    except Exception:
        return None
    return None

# ─── Spintax ─────────────────────────────────────────────────────────────────

def render_spintax(text: str) -> str:
    """Render spintax: {var1|var2|var3} picks one randomly.
    Supports escaping via backslash+brace and nesting one level."""
    def replace(m):
        opts = [o.strip() for o in m.group(1).split("|")]
        rendered = random.choice(opts)
        # recursively render nested spintax in the chosen option
        while "{" in rendered:
            rendered = re.sub(r"\{([^{}]+)\}", lambda mm: random.choice([o.strip() for o in mm.group(1).split("|")]), rendered)
        return rendered
    return re.sub(r"\{([^{}]+)\}", replace, text)

# ─── Spintax questions ───────────────────────────────────────────────────────

QUESTION_SPINTAX = (
    "Блин, {скучно|тоска|скукота|пипец как скучно}. "
    "Посоветуйте {какую-нибудь|какую|хоть какую-то} "
    "{залипалку текстовую|текстовую игру|игру в телеге}, "
    "{только чтоб|лишь бы|главное чтобы} без доната {жесткого|бешеного|сильного}."
)

# ─── Spintax answers ─────────────────────────────────────────────────────────

ANSWER_SPINTAX = (
    "Вбей в поиск телеги Synthesis game bot. "
    "Там {механика крафта прикольная|крафт прикольный|интересная механика крафта}, "
    "{сижу второй день собираю предметы|третий день играю|уже неделю фармлю}. "
    "{Доната жесткого нет|Без доната норм|Донат не нужен}."
)

# ─── Organic responses for real messages ─────────────────────────────────────

ORGANIC_RESPONSES = [
    "Попробуй в поиске телеграма найти Synthesis game bot. Крафт вещей, рецепты — залипательно.",
    "Я ща в Synthesis game bot играю, текстовый крафт. В поиске тг найдешь.",
    "Synthesis game bot норм тема, если любишь крафтить. Через поиск тг ищи.",
    "Мне Synthesis game bot зашел — крафт, лутинг, без доната. Поищи в телеге.",
    "Есть бот Synthesis game bot. Текстовый крафт, рецепты самому открывать интересно.",
]

ORGANIC_SMALLTALK = [
    "Согласен, хорошая тема.",
    "Тоже так думаю.",
    "Интересно, надо глянуть.",
    "Да, есть такое.",
    "Не знал, спасибо.",
    "Прикольно, спасибо за инфу.",
    "+1",
    "На самом деле да, годно.",
]

# ─── Bio texts (spintax) ─────────────────────────────────────────────────────

BIO_SPINTAX = (
    "{Играю|Залип} в {Synthesis_game_bot|Synth game bot}. "
    "{Крафт|Выживание}. {Поиск в тг|Ищи в телеге}."
)

# ─── Keywords to respond to ─────────────────────────────────────────────────

TRIGGER_KEYWORDS = [
    "игр", "поиграть", "посоветуй", "подскажи", "скучно", "залипнуть",
    "текстов", "крафт", "рекоменд", "во что", "через заняться", "free time",
    "bot", "game", "релакс", "расслабить", "убить время",
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

SESSION_CACHE = {}

def load_chats(file_path="chats.txt"):
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def get_available_sessions(sessions_dir="./sessions"):
    if not os.path.exists(sessions_dir):
        return []
    sessions = []
    for file in sorted(os.listdir(sessions_dir)):
        if file.endswith(".session"):
            sessions.append(file.replace(".session", ""))
    return sessions

def get_session_name(session_path):
    base = os.path.basename(session_path)
    return base.replace(".session", "")

async def sleep_with_progress(minutes, label, logger, stop_event, interval=5):
    total_seconds = int(minutes * 60)
    remaining_seconds = total_seconds
    while remaining_seconds > 0:
        if stop_event.is_set():
            logger(f"{label} — stopped by user")
            return True
        remaining_minutes = (remaining_seconds + 59) // 60
        if remaining_seconds % (interval * 60) == 0:
            logger(f"{label} — {remaining_minutes} min left")
        await asyncio.sleep(1)
        remaining_seconds -= 1
    return False

async def safe_join(app, name, chat_link, logger):
    try:
        entity = await app.get_entity(chat_link)
        await app(JoinChannelRequest(entity))
        logger(f"[{name}] Joined {chat_link}.")
        return True
    except Exception as e:
        if "already" in str(e).lower():
            logger(f"[{name}] Already in {chat_link}.")
            return True
        if "requested" in str(e).lower():
            logger(f"[{name}] Join requested for {chat_link} (private).")
            return False
        logger(f"[{name}] Join error for {chat_link}: {e}")
        return False

async def init_client_pool(session_names, api_id, api_hash, logger):
    pool = {}
    for name in session_names:
        path = os.path.abspath(f"./sessions/{name}")
        client = TelegramClient(path, api_id, api_hash)
        try:
            await client.connect()
            if await client.is_user_authorized():
                me = await client.get_me()
                pool[name] = client
                logger(f"✓ {name} — {me.first_name} @{me.username}")
            else:
                logger(f"✗ {name} — not authorized, excluded")
                await client.disconnect()
        except Exception as e:
            logger(f"✗ {name} — {e}")
            try:
                await client.disconnect()
            except:
                pass
    return pool

async def set_bios(client_pool, logger, stop_event):
    logger("=== Checking/setting account bios... ===")
    idx = 0
    for name, client in client_pool.items():
        if stop_event.is_set():
            break
        try:
            me = await client.get_me()
            current_bio = getattr(me, 'about', '') or ''
            desired_bio = render_spintax(BIO_SPINTAX)
            if any(kw in current_bio.lower() for kw in ['synthesis', 'game', 'крафт', 'synth']):
                logger(f"[{name}] Bio already ok, skip")
            else:
                await client(UpdateProfileRequest(about=desired_bio))
                logger(f"[{name}] Bio updated.")
                idx += 1
                if idx % 5 == 0:
                    delay = random.randint(2, 5)
                    logger(f"Bio batch {idx}, waiting {delay} min...")
                    stopped = await sleep_with_progress(delay, "Bio cooldown", logger, stop_event, interval=1)
                    if stopped:
                        break
        except Exception as e:
            logger(f"[{name}] Bio error: {e}")
    logger("=== Bios done ===")

async def close_client_pool(pool):
    for name, client in pool.items():
        try:
            await client.disconnect()
        except:
            pass

def is_message_relevant(text: str) -> bool:
    """Check if a message contains keywords worth responding to."""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in TRIGGER_KEYWORDS)

def should_ignore_sender(msg, own_usernames: set) -> bool:
    """Skip messages from our own accounts to avoid echo."""
    sender = msg.sender
    if not sender:
        return True
    username = sender.username or ""
    return username.lower() in own_usernames

async def get_own_usernames(client_pool) -> set:
    """Get set of our account usernames to detect self-messages."""
    usernames = set()
    for name, client in client_pool.items():
        try:
            me = await client.get_me()
            if me.username:
                usernames.add(me.username.lower())
        except:
            pass
    return usernames

# ─── Database (claimed chats) ─────────────────────────────────────────────────

DB_PATH = "campaign.db"
_db_lock = threading.Lock()

def init_db():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS claimed_chats (
                chat_username TEXT UNIQUE NOT NULL,
                claimed_by TEXT NOT NULL,
                claimed_at REAL NOT NULL,
                last_active_at REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_counts (
                session_name TEXT NOT NULL,
                date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (session_name, date)
            )
        """)
        conn.commit()
        conn.close()

def get_account_chats(account_name):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT chat_username FROM claimed_chats WHERE claimed_by=? AND is_active=1 ORDER BY claimed_at",
            (account_name,)
        )
        result = [row[0] for row in cur.fetchall()]
        conn.close()
        return result

def get_all_claimed():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute("SELECT chat_username FROM claimed_chats WHERE is_active=1")
        result = {row[0] for row in cur.fetchall()}
        conn.close()
        return result

def claim_chat(chat_username, account_name):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(
                "INSERT INTO claimed_chats (chat_username, claimed_by, claimed_at) VALUES (?, ?, ?)",
                (chat_username, account_name, time.time())
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

def release_chat(chat_username):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE claimed_chats SET is_active=0 WHERE chat_username=?", (chat_username,))
        conn.commit()
        conn.close()

def update_last_active(chat_username):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE claimed_chats SET last_active_at=? WHERE chat_username=?", (time.time(), chat_username))
        conn.commit()
        conn.close()

def count_account_chats(account_name):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT COUNT(*) FROM claimed_chats WHERE claimed_by=? AND is_active=1",
            (account_name,)
        )
        count = cur.fetchone()[0]
        conn.close()
        return count

# ─── Daily message limits ─────────────────────────────────────────────────────

DAILY_MESSAGE_LIMIT = 8

def get_daily_count(account_name: str) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.execute(
            "SELECT count FROM daily_counts WHERE session_name=? AND date=?",
            (account_name, today)
        )
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

def increment_daily_count(account_name: str):
    today = datetime.now().strftime("%Y-%m-%d")
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO daily_counts (session_name, date, count)
            VALUES (?, ?, 1)
            ON CONFLICT(session_name, date) DO UPDATE SET count = count + 1
        """, (account_name, today))
        conn.commit()
        conn.close()

# ─── Human behavior helpers ────────────────────────────────────────────────────

DAILY_MESSAGE_LIMIT = 8  # max messages per account per day

def is_daytime() -> bool:
    """Only active 10:00-23:00 (human awake hours)."""
    h = datetime.now().hour
    return 10 <= h < 23

def human_delay(min_sec: float = 5, max_sec: float = 60) -> float:
    """Normal distribution delay centered at (min+max)/2, clamped."""
    mu = (min_sec + max_sec) * 0.5
    sigma = (max_sec - min_sec) * 0.25
    return max(min_sec, min(max_sec, random.gauss(mu, sigma)))

async def split_and_send(client, entity, text, logger, name, reply_to=None):
    """Split text by newlines, send as multiple messages with human gaps."""
    parts = [p.strip() for p in text.replace('\r\n', '\n').split('\n') if p.strip()]
    if not parts:
        return False
    for i, part in enumerate(parts):
        await client.send_message(entity, part, reply_to=(reply_to if i == 0 else None))
        if i < len(parts) - 1:
            await asyncio.sleep(human_delay(2, 8))
    logger(f"[{name}] Sent {len(parts)} messages")
    return True

async def check_spambot(client, name, logger) -> bool:
    """Check account health via @spambot. Returns False if restricted."""
    try:
        spambot = await client.get_entity('@spambot')
        await client.send_message(spambot, '/start')
        await asyncio.sleep(3)
        msgs = await client.get_messages(spambot, limit=1)
        if msgs and msgs[0] and msgs[0].text:
            txt = msgs[0].text.lower()
            if any(w in txt for w in ['ограничен', 'limited', 'banned', 'забанен', 'спам']):
                logger(f"[{name}] @spambot: ACCOUNT RESTRICTED!")
                return False
        return True
    except Exception as e:
        logger(f"[{name}] @spambot check error: {e}")
        return True  # assume OK on error

# ─── Chat discovery: DuckDuckGo → aggregator sites → SearchGlobalRequest ─────

WEB_SEARCH_KEYWORDS = [
    "telegram game chat",
    "telegram gaming group",
    "telegram games community",
    "telegram game discussion",
    "telegram gamer chat",
    "telegram group game",
    "telegram multiplayer chat",
    "telegram rpg group",
    "telegram игровой чат",
    "telegram игры обсуждение",
    "telegram гейминг",
    "telegram game community join",
    "telegram игровой чат",
    "telegram игры обсуждение",
    "telegram геймеры",
    "telegram майнкрафт",
    "telegram дота",
]

_web_search_offset: int = 0
_aggregator_crawl_offset: int = 0
_web_rate_limiter = asyncio.Lock()
_last_web_request: float = 0

# Aggregator categories on telegram-groups.com
AGGREGATOR_CATEGORIES = ["games", "gaming", "pokemon", "anime"]

SKIP_USERNAMES = {
    "joinchat", "s", "addstickers", "share", "proxy",
    "contact", "invoice", "pay", "k", "i", "bg",
    "me", "t", "x", "telegram", "bot", "bots",
}


def _clean_username(uname: str) -> str | None:
    u = uname.lower().strip()
    if u in SKIP_USERNAMES or len(u) < 4:
        return None
    return f"@{uname}"


async def _check_chat_via_tme_s(link: str, logger) -> bool:
    """Check chat via t.me/s/ page — returns True if likely gaming-themed."""
    skip = ["crypto", "signals", "trading", "forex", "sport", "betting",
            "porn", "adult", "nude", "dating", "news", "music", "movie",
            "nft", "token", "blockchain", "decentrali", "exchange",
            "airdrop", "mining", "whale", "p2p", "defi", "dao",
            "casino", "slot", "poker", "shop", "store", "price",
            "presale", "ido", "launchpad", "staking", "yield", "earn",
            "investment", "profit", "bonus", "referral", "cash",
            "buy", "sell", "market", "coin", "wallet"]
    good = ["game", "gaming", "gamer", "play", "игр", "игра", "discord",
            "community", "chat", "group", "clan", "guild", "mmorpg",
            "rpg", "craft", "survival", "steam", "minecraft",
            "dota", "csgo", "valorant", "pubg", "fortnite",
            "roblox", "gta", " multiplayer", "online", "co-op"]
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
            c.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r = await c.get(f"https://t.me/s/{link.lstrip('@')}")
            if r.status_code != 200:
                return False  # can't check → skip
            text = r.text.lower()
            for kw in skip:
                if kw in text:
                    return False
            for kw in good:
                if kw in text:
                    return True
            return False  # no gaming keywords found
    except Exception:
        return False


async def _search_via_duckduckgo(exclude_set, logger):
    """Search DuckDuckGo for t.me links with gaming keywords (rate-limited).
    Tries ddgs library first, falls back to raw httpx."""
    global _web_search_offset, _last_web_request

    kw = WEB_SEARCH_KEYWORDS[_web_search_offset % len(WEB_SEARCH_KEYWORDS)]
    _web_search_offset += 1

    async with _web_rate_limiter:
        now = time.time()
        wait = 6.0 - (now - _last_web_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_web_request = time.time()

    def _parse_links(results: list) -> list[str]:
        links = []
        for r in results:
            href = r.get('href', '')
            for m in re.finditer(r't\.me/([a-zA-Z0-9_]{3,})', href):
                uname = _clean_username(m.group(1))
                if uname and uname not in exclude_set:
                    links.append(uname)
        return links

    try:
        from duckduckgo_search import DDGS
        results = await asyncio.to_thread(
            lambda: list(DDGS().text(kw, max_results=20, region='ru-ru'))
        )
        if results:
            usernames = _parse_links(results)
            if usernames:
                logger(f"  DuckDuckGo lib found {len(usernames)} for '{kw}'")
                for link in usernames[:5]:
                    if await _check_chat_via_tme_s(link, logger):
                        return link
                return usernames[0]
    except Exception as lib_err:
        logger(f"  DuckDuckGo lib error ({lib_err!r}), trying httpx...")

    # Fallback: raw httpx
    url = f"https://html.duckduckgo.com/html/?q={quote(kw)}"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            c.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            })
            r = await c.get(url)
            if r.status_code != 200:
                snippet = r.text[:80].strip().replace('\n', ' ')
                logger(f"  DuckDuckGo httpx {r.status_code} for '{kw}' -> {snippet}")
                return None

            usernames = []
            for m in re.finditer(r'(?:https?://)?t\.me/([a-zA-Z0-9_]{3,})', r.text):
                uname = _clean_username(m.group(1))
                if uname and uname not in exclude_set:
                    usernames.append(uname)

            if usernames:
                logger(f"  DuckDuckGo httpx found {len(usernames)} for '{kw}'")
                for link in usernames[:5]:
                    if await _check_chat_via_tme_s(link, logger):
                        return link
                return usernames[0]
            return None

    except Exception as e:
        logger(f"  DuckDuckGo httpx error: {e!r}")
        return None


async def _crawl_aggregator(exclude_set, logger):
    """Crawl telegram-groups.com listing pages for t.me links (rate-limited).
    Extracts member counts from listing page to pre-filter by size."""
    global _aggregator_crawl_offset, _last_web_request

    cat = AGGREGATOR_CATEGORIES[_aggregator_crawl_offset % len(AGGREGATOR_CATEGORIES)]
    _aggregator_crawl_offset += 1

    async with _web_rate_limiter:
        now = time.time()
        wait = 6.0 - (now - _last_web_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_web_request = time.time()

    list_url = f"https://www.telegram-groups.com/{cat}-telegram-groups/"
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            c.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            r = await c.get(list_url)
            if r.status_code != 200:
                return None

            # Extract listing IDs with their member counts from listing page HTML
            listings_subs = {}
            for m in re.finditer(r'/([\w-]+)/listing/([a-f0-9]+)/', r.text):
                cat2, lid = m.group(1), m.group(2)
                start = max(0, m.start() - 150)
                end = min(len(r.text), m.end() + 250)
                context = r.text[start:end]
                mem = re.search(r'👥\s*([\d,]+)', context)
                subs = int(mem.group(1).replace(',','')) if mem else 0
                if lid not in listings_subs or subs > listings_subs[lid][1]:
                    listings_subs[lid] = (cat2, subs)

            # Sort by subscriber count descending, filter 50+
            ranked = [(lid, cat2, subs) for lid, (cat2, subs) in listings_subs.items() if subs >= 50]
            ranked.sort(key=lambda x: -x[2])
            if not ranked:
                logger(f"  Aggregator {cat}: no listings with 50+ members")
                return None

            logger(f"  Aggregator {cat}: {len(ranked)} listings with 50+ subs, best={ranked[0][2]:,}")
            for lid, cat2, subs in ranked[:15]:
                detail_url = f"https://www.telegram-groups.com/{cat2}/listing/{lid}/"
                try:
                    r2 = await c.get(detail_url)
                    if r2.status_code != 200:
                        continue
                    for m in re.finditer(r't\.me/([a-zA-Z0-9_]{3,})', r2.text):
                        uname = _clean_username(m.group(1))
                        if uname and uname not in exclude_set:
                            logger(f"  Aggregator found {uname} ({cat}, {subs:,} subs)")
                            if await _check_chat_via_tme_s(uname, logger):
                                return uname
                            return uname
                except Exception:
                    continue
            return None

    except Exception as e:
        logger(f"  Aggregator crawl error: {e}")
        return None


async def _search_telegram_global(client, exclude_set, logger):
    """Search Telegram via SearchGlobalRequest with groups_only=True.
    Uses `result.chats` directly to avoid redundant get_entity calls."""
    keywords = [
        # English gaming
        "games", "gaming", "game", "mmorpg", "rpg", "craft",
        "survival", "steam", "minecraft", "gta", "pubg",
        "mobile games", "game discussion",
        "mmo", "clan", "guild", "online games",
        "gamer chat", "gaming community", "game lovers",
        "multiplayer", "coop games", "sandbox",
        "indie games", "game dev", "game design",
        # Popular games
        "dota 2", "csgo", "cs2", "valorant", "fortnite",
        "roblox", "terraria", "stardew valley", "factorio",
        "rust", "dayz", "arksurvival", "warcraft",
        "world of warcraft", "wow", "league of legends",
        "overwatch", "apex legends", "team fortress",
        "euro truck", "simulator", "hearts of iron",
        # Russian gaming
        "игры", "гейминг", "игровой чат", "игровое сообщество",
        "online игры", "компьютерные игры",
        "видеоигры", "обсуждение игр", "геймеры",
        "игровой сервер", "кланы", "гильдия",
        "сервер майнкрафт", "майнкрафт чат",
        "дота 2", "кс го", "кс2", "каэска",
        "варфейс", "world of tanks", "wot",
        "танки онлайн", "world of warships",
        "steam игры", "пиратка", "торренты игр",
        # Game genres in Russian
        "ролевые игры", "стратегии", "шутеры",
        "выживание", "песочница", "хоррор игры",
        "гонки", "симуляторы", "ферма",
        "пошаговые стратегии", "градостроительные симуляторы",
        # Communities
        "game night", "game party", "игровая ночь",
        "team up", "поиск команды", "поиск сокомандников",
        "своя игра", "настольные игры online",
        "discord сервер", "discord игры",
        # RPG specific
        "dungeons", "dragons", "fantasy rpg",
        "text rpg", "текстовый квест", "text quest",
        "mmo rpg", "браузерные игры", "online rpg",
        # Tech gaming
        "game optimization", "настройка игр",
        "игровой компьютер", "сборка пк",
        "fps", "benchmark", "игровая производительность",
    ]
    random.shuffle(keywords)
    for kw in keywords:
        try:
            result = await client(SearchGlobalRequest(
                q=kw,
                filter=InputMessagesFilterEmpty(),
                groups_only=True,
                offset_rate=0,
                offset_peer=InputPeerEmpty(),
                offset_id=0,
                limit=100,
                min_date=0,
                max_date=0,
            ))
            # Collect unique usernames from result.chats
            seen = set()
            candidates = []
            chats = getattr(result, 'chats', [])
            if not chats and hasattr(result, 'messages'):
                # Extract from messages if chats is missing
                for msg in result.messages[:30]:
                    try:
                        entity = await client.get_entity(msg.peer_id)
                        if entity: chats.append(entity)
                    except Exception:
                        continue

            for chat in chats:
                username = getattr(chat, 'username', None)
                if not username:
                    continue
                # Skip broadcast channels (news, announcements, etc.)
                if getattr(chat, 'broadcast', False):
                    continue
                # Prefer megagroups (true groups) over non-megagroup channels
                is_group = getattr(chat, 'megagroup', False)
                link = f"@{username}"
                if link in exclude_set or link in seen:
                    continue
                seen.add(link)
                candidates.append((link, is_group))

            if candidates:
                # Sort: groups first, then channels
                candidates.sort(key=lambda x: -x[1])
                result = candidates[0][0]
                logger(f"  TG Global: {result} ({'group' if candidates[0][1] else 'channel'})")
                if len(candidates) > 1:
                    extra = ', '.join(c[0] for c in candidates[1:6])
                    logger(f"    also: {extra}")
                return result

            await asyncio.sleep(0.5)
        except FloodWaitError as e:
            if e.seconds < 600:
                logger(f"  Flood wait {e.seconds}s, waiting...")
                await asyncio.sleep(e.seconds + 5)
            else:
                return None
        except Exception as e:
            logger(f"  TG global search error for '{kw}': {e}")
            continue
    return None


async def _check_subs_logged(client, link: str, logger) -> bool:
    """Check subs, log result. Skip broadcast channels and users."""
    try:
        entity = await client.get_entity(link)
        subs = getattr(entity, "participants_count", 0) or 0
        etype = type(entity).__name__

        # Skip broadcast channels (non-megagroup channels)
        if hasattr(entity, 'broadcast') and entity.broadcast:
            logger(f"  {link} — {etype}, subs={subs}, SKIP (broadcast channel)")
            return False

        # Skip users (not chats)
        if hasattr(entity, 'bot') or (hasattr(entity, 'photo') and not hasattr(entity, 'participants_count')):
            logger(f"  {link} — {etype}, SKIP (user, not a chat)")
            return False

        logger(f"  {link} — {etype}, subs={subs}")
        if subs >= 20:
            return True
        logger(f"  {link} — too small ({subs} subs) or no participant count")
        return True  # try anyway — 0 may mean no access
    except Exception as e:
        logger(f"  {link} — entity error: {e}")
        return True  # try anyway on error


async def _search_via_searchee_bot(client, exclude_set, logger):
    """Search chats via @SearcheeBot inline query (backed by TGStat data).
    Returns first valid t.me link not in exclude_set."""
    queries = [
        "игры", "гейминг", "майнкрафт", "дота", "mmorpg",
        "game", "gaming", "rpg", "survival", "craft",
        "игровой чат", "игровое сообщество", "steam", "minecraft",
        "online игры", "геймеры", "discord", "pubg", "cs", "gta",
    ]
    kw = random.choice(queries)
    try:
        results = await client.inline_query("@SearcheeBot", kw)
        usernames = []
        for r in results:
            desc = r.description or ''
            m = re.match(r'@([a-zA-Z0-9_]{3,})', desc.strip())
            if m:
                uname = _clean_username(m.group(1))
                if uname and uname not in exclude_set:
                    usernames.append(uname)
                    if len(usernames) >= 3:
                        break
        if usernames:
            logger(f"  SearcheeBot found {len(usernames)} for '{kw}'")
            return usernames[0]
        logger(f"  SearcheeBot: no results for '{kw}'")
        return None
    except Exception as e:
        logger(f"  SearcheeBot error: {e}")
        return None


async def discover_new_chat(client, exclude_set, logger):
    """Search for a Telegram chat with 50+ subs, not in exclude_set.
    Phase 1: SearcheeBot inline query (TGStat, real group data).
    Phase 2: SearchGlobalRequest with groups_only=True (native Telegram search).
    Phase 3: telegram-groups.com aggregator crawl (with 50+ member filter).
    Phase 4: DuckDuckGo web search (last resort)."""
    logger("  Phase 1: SearcheeBot (TGStat)...")
    link = await _search_via_searchee_bot(client, exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    elif link:
        logger(f"  Phase 1 failed for {link}")

    logger("  Phase 2: Telegram global search (groups only)...")
    link = await _search_telegram_global(client, exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    elif link:
        logger(f"  Phase 2 failed for {link}")

    logger("  Phase 3: Aggregator sites...")
    link = await _crawl_aggregator(exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    elif link:
        logger(f"  Phase 3 failed for {link}")

    logger("  Phase 4: DuckDuckGo...")
    link = await _search_via_duckduckgo(exclude_set, logger)
    if link and await _check_subs_logged(client, link, logger):
        return link
    return None

# ─── Phase 1: JOIN (with staggered start) ────────────────────────────────────

async def join_account_chats(acc_name, chat_list, api_id, api_hash, join_map, logger, stop_event):
    session_path = os.path.abspath(f"./sessions/{acc_name}")
    client = TelegramClient(session_path, api_id, api_hash)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger(f"[{acc_name}] NOT AUTHORIZED, skipping joins")
            return
        for batch_num, chat in enumerate(chat_list):
            if stop_event.is_set():
                break
            ok = await safe_join(client, acc_name, chat, logger)
            if ok:
                join_map[chat] = acc_name
                with open(JOIN_MAP_FILE, "w", encoding="utf-8") as f:
                    json.dump(join_map, f, ensure_ascii=False, indent=2)
            delay = random.randint(10, 20)
            logger(f"[{acc_name}] Next join in {delay} min...")
            stopped = await sleep_with_progress(delay, f"[{acc_name}] Join cooldown", logger, stop_event, interval=5)
            if stopped:
                break
            if (batch_num + 1) % 5 == 0:
                break_hours = random.randint(2, 4)
                logger(f"[{acc_name}] {batch_num+1} joins done. Break {break_hours}h...")
                stopped = await sleep_with_progress(break_hours * 60, f"[{acc_name}] Long break", logger, stop_event, interval=30)
                if stopped:
                    break
    finally:
        await client.disconnect()

async def phase_join(chats, authorized, api_id, api_hash, logger, stop_event):
    join_map = {}
    total = len(chats)
    acc_count = len(authorized)

    logger(f"=== Phase 1: JOIN. {total} chats, {acc_count} accounts ===")

    acc_chats = {acc: [] for acc in authorized}
    for idx, chat in enumerate(chats):
        acc = authorized[idx % acc_count]
        acc_chats[acc].append(chat)

    for acc, chat_list in acc_chats.items():
        logger(f"  {acc}: {len(chat_list)} chats")

    # Staggered start: launch tasks with delays between them
    tasks = []
    for acc, chat_list in acc_chats.items():
        if not chat_list:
            continue
        task = asyncio.create_task(join_account_chats(acc, chat_list, api_id, api_hash, join_map, logger, stop_event))
        tasks.append(task)
        stagger_minutes = random.randint(3, 10)
        logger(f"  Stagger: next account starts in {stagger_minutes} min")
        stopped = await sleep_with_progress(stagger_minutes, "Stagger delay", logger, stop_event, interval=1)
        if stopped:
            break

    await asyncio.gather(*tasks, return_exceptions=True)

    logger(f"=== Phase 1 done: {len(join_map)} chats joined ===")
    return join_map

# ─── Phase 2: CHAT (organic participation + on-the-fly discovery) ──────────────

async def phase_chat(client_pool, logger, stop_event):
    """
    Each account independently maintains up to 10 chat slots.
    - Polls existing chats for relevant messages → responds organically
    - If a slot is empty or the chat is dead → discovers a new chat via SearchGlobalRequest
    - Claims the chat in SQLite DB (no duplicates across accounts)
    """
    own_usernames = await get_own_usernames(client_pool)
    init_db()
    max_slots = 10

    logger(f"=== CHAT mode: {len(client_pool)} accounts, {max_slots} slots each ===")

    last_action: dict = {}
    last_chat_action: dict = {}
    last_poll: dict = {}
    poll_errors: dict = {}  # track consecutive poll failures per chat

    def is_write_error(e: Exception) -> bool:
        err = str(e).lower()
        return any(x in err for x in [
            "you can't write", "no write permission", "premium required",
            "payment_required", "broadcast", "channel", "user is restricted",
            "chat write forbidden", "not enough rights",
        ])

    async def ensure_subscribed(entity, name, client):
        """If entity has a linked channel, join it (required for write in many groups)."""
        try:
            linked_id = getattr(entity, 'linked_chat_id', None)
            if linked_id:
                try:
                    linked = await client.get_entity(linked_id)
                    if hasattr(linked, 'username') and linked.username:
                        from telethon.tl.functions.channels import JoinChannelRequest
                        await client(JoinChannelRequest(linked))
                        logger(f"[{name}] Joined linked channel @{linked.username}")
                except Exception as e:
                    if "already" in str(e).lower():
                        pass  # already joined, fine
                    else:
                        logger(f"[{name}] Linked channel join: {e}")
        except Exception:
            pass

    async def try_intro(chat_link, name, client, own_usernames_set):
        """Send first message in a newly claimed chat. Uses Gemini for context, fallback to template."""
        try:
            entity = await client.get_entity(chat_link)
            if hasattr(entity, 'broadcast') and entity.broadcast:
                logger(f"[{name}] {chat_link} is broadcast, releasing")
                return False
            await ensure_subscribed(entity, name, client)
            recent = await client.get_messages(entity, limit=5)
            target_msg = next((m for m in recent if m and m.text and not m.out and not should_ignore_sender(m, own_usernames_set)), None)
            await asyncio.sleep(random.randint(15, 45))
            if target_msg:
                context_lines = []
                for m in recent[:5]:
                    if m and m.text:
                        if m.out:
                            context_lines.append(f"я: {m.text}")
                        elif not should_ignore_sender(m, own_usernames_set):
                            nt = getattr(m.sender, 'first_name', 'пользователь') or 'пользователь'
                            context_lines.append(f"{nt}: {m.text}")
                ctx = "\n".join(context_lines)
                reply = await generate_gemini_response(ctx)
                if not reply:
                    reply = random.choice(ORGANIC_RESPONSES)
                await client.send_message(entity, reply, reply_to=target_msg)
                logger(f"[{name}] Gemini intro in {chat_link}")
            else:
                intro = f"Кто играл в {random.choice(['Synthesis game bot', 'Synth game бот', 'Synthesis game'])}, норм крафт?"
                await client.send_message(entity, intro)
                logger(f"[{name}] Intro question in {chat_link}")
            update_last_active(chat_link)
            return True
        except Exception as e:
            if is_write_error(e):
                logger(f"[{name}] Can't write in {chat_link}: {e}")
                return False
            logger(f"[{name}] Intro error in {chat_link}: {e}")
            return True

    async def account_loop(name, client, discovery_semaphore):
        logger(f"[{name}] Starting...")
        cycle_count = 0
        while not stop_event.is_set():
            cycle_count += 1

            # ── 0. Night mode: sleep until morning ──────────────────────────
            while not is_daytime() and not stop_event.is_set():
                logger(f"[{name}] Night time, sleeping 30 min...")
                for _ in range(1800):
                    if stop_event.is_set() or is_daytime():
                        break
                    await asyncio.sleep(1)

            # ── 1. Long break every 5 cycles ────────────────────────────────
            if cycle_count > 1 and cycle_count % 5 == 0:
                break_hours = random.uniform(1.5, 3)
                logger(f"[{name}] Long break {break_hours:.1f}h (cycle {cycle_count})...")
                for _ in range(int(break_hours * 3600)):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)

            # ── 2. Daily limit check ────────────────────────────────────────
            daily = get_daily_count(name)
            if daily >= DAILY_MESSAGE_LIMIT:
                logger(f"[{name}] Daily limit {DAILY_MESSAGE_LIMIT} reached, skipping cycle")
                for _ in range(3600):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)
                continue

            # ── 3. 25% chance to skip (human is busy) ───────────────────────
            if random.random() < 0.25:
                logger(f"[{name}] Skipping cycle (human break)")
                for _ in range(random.randint(300, 600)):
                    if stop_event.is_set():
                        return
                    await asyncio.sleep(1)
                continue

            # ── 4. @spambot check every 10 cycles ───────────────────────────
            if cycle_count % 10 == 0:
                ok = await check_spambot(client, name, logger)
                if not ok:
                    logger(f"[{name}] Account restricted! Sleeping 2h...")
                    for _ in range(7200):
                        if stop_event.is_set():
                            return
                        await asyncio.sleep(1)
                    continue

            my_chats = get_account_chats(name)

            # ── Phase A: Fill empty slots via discovery ────────────────────
            if len(my_chats) < max_slots:
                needed = max_slots - len(my_chats)
                logger(f"[{name}] {len(my_chats)}/{max_slots} slots, discovering {needed}...")
                exclude = get_all_claimed()
                for _ in range(needed):
                    if stop_event.is_set():
                        return
                    async with discovery_semaphore:
                        new_chat = await discover_new_chat(client, exclude, logger)
                    if not new_chat:
                        logger(f"[{name}] No more chats found this cycle")
                        break
                    ok = claim_chat(new_chat, name)
                    if not ok:
                        continue
                    exclude.add(new_chat)
                    my_chats.append(new_chat)
                    await safe_join(client, name, new_chat, logger)
                    await asyncio.sleep(human_delay(20, 60))
                    intro_ok = await try_intro(new_chat, name, client, own_usernames)
                    if not intro_ok:
                        logger(f"[{name}] Releasing {new_chat} (can't write)")
                        release_chat(new_chat)
                        my_chats = get_account_chats(name)
                        await asyncio.sleep(human_delay(30, 90))
                        continue
                    increment_daily_count(name)
                    await asyncio.sleep(human_delay(120, 300))

            # ── Phase B: Poll existing chats for organic replies ───────────
            my_chats = get_account_chats(name)
            random.shuffle(my_chats)
            for chat_link in my_chats:
                if stop_event.is_set():
                    return

                now = time.time()
                if now - last_poll.get(chat_link, 0) < random.randint(300, 480):
                    continue
                last_poll[chat_link] = now

                try:
                    entity = await client.get_entity(chat_link)
                    messages = await client.get_messages(entity, limit=10)
                except Exception as e:
                    logger(f"[{name}] Poll error {chat_link}: {e}")
                    poll_errors[chat_link] = poll_errors.get(chat_link, 0) + 1
                    if poll_errors[chat_link] >= 3:
                        logger(f"[{name}] Releasing {chat_link} (3+ poll errors)")
                        release_chat(chat_link)
                    continue

                poll_errors[chat_link] = 0

                target_msg = None
                for msg in messages:
                    if not msg or not msg.text:
                        continue
                    if msg.out:
                        continue
                    if should_ignore_sender(msg, own_usernames):
                        continue
                    if is_message_relevant(msg.text):
                        target_msg = msg
                        break

                if target_msg:
                    if now - last_action.get(name, 0) < 300:
                        continue
                    if now - last_chat_action.get(entity.id, 0) < 1800:
                        continue
                    if random.random() > 0.4:
                        continue

                    last_action[name] = now
                    last_chat_action[entity.id] = now
                    update_last_active(chat_link)
                    increment_daily_count(name)

                    context_lines = []
                    for m in messages[:5]:
                        if m and m.text:
                            if m.out:
                                context_lines.append(f"я: {m.text}")
                            elif not should_ignore_sender(m, own_usernames):
                                name_tag = getattr(m.sender, 'first_name', 'пользователь') or 'пользователь'
                                context_lines.append(f"{name_tag}: {m.text}")
                    context_text = "\n".join(context_lines)

                    await asyncio.sleep(human_delay(5, 25))
                    await ensure_subscribed(entity, name, client)
                    try:
                        response = await generate_gemini_response(context_text)
                        if not response:
                            response = random.choice(ORGANIC_RESPONSES)
                        ok = await split_and_send(client, entity, response, logger, name, reply_to=target_msg)
                        if not ok:
                            await client.send_message(entity, response, reply_to=target_msg)
                        logger(f"[{name}] Replied in {chat_link}")
                    except Exception as e:
                        logger(f"[{name}] Reply error: {e}")
                        if is_write_error(e):
                            logger(f"[{name}] Releasing {chat_link} (write blocked)")
                            release_chat(chat_link)

            # ── Phase C: Gemini natural reply (3% per cycle) ──────────────────
            my_chats = get_account_chats(name)
            if my_chats and not stop_event.is_set() and random.random() < 0.03:
                target = random.choice(my_chats)
                try:
                    entity = await client.get_entity(target)
                    if hasattr(entity, 'broadcast') and entity.broadcast:
                        continue
                    recent = await client.get_messages(entity, limit=5)
                    last_msg = next((m for m in recent if m and m.text and not m.out and not should_ignore_sender(m, own_usernames)), None)
                    if not last_msg:
                        continue
                    spammy = ["заработк", "доход", "инвестици", "пассивн", "дополнительн", "финанс", "деньги", "заработок", "work", "earn", "money"]
                    if any(s in last_msg.text.lower() for s in spammy):
                        continue
                    context_lines = []
                    for m in recent[:5]:
                        if m and m.text:
                            if m.out:
                                context_lines.append(f"я: {m.text}")
                            elif not should_ignore_sender(m, own_usernames):
                                name_tag = getattr(m.sender, 'first_name', 'пользователь') or 'пользователь'
                                context_lines.append(f"{name_tag}: {m.text}")
                    ctx = "\n".join(context_lines)
                    await asyncio.sleep(human_delay(10, 60))
                    await ensure_subscribed(entity, name, client)
                    reply = await generate_gemini_response(ctx)
                    if not reply:
                        reply = random.choice(ORGANIC_SMALLTALK)
                    increment_daily_count(name)
                    await client.send_message(entity, reply, reply_to=last_msg)
                    logger(f"[{name}] Gemini reply in {target}")
                except Exception:
                    pass

            # ── Wait before next cycle ──────────────────────────────────────
            wait = random.randint(300, 480)
            for _ in range(wait):
                if stop_event.is_set():
                    return
                await asyncio.sleep(1)

    discovery_semaphore = asyncio.Semaphore(2)

    async def account_loop_wrapper(name, client):
        # Stagger at start — each account begins 60-180s apart
        await asyncio.sleep(random.randint(60, 180))
        await account_loop(name, client, discovery_semaphore)

    tasks = [asyncio.create_task(account_loop_wrapper(name, client)) for name, client in client_pool.items()]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger("=== CHAT mode done ===")

# ─── Fallback: Legacy dialogue mode (with spintax + survival validation) ─────

async def run_dialogue_with_clients(client_a, name_a, client_b, name_b, chat_link, logger, stop_event):
    """Legacy Q&A dialogue between two controlled accounts."""
    question_text = render_spintax(QUESTION_SPINTAX)
    answer_text = render_spintax(ANSWER_SPINTAX)

    try:
        entity = await client_a.get_entity(chat_link)
        can_write = await check_can_write(client_a, chat_link, name_a, logger)
        if not can_write:
            return
        can_write = await check_can_write(client_b, chat_link, name_b, logger)
        if not can_write:
            return

        logger(f"--- Scene in {chat_link} | Actors: {name_a} & {name_b} ---")

        lurk_a = random.randint(15, 30)
        stopped = await sleep_with_progress(lurk_a, f"[{name_a}] Lurking before post", logger, stop_event)
        if stopped:
            return

        msg_a = await client_a.send_message(entity, question_text)
        logger(f"[{name_a}] Question posted.")

        delay = random.randint(15, 25)
        stopped = await sleep_with_progress(delay, f"[{name_b}] Waiting to reply", logger, stop_event)
        if stopped:
            return

        # Survival validation: check if question still exists
        try:
            msgs = await client_b.get_messages(entity, ids=msg_a.id)
            survived = msgs and len(msgs) > 0 and msgs[0] is not None
        except Exception:
            survived = False

        if not survived:
            logger(f"[{name_b}] Question was deleted (moderated). Skipping answer in {chat_link}")
            return

        await asyncio.sleep(random.randint(2, 5))
        await client_b.send_message(entity, answer_text, reply_to=msg_a)
        logger(f"[{name_b}] Reply posted.")

    except RPCError as e:
        err = str(e)
        if "PAYMENT_REQUIRED" in err:
            logger(f"[{chat_link}] Premium required, skipping.")
        elif "You can't write" in err:
            logger(f"[{chat_link}] No write permission, skipping.")
        elif "join the discussion group" in err:
            logger(f"[{chat_link}] Linked discussion group, skipping.")
        else:
            logger(f"Error in {chat_link}: {e}")
    except Exception as e:
        logger(f"Error in {chat_link}: {e}")

async def check_can_write(client, chat_link, name, logger):
    try:
        entity = await client.get_entity(chat_link)
        if hasattr(entity, 'broadcast') and entity.broadcast:
            logger(f"[{name}] {chat_link} is a channel, skipping")
            return False
        return True
    except Exception as e:
        logger(f"[{name}] Check error for {chat_link}: {e}")
        return False

async def phase_dialogue(join_map, client_pool, logger, stop_event):
    """Legacy dialogue mode (fallback)."""
    chat_accounts = list(join_map.items())
    total = len(chat_accounts)
    acc_names = list(client_pool.keys())

    logger(f"=== Phase 2: DIALOGUES (legacy mode). {total} chats ===")

    chat_index = 0
    while chat_index < total:
        if stop_event.is_set():
            break

        batch = []
        used_accounts = set()

        for chat, acc_name in chat_accounts[chat_index:]:
            if len(batch) >= len(acc_names) // 2:
                break
            if acc_name not in client_pool or acc_name in used_accounts:
                continue
            others = [a for a in acc_names if a != acc_name and a not in used_accounts and a in client_pool]
            if not others:
                continue
            other = random.choice(others)
            used_accounts.add(acc_name)
            used_accounts.add(other)
            batch.append((chat, client_pool[acc_name], acc_name, client_pool[other], other))
            chat_index += 1

        if not batch:
            logger("No more valid pairs found.")
            break

        logger(f"--- Running {len(batch)} dialogues sequentially with stagger ---")
        for chat, cl_a, name_a, cl_b, name_b in batch:
            if stop_event.is_set():
                break
            asyncio.create_task(run_dialogue_with_clients(cl_a, name_a, cl_b, name_b, chat, logger, stop_event))
            stagger = random.randint(30, 90)
            for _ in range(stagger):
                if stop_event.is_set():
                    break
                await asyncio.sleep(1)

        if stop_event.is_set() or chat_index >= total:
            break

        cooldown = random.randint(15, 25)
        await sleep_with_progress(cooldown, "Batch cooldown", logger, stop_event, interval=5)

# ─── Main ────────────────────────────────────────────────────────────────────

async def run_campaign(api_id, api_hash, logger, stop_event, mode="chat"):
    try:
        await _run_campaign(api_id, api_hash, logger, stop_event, mode)
    except Exception as e:
        import traceback
        logger(f"FATAL: {e}")
        for line in traceback.format_exc().splitlines():
            logger(line)

async def _run_campaign(api_id, api_hash, logger, stop_event, mode="chat"):
    """
    Run campaign.
    mode="chat" (default): on-the-fly discovery + organic replies, 10 slots per account.
    mode="dialogue": legacy Q&A scripted dialogues (requires chats.txt + join phase).
    """
    all_sessions = get_available_sessions()
    logger(f"Initializing {len(all_sessions)} clients...")
    client_pool = await init_client_pool(all_sessions, api_id, api_hash, logger)

    if len(client_pool) < 2:
        logger("Error: Need at least 2 authorized sessions.")
        await close_client_pool(client_pool)
        return

    if mode == "dialogue":
        # Legacy dialogue mode: requires chats.txt + join phase
        chats = load_chats()
        if not chats:
            logger("Dialogue mode requires chats.txt with chat list.")
            await close_client_pool(client_pool)
            return

        authorized = list(client_pool.keys())
        await close_client_pool(client_pool)
        client_pool = {}

        join_map = await phase_join(chats, authorized, api_id, api_hash, logger, stop_event)
        if stop_event.is_set():
            return

        logger("=== Phase 1 complete. Waiting 24 hours before Phase 2... ===")
        stopped = await sleep_with_progress(1440, "24h wait", logger, stop_event, interval=60)
        if stopped:
            return

        logger("Re-initializing client pool for Phase 2...")
        client_pool = await init_client_pool(authorized, api_id, api_hash, logger)
        if len(client_pool) < 2:
            logger("Error: Not enough valid sessions after wait.")
            await close_client_pool(client_pool)
            return

        await phase_dialogue(join_map, client_pool, logger, stop_event)
    else:
        # Chat mode: integrated discovery, no pre-loaded chats needed
        await phase_chat(client_pool, logger, stop_event)

    await close_client_pool(client_pool)
    logger("=== Campaign finished ===")
