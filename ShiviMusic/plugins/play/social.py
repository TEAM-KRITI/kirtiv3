# ===========================================================
# 👥 MUSIC PROFILE + FRIENDS  (Profile song / Dusre ki playlist / Share)
#
# 1) Favourite Song on Profile
#   /setprofilesong [song name | link]  -> profile pe favourite song lagao
#                                          (bina naam ke = abhi baj raha gaana)
#   /delprofilesong                     -> profile song hatao
#   /profile (/myprofile)               -> apna music profile
#   /profile @user  (ya reply karke)    -> dusre ka music profile
#
# 2) Dusre user ki Playlist sunna
#   /userplaylist @user (ya reply)      -> uski playlists dekho, gaana bajao,
#                                          Play All / Shuffle, ❤️ se apne fav me save
#   /playlistprivacy [public|private]   -> apni playlists dusron ko dikhani hain ya nahi
#                                          (default: public)
#
# 3) Friends ke saath Songs Share
#   /share [@user] [song name | link]   -> song share (bina naam ke = abhi baj raha)
#                                          reply karke bhi: dost ke message pe /share
#   /sharepl <playlist name> [@user]    -> apni playlist share (private ho tab bhi,
#                                          jisko share karo wo khol sakta hai)
#
# Share card me: ▶ Play  |  ❤️ Save to my favourites
# Dost ne bot start kiya hai to usko DM me bhi card jata hai.
# Gaana bajane ke liye group chahiye (VC), baaki sab private me bhi chalta hai.
# ===========================================================

import random
import traceback

from pyrogram import StopPropagation, enums, filters
from pyrogram.types import InlineKeyboardButton as Btn
from pyrogram.types import InlineKeyboardMarkup as Markup

from ShiviMusic import app
from ShiviMusic.misc import SUDOERS
from ShiviMusic.plugins.play.favourites import (
    PAGE,
    _arg,
    _clamp,
    _current_song,
    _edit,
    _esc,
    _pages,
    _play_from_callback,
    _resolve,
    _song_lines,
    short_title,
)
from ShiviMusic.utils.database import (
    add_fav,
    clear_profile_song,
    create_share,
    find_user_playlist_by_name,
    get_favs,
    get_profile,
    get_share,
    get_user_playlist,
    get_user_playlists,
    set_playlists_private,
    set_profile_song,
)
from config import BANNED_USERS

HTML = enums.ParseMode.HTML
CLOSE_ROW = [Btn("• ᴄʟᴏsᴇ •", callback_data="close")]

_SAVE_TXT = {
    "added": "❤️ Tumhare favourites me add ho gaya!",
    "exists": "ℹ️ Ye pehle se tumhare favourites me hai.",
    "full": "❌ Tumhare favourites full hain.",
}


# ===========================================================
# HELPERS
# ===========================================================

def _uname(u) -> str:
    return _esc((getattr(u, "first_name", None) or "User")[:40])


def _ulink(u) -> str:
    return f'<a href="tg://user?id={u.id}">{_uname(u)}</a>'


async def _get_user(ref):
    try:
        return await app.get_users(ref)
    except Exception:
        return None


async def _split_target(message):
    """Command ke arg se target user nikalo.
    -> (user | None, bacha hua text, error_text | None)
    Reply ho to replied user; warna pehla word @username / numeric id ho to wo."""
    text = _arg(message)
    rep = message.reply_to_message
    if rep and rep.from_user and not rep.from_user.is_bot:
        return rep.from_user, text, None
    first, _sep, rest = text.partition(" ")
    if first.startswith("@") or (first.isdigit() and len(first) >= 6):
        user = await _get_user(int(first) if first.isdigit() else first)
        if not user:
            return None, rest.strip(), (
                "❌ User nahi mila. Ya to usne bot ko kabhi start nahi kiya, ya username galat hai.\n"
                "Dost ke message pe <b>reply</b> karke command try karo."
            )
        return user, rest.strip(), None
    return None, text, None


async def _can_view(owner_id: int, viewer_id: int, bypass: bool = False) -> bool:
    if bypass or owner_id == viewer_id or viewer_id in SUDOERS:
        return True
    prof = await get_profile(owner_id)
    return not prof.get("pl_private", False)


def _owner_name_cache(owner) -> str:
    return _uname(owner) if owner else "User"


# ===========================================================
# PANELS
# ===========================================================

