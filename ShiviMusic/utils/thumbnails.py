# ===========================================================
# 🖼 NOW PLAYING THUMBNAIL — orange pill card
#
# Design: blurred dark background, left me "NOW PLAYING" orange pill,
# 2-line title, channel, views | duration, orange progress bar,
# "Player : @bot"; right me orange glow frame ke andar song image;
# neeche right me yellow credit text.
#
# Use (purane jaisa hi):
#   from ShiviMusic.utils.thumbnails import get_thumb
#   thumb = await get_thumb(videoid)
#
# 🔤 FONT: Poppins + Itim auto-download (neeche FONTS section dekho)
#   ShiviMusic/assets/title_font.ttf
# ===========================================================

import asyncio
import glob
import io
import os
import random
import traceback

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1280, 720
ORANGE = (255, 138, 0)
BOT_USERNAME = "@Hinduprobot"   # "Player : ..." line (bot ka username)
CREDIT_TEXT = "By : @kirti_bots"    # neeche right wala yellow text
BLUR_RADIUS = 35

_ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


def _a(name):
    return os.path.join(_ASSETS, name)


# ---------------------------------------------------------------- FONTS
# Screenshot wale fonts: UI text = Poppins, title = rounded handwriting
# style (Itim). Pehli baar chalne par ye apne aap assets/ me download ho
# jaate hain. Title font alag chahiye to bas assets/title_font.ttf rakh do
# (usko priority milti hai) ya neeche TITLE_FONT_URL badlo.
_GF = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
_FONT_URLS = {
    "Poppins-Medium.ttf": _GF + "poppins/Poppins-Medium.ttf",
    "Poppins-SemiBold.ttf": _GF + "poppins/Poppins-SemiBold.ttf",
    "Poppins-Bold.ttf": _GF + "poppins/Poppins-Bold.ttf",
    "Itim-Regular.ttf": _GF + "itim/Itim-Regular.ttf",
}
_SYS = [
    "/usr/share/fonts/truetype/google-fonts/",
    "/usr/share/fonts/truetype/dejavu/",
]


def _ensure_fonts():
    import urllib.request

    os.makedirs(_ASSETS, exist_ok=True)
    for name, url in _FONT_URLS.items():
        p = _a(name)
        if os.path.exists(p) and os.path.getsize(p) > 10000:
            continue
        try:
            urllib.request.urlretrieve(url, p)
        except Exception:
            print(f"[THUMB] font download fail: {name}")


try:
    _ensure_fonts()
except Exception:
    pass


def _cands(*names):
    out = [_a(n) for n in names]
    out += [d + n for d in _SYS for n in names]
    out += ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    return out


_TITLE_FONTS = [_a("title_font.ttf")] + _cands("Itim-Regular.ttf", "Poppins-Medium.ttf")
_PILL_FONTS = _cands("Poppins-Bold.ttf", "Poppins-SemiBold.ttf")
_HEAD_FONTS = _cands("Poppins-SemiBold.ttf", "Poppins-Bold.ttf")   # channel
_UI_FONTS = _cands("Poppins-Medium.ttf", "Poppins-Regular.ttf")    # baaki text


def _load(cands, size):
    for p in cands:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:
        return ImageFont.load_default()


def _bot_username():
    try:
        from ShiviMusic import app  # type: ignore

        u = getattr(app, "username", None)
        if u:
            return "@" + str(u).lstrip("@")
    except Exception:
        pass
    return BOT_USERNAME


def _cover_crop(img, w, h):
    iw, ih = img.size
    sc = max(w / iw, h / ih)
    img = img.resize((int(iw * sc) + 1, int(ih * sc) + 1), Image.LANCZOS)
    l, t = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((l, t, l + w, t + h))


def _rounded(img, radius):
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *img.size), radius, fill=255)
    img.putalpha(mask)
    return img


def _trim(draw, text, font, max_w):
    text = str(text or "")
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "...", font=font) > max_w:
        text = text[:-1]
    return text.rstrip() + "..."


def _two_lines(draw, text, font, max_w):
    words = str(text or "").split()
    if not words:
        return "", ""
    line1, i = "", 0
    while i < len(words):
        test = (line1 + " " + words[i]).strip()
        if draw.textlength(test, font=font) <= max_w:
            line1 = test
            i += 1
        else:
            break
    if i >= len(words):
        return line1, ""
    if not line1:  # ek hi bada word
        line1, i = _trim(draw, words[0], font, max_w), 1
    return line1, _trim(draw, " ".join(words[i:]), font, max_w)


def _secs(duration):
    try:
        sec = 0
        for p in str(duration).split(":"):
            sec = sec * 60 + int(p)
        return sec
    except Exception:
        return 0


