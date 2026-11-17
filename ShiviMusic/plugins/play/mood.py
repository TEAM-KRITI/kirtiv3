# ===========================================================
# 🎭 MUSIC MOOD DETECTOR
#
# Categories : Sad 😢 | Romantic 🌹 | Love ❤️ | Party 🎉 | Bhakti 🙏
#
#   /mood               -> mood chunne ka panel
#   /mood sad           -> seedha Sad songs
#   /mood dil toot gaya -> text se mood detect (Hinglish / Hindi / English)
#
# Mood chunte hi usi mood ke 5 songs aate hain (tap = play).
#   🔄 More   -> naye songs (pehle dikhaye hue repeat nahi hote)
#   🎲 Random -> usi mood ka ek random song seedha play
#   ⬅ Moods   -> mood panel pe wapas
#
# Play button purane "RecPlay" callback ko hi use karta hai
# (plugins/play/recommend.py), isliye queue / thumb / logger sab
# normal /play jaisa hi chalta hai.
# ===========================================================

import asyncio
import random
import re
import traceback

from pyrogram import StopPropagation, filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardMarkup

import config
from ShiviMusic import app
from ShiviMusic.plugins.play.recommend import _play_vidid
from ShiviMusic.utils.formatters import time_to_seconds
from ShiviMusic.utils.recommend import (
    _BLUE,
    _RED,
    _btn,
    _search_many,
    _unique_songs,
    short_title,
)
from config import BANNED_USERS

SHOW_COUNT = 5  # ek baar me kitne songs dikhane hain
MIN_SEC = 60  # 1 min se chhota -> short/reel, skip
_SEEN_LIMIT = 200

# ---------------------------------------------------------------
# Mood data : label, emoji, YouTube search queries, keywords (detect ke liye)
# ---------------------------------------------------------------
MOODS = {
    "sad": {
        "emoji": "😢",
        "label": "sᴀᴅ",
        "queries": [
            "sad hindi songs",
            "dard bhare gaane hindi",
            "heartbreak songs hindi",
            "bewafa sad songs",
            "arijit singh sad songs",
            "emotional hindi songs",
            "breakup songs hindi",
        ],
        "max_min": 10,
        "words": (
            "sad", "udaas", "udas", "dukhi", "dukh", "dard", "dard bhare", "rona", "ro raha",
            "ro rahi", "toot", "tut gaya", "breakup", "heartbreak", "bewafa", "bewafai",
            "alone", "akela", "akeli", "tanha", "cry", "depressed", "yaad aa rahi",
            "उदास", "दुखी", "दर्द", "रोना", "टूट", "बेवफा", "अकेला", "अकेली", "तन्हा",
        ),
    },
    "romantic": {
        "emoji": "🌹",
        "label": "ʀᴏᴍᴀɴᴛɪᴄ",
        "queries": [
            "romantic hindi songs",
            "bollywood romantic songs",
            "arijit singh romantic songs",
            "romantic songs for couples hindi",
            "atif aslam romantic songs",
            "soft romantic hindi songs",
            "jubin nautiyal romantic songs",
        ],
        "max_min": 10,
        "words": (
            "romantic", "romance", "romantik", "date", "candle", "couple", "valentine",
            "dinner", "baarish", "barish", "rain", "mausam", "intezaar", "intezar",
            "रोमांटिक", "बारिश", "मौसम", "इंतज़ार", "इंतजार",
        ),
    },
    "love": {
        "emoji": "❤️",
        "label": "ʟᴏᴠᴇ",
        "queries": [
            "love songs hindi",
            "pyar bhare gaane",
            "hindi love songs 2024",
            "new love songs bollywood",
            "prem geet hindi",
            "tum hi ho love songs",
            "punjabi love songs",
        ],
        "max_min": 10,
        "words": (
            "love", "pyar", "pyaar", "pyar hua", "mohabbat", "ishq", "ishk", "dil", "dilbar",
            "crush", "gf", "bf", "girlfriend", "boyfriend", "jaan", "sanam", "mehboob",
            "प्यार", "प्रेम", "इश्क", "मोहब्बत", "दिल", "जान", "सनम",
        ),
    },
    "party": {
        "emoji": "🎉",
        "label": "ᴘᴀʀᴛʏ",
        "queries": [
            "party songs hindi",
            "bollywood party songs",
            "punjabi party songs",
            "dance songs hindi",
            "badshah party songs",
            "club songs hindi",
            "wedding dance songs bollywood",
        ],
        "max_min": 8,
        "words": (
            "party", "dance", "naach", "nach", "nachna", "dj", "masti", "mast", "dhamaal",
            "dhamaka", "club", "shaadi", "wedding", "baraat", "birthday", "celebrate",
            "enjoy", "khushi", "happy", "josh", "energy",
            "पार्टी", "डांस", "नाच", "मस्ती", "धमाल", "शादी", "बारात", "जश्न", "खुश",
        ),
    },
    "bhakti": {
        "emoji": "🙏",
        "label": "ʙʜᴀᴋᴛɪ",
        "queries": [
            "bhakti songs hindi",
            "bhajan hindi",
            "shiv bhajan",
            "krishna bhajan",
            "hanuman bhajan",
            "ram bhajan",
            "durga mata bhajan",
            "ganesh bhajan aarti",
        ],
        "max_min": 15,
        "words": (
            "bhakti", "bhajan", "bhagwan", "bhagwaan", "god", "ram", "shiv", "shiva", "krishna",
            "kanha", "hanuman", "durga", "mata", "ganesh", "sai", "aarti", "mandir", "pooja",
            "puja", "devotional", "jai", "mahadev", "bholenath", "navratri",
            "भक्ति", "भजन", "भगवान", "राम", "शिव", "कृष्ण", "हनुमान", "दुर्गा", "माता",
            "गणेश", "आरती", "मंदिर", "पूजा", "जय", "महादेव", "भोलेनाथ",
        ),
    },
}