async def profile_panel(owner, viewer_id: int):
    """(text, markup) - owner ka music profile."""
    uid = owner.id
    prof = await get_profile(uid)
    song = prof.get("song")
    pls = await get_user_playlists(uid)
    favs = await get_favs(uid)
    private = prof.get("pl_private", False)
    mine = uid == viewer_id

    song_line = (
        f"{_esc(song['title'][:50])} <code>{_esc(song['dur'])}</code>"
        if song
        else "<i>ᴀʙʜɪ sᴇᴛ ɴᴀʜɪ</i>"
    )
    pl_state = "🔒 ᴘʀɪᴠᴀᴛᴇ" if private else "🌐 ᴘᴜʙʟɪᴄ"
    text = (
        f"<b>👤 {_uname(owner)} ᴋɪ ᴍᴜsɪᴄ ᴘʀᴏꜰɪʟᴇ</b>\n"
        "<blockquote>"
        f"<b>🎵 ꜰᴀᴠᴏᴜʀɪᴛᴇ sᴏɴɢ :</b> {song_line}\n"
        f"<b>📂 ᴘʟᴀʏʟɪsᴛs :</b> <code>{len(pls)}</code> • {pl_state}\n"
        f"<b>❤️ ꜰᴀᴠᴏᴜʀɪᴛᴇs :</b> <code>{len(favs)}</code>"
        "</blockquote>"
    )
    if mine and not song:
        text += "\n<b>💡</b> <code>/setprofilesong song name</code> se favourite song lagao."
    if mine:
        text += "\n<b>🔐</b> <code>/playlistprivacy private</code> / <code>public</code>"

    rows = []
    if song:
        row = [Btn("▶ ᴘʟᴀʏ sᴏɴɢ", callback_data=f"PfSong {uid}")]
        if not mine:
            row.append(Btn("❤️ sᴀᴠᴇ", callback_data=f"PfFav {uid}|-|{song['vidid']}|0"))
        rows.append(row)
    if pls:
        if private and not mine and viewer_id not in SUDOERS:
            rows.append([Btn("🔒 ᴘʟᴀʏʟɪsᴛs ᴘʀɪᴠᴀᴛᴇ ʜᴀɪɴ", callback_data="FavN 0")])
        else:
            rows.append([Btn(f"📂 ᴘʟᴀʏʟɪsᴛs ({len(pls)})", callback_data=f"PfPls {uid}|0")])
    rows.append(CLOSE_ROW)
    return text, Markup(rows)


def others_playlists_panel(owner, pls: list, bypass: bool = False):
    b = 1 if bypass else 0
    uid = owner.id
    text = f"<b>📂 {_uname(owner)} ᴋɪ ᴘʟᴀʏʟɪsᴛs</b> <code>({len(pls)})</code>\n\n"
    if not pls:
        text += "<blockquote>Koi playlist nahi hai.</blockquote>"
    else:
        text += "<blockquote>" + "\n".join(
            f"<b>{i}.</b> {_esc(p['name'])} <code>({len(p['songs'])})</code>"
            for i, p in enumerate(pls, 1)
        ) + "</blockquote>"
    rows = [
        [Btn(f"📂 {p['name'][:24]} ({len(p['songs'])})", callback_data=f"PfPl {uid}|{p['id']}|0|{b}")]
        for p in pls
    ]
    rows.append([Btn("⬅ ᴘʀᴏꜰɪʟᴇ", callback_data=f"PfView {uid}")])
    rows.append(CLOSE_ROW)
    return text, Markup(rows)


def _nav(prefix: str, page: int, pages: int, b: int):
    if pages <= 1:
        return None
    row = []
    if page > 0:
        row.append(Btn("⬅", callback_data=f"{prefix}|{page - 1}|{b}"))
    row.append(Btn(f"{page + 1}/{pages}", callback_data="FavN 0"))
    if page < pages - 1:
        row.append(Btn("➡", callback_data=f"{prefix}|{page + 1}|{b}"))
    return row