def _fmt(sec):
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def compose_thumb(cover, title, artist, views, duration, path):
    cover = cover.convert("RGB")
    bg = _cover_crop(cover, W, H).filter(ImageFilter.GaussianBlur(BLUR_RADIUS))
    bg = ImageEnhance.Brightness(bg).enhance(0.40)
    canvas = bg.convert("RGBA")

    # ---- right: orange glow frame + song image ----
    fx1, fy1, fx2, fy2 = 641, 107, 1229, 594
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).rounded_rectangle(
        (fx1, fy1, fx2, fy2), 34, outline=ORANGE + (255,), width=12
    )
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(14)))
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((fx1, fy1, fx2, fy2), 34, outline=ORANGE, width=8)
    ix1, iy1, ix2, iy2 = 660, 125, 1210, 575
    art = _rounded(_cover_crop(cover, ix2 - ix1, iy2 - iy1), 22)
    canvas.alpha_composite(art, (ix1, iy1))
    d = ImageDraw.Draw(canvas)

    # ---- NOW PLAYING pill ----
    d.rounded_rectangle((80, 116, 327, 154), 19, fill=ORANGE)
    d.text((203, 135), "NOW PLAYING", font=_load(_PILL_FONTS, 25),
           fill=(35, 20, 0), anchor="mm")

    # ---- title (2 lines) ----
    f_title = _load(_TITLE_FONTS, 60)
    l1, l2 = _two_lines(d, title, f_title, 500)
    d.text((80, 180), l1, font=f_title, fill="white")
    if l2:
        d.text((80, 250), l2, font=f_title, fill="white")

    # ---- orange small line ----
    d.rectangle((80, 336, 181, 341), fill=ORANGE)

    # ---- channel + views | duration ----
    f_ch = _load(_HEAD_FONTS, 36)
    f_sm = _load(_UI_FONTS, 27)
    d.text((80, 372), _trim(d, artist or "Unknown", f_ch, 500), font=f_ch,
           fill=(235, 235, 235))
    info = " | ".join([x for x in (views, f"{duration} Minutes") if x])
    d.text((80, 416), info, font=f_sm, fill=(215, 215, 215))

    # ---- progress bar ----
    total = max(_secs(duration), 1)
    pos = int(total * random.uniform(0.2, 0.5))
    bx1, bx2, by = 80, 510, 490
    cx = bx1 + int((bx2 - bx1) * pos / total)
    d.rounded_rectangle((bx1, by - 3, bx2, by + 3), 3, fill=(95, 95, 110))
    d.rounded_rectangle((bx1, by - 3, cx, by + 3), 3, fill=ORANGE)
    d.ellipse((cx - 13, by - 13, cx + 13, by + 13), fill="white")
    f_t = _load(_UI_FONTS, 19)
    d.text((bx1, 515), _fmt(pos), font=f_t, fill=(225, 225, 225))
    d.text((bx2, 515), duration, font=f_t, fill=(225, 225, 225), anchor="ra")

    # ---- player + credit ----
    d.text((80, 560), f"Player :  {_bot_username()}", font=_load(_HEAD_FONTS, 27),
           fill=(205, 205, 205))
    d.text((W - 25, H - 28), CREDIT_TEXT, font=_load(_HEAD_FONTS, 26),
           fill=(255, 235, 0), anchor="rs")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    canvas.convert("RGB").save(path, "JPEG", quality=92)
    return path


async def _download(session, vidid):
    for q in ("maxresdefault", "sddefault", "hqdefault", "mqdefault"):
        try:
            async with session.get(
                f"https://i.ytimg.com/vi/{vidid}/{q}.jpg",
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                if r.status == 200:
                    img = Image.open(io.BytesIO(await r.read())).convert("RGB")
                    if img.width > 200:
                        return img
        except Exception:
            continue
    return None


def _parse(r):
    views = ((r.get("viewCount") or {}).get("short")) or ""
    views = views.replace(" views", " Views").replace(" view", " View")
    return (r.get("title"), (r.get("channel") or {}).get("name"),
            r.get("duration"), views)


async def _meta(session, videoid):
    """(title, artist, duration, views) -- jo library mile usse; sab fail to oEmbed."""
    url = f"https://www.youtube.com/watch?v={videoid}"
    try:
        from py_yt import VideosSearch

        return _parse((await VideosSearch(url, limit=1).next())["result"][0])
    except Exception:
        pass
    try:
        from youtubesearchpython.__future__ import VideosSearch

        return _parse((await VideosSearch(url, limit=1).next())["result"][0])
    except Exception:
        pass
    try:
        from youtubesearchpython import VideosSearch

        res = await asyncio.get_running_loop().run_in_executor(
            None, lambda: VideosSearch(url, limit=1).result()
        )
        return _parse(res["result"][0])
    except Exception:
        pass
    try:
        async with session.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=aiohttp.ClientTimeout(total=8),
        ) as r:
            if r.status == 200:
                j = await r.json()
                return j.get("title"), j.get("author_name"), None, ""
    except Exception:
        pass
    return None, None, None, ""


async def get_thumb(videoid, *args, title=None, artist=None, duration=None,
                    views=None, **kwargs):
    """NOW PLAYING card banata hai. Fail => YouTube thumb URL.

    get_thumb(vidid), get_thumb(vidid, user_id), get_thumb(vidid, a, b ...)
    -- sab chalte hain, extra args ignore.
    """
    videoid = str(videoid)
    title = title if isinstance(title, str) else None
    artist = artist if isinstance(artist, str) else None
    duration = duration if isinstance(duration, str) else None
    views = views if isinstance(views, str) else None
    fallback = f"https://i.ytimg.com/vi/{videoid}/hqdefault.jpg"

    os.makedirs("cache", exist_ok=True)
    for old in glob.glob(f"cache/{videoid}_np_*.jpg"):
        try:
            os.remove(old)
        except Exception:
            pass
    path = f"cache/{videoid}_np_{random.randint(1000, 9999)}.jpg"
    try:
        async with aiohttp.ClientSession() as session:
            if not (title and artist and duration and views is not None):
                t, a, dur, v = await _meta(session, videoid)
                title, artist = title or t, artist or a
                duration, views = duration or dur, (views if views is not None else v)
            cover = await _download(session, videoid)
        if cover is None:
            print(f"[THUMB] cover download fail for {videoid}")
            return fallback
        await asyncio.get_running_loop().run_in_executor(
            None, compose_thumb, cover, title or "Unknown Title",
            artist or "YouTube", views or "", duration or "0:00", path,
        )
        return path
    except Exception:
        print("[THUMB] FAIL -> fallback image. Error:")
        traceback.print_exc()
        return fallback


gen_thumb = get_thumb  # purane naam se bhi chale