# Pehle specific -> baad me general (love sabse last, kyunki 'dil' jaise words common hain)
_DETECT_ORDER = ("bhakti", "party", "sad", "romantic", "love")


def _has_word(text: str, w: str) -> bool:
    if w.isascii():
        return re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) is not None
    return w in text


def detect_mood(text: str):
    """Text se mood nikalo. Seedha naam (sad/party...) ho to wahi, warna keyword score."""
    text = (text or "").lower().strip()
    if not text:
        return None
    for key in MOODS:  # direct naam
        if text == key:
            return key
    best, best_score = None, 0
    for key in _DETECT_ORDER:
        score = sum(1 for w in MOODS[key]["words"] if _has_word(text, w))
        if score > best_score:  # tie me pehle wala (specific) jeet-ta hai
            best, best_score = key, score
    return best


# ---------------------------------------------------------------
# Songs laana
# ---------------------------------------------------------------
_SEEN: dict = {}  # (chat_id, mood) -> [vidid, ...]
_LOCKS: dict = {}


def _seen(chat_id: int, key: str) -> list:
    return _SEEN.setdefault((chat_id, key), [])


def _mark_seen(chat_id: int, key: str, tracks: list):
    lst = _seen(chat_id, key)
    lst.extend(t["vidid"] for t in tracks)
    del lst[:-_SEEN_LIMIT]


def _duration_ok(track: dict, max_min: int) -> bool:
    try:
        sec = time_to_seconds(track["duration_min"])
    except Exception:
        return False
    if sec < MIN_SEC or sec > max_min * 60:
        return False
    return sec <= getattr(config, "DURATION_LIMIT", 10**9)


async def fetch_mood_tracks(chat_id: int, key: str, count: int = SHOW_COUNT) -> list:
    data = MOODS[key]
    queries = random.sample(data["queries"], k=min(3, len(data["queries"])))
    pool = await _search_many(queries, None)  # region filter nahi: mood = poora Hindi/Punjabi mix
    pool = [t for t in pool if _duration_ok(t, data["max_min"])]
    pool = _unique_songs(pool)

    seen = set(_seen(chat_id, key))
    fresh = [t for t in pool if t["vidid"] not in seen]
    if len(fresh) < count:  # sab dekh liye -> history reset, dobara shuru
        _SEEN.pop((chat_id, key), None)
        fresh = pool
    head = fresh[: count * 3]
    random.shuffle(head)  # har baar thoda alag order
    return head[:count]