def others_playlist_panel(owner, pl: dict, page: int = 0, bypass: bool = False):
    b = 1 if bypass else 0
    uid = owner.id
    songs = pl["songs"]
    page = _clamp(page, len(songs))
    text = f"<b>📂 {_esc(pl['name'])}</b> <i>({_uname(owner)})</i> <code>({len(songs)})</code>\n\n"
    if songs:
        text += f"<blockquote expandable>{_song_lines(songs, page)}</blockquote>"
    else:
        text += "<blockquote>Playlist khali hai.</blockquote>"

    rows = []
    for s in songs[page * PAGE : (page + 1) * PAGE]:
        rows.append(
            [
                Btn(f"▶ {short_title(s['title'], 26)}", callback_data=f"PfPlay {uid}|{pl['id']}|{s['vidid']}|{b}"),
                Btn("❤️", callback_data=f"PfFav {uid}|{pl['id']}|{s['vidid']}|{b}"),
            ]
        )
    nav = _nav(f"PfPl {uid}|{pl['id']}", page, _pages(len(songs)), b)
    if nav:
        rows.append(nav)
    if songs:
        rows.append(
            [
                Btn("▶ ᴘʟᴀʏ ᴀʟʟ", callback_data=f"PfAll {uid}|{pl['id']}|0|{b}"),
                Btn("🔀 sʜᴜꜰꜰʟᴇ", callback_data=f"PfAll {uid}|{pl['id']}|1|{b}"),
            ]
        )
    if not bypass:
        rows.append([Btn("⬅ ʙᴀᴄᴋ", callback_data=f"PfPls {uid}|{b}")])
    rows.append(CLOSE_ROW)
    return text, Markup(rows)


# ===========================================================
# COMMANDS — profile song
# ===========================================================

@app.on_message(filters.command(["setprofilesong", "setmysong", "profilesong"]) & ~BANNED_USERS)
async def setprofilesong_cmd(client, message):
    if not message.from_user:
        return
    query = _arg(message)
    if not query:
        song = _current_song(message.chat.id)
        if not song:
            return await message.reply_text(
                "ℹ️ Usage: <code>/setprofilesong song name</code> ya link.\n"
                "Ya gaana bajte waqt bina naam ke <code>/setprofilesong</code> likho.",
                parse_mode=HTML,
            )
        mystic = None
    else:
        mystic = await message.reply_text("🔎 ᴅʜᴜɴᴅ ʀᴀʜᴀ ʜᴏᴏɴ...")
        try:
            song = await _resolve(query)
        except Exception:
            return await mystic.edit_text("❌ Gaana nahi mila. Naam ya YouTube link check karo.")
    await set_profile_song(message.from_user.id, song)
    text = (
        f"🎵 <b>{_esc(song['title'][:60])}</b> ab tumhare profile ka favourite song hai!\n"
        "Dekhne ke liye: <code>/profile</code>"
    )
    if mystic:
        await mystic.edit_text(text, parse_mode=HTML)
    else:
        await message.reply_text(text, parse_mode=HTML)


@app.on_message(filters.command(["delprofilesong", "removeprofilesong"]) & ~BANNED_USERS)
async def delprofilesong_cmd(client, message):
    if not message.from_user:
        return
    await clear_profile_song(message.from_user.id)
    await message.reply_text("🗑 Profile song hata diya.")


@app.on_message(filters.command(["profile", "myprofile", "musicprofile"]) & ~BANNED_USERS)
async def profile_cmd(client, message):
    if not message.from_user:
        return
    user, _rest, err = await _split_target(message)
    if err:
        return await message.reply_text(err, parse_mode=HTML)
    owner = user or message.from_user
    text, mk = await profile_panel(owner, message.from_user.id)
    await message.reply_text(text, reply_markup=mk, parse_mode=HTML)


@app.on_message(filters.command(["playlistprivacy", "plprivacy"]) & ~BANNED_USERS)
async def playlistprivacy_cmd(client, message):
    if not message.from_user:
        return
    uid = message.from_user.id
    arg = _arg(message).lower()
    if arg in ("private", "on", "hide"):
        await set_playlists_private(uid, True)
        return await message.reply_text("🔒 Ab tumhari playlists dusre log nahi dekh sakte.")
    if arg in ("public", "off", "show"):
        await set_playlists_private(uid, False)
        return await message.reply_text("🌐 Ab tumhari playlists dusre log dekh aur sun sakte hain.")
    private = (await get_profile(uid)).get("pl_private", False)
    await message.reply_text(
        f"📂 Playlist privacy abhi: <b>{'🔒 private' if private else '🌐 public'}</b>\n"
        "Badalne ke liye: <code>/playlistprivacy private</code> ya <code>/playlistprivacy public</code>",
        parse_mode=HTML,
    )


# ===========================================================
# COMMANDS — dusre ki playlist
# ===========================================================

@app.on_message(filters.command(["userplaylist", "userplaylists", "friendplaylist"]) & ~BANNED_USERS)
async def userplaylist_cmd(client, message):
    if not message.from_user:
        return
    user, _rest, err = await _split_target(message)
    if err:
        return await message.reply_text(err, parse_mode=HTML)
    if not user:
        return await message.reply_text(
            "ℹ️ Usage: <code>/userplaylist @username</code>\n"
            "Ya dost ke message pe reply karke <code>/userplaylist</code> likho.",
            parse_mode=HTML,
        )
    if not await _can_view(user.id, message.from_user.id):
        return await message.reply_text("🔒 Is user ki playlists private hain.")
    pls = await get_user_playlists(user.id)
    text, mk = others_playlists_panel(user, pls)
    await message.reply_text(text, reply_markup=mk, parse_mode=HTML)


# ===========================================================
# COMMANDS — share
# ===========================================================

def _share_markup(token: str) -> Markup:
    return Markup(
        [
            [
                Btn("▶ ᴘʟᴀʏ", callback_data=f"ShPlay {token}"),
                Btn("❤️ sᴀᴠᴇ", callback_data=f"ShFav {token}"),
            ],
            CLOSE_ROW,
        ]
    )


async def _dm_friend(target, text: str, markup: Markup) -> bool:
    if not target or target.is_bot:
        return False
    try:
        await app.send_message(target.id, text, reply_markup=markup, parse_mode=HTML)
        return True
    except Exception:
        return False  # usne bot start nahi kiya / block hai


@app.on_message(filters.command(["share", "sharesong", "gift"]) & ~BANNED_USERS)
async def share_cmd(client, message):
    if not message.from_user:
        return
    me = message.from_user
    target, query, err = await _split_target(message)
    if err:
        return await message.reply_text(err, parse_mode=HTML)
    if target and target.id == me.id:
        target = None

    mystic = None
    if query:
        mystic = await message.reply_text("🔎 ᴅʜᴜɴᴅ ʀᴀʜᴀ ʜᴏᴏɴ...")
        try:
            song = await _resolve(query)
        except Exception:
            return await mystic.edit_text("❌ Gaana nahi mila. Naam ya YouTube link check karo.")
    else:
        song = _current_song(message.chat.id)
        if not song:
            return await message.reply_text(
                "ℹ️ Usage:\n"
                "<code>/share @friend song name</code>\n"
                "<code>/share song name</code> (dost ke message pe reply karke)\n"
                "<code>/share</code> (abhi baj rahe gaane ko share)",
                parse_mode=HTML,
            )

    token = await create_share(me.id, me.first_name, "song", song)
    who = f"{_ulink(me)} ne " + (f"{_ulink(target)} ko " if target else "") + "ek song share kiya"
    text = (
        f"<b>🎁 {who}</b>\n"
        "<blockquote>"
        f"<b>🎵 {_esc(song['title'][:60])}</b> <code>{_esc(song['dur'])}</code>"
        "</blockquote>"
    )
    mk = _share_markup(token)
    if mystic:
        await mystic.edit_text(text, reply_markup=mk, parse_mode=HTML)
    else:
        await message.reply_text(text, reply_markup=mk, parse_mode=HTML)

    if target:
        dm = (
            f"<b>🎁 {_ulink(me)} ne tumhe ek song share kiya!</b>\n"
            "<blockquote>"
            f"<b>🎵 {_esc(song['title'][:60])}</b> <code>{_esc(song['dur'])}</code>"
            "</blockquote>"
        )
        dm_mk = Markup(
            [
                [
                    Btn("❤️ sᴀᴠᴇ", callback_data=f"ShFav {token}"),
                    Btn("🔗 ʏᴏᴜᴛᴜʙᴇ", url=f"https://www.youtube.com/watch?v={song['vidid']}"),
                ]
            ]
        )
        await _dm_friend(target, dm, dm_mk)