# ---------------------------------------------------------------
# UI
# ---------------------------------------------------------------
def moods_text(detected: str = None) -> str:
    line = ""
    if detected:
        d = MOODS[detected]
        line = f"\n<b>🎯 ᴅᴇᴛᴇᴄᴛᴇᴅ ᴍᴏᴏᴅ :</b> <code>{d['emoji']} {d['label']}</code>\n"
    return (
        "<b>❖ ᴍᴜsɪᴄ ᴍᴏᴏᴅ ᴅᴇᴛᴇᴄᴛᴏʀ</b>\n"
        "<blockquote>"
        "<b>🎭 ᴀᴀᴊ ᴋᴀ ᴍᴏᴏᴅ ᴄʜᴜɴᴏ, ᴡᴀɪsᴇ ʜɪ ɢᴀᴀɴᴇ ᴍɪʟᴇɴɢᴇ</b>"
        f"{line}"
        "</blockquote>"
    )


def moods_markup() -> InlineKeyboardMarkup:
    def b(k):
        d = MOODS[k]
        return _btn(f"{d['emoji']} {d['label']}", f"MoodPick {k}", _BLUE)

    return InlineKeyboardMarkup(
        [
            [b("sad"), b("romantic")],
            [b("love"), b("party")],
            [b("bhakti")],
            [_btn("ᴄʟᴏsᴇ", "close", _RED)],
        ]
    )


def list_text(key: str) -> str:
    d = MOODS[key]
    return (
        f"<b>{d['emoji']} {d['label']} ᴍᴏᴏᴅ sᴏɴɢs</b>\n"
        "<blockquote><b>💡 ᴛᴀᴘ ʙᴇʟᴏᴡ ᴛᴏ ᴘʟᴀʏ</b></blockquote>"
    )


def list_markup(key: str, tracks: list) -> InlineKeyboardMarkup:
    btns = [
        _btn(f"{i}. {short_title(t['title'], 16)}", f"RecPlay {t['vidid']}", _BLUE)
        for i, t in enumerate(tracks, 1)
    ]
    rows = [btns[i : i + 2] for i in range(0, len(btns), 2)]
    rows.append(
        [
            _btn("🔄 ᴍᴏʀᴇ", f"MoodPick {key}", _BLUE),
            _btn("🎲 ʀᴀɴᴅᴏᴍ", f"MoodRand {key}", _BLUE),
        ]
    )
    rows.append([_btn("⬅ ᴍᴏᴏᴅs", "MoodMenu", _BLUE)])
    rows.append([_btn("ᴄʟᴏsᴇ", "close", _RED)])
    return InlineKeyboardMarkup(rows)


async def _edit(msg, text: str, markup):
    await msg.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------
# /mood command
# ---------------------------------------------------------------
@app.on_message(filters.command(["mood", "moods"]) & ~BANNED_USERS)
async def mood_command(client, message):
    try:
        arg = " ".join(message.command[1:]).strip()
        key = detect_mood(arg) if arg else None
        if arg and not key:  # kuch likha par samajh nahi aaya -> panel dikhao
            return await message.reply_text(
                moods_text() + "\n<i>ᴍᴏᴏᴅ sᴀᴍᴀᴊʜ ɴᴀʜɪ ᴀᴀʏᴀ, ɴᴇᴇᴄʜᴇ sᴇ ᴄʜᴜɴᴏ 👇</i>",
                reply_markup=moods_markup(),
                parse_mode=ParseMode.HTML,
            )
        if not key:
            return await message.reply_text(
                moods_text(), reply_markup=moods_markup(), parse_mode=ParseMode.HTML
            )

        mystic = await message.reply_text(
            f"<b>{MOODS[key]['emoji']} {MOODS[key]['label']} ᴍᴏᴏᴅ ᴅᴇᴛᴇᴄᴛ ʜᴜᴀ, sᴏɴɢs ᴅʜᴜɴᴅ ʀᴀʜᴀ ʜᴜɴ...</b>",
            parse_mode=ParseMode.HTML,
        )
        tracks = await fetch_mood_tracks(message.chat.id, key)
        if not tracks:
            return await _edit(
                mystic,
                "<b>❌ ᴀʙʜɪ sᴏɴɢs ɴᴀʜɪ ᴍɪʟᴇ, ᴅᴏʙᴀʀᴀ ᴛʀʏ ᴋᴀʀᴏ.</b>",
                moods_markup(),
            )
        _mark_seen(message.chat.id, key, tracks)
        await _edit(mystic, list_text(key), list_markup(key, tracks))
    except Exception:
        traceback.print_exc()