@app.on_message(filters.command(["sharepl", "shareplaylist"]) & ~BANNED_USERS)
async def sharepl_cmd(client, message):
    if not message.from_user:
        return
    me = message.from_user
    target, name, err = await _split_target(message)
    if err:
        return await message.reply_text(err, parse_mode=HTML)
    if target and target.id == me.id:
        target = None
    if not name:
        return await message.reply_text(
            "ℹ️ Usage: <code>/sharepl playlist name [@friend]</code>\n"
            "Ya dost ke message pe reply karke <code>/sharepl playlist name</code>",
            parse_mode=HTML,
        )
    # "name @friend" -> naam ke end ka @username target maano
    if not target and " " in name and name.rsplit(None, 1)[1].startswith("@"):
        name, ref = name.rsplit(None, 1)
        target = await _get_user(ref)
    pl = await find_user_playlist_by_name(me.id, name)
    if not pl:
        return await message.reply_text("❌ Is naam ki playlist nahi mili. /playlist se dekho.")
    if not pl["songs"]:
        return await message.reply_text("❌ Ye playlist khali hai, pehle gaane add karo.")

    token = await create_share(me.id, me.first_name, "playlist", {"uid": me.id, "pid": pl["id"]})
    who = f"{_ulink(me)} ne " + (f"{_ulink(target)} ko " if target else "") + "apni playlist share ki"
    text = (
        f"<b>🎁 {who}</b>\n"
        "<blockquote>"
        f"<b>📂 {_esc(pl['name'])}</b> <code>({len(pl['songs'])} songs)</code>"
        "</blockquote>"
    )
    mk = Markup([[Btn("📂 ᴏᴘᴇɴ ᴘʟᴀʏʟɪsᴛ", callback_data=f"ShOpen {token}")], CLOSE_ROW])
    await message.reply_text(text, reply_markup=mk, parse_mode=HTML)
    if target:
        await _dm_friend(
            target,
            f"<b>🎁 {_ulink(me)} ne tumhe playlist share ki!</b>\n"
            f"<blockquote><b>📂 {_esc(pl['name'])}</b> <code>({len(pl['songs'])} songs)</code></blockquote>\n"
            "Sunne ke liye kisi group me <code>/userplaylist</code> ya share wala message use karo.",
            Markup([CLOSE_ROW]),
        )


# ===========================================================
# CALLBACKS
# ===========================================================

async def _need_user(uid: int):
    return await _get_user(uid)


async def cb_view(q, a):
    uid = int(a[0])
    owner = await _need_user(uid)
    if not owner:
        return await q.answer("❌ User nahi mila.", show_alert=True)
    text, mk = await profile_panel(owner, q.from_user.id)
    await _edit(q, text, mk)
    await q.answer()


async def cb_song(q, a):
    uid = int(a[0])
    song = (await get_profile(uid)).get("song")
    if not song:
        return await q.answer("❌ Profile song hata diya gaya hai.", show_alert=True)
    owner = await _need_user(uid)
    await _play_from_callback(q, [song], f"Profile Song ({_owner_name_cache(owner)})")


async def cb_playlists(q, a):
    uid = int(a[0])
    bypass = len(a) > 1 and a[1] == "1"
    if not await _can_view(uid, q.from_user.id, bypass):
        return await q.answer("🔒 Is user ki playlists private hain.", show_alert=True)
    owner = await _need_user(uid)
    if not owner:
        return await q.answer("❌ User nahi mila.", show_alert=True)
    text, mk = others_playlists_panel(owner, await get_user_playlists(uid), bypass)
    await _edit(q, text, mk)
    await q.answer()


async def _load_pl(q, a):
    """(owner, playlist, bypass) ya None (alert de diya)."""
    uid, pid = int(a[0]), a[1]
    bypass = len(a) > 3 and a[3] == "1"
    if not await _can_view(uid, q.from_user.id, bypass):
        await q.answer("🔒 Is user ki playlists private hain.", show_alert=True)
        return None
    pl = await get_user_playlist(uid, pid)
    if not pl:
        await q.answer("❌ Playlist ab nahi hai.", show_alert=True)
        return None
    return await _need_user(uid), pl, bypass


async def cb_playlist_open(q, a):
    loaded = await _load_pl(q, a)
    if not loaded:
        return
    owner, pl, bypass = loaded
    if not owner:
        return await q.answer("❌ User nahi mila.", show_alert=True)
    text, mk = others_playlist_panel(owner, pl, int(a[2]), bypass)
    await _edit(q, text, mk)
    await q.answer()