# ---------------------------------------------------------------
# Buttons  (group=-1 + StopPropagation: purane unanchored regex
# handlers ("close", "LG" ...) beech me na aayein)
# ---------------------------------------------------------------
@app.on_callback_query(filters.regex(r"^MoodMenu$") & ~BANNED_USERS, group=-1)
async def mood_menu(client, cq):
    try:
        await cq.answer()
        await _edit(cq.message, moods_text(), moods_markup())
    except Exception:
        traceback.print_exc()
    raise StopPropagation


@app.on_callback_query(filters.regex(r"^MoodPick \w+$") & ~BANNED_USERS, group=-1)
async def mood_pick(client, cq):
    msg = cq.message
    try:
        key = cq.data.split(None, 1)[1].strip()
        if key not in MOODS:
            return await cq.answer("❌ ɢᴀʟᴀᴛ ᴍᴏᴏᴅ", show_alert=True)
        chat_id = msg.chat.id
        lock = _LOCKS.setdefault(chat_id, asyncio.Lock())
        if lock.locked():
            return await cq.answer("⏳ ʟᴏᴀᴅɪɴɢ ʜᴏ ʀᴀʜᴀ ʜᴀɪ, ʀᴜᴋᴏ...")
        async with lock:
            await cq.answer(f"{MOODS[key]['emoji']} ʟᴏᴀᴅɪɴɢ...")
            old_markup = msg.reply_markup
            try:
                await _edit(
                    msg,
                    f"<b>{MOODS[key]['emoji']} {MOODS[key]['label']} sᴏɴɢs ʟᴏᴀᴅ ʜᴏ ʀᴀʜᴇ ʜᴀɪɴ...</b>",
                    old_markup,
                )
            except Exception:
                pass
            tracks = await fetch_mood_tracks(chat_id, key)
            if not tracks:
                return await _edit(
                    msg, "<b>❌ sᴏɴɢs ɴᴀʜɪ ᴍɪʟᴇ, ᴅᴏʙᴀʀᴀ ᴛʀʏ ᴋᴀʀᴏ.</b>", moods_markup()
                )
            _mark_seen(chat_id, key, tracks)
            await _edit(msg, list_text(key), list_markup(key, tracks))
    except Exception:
        traceback.print_exc()
    raise StopPropagation


@app.on_callback_query(filters.regex(r"^MoodRand \w+$") & ~BANNED_USERS, group=-1)
async def mood_random(client, cq):
    try:
        key = cq.data.split(None, 1)[1].strip()
        if key not in MOODS:
            return await cq.answer("❌ ɢᴀʟᴀᴛ ᴍᴏᴏᴅ", show_alert=True)
        tracks = await fetch_mood_tracks(cq.message.chat.id, key, count=1)
        if not tracks:
            return await cq.answer("❌ ᴛʀᴀᴄᴋ ɴᴀʜɪ ᴍɪʟᴀ", show_alert=True)
        _mark_seen(cq.message.chat.id, key, tracks)
        await _play_vidid(cq, tracks[0]["vidid"], f"Mood ({MOODS[key]['label']})")
    except Exception:
        traceback.print_exc()
    raise StopPropagation