async def cb_play(q, a):
    # PfPlay uid|pid|vidid|b  -> _load_pl ko a[3] = b chahiye
    loaded = await _load_pl(q, a)
    if not loaded:
        return
    owner, pl, _bypass = loaded
    song = next((s for s in pl["songs"] if s["vidid"] == a[2]), None)
    if not song:
        return await q.answer("❌ Ye gaana ab playlist me nahi hai.", show_alert=True)
    await _play_from_callback(q, [song], f"{_owner_name_cache(owner)} ki Playlist ({pl['name']})")


async def cb_play_all(q, a):
    # PfAll uid|pid|shuffle|b
    loaded = await _load_pl(q, a)
    if not loaded:
        return
    owner, pl, _bypass = loaded
    songs = pl["songs"][:]
    if not songs:
        return await q.answer("❌ Playlist khali hai.", show_alert=True)
    if a[2] == "1":
        random.shuffle(songs)
    await _play_from_callback(q, songs, f"{_owner_name_cache(owner)} ki Playlist ({pl['name']})")


async def cb_fav(q, a):
    # PfFav uid|pid|vidid|b   (pid "-" = profile song)
    uid, pid, vidid = int(a[0]), a[1], a[2]
    bypass = len(a) > 3 and a[3] == "1"
    if pid == "-":
        song = (await get_profile(uid)).get("song")
        song = song if song and song["vidid"] == vidid else None
    else:
        if not await _can_view(uid, q.from_user.id, bypass):
            return await q.answer("🔒 Is user ki playlists private hain.", show_alert=True)
        pl = await get_user_playlist(uid, pid)
        song = next((s for s in (pl or {}).get("songs", []) if s["vidid"] == vidid), None)
    if not song:
        return await q.answer("❌ Ye gaana ab nahi mila.", show_alert=True)
    status = await add_fav(q.from_user.id, song)
    await q.answer(_SAVE_TXT[status], show_alert=status != "added")


async def _share_data(q, token: str, kind: str):
    sh = await get_share(token)
    if not sh or sh.get("kind") != kind:
        await q.answer("❌ Ye share ab available nahi hai.", show_alert=True)
        return None
    return sh


async def cb_share_play(q, a):
    sh = await _share_data(q, a[0], "song")
    if sh:
        await _play_from_callback(q, [sh["data"]], f"Shared by {sh.get('from_name') or 'friend'}")


async def cb_share_fav(q, a):
    sh = await _share_data(q, a[0], "song")
    if sh:
        status = await add_fav(q.from_user.id, sh["data"])
        await q.answer(_SAVE_TXT[status], show_alert=status != "added")


async def cb_share_open(q, a):
    sh = await _share_data(q, a[0], "playlist")
    if not sh:
        return
    uid, pid = int(sh["data"]["uid"]), sh["data"]["pid"]
    pl = await get_user_playlist(uid, pid)
    owner = await _need_user(uid)
    if not pl or not owner:
        return await q.answer("❌ Playlist ab nahi hai.", show_alert=True)
    # share = owner ki marzi -> private ho tab bhi khulti hai (bypass=True)
    text, mk = others_playlist_panel(owner, pl, 0, True)
    await _edit(q, text, mk)
    await q.answer()


# NOTE: playlist ke andar ke buttons (PfPl/PfPlay/PfAll/PfFav) me last arg b=1 hota hai
# jab playlist share ke through kholi gayi ho, isliye private playlist bhi sunn sakte hain.
CALLBACKS = {
    "PfView": cb_view,
    "PfSong": cb_song,
    "PfPls": cb_playlists,
    "PfPl": cb_playlist_open,
    "PfPlay": cb_play,
    "PfAll": cb_play_all,
    "PfFav": cb_fav,
    "ShPlay": cb_share_play,
    "ShFav": cb_share_fav,
    "ShOpen": cb_share_open,
}
_CB_REGEX = r"^(" + "|".join(sorted(CALLBACKS, key=len, reverse=True)) + r") "


# group=-1 + StopPropagation: purane unanchored regex handlers beech me na aayein
@app.on_callback_query(filters.regex(_CB_REGEX) & ~BANNED_USERS, group=-1)
async def social_callbacks(client, q):
    try:
        cmd, _sep, arg = q.data.partition(" ")
        await CALLBACKS[cmd](q, arg.split("|"))
    except Exception:
        traceback.print_exc()
        try:
            await q.answer("❌ Kuch gadbad ho gayi, dobara try karo.", show_alert=True)
        except Exception:
            pass
    raise StopPropagation
