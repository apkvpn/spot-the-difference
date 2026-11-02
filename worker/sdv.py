#!/usr/bin/env python3
"""Spot-the-Difference YouTube video builder. Usage: sdv.py <job_dir>"""
import os, sys, json, math, time, shutil, subprocess, hashlib, re, random, fcntl, traceback, site, importlib

JOB = os.path.abspath(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, 'data', 'assets')
os.makedirs(ASSETS, exist_ok=True)
CFG = json.load(open(os.path.join(JOB, 'config.json')))
FFMPEG = CFG.get('ffmpeg') or 'ffmpeg'
FFPROBE = CFG.get('ffprobe') or 'ffprobe'
STATUS_PATH = os.path.join(JOB, 'status.json')
status = {'status': 'queued', 'progress': 0, 'stage': 'در صف انتظار', 'log': [], 'report': None, 'output': None, 'error': None}


def save_status():
    tmp = STATUS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(status, f, ensure_ascii=False)
    os.replace(tmp, STATUS_PATH)


def log(msg):
    print(time.strftime('%H:%M:%S'), msg, flush=True)
    status['log'] = (status['log'] + [time.strftime('%H:%M:%S ') + msg])[-80:]
    save_status()


def setp(stage, prog):
    status['stage'] = stage
    status['progress'] = int(max(0, min(100, prog)))
    save_status()


save_status()


# ---------------- deps & assets ----------------
def pip_install(pkgs):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--user', '--break-system-packages', '-q', *pkgs], check=False)
    site.addsitedir(site.getusersitepackages())
    importlib.invalidate_caches()


def ensure_deps():
    need = []
    for mod, pkg in [('PIL', 'pillow'), ('numpy', 'numpy'), ('scipy', 'scipy'), ('soundfile', 'soundfile')]:
        try:
            __import__(mod)
        except ImportError:
            need.append(pkg)
    if need:
        log('نصب کتابخانه‌ها: ' + ', '.join(need))
        pip_install(need)
    try:
        __import__('kokoro_onnx')
    except ImportError:
        log('نصب kokoro-onnx ...')
        pip_install(['kokoro-onnx'])


def download(url, path, min_size=1000):
    import urllib.request
    if os.path.exists(path) and os.path.getsize(path) >= min_size:
        return True
    try:
        tmp = path + '.part'
        urllib.request.urlretrieve(url, tmp)
        if os.path.getsize(tmp) >= min_size:
            os.replace(tmp, path)
            return True
    except Exception as e:
        log(f'دانلود ناموفق {os.path.basename(path)}: {e}')
    return False


FREDOKA = os.path.join(ASSETS, 'Fredoka.ttf')
EMOJI_TTF = os.path.join(ASSETS, 'NotoColorEmoji.ttf')
KOK_MODEL = os.path.join(ASSETS, 'kokoro-v1.0.onnx')
KOK_VOICES = os.path.join(ASSETS, 'voices-v1.0.bin')


def ensure_assets():
    download('https://raw.githubusercontent.com/google/fonts/main/ofl/fredoka/Fredoka%5Bwdth%2Cwght%5D.ttf', FREDOKA, 50000)
    if not (os.path.exists(EMOJI_TTF) and os.path.getsize(EMOJI_TTF) > 1000000):
        try:
            import urllib.request
            base = 'http://deb.debian.org/debian/pool/main/f/fonts-noto-color-emoji/'
            html = urllib.request.urlopen(base).read().decode()
            debs = sorted(set(re.findall(r'fonts-noto-color-emoji_[^"]*_all\.deb', html)))
            deb = os.path.join(ASSETS, 'emo.deb')
            urllib.request.urlretrieve(base + debs[-1], deb)
            ex = os.path.join(ASSETS, 'emo_x')
            subprocess.run(['dpkg-deb', '-x', deb, ex], check=True)
            for r, _, fs in os.walk(ex):
                for f in fs:
                    if f.endswith('.ttf'):
                        shutil.copy(os.path.join(r, f), EMOJI_TTF)
            shutil.rmtree(ex, ignore_errors=True)
            os.remove(deb)
        except Exception as e:
            log(f'فونت ایموجی در دسترس نیست: {e}')
    rel = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/'
    download(rel + 'kokoro-v1.0.onnx', KOK_MODEL, 10_000_000)
    download(rel + 'voices-v1.0.bin', KOK_VOICES, 1_000_000)


ensure_deps()
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage
from scipy.signal import resample_poly
import soundfile as sf
sys.path.insert(0, HERE)
import scenes

W, H, FPS = 1920, 1080, 60
SR = 44100
SPF = SR // FPS  # 735 samples / frame
INK = (58, 31, 107); PURPLE = (123, 77, 255); PINK = (255, 79, 154); GREEN = (67, 201, 92)
ORANGE = (255, 138, 31); YELLOW = (255, 201, 40); RED = (255, 59, 59); BLUE = (40, 170, 255)
RAINBOW_TXT = [PINK, PURPLE, GREEN, ORANGE, BLUE, RED]
RB = [PINK, ORANGE, YELLOW, GREEN, BLUE, PURPLE]
NUMW = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve',
        'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty']


def numw(n):
    if n < len(NUMW):
        return NUMW[n]
    tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety']
    if n < 100:
        return tens[n // 10] + ('' if n % 10 == 0 else '-' + NUMW[n % 10])
    return str(n)


def F(sec):
    return int(round(sec * FPS))


def ease_io(p):
    return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_back(p):
    c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


# ---------------- text ----------------
_fc = {}


def font(size):
    size = int(size)
    if size not in _fc:
        f = ImageFont.truetype(FREDOKA, size)
        try:
            f.set_variation_by_axes([700, 100])
        except Exception:
            pass
        _fc[size] = f
    return _fc[size]


_ec = {}
_efont = None


def is_emoji(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF or o in (0x23F0, 0x231B, 0x23F3, 0x23F1)


def emoji_img(ch, size):
    global _efont
    key = (ch, int(size))
    if key in _ec:
        return _ec[key]
    im = None
    try:
        if _efont is None:
            _efont = ImageFont.truetype(EMOJI_TTF, 109)
        cv = Image.new('RGBA', (180, 160), (0, 0, 0, 0))
        ImageDraw.Draw(cv).text((10, 10), ch, font=_efont, embedded_color=True)
        bb = cv.getbbox()
        if bb:
            crop = cv.crop(bb)
            sc = size / 128.0
            im = crop.resize((max(1, int(crop.width * sc)), max(1, int(crop.height * sc))), Image.LANCZOS)
    except Exception:
        im = None
    _ec[key] = im
    return im


def runs(text):
    out, buf = [], ''
    for ch in text:
        if ch in '\ufe0f\u200d':
            continue
        if is_emoji(ch):
            if buf:
                out.append((False, buf)); buf = ''
            out.append((True, ch))
        else:
            buf += ch
    if buf:
        out.append((False, buf))
    return out


def text_w(text, size):
    f = font(size)
    return sum(size * 1.12 if e else f.getlength(s) for e, s in runs(text))


def draw_text(img, x, y, text, size, fill=INK, anchor='l', shadow=None, stroke=0, stroke_fill=(255, 255, 255)):
    w = text_w(text, size)
    if anchor == 'm':
        x -= w / 2
    elif anchor == 'r':
        x -= w
    d = ImageDraw.Draw(img)
    f = font(size)
    for e, s in runs(text):
        if e:
            em = emoji_img(s, size * 0.98)
            if em:
                img.paste(em, (int(x + size * 0.06), int(y + size * 0.16)), em)
            x += size * 1.12
        else:
            if shadow:
                d.text((x + shadow[0], y + shadow[1]), s, font=f, fill=shadow[2], stroke_width=stroke, stroke_fill=shadow[2])
            d.text((x, y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
            x += f.getlength(s)
    return w


def draw_colorful(img, cx, y, text, size, shadow=True, start=0):
    w = text_w(text, size)
    x = cx - w / 2
    f = font(size)
    d = ImageDraw.Draw(img)
    i = start
    sw = max(2, size // 16)
    off = max(3, size // 14)
    for e, s in runs(text):
        if e:
            em = emoji_img(s, size * 0.98)
            if em:
                img.paste(em, (int(x + size * 0.06), int(y + size * 0.16)), em)
            x += size * 1.12
            continue
        for ch in s:
            if shadow:
                d.text((x + off * .7, y + off), ch, font=f, fill=(70, 30, 120), stroke_width=sw, stroke_fill=(70, 30, 120))
            d.text((x, y), ch, font=f, fill=RAINBOW_TXT[i % len(RAINBOW_TXT)], stroke_width=sw, stroke_fill=(255, 255, 255))
            if ch != ' ':
                i += 1
            x += f.getlength(ch)
    return w


def wrap(text, size, maxw):
    words = text.split()
    lines, cur = [], ''
    for wd in words:
        t = (cur + ' ' + wd).strip()
        if text_w(t, size) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur); cur = wd
    if cur:
        lines.append(cur)
    return lines


def fit_lines(text, maxw, maxlines=2, sizes=(32, 29, 26, 23, 21)):
    for s in sizes:
        ls = wrap(text, s, maxw)
        if len(ls) <= maxlines and all(text_w(l, s) <= maxw for l in ls):
            return s, ls
    s = sizes[-1]
    ls = wrap(text, s, maxw)[:maxlines]
    while ls and text_w(ls[-1] + '…', s) > maxw:
        ls[-1] = ls[-1][:-1]
    ls[-1] = ls[-1].rstrip() + '…'
    return s, ls


# ---------------- graphics ----------------
def grad_img(w, h, stops, diag=(0.6, 0.4)):
    t = (np.linspace(0, 1, w)[None, :] * diag[0] + np.linspace(0, 1, h)[:, None] * diag[1]) / (diag[0] + diag[1])
    xs = [s[0] for s in stops]
    arr = np.stack([np.interp(t, xs, [s[1][c] for s in stops]) for c in range(3)], -1)
    return Image.fromarray(arr.astype(np.uint8))


def make_bg():
    img = grad_img(W, H, [(0, (255, 214, 232)), (0.36, (255, 244, 200)), (0.68, (200, 242, 238)), (1, (228, 214, 255))]).convert('RGBA')
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for x, y, r, c in [(170, 880, 240, (255, 214, 60, 130)), (1730, 240, 260, (80, 220, 210, 120)), (1520, 960, 230, (255, 120, 180, 120)),
                       (300, 160, 210, (170, 120, 255, 110)), (980, 1010, 190, (255, 160, 60, 110)), (1000, 90, 150, (255, 214, 60, 90))]:
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    layer = layer.filter(ImageFilter.GaussianBlur(80))
    return Image.alpha_composite(img, layer).convert('RGB')


_rb = {}


def rainbow(w, h):
    k = (w, h)
    if k not in _rb:
        if len(_rb) > 80:
            _rb.clear()
        _rb[k] = grad_img(w, h, [(i / (len(RB) - 1), c) for i, c in enumerate(RB)], (0.85, 0.15))
    return _rb[k]


def rr_mask(w, h, r, ss=2):
    m = Image.new('L', (w * ss, h * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * ss - 1, h * ss - 1], r * ss, fill=255)
    return m.resize((w, h), Image.LANCZOS)


FB, FPAD, FRAD = 10, 36, 26
_fr = {}


def framed(src, w, h, key):
    k = (key, w, h)
    if k in _fr:
        return _fr[k]
    if len(_fr) > 60:
        _fr.clear()
    b, pad, r = FB, FPAD, FRAD
    cw, ch = w + 2 * b + 2 * pad, h + 2 * b + 2 * pad
    can = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    sh = Image.new('L', (cw, ch), 0)
    ImageDraw.Draw(sh).rounded_rectangle([pad + 4, pad + 14, pad + w + 2 * b + 4, pad + h + 2 * b + 14], r + b, fill=120)
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    can.paste(Image.new('RGBA', (cw, ch), (60, 30, 100, 255)), (0, 0), sh)
    can.paste(rainbow(w + 2 * b, h + 2 * b), (pad, pad), rr_mask(w + 2 * b, h + 2 * b, r + b, 1))
    can.paste(src.resize((w, h), Image.LANCZOS), (pad + b, pad + b), rr_mask(w, h, r, 1))
    _fr[k] = can
    return can


def paste_framed(img, src, rect, key):
    x, y, w, h = rect
    f = framed(src, w, h, key)
    img.paste(f, (x - FB - FPAD, y - FB - FPAD), f)


def fit_rect(iw, ih, box):
    bw, bh = box[2] - box[0], box[3] - box[1]
    s = min(bw / iw, bh / ih)
    w, h = int(iw * s), int(ih * s)
    return (box[0] + (bw - w) // 2, box[1] + (bh - h) // 2, w, h)


CD_BOX = (40, 192, 1880, 1062)  # big, almost full-screen during countdown
AN_BOX = (36, 200, 1000, 1052)  # smaller during answers
CARD = (1036, 196, 1890, 1052)
TITLE = 'How many differences can you spot? 🔍'


def draw_badge(img, i, n):
    d = ImageDraw.Draw(img)
    label = f'Picture {i + 1} / {n}'
    tw = text_w(label, 36)
    x0, y0 = 28, 20
    d.rounded_rectangle([x0 + 3, y0 + 6, x0 + tw + 56 + 3, y0 + 70 + 6], 36, fill=(70, 30, 120))
    d.rounded_rectangle([x0, y0, x0 + tw + 56, y0 + 70], 36, fill=PURPLE, outline=(255, 255, 255), width=4)
    draw_text(img, x0 + 28, y0 + 11, label, 36, (255, 255, 255))
    sp = min(26, 560 / max(1, n))
    rad = max(4, min(9, sp * 0.36))
    for k in range(n):
        cx, cy = x0 + 18 + k * sp, y0 + 100
        c = GREEN if k < i else (YELLOW if k == i else (255, 255, 255))
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=c, outline=PURPLE, width=2)


def timer_img(rem, total, done=False):
    S = 2
    sz = 170 * S
    im = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = sz // 2
    R0 = 75 * S
    d.ellipse([c - R0 + 4 * S, c - R0 + 8 * S, c + R0 + 4 * S, c + R0 + 8 * S], fill=(70, 30, 120, 90))
    if done:
        d.ellipse([c - R0, c - R0, c + R0, c + R0], fill=GREEN, outline=(255, 255, 255), width=8 * S)
        em = emoji_img('✅', 80 * S)
        if em:
            im.paste(em, (c - em.width // 2, c - em.height // 2), em)
        return im.resize((170, 170), Image.LANCZOS)
    d.ellipse([c - R0, c - R0, c + R0, c + R0], fill=(255, 255, 255), outline=(255, 255, 255))
    rr = R0 - 12 * S
    d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=(232, 226, 245), width=14 * S)
    frac = max(0.0, min(1.0, rem / max(total, 0.01)))
    col = GREEN if frac > 0.5 else (ORANGE if frac > 0.2 else RED)
    if rem <= 10:
        col = RED if rem <= 5 else ORANGE
    if frac > 0:
        d.arc([c - rr, c - rr, c + rr, c + rr], -90, -90 + 360 * frac, fill=col, width=14 * S)
    num = str(int(math.ceil(rem - 1e-6)))
    size = 62 * S
    if rem <= 10:
        ph = rem % 1.0
        size = int(size * (1 + 0.16 * (0.5 - 0.5 * math.cos(2 * math.pi * ph))))
    f = font(size)
    tw = f.getlength(num)
    asc, desc = f.getmetrics()
    d.text((c - tw / 2, c - (asc + desc) / 2 - 2 * S), num, font=f, fill=col if rem <= 10 else INK)
    return im.resize((170, 170), Image.LANCZOS)


TIMER_POS = (W - 192, 6)


def cta_img(channel, phase):
    """Like & subscribe banner. phase 0..1 (after 0.5 the subscribe is pressed)."""
    name = (channel or '').strip()
    pw = 980 if name else 760
    ph = 124
    im = Image.new('RGBA', (pw + 20, ph + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([6, 14, pw + 6, ph + 14], 62, fill=(70, 30, 120, 110))
    d.rounded_rectangle([0, 4, pw, ph + 4], 62, fill=(255, 255, 255), outline=PURPLE, width=5)
    x = 22
    if name:
        d.ellipse([x, 18, x + 92, 110], fill=PINK, outline=(255, 255, 255), width=4)
        ini = name[0].upper() if name[0].isascii() else '★'
        draw_text(im, x + 46, 30, ini, 52, (255, 255, 255), anchor='m')
        x += 108
        nm = name if text_w(name, 38) < 250 else name[:14] + '…'
        draw_text(im, x, 36, nm, 38, INK)
        x += max(text_w(nm, 38), 120) + 22
    liked = phase > 0.35
    lw = 210
    d.rounded_rectangle([x, 22, x + lw, 106], 42, fill=BLUE if liked else (238, 240, 250), outline=BLUE, width=4)
    draw_text(im, x + 22, 36, '👍 LIKE', 40, (255, 255, 255) if liked else BLUE)
    x += lw + 18
    sub = phase > 0.55
    sw = 330
    d.rounded_rectangle([x, 22, x + sw, 106], 42, fill=(150, 150, 160) if sub else RED)
    draw_text(im, x + 22, 36, ('SUBSCRIBED 🔔' if sub else 'SUBSCRIBE 🔔'), 36 if sub else 40, (255, 255, 255))
    return im


_cta_cache = {}


def paste_cta(img, channel, t, dur, cy):
    """t: seconds since CTA start."""
    if t < 0 or t > dur:
        return
    key = 1 if t / dur > 0.55 else (2 if t / dur > 0.35 else 0)
    if key not in _cta_cache:
        _cta_cache[key] = cta_img(channel, {0: 0.0, 2: 0.4, 1: 0.6}[key])
    im = _cta_cache[key]
    if t < 0.5:
        off = (1 - ease_back(t / 0.5)) * 260
    elif t > dur - 0.4:
        off = ease_io((t - (dur - 0.4)) / 0.4) * 300
    else:
        off = 0
    img.paste(im, (int(W / 2 - im.width / 2), int(cy + off)), im)


# ---------------- diff analysis ----------------
def find_halves(arr):
    """arr HxWx3 float. returns (orientation, a0,a1,b0,b1) along split axis."""
    h, w = arr.shape[:2]
    horiz = w >= h * 1.15
    g = arr.mean(axis=2)
    if not horiz:
        g = g.T
    n = g.shape[1]
    std = g.std(axis=0)
    c0, c1 = int(n * 0.35), int(n * 0.65)
    low = std[c0:c1] < min(14.0, float(std[c0:c1].min()) * 2 + 4)
    best = None
    i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]:
                j += 1
            mid = (i + j) / 2 + c0
            if best is None or abs(mid - n / 2) < abs((best[0] + best[1]) / 2 - n / 2):
                best = (i + c0, j + c0)
            i = j
        else:
            i += 1
    if best is None:
        g0 = g1 = n // 2
    else:
        g0, g1 = best
    return horiz, g0, g1, n


def diff_map(L, Rr):
    a = ndimage.gaussian_filter(L, sigma=(2, 2, 0))
    b = ndimage.gaussian_filter(Rr, sigma=(2, 2, 0))
    return np.abs(a - b).sum(axis=2)


def align(L, Rr, rng=6):
    gl = ndimage.gaussian_filter(L.mean(axis=2), 1.5)
    gr = ndimage.gaussian_filter(Rr.mean(axis=2), 1.5)
    m = rng + 2
    h, w = gl.shape
    best = (1e18, 0, 0)
    ref = gl[m:h - m, m:w - m]
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            cand = gr[m + dy:h - m + dy, m + dx:w - m + dx]
            if cand.shape != ref.shape:
                continue
            e = float(np.abs(ref - cand).mean())
            if e < best[0]:
                best = (e, dx, dy)
    return best[1], best[2]


def color_name(rgb):
    import colorsys
    r, g, b = [v / 255 for v in rgb]
    hh, s, v = colorsys.rgb_to_hsv(r, g, b)
    hd = hh * 360
    if v < 0.18:
        return 'black'
    if s < 0.16:
        return 'white' if v > 0.82 else 'gray'
    if 15 <= hd < 45 and v < 0.6:
        return 'brown'
    for lim, nm in [(15, 'red'), (40, 'orange'), (68, 'yellow'), (160, 'green'), (195, 'teal'), (250, 'blue'), (290, 'purple'), (340, 'pink'), (361, 'red')]:
        if hd < lim:
            return nm
    return 'red'


def area_phrase(x, y, w, h):
    v = 'top' if y < h * .33 else ('bottom' if y > h * .67 else 'middle')
    hz = 'left' if x < w * .33 else ('right' if x > w * .67 else 'center')
    if v == 'middle' and hz == 'center':
        return 'In the middle'
    if v == 'middle':
        return f'On the {hz} side'
    if hz == 'center':
        return f'At the {v}'
    return f'In the {v} {hz}'


def describe(L, Rr, mask, cx, cy):
    h, w = mask.shape
    ring = ndimage.binary_dilation(mask, iterations=14) & ~ndimage.binary_dilation(mask, iterations=4)
    if ring.sum() < 10 or mask.sum() < 4:
        return '🔄', f'{area_phrase(cx, cy, w, h)}, something is different on the left than on the right'
    ml, mr = L[mask].mean(0), Rr[mask].mean(0)
    bl, br = L[ring].mean(0), Rr[ring].mean(0)
    cl = float(np.abs(ml - bl).sum()); cr = float(np.abs(mr - br).sum())
    tl = float(L[mask].std(0).mean()); tr = float(Rr[mask].std(0).mean())
    where = area_phrase(cx, cy, w, h)
    nl, nr = color_name(ml), color_name(mr)
    if cl > 40 and cr < cl * 0.45 and tr < tl * 0.8 + 6:
        return '❌', f'{where}, something {nl} is there on the left, but missing on the right'
    if cr > 40 and cl < cr * 0.45 and tl < tr * 0.8 + 6:
        return '➕', f'{where}, nothing is there on the left, but something {nr} appears on the right'
    if nl != nr:
        return '🎨', f'{where}, it is {nl} on the left, but {nr} on the right'
    return '🔄', f'{where}, a shape on the left is changed on the right'


def parse_user_diffs(text):
    items = []
    for line in (text or '').splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*%?\s*[,،\s]\s*(\d+(?:\.\d+)?)\s*%?\s*[|:\-–]?\s*(.*)$', line)
        if m:
            txt = m.group(3).strip()
            emo = None
            if txt and is_emoji(txt[0]):
                emo = txt[0]
                txt = txt[1:].lstrip('\ufe0f ').strip()
            items.append(dict(x=float(m.group(1)), y=float(m.group(2)), text=txt, emoji=emo, raw=line))
        else:
            items.append(dict(x=None, y=None, text=line, emoji=None, raw=line))
    return items


def analyze_pair(img, user_text=None, known=None, right_off=None):
    """Return dict with diffs in full-image coords + report notes. known: generated ground truth."""
    arr = np.asarray(img, dtype=np.float32)
    notes = []
    if right_off is not None:
        rx0, ry0 = right_off
        hw = rx0 - scenes.GUT if rx0 > 0 else arr.shape[1]
        if rx0 > 0:
            L = arr[:, :hw]; Rr = arr[:, rx0:rx0 + hw]
        else:
            hh = ry0 - scenes.GUT
            L = arr[:hh]; Rr = arr[ry0:ry0 + hh]
        dx = dy = 0
        horiz = rx0 > 0
    else:
        horiz, g0, g1, n = find_halves(arr)
        if horiz:
            nn = min(g0, arr.shape[1] - g1)
            L = arr[:, g0 - nn:g0] if g0 - nn > 0 else arr[:, :nn]
            lx0 = g0 - nn if g0 - nn > 0 else 0
            R0 = g1
            Rr0 = arr[:, R0:R0 + nn]
            dx, dy = align(L, Rr0)
            Lh, Lw = L.shape[:2]
            # crop overlap
            ys0, ys1 = max(0, -dy), min(Lh, Lh - dy)
            xs0, xs1 = max(0, -dx), min(Lw, Lw - dx, arr.shape[1] - R0 - dx)
            Lc = L[ys0:ys1, xs0:xs1]
            Rc = arr[ys0 + dy:ys1 + dy, R0 + xs0 + dx:R0 + xs1 + dx]
            L, Rr = Lc, Rc
            off_l = (lx0 + xs0, ys0)
            off_r = (R0 + xs0 + dx, ys0 + dy)
        else:
            nn = min(g0, arr.shape[0] - g1)
            ly0 = g0 - nn if g0 - nn > 0 else 0
            L = arr[ly0:ly0 + nn]
            R0 = g1
            Rr0 = arr[R0:R0 + nn]
            dx, dy = align(L, Rr0)
            Lh, Lw = L.shape[:2]
            ys0, ys1 = max(0, -dy), min(Lh, Lh - dy, arr.shape[0] - R0 - dy)
            xs0, xs1 = max(0, -dx), min(Lw, Lw - dx)
            Lc = L[ys0:ys1, xs0:xs1]
            Rc = arr[R0 + ys0 + dy:R0 + ys1 + dy, xs0 + dx:xs1 + dx]
            L, Rr = Lc, Rc
            off_l = (xs0, ly0 + ys0)
            off_r = (xs0 + dx, R0 + ys0 + dy)
    if right_off is not None:
        off_l = (0, 0)
        off_r = right_off
    h, w = L.shape[:2]
    if h < 60 or w < 60:
        return dict(ok=False, reason='نیمه‌های چپ/راست قابل جداسازی نبودند', diffs=[], notes=notes)
    D = diff_map(L, Rr)
    T = max(45.0, 3.5 * float(np.percentile(D, 95)))
    mask = D > T
    mask = ndimage.binary_opening(mask, iterations=2)
    mask = ndimage.binary_closing(mask, structure=np.ones((5, 5)), iterations=3)
    frac = mask.mean()
    if frac > 0.25 and known is None:
        return dict(ok=False, reason=f'دو نیمه بیش از حد متفاوت‌اند ({frac*100:.0f}٪ تصویر) — احتمالاً جفت هم‌تراز نیست یا دو تصویر متفاوت است', diffs=[], notes=notes)
    merged = ndimage.binary_dilation(mask, iterations=8)
    lab, nlab = ndimage.label(merged)
    minarea = max(50, 0.00012 * h * w)
    blobs = []
    for k in range(1, nlab + 1):
        reg = (lab == k) & mask
        a = int(reg.sum())
        if a < minarea:
            continue
        ys, xs = np.nonzero(reg)
        wts = D[ys, xs]
        cx, cy = float((xs * wts).sum() / wts.sum()), float((ys * wts).sum() / wts.sum())
        r = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2
        blobs.append(dict(cx=cx, cy=cy, r=float(r), area=a, score=float(wts.sum()), label=k))
    blobs.sort(key=lambda b: -b['score'])

    def window_check(x, y):
        x0, x1 = int(max(0, x - 45)), int(min(w, x + 45))
        y0, y1 = int(max(0, y - 45)), int(min(h, y + 45))
        if x1 <= x0 or y1 <= y0:
            return False, x, y
        win = D[y0:y1, x0:x1]
        ok = float(win.mean()) > max(12.0, T * 0.22) or float(win.max()) > T * 1.4 and float((win > T).mean()) > 0.04
        iy, ix = np.unravel_index(np.argmax(win), win.shape)
        return ok, x0 + ix, y0 + iy

    def blob_at(x, y):
        x, y = int(min(w - 1, max(0, x))), int(min(h - 1, max(0, y)))
        k = lab[y, x]
        for b in blobs:
            if b['label'] == k and k > 0:
                return b
        return None

    diffs = []
    used = set()
    if known is not None:
        for kd in known:
            ok, px, py = window_check(kd['x'], kd['y'])
            if ok:
                b = blob_at(px, py)
                if b:
                    used.add(b['label'])
                diffs.append(dict(emoji=kd['emoji'], text=kd['text'], x=kd['x'], y=kd['y'], r=kd['r'], src='generated'))
            else:
                notes.append(f'تفاوت ساخته‌شده «{kd["text"]}» در بررسی عددی قابل تشخیص نبود و حذف شد')
    else:
        for it in parse_user_diffs(user_text):
            if it['x'] is None:
                notes.append(f'مورد «{it["raw"]}» مختصات نداشت و قابل تأیید روی تصویر نبود؛ حذف شد')
                continue
            gx, gy = it['x'] / 100 * w, it['y'] / 100 * h
            ok, px, py = window_check(gx, gy)
            if not ok:
                notes.append(f'مورد «{it["raw"]}» در اطراف ({it["x"]:.0f}٪,{it["y"]:.0f}٪) اختلافی نداشت؛ نادرست بود و حذف شد')
                continue
            b = blob_at(px, py)
            if b and b['label'] in used:
                notes.append(f'مورد «{it["raw"]}» تکراری بود (همان ناحیه‌ی مورد قبلی)؛ حذف شد')
                continue
            if b:
                used.add(b['label'])
                cx, cy, r = b['cx'], b['cy'], b['r']
            else:
                cx, cy, r = float(px), float(py), 30.0
            emo, auto = describe(L, Rr, (lab == b['label']) & mask if b else (D > T), cx, cy)
            txt = it['text'] or auto
            if it['text'] and not re.search(r'left', txt, re.I):
                notes.append(f'متن «{it["text"]}» تأیید شد (قالب «on the left / on the right» را ندارد، همان‌طور که دادید نگه داشته شد)')
            else:
                notes.append(f'مورد «{it["raw"]}» تأیید شد')
            diffs.append(dict(emoji=it['emoji'] or emo, text=txt, x=cx, y=cy, r=r, src='user'))
        had_list = bool((user_text or '').strip())
        for b in blobs:
            if b['label'] in used or len(diffs) >= 10:
                continue
            used.add(b['label'])
            emo, txt = describe(L, Rr, (lab == b['label']) & mask, b['cx'], b['cy'])
            diffs.append(dict(emoji=emo, text=txt, x=b['cx'], y=b['cy'], r=b['r'], src='auto'))
            if had_list:
                notes.append(f'تفاوت واقعی دیگری پیدا و اضافه شد: «{txt}»')
        extra = [b for b in blobs if b['label'] not in used]
        if extra:
            notes.append(f'{len(extra)} ناحیه‌ی اختلاف کوچک‌تر به دلیل سقف ۱۰ تفاوت در هر تصویر کنار گذاشته شد')
    out = []
    for dd in diffs:
        out.append(dict(emoji=dd['emoji'], text=dd['text'][:120],
                        L=[float(dd['x'] + off_l[0]), float(dd['y'] + off_l[1])],
                        R=[float(dd['x'] + off_r[0]), float(dd['y'] + off_r[1])],
                        r=float(max(18, min(140, dd['r']))), src=dd.get('src')))
    if not out:
        return dict(ok=False, reason='هیچ تفاوت قابل‌اتکایی بین دو نیمه پیدا نشد', diffs=[], notes=notes)
    return dict(ok=True, diffs=out, notes=notes, horiz=bool(horiz))


# ---------------- TTS ----------------
KOK = None


def init_tts():
    global KOK
    try:
        from kokoro_onnx import Kokoro
        if os.path.exists(KOK_MODEL) and os.path.exists(KOK_VOICES):
            KOK = Kokoro(KOK_MODEL, KOK_VOICES)
    except Exception as e:
        log(f'راوی Kokoro در دسترس نیست ({e}); ویدیو بدون راوی ساخته می‌شود')
        KOK = None


TTS_DIR = os.path.join(ASSETS, 'tts')
os.makedirs(TTS_DIR, exist_ok=True)


def tts(text):
    h = hashlib.md5(('af_heart|0.93|v1|' + text).encode()).hexdigest()
    p = os.path.join(TTS_DIR, h + '.npy')
    if os.path.exists(p):
        return np.load(p)
    if KOK is None:
        return np.zeros(int(SR * (0.4 + 0.36 * len(text.split()))), np.float32)
    try:
        s, sr = KOK.create(text, voice='af_heart', speed=0.93, lang='en-us')
        y = resample_poly(np.asarray(s, dtype=np.float32), 147, 80).astype(np.float32)
        pk = float(np.abs(y).max()) or 1.0
        y = y / pk * 0.8
        np.save(p, y)
        return y
    except Exception as e:
        log(f'خطای TTS: {e}')
        return np.zeros(int(SR * (0.4 + 0.36 * len(text.split()))), np.float32)


def tlen(text):
    return len(tts(text)) / SR


# ---------------- music & fx ----------------
def make_music():
    beat = 0.6
    bar = 4 * beat
    chords = [[261.63, 329.63, 392.0], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66]]
    L = int(SR * bar * 4)
    out = np.zeros(L, np.float32)

    def add(a, seg):
        idx = (a + np.arange(len(seg))) % L
        out[idx] += seg.astype(np.float32)

    rs = np.random.RandomState(3)
    for ci, ch in enumerate(chords):
        s = int(ci * bar * SR)
        n = int(bar * SR)
        tt = np.arange(n) / SR
        env = np.minimum(1, tt / 0.5) * np.minimum(1, (bar - tt) / 0.5)
        pad = sum(np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * f * 2.001 * tt) for f in ch) * 0.03 * env
        add(s, pad)
        notes = [ch[0] * 2, ch[1] * 2, ch[2] * 2, ch[1] * 2] * 2
        for k, f in enumerate(notes):
            m = int(0.5 * SR)
            t2 = np.arange(m) / SR
            tri = 2 / np.pi * np.arcsin(np.sin(2 * np.pi * f * t2))
            add(s + int(k * beat / 2 * SR), tri * np.exp(-t2 * 7) * 0.045 * np.minimum(1, t2 / 0.005))
        m = int(2.3 * SR)
        t3 = np.arange(m) / SR
        fb = ch[0] * 4
        add(s, (np.sin(2 * np.pi * fb * t3) + 0.35 * np.sin(2 * np.pi * fb * 2.76 * t3)) * np.exp(-t3 * 2.0) * 0.028)
        for b in range(4):
            m = int(0.25 * SR)
            t4 = np.arange(m) / SR
            ph = 2 * np.pi * (45 * t4 + 70 / 30 * (1 - np.exp(-30 * t4)))
            add(s + int(b * beat * SR), np.sin(ph) * np.exp(-t4 * 16) * 0.11)
            mh = int(0.06 * SR)
            nz = np.diff(rs.randn(mh + 1)) * np.exp(-np.arange(mh) / SR * 70) * 0.012
            add(s + int((b + 0.5) * beat * SR), nz)
    Lc, Rc = out.copy(), out.copy()
    for k in range(1, 4):
        Lc += np.roll(out, int(0.42 * k * SR)) * (0.33 ** k)
        Rc += np.roll(out, int(0.55 * k * SR)) * (0.33 ** k)
    return np.stack([Lc, Rc], 1).astype(np.float32)


def tone(f, dur, amp, decay=6.0, harm=0.0):
    t = np.arange(int(dur * SR)) / SR
    y = (np.sin(2 * np.pi * f * t) + harm * np.sin(2 * np.pi * f * 2 * t)) * np.exp(-t * decay) * amp
    y *= np.minimum(1, t / 0.004)
    return y.astype(np.float32)


BEEP = tone(660, 0.22, 0.32, 9)
DING = np.zeros(int(1.5 * SR), np.float32)
DING[:int(1.2 * SR)] += tone(1318.5, 1.2, 0.26, 3, 0.3)
DING[int(0.15 * SR):int(0.15 * SR) + int(1.2 * SR)] += tone(1760, 1.2, 0.28, 3, 0.3)


def pop_sound():
    t = np.arange(int(0.12 * SR)) / SR
    f = 400 + 500 * np.minimum(1, t / 0.08)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t * 30) * 0.28).astype(np.float32)


POP = pop_sound()


# ---------------- frame segment writer ----------------
class Seg:
    def __init__(self, name):
        self.name = name
        self.dir = os.path.join(JOB, 'frames', name)
        shutil.rmtree(self.dir, ignore_errors=True)
        os.makedirs(self.dir, exist_ok=True)
        self.entries = []
        self.n = 0
        self.k = 0

    def save(self, img):
        p = os.path.join(self.dir, f'{self.k:06d}.jpg')
        img.save(p, quality=88)
        self.k += 1
        return p

    def add(self, img, frames):
        if frames <= 0:
            return None
        p = img if isinstance(img, str) else self.save(img)
        if self.entries and self.entries[-1][0] == p:
            self.entries[-1][1] += frames
        else:
            self.entries.append([p, frames])
        self.n += frames
        RENDER['done'] += frames
        if self.k % 40 == 0:
            setp(f'ساخت فریم‌ها: {self.name}', 22 + 66 * RENDER['done'] / max(1, RENDER['total']))
        return p

    def encode(self, out, nframes):
        lst = os.path.join(self.dir, 'list.txt')
        with open(lst, 'w') as f:
            for p, n in self.entries:
                f.write(f"file '{p}'\nduration {n / FPS:.6f}\n")
            f.write(f"file '{self.entries[-1][0]}'\n")
        tmp = out + '.tmp.mp4'
        cmd = [FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
               '-vf', 'fps=60,tpad=stop_mode=clone:stop_duration=0.3', '-frames:v', str(nframes),
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', '60', '-an', tmp]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('ffmpeg segment failed: ' + r.stderr[-800:])
        os.replace(tmp, out)
        shutil.rmtree(self.dir, ignore_errors=True)


RENDER = {'done': 0, 'total': 1}


# ---------------- scenes rendering ----------------
def marker_dirs():
    s = 1 / math.sqrt(2)
    return [(s, s), (-s, s), (s, -s), (-s, -s), (1, 0), (-1, 0), (0, 1), (0, -1)]


def pick_dir(cx, cy, r, rect, length=100):
    x, y, w, h = rect
    for dv in marker_dirs():
        tx, ty = cx - dv[0] * (r + length + 30), cy - dv[1] * (r + length + 30)
        if x + 8 < tx < x + w - 8 and y + 8 < ty < y + h - 8:
            return dv
    return marker_dirs()[0]


def draw_arrow(d, tip, dv, length=100, sw=10, hw=26, hl=38, color=RED):
    ux, uy = dv
    px, py = -uy, ux
    tx, ty = tip
    bx, by = tx - ux * hl, ty - uy * hl
    ex, ey = tx - ux * length, ty - uy * length
    pts = [(tx, ty), (bx + px * hw, by + py * hw), (bx + px * sw, by + py * sw), (ex + px * sw, ey + py * sw),
           (ex - px * sw, ey - py * sw), (bx - px * sw, by - py * sw), (bx - px * hw, by - py * hw)]
    d.polygon(pts, fill=color, outline=(255, 255, 255), width=4)


def disp_pt(pt, rect, iw):
    s = rect[2] / iw
    return rect[0] + pt[0] * s, rect[1] + pt[1] * s, s


def draw_red(img, diff, rect, iw, p_entry=1.0, loop_f=0):
    d = ImageDraw.Draw(img)
    for side in ('L', 'R'):
        cx, cy, s = disp_pt(diff[side], rect, iw)
        r0 = max(24, diff['r'] * s * 1.25 + 12)
        eb = ease_back(min(1, p_entry))
        pulse = 1 + 0.08 * math.sin(2 * math.pi * loop_f / 48)
        r = max(2, r0 * eb * pulse)
        d.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3], outline=(255, 255, 255), width=12)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RED, width=7)
        dv = pick_dir(cx, cy, r0, rect)
        bob = 8 * math.sin(2 * math.pi * loop_f / 48)
        dist = r0 + 8 + (1 - eb) * 150 + bob
        if p_entry > 0.02:
            draw_arrow(d, (cx - dv[0] * dist, cy - dv[1] * dist), dv)


def draw_yellow(img, diff, num, rect, iw):
    d = ImageDraw.Draw(img)
    for side in ('L', 'R'):
        cx, cy, s = disp_pt(diff[side], rect, iw)
        r = max(24, diff['r'] * s * 1.25 + 12)
        d.ellipse([cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2], outline=(255, 255, 255), width=10)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=YELLOW, width=6)
        bx, by = cx + r * 0.72, cy - r * 0.72
        d.ellipse([bx - 17, by - 17, bx + 17, by + 17], fill=YELLOW, outline=(255, 255, 255), width=3)
        draw_text(img, bx, by - 15, str(num), 24, INK, anchor='m')


ROW_COLS = [(255, 228, 240), (232, 224, 255), (222, 247, 228), (255, 238, 214), (220, 240, 255)]
ROW_Y0, ROW_H, ROW_GAP = CARD[1] + 178, 120, 13


def draw_card(img, pic, offx=0):
    x0, y0, x1, y1 = CARD
    x0 += offx; x1 += offx
    w, h = x1 - x0, y1 - y0
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0 + 6, y0 + 14, x1 + 6, y1 + 14], 40, fill=(150, 110, 200))
    img.paste(rainbow(w, h), (x0, y0), rr_mask(w, h, 40, 1))
    d.rounded_rectangle([x0 + 10, y0 + 10, x1 - 10, y1 - 10], 32, fill=(255, 255, 255))
    n = len(pic['diffs'])
    title = '1 difference!' if n == 1 else f'{n} differences!'
    draw_colorful(img, (x0 + x1) / 2, y0 + 26, title, 66)
    sub = f"{pic['name']}: here is what changed ✨"
    ss = 30
    while text_w(sub, ss) > w - 70 and ss > 20:
        ss -= 2
    draw_text(img, (x0 + x1) / 2, y0 + 120, sub, ss, PURPLE, anchor='m')


def draw_row(img, k, pos, diff, p=1.0, offx=0):
    if p <= 0:
        return
    x0, x1 = CARD[0] + 30 + offx, CARD[2] - 30 + offx
    sl = (1 - ease_out(min(1, p))) * 320
    x0 += sl; x1 += sl
    y = ROW_Y0 + pos * (ROW_H + ROW_GAP)
    d = ImageDraw.Draw(img)
    c = ROW_COLS[k % len(ROW_COLS)]
    d.rounded_rectangle([x0, y, x1, y + ROW_H], 26, fill=c, outline=tuple(max(0, v - 30) for v in c), width=3)
    d.ellipse([x0 + 14, y + ROW_H / 2 - 24, x0 + 62, y + ROW_H / 2 + 24], fill=RED, outline=(255, 255, 255), width=3)
    draw_text(img, x0 + 38, y + ROW_H / 2 - 21, str(k + 1), 30, (255, 255, 255), anchor='m')
    em = emoji_img(diff['emoji'][0] if diff['emoji'] else '🔎', 58)
    if em:
        img.paste(em, (int(x0 + 76), int(y + ROW_H / 2 - em.height / 2)), em)
    tx = x0 + 150
    maxw = x1 - tx - 16
    size, lines = fit_lines(diff['text'], maxw, 2, (31, 28, 25, 23, 21))
    lh = size * 1.22
    ty = y + ROW_H / 2 - lh * len(lines) / 2 - size * 0.12
    for li, ln in enumerate(lines):
        draw_text(img, tx, ty + li * lh, ln, size, INK)


def window_rows(k, n):
    """rows visible while showing row k (0-based), max 5."""
    start = max(0, k - 4)
    return list(range(start, k + 1))


def render_intro(seg, nframes, plan):
    base = BG.copy()
    ep = plan.get('episode')
    n = len(plan['pictures'])
    em_row = ['🔍', '🧩', '⏰', '👀', '🎨']
    static = base.copy()
    y = 470
    if ep:
        lbl = f'Episode {ep}'
        tw = text_w(lbl, 50)
        d = ImageDraw.Draw(static)
        d.rounded_rectangle([W / 2 - tw / 2 - 40 + 4, 150 + 6, W / 2 + tw / 2 + 40 + 4, 236 + 6], 44, fill=(70, 30, 120))
        d.rounded_rectangle([W / 2 - tw / 2 - 40, 150, W / 2 + tw / 2 + 40, 236], 44, fill=PINK, outline=(255, 255, 255), width=5)
        draw_text(static, W / 2, 162, lbl, 50, (255, 255, 255), anchor='m')
    draw_text(static, W / 2, y, 'Find all the differences between the two pictures', 46, INK, anchor='m')
    draw_text(static, W / 2, y + 66, 'before the timer runs out! ⏰', 46, INK, anchor='m')
    draw_text(static, W / 2, y + 150, f'{n} pictures  •  {int(plan["C"])} seconds each', 38, PURPLE, anchor='m')
    cta = plan['cta'].get('start')
    f = 0
    while f < nframes:
        step = min(3, nframes - f)
        t = f / FPS
        fr = static.copy()
        p = min(1, t / 0.7)
        sc = ease_back(p) if p < 1 else 1
        size = max(10, int(130 * sc))
        draw_colorful(fr, W / 2, 268 + (130 - size) * 0.5, 'Spot the Difference!', size)
        for i, e in enumerate(em_row):
            em = emoji_img(e, 96)
            if em:
                bob = 14 * math.sin(2 * math.pi * (t * 0.9 + i * 0.18))
                fr.paste(em, (int(W / 2 - 2.5 * 150 + i * 150 + 75 - em.width / 2), int(770 + bob)), em)
        if cta:
            paste_cta(fr, plan['channel'], t - cta['t'], cta['dur'], H - 200)
        seg.add(fr, step)
        f += step


def render_outro(seg, nframes, plan):
    static = BG.copy()
    draw_text(static, W / 2, 420, 'Like and subscribe for more puzzles!', 58, INK, anchor='m')
    if plan.get('channel'):
        draw_text(static, W / 2, 510, '@' + plan['channel'].lstrip('@'), 44, PURPLE, anchor='m')
    cta = plan['cta'].get('end')
    f = 0
    while f < nframes:
        step = min(3, nframes - f)
        t = f / FPS
        fr = static.copy()
        p = min(1, t / 0.7)
        size = max(10, int(140 * (ease_back(p) if p < 1 else 1)))
        draw_colorful(fr, W / 2, 200 + (140 - size) * 0.5, 'Great job! 🎉', size)
        for i, e in enumerate(['👍', '🔔', '🧩']):
            em = emoji_img(e, 130)
            if em:
                bob = 16 * math.sin(2 * math.pi * (t * 0.8 + i * 0.25))
                fr.paste(em, (int(W / 2 - 230 + i * 230 - em.width / 2), int(620 + bob)), em)
        if cta:
            paste_cta(fr, plan['channel'], t - cta['t'], cta['dur'], H - 200)
        seg.add(fr, step)
        f += step


def render_picture(seg, i, plan):
    pic = plan['pictures'][i]
    n = len(plan['pictures'])
    src = Image.open(pic['path']).convert('RGB')
    iw, ih = src.size
    _fr.clear()
    rc = fit_rect(iw, ih, CD_BOX)
    ra = fit_rect(iw, ih, AN_BOX)
    tm = pic['timing']
    C = plan['C']
    base = BG.copy()
    draw_badge(base, i, n)
    draw_colorful(base, W / 2 + 10, 40, TITLE, 52)
    paste_framed(base, src, rc, 'cd')
    CF = F(C)
    cta = plan['cta'].get('middle') if plan['cta'].get('middle', {}).get('pic') == i else None
    f = 0
    while f < CF:
        rem = (CF - f) / FPS
        step = 3 if rem > 10 else 1
        step = min(step, CF - f)
        fr = base.copy()
        ti = timer_img(rem, C)
        fr.paste(ti, TIMER_POS, ti)
        if cta:
            paste_cta(fr, plan['channel'], f / FPS - cta['t'], cta['dur'], H - 190)
        seg.add(fr, step)
        f += step
    # ---- answers
    ans = BG.copy()
    draw_badge(ans, i, n)
    draw_colorful(ans, W / 2 + 10, 40, "Time's up! ⏰", 60)
    ti = timer_img(0, C, done=True)
    ans.paste(ti, TIMER_POS, ti)
    HF = F(tm['H'])
    for k in range(36):
        p = ease_io((k + 1) / 36)
        rect = tuple(int(rc[j] + (ra[j] - rc[j]) * p) for j in range(4))
        fr = ans.copy()
        paste_framed(fr, src, rect, 'anim')
        cp = max(0, (k - 8) / 28)
        draw_card(fr, pic, offx=int((1 - ease_out(min(1, cp))) * 950))
        seg.add(fr, 1)
    head = ans.copy()
    paste_framed(head, src, ra, 'an')
    draw_card(head, pic)
    ans_img = head.copy()
    seg.add(head, max(1, HF - 36))
    diffs = pic['diffs']
    for k, dfx in enumerate(diffs):
        SF = F(tm['slots'][k])
        rows = window_rows(k, len(diffs))
        basek = ans_img.copy()
        for pos, rk in enumerate(rows[:-1]):
            draw_row(basek, rk, pos, diffs[rk])
        for j in range(k):
            draw_yellow(basek, diffs[j], j + 1, ra, iw)
        for e in range(18):
            fr = basek.copy()
            draw_row(fr, k, len(rows) - 1, dfx, (e + 1) / 18)
            draw_red(fr, dfx, ra, iw, (e + 1) / 18, e)
            seg.add(fr, 1)
        basek2 = basek.copy()
        draw_row(basek2, k, len(rows) - 1, dfx)
        rest = SF - 18
        loop_paths = []
        for lf in range(min(48, max(0, rest))):
            fr = basek2.copy()
            draw_red(fr, dfx, ra, iw, 1.0, 18 + lf)
            loop_paths.append(fr)
        paths = []
        for idx in range(rest):
            li = idx % 48
            if li >= len(paths):
                paths.append(seg.add(loop_paths[li], 1))
            else:
                seg.add(paths[li], 1)
    fin = ans_img.copy()
    rows = window_rows(len(diffs) - 1, len(diffs))
    for pos, rk in enumerate(rows):
        draw_row(fin, rk, pos, diffs[rk])
    for j in range(len(diffs)):
        draw_yellow(fin, diffs[j], j + 1, ra, iw)
    seg.add(fin, F(tm['hold']))


# ---------------- planning ----------------
def ffprobe_json(path):
    r = subprocess.run([FFPROBE, '-v', 'error', '-show_entries', 'stream=codec_type,width,height,r_frame_rate,nb_frames:format=duration',
                        '-of', 'json', path], capture_output=True, text=True)
    return json.loads(r.stdout or '{}')


def prepare_pictures():
    pics, excluded, report_pics = [], [], []
    os.makedirs(os.path.join(JOB, 'prepared'), exist_ok=True)
    if CFG['source'] == 'ai':
        T = CFG['duration_min'] * 60
        nd = int(CFG.get('ai_diffs') or 5)
        count = int(CFG.get('ai_count') or 0)
        if count <= 0:
            A = 3.5 + 4.8 * nd + 1.5
            count = max(1, int((T - 24) // (38 + A)))
        keys = list(scenes.SCENES.keys())
        stype = CFG.get('ai_type') or 'mixed'
        style = CFG.get('ai_style') or 'vivid'
        styles = list(scenes.STYLES.keys())
        seed0 = int(CFG.get('seed') or 7)
        for i in range(count):
            sk = keys[i % len(keys)] if stype == 'mixed' else stype
            sty = styles[i % len(styles)] if style == 'mixed' else style
            pair, title, gt, roff = scenes.generate_pair(sk, sty, nd, seed0 * 1000 + i)
            pth = os.path.join(JOB, 'prepared', f'pic_{i:03d}.png')
            pair.save(pth)
            res = analyze_pair(pair, known=gt, right_off=roff)
            fname = f'{title} #{i + 1}'
            if res['ok']:
                pics.append(dict(path=pth, name=title, diffs=res['diffs'], file=fname))
            else:
                excluded.append(dict(file=fname, reason=res['reason']))
            report_pics.append(dict(file=fname, notes=res['notes'], ok=res['ok']))
            setp(f'ساخت تصویر {i + 1}/{count}', 2 + 10 * (i + 1) / count)
    else:
        imgs = CFG.get('images') or []
        for i, it in enumerate(imgs):
            pth = os.path.join(JOB, 'input', it['file'])
            fname = it.get('original') or it['file']
            try:
                im = Image.open(pth).convert('RGB')
            except Exception as e:
                excluded.append(dict(file=fname, reason=f'فایل تصویر خوانده نشد: {e}'))
                continue
            if max(im.size) > 2400:
                s = 2400 / max(im.size)
                im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            res = analyze_pair(im, user_text=it.get('diffs') or '')
            base = re.sub(r'^\d+[_\-\s]*', '', os.path.splitext(fname)[0])
            name = re.sub(r'[^A-Za-z0-9 ]+', ' ', base.replace('_', ' ').replace('-', ' ')).strip().title()
            if not name:
                name = f'Picture {len(pics) + 1}'
            if res['ok']:
                pp = os.path.join(JOB, 'prepared', f'pic_{i:03d}.png')
                im.save(pp)
                pics.append(dict(path=pp, name=name[:28], diffs=res['diffs'], file=fname))
            else:
                excluded.append(dict(file=fname, reason=res['reason']))
            report_pics.append(dict(file=fname, notes=res['notes'], ok=res['ok']))
            setp(f'تحلیل تصویر {i + 1}/{len(imgs)}', 2 + 10 * (i + 1) / max(1, len(imgs)))
    return pics, excluded, report_pics


def build_plan():
    T = CFG['duration_min'] * 60
    warnings = []
    pics, excluded, report_pics = prepare_pictures()
    if not pics:
        raise RuntimeError('هیچ تصویری با تفاوت قابل‌اتکا باقی نماند؛ ویدیو ساخته نشد')
    setp('ساخت صدای راوی (Kokoro)', 13)
    init_tts()
    ep = CFG.get('episode')
    channel = (CFG.get('channel') or '').strip()
    cta_on = bool(CFG.get('cta_enabled'))
    cta_pos = CFG.get('cta_positions') or []
    intro_txt = ''
    if ep:
        intro_txt += f'Welcome to episode {numw(int(ep))} of our spot the difference series! '
    else:
        intro_txt += 'Welcome to spot the difference! '
    intro_txt += 'Look closely at the two pictures, and find every difference before the timer runs out. '
    if cta_on and 'start' in cta_pos:
        intro_txt += "Don't forget to like and subscribe! "
    intro_txt += "Let's go!"
    outro_txt = 'Great job! Thanks for playing. Like and subscribe for more puzzles!'
    timesup = "Time's up! Here are the differences."
    intro_len = max(12.0, tlen(intro_txt) + 1.6)
    outro_len = max(10.0, tlen(outro_txt) + 1.8)

    def timing_for(p):
        Hh = max(3.0, tlen(timesup) + 0.6)
        slots = []
        for k, dfx in enumerate(p['diffs']):
            txt = f'Number {numw(k + 1)}. {dfx["text"]}.'
            slots.append(round(max(4.0, tlen(txt) + 0.9), 3))
        return dict(H=round(Hh, 3), slots=slots, hold=1.5)

    total_tts = sum(len(p['diffs']) for p in pics) + 2
    done = 0
    for p in pics:
        p['timing'] = timing_for(p)
        done += len(p['diffs'])
        setp('ساخت صدای راوی (Kokoro)', 13 + 8 * done / total_tts)

    def calc_C(ps):
        A = sum(p['timing']['H'] + sum(p['timing']['slots']) + p['timing']['hold'] for p in ps)
        return (T - intro_len - outro_len - A) / len(ps)

    C = calc_C(pics)
    dropped = []
    while C < 13 and len(pics) > 1:
        dropped.append(pics.pop())
        C = calc_C(pics)
    if dropped:
        warnings.append(f'{len(dropped)} تصویر آخر ({", ".join(d["file"] for d in dropped)}) در {CFG["duration_min"]} دقیقه جا نشد و کنار گذاشته شد')
    if C < 13:
        warnings.append('حتی با یک تصویر هم زمان کافی نبود؛ شمارش معکوس ۱۳ ثانیه گذاشته شد و ویدیو کمی بلندتر شد')
        C = 13
    elif C < 36:
        warnings.append(f'برای جا شدن همه‌ی تصاویر، شمارش معکوس هر تصویر {int(C)} ثانیه شد (کمتر از ۳۶ ثانیه‌ی پیشنهادی)')
    if C > 180:
        warnings.append(f'تعداد تصاویر برای {CFG["duration_min"]} دقیقه کم است؛ شمارش به ۱۸۰ ثانیه محدود شد و ویدیو کوتاه‌تر از زمان انتخابی است')
        C = 180
    C = float(int(C))
    # narration lines per picture
    for i, p in enumerate(pics):
        lines = [(0.35, f'Picture {numw(i + 1)}. How many differences can you spot? Time starts now!')]
        if C >= 42:
            lines.append((C - 30, 'Thirty seconds left!'))
        if C >= 16:
            lines.append((C - 10, 'Ten seconds left! Keep looking!'))
        p['cd_lines'] = lines
        tts(lines[0][1])
    cta = {}
    if cta_on:
        if 'start' in cta_pos:
            cta['start'] = dict(t=max(2.0, intro_len - 7.5), dur=6.0)
        if 'end' in cta_pos:
            cta['end'] = dict(t=2.2, dur=min(6.5, outro_len - 2.5))
        if 'middle' in cta_pos:
            mid = len(pics) // 2
            busy = [(l[0], l[0] + tlen(l[1]) + 0.3) for l in pics[mid]['cd_lines']]
            ct = None
            mt = 'Enjoying the puzzles? Hit like and subscribe!'
            ml = tlen(mt)
            t = 5.0
            while t + 6 < C - 5:
                if all(t + ml + 0.5 < b0 or t > b1 for b0, b1 in busy):
                    ct = t
                    break
                t += 0.5
            if ct is None:
                cta['middle'] = dict(pic=mid, t=min(5.0, max(0.5, C - 7)), dur=min(6.0, max(2.0, C - 1)), say=None)
            else:
                cta['middle'] = dict(pic=mid, t=ct, dur=6.0, say=mt)
    plan = dict(T=T, C=C, intro=intro_len, outro=outro_len, intro_txt=intro_txt, outro_txt=outro_txt, timesup=timesup,
                pictures=pics, episode=ep, channel=channel, cta=cta, excluded=excluded, report_pics=report_pics,
                warnings=warnings, narration=KOK is not None)
    # frame counts
    segs = [('intro', F(intro_len))]
    for i, p in enumerate(pics):
        tm = p['timing']
        segs.append((f'pic_{i:03d}', F(C) + F(tm['H']) + sum(F(s) for s in tm['slots']) + F(tm['hold'])))
    used = sum(n for _, n in segs)
    of = int(max(F(outro_len), int(T * FPS) - used))
    segs.append(('outro', of))
    plan['outro'] = of / FPS
    plan['segments'] = segs
    return plan


# ---------------- audio ----------------
def place(buf, t, clip):
    a = int(round(t * SR))
    if a >= len(buf) or a < 0:
        return
    b = min(len(buf), a + len(clip))
    buf[a:b] += clip[:b - a]


def segment_audio(name, nframes, offset, plan, idx):
    n = nframes * SPF
    voice = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    if name == 'intro':
        place(voice, 0.6, tts(plan['intro_txt']))
    elif name == 'outro':
        place(voice, 0.5, tts(plan['outro_txt']))
        place(fx, 0.2, DING * 0.8)
    else:
        p = plan['pictures'][idx]
        C = plan['C']
        tm = p['timing']
        for t, txt in p['cd_lines']:
            place(voice, t, tts(txt))
        mc = plan['cta'].get('middle')
        if mc and mc.get('pic') == idx and mc.get('say'):
            place(voice, mc['t'] + 0.3, tts(mc['say']))
        for s in range(4, 0, -1):
            place(fx, C - s, BEEP)
        place(fx, C, DING)
        place(voice, C + 0.45, tts(plan['timesup']))
        t = C + tm['H']
        for k, dfx in enumerate(p['diffs']):
            place(fx, t + 0.05, POP)
            place(voice, t + 0.3, tts(f'Number {numw(k + 1)}. {dfx["text"]}.'))
            t += F(tm['slots'][k]) / FPS
    vm = (np.abs(voice) > 0.003).astype(np.float32)
    vm = ndimage.maximum_filter1d(vm, size=int(0.25 * SR))
    duck = 1 - 0.5 * ndimage.uniform_filter1d(vm, size=int(0.35 * SR))
    idxs = (offset + np.arange(n)) % len(MUSIC)
    mus = MUSIC[idxs] * 0.9
    out = mus * duck[:, None] + (voice + fx)[:, None]
    return out.astype(np.float32)


# ---------------- main ----------------
def fmt_ts(sec):
    sec = int(sec)
    return f'{sec // 60}:{sec % 60:02d}'


def main():
    global BG, MUSIC
    lockf = open(os.path.join(ROOT, 'data', 'worker.lock'), 'w')
    status['status'] = 'queued'
    setp('در صف انتظار (کار دیگری در حال ساخت است)', 0)
    fcntl.flock(lockf, fcntl.LOCK_EX)
    status['status'] = 'running'
    setp('آماده‌سازی فونت‌ها و مدل‌ها', 1)
    ensure_assets()
    plan_path = os.path.join(JOB, 'plan.json')
    if os.path.exists(plan_path):
        plan = json.load(open(plan_path))
        init_tts()
        log('برنامه‌ی قبلی پیدا شد؛ ادامه از همان‌جا')
    else:
        log('تحلیل و تأیید تفاوت‌ها ...')
        plan = build_plan()
        json.dump(plan, open(plan_path, 'w'))
    log(f"{len(plan['pictures'])} تصویر، شمارش {int(plan['C'])} ثانیه، راوی: {'Kokoro' if plan['narration'] else 'ندارد'}")
    BG = make_bg()
    MUSIC = make_music()
    segdir = os.path.join(JOB, 'segments')
    os.makedirs(segdir, exist_ok=True)
    RENDER['total'] = sum(n for _, n in plan['segments'])
    RENDER['done'] = 0
    for si, (name, nf) in enumerate(plan['segments']):
        out = os.path.join(segdir, name + '.mp4')
        if os.path.exists(out):
            RENDER['done'] += nf
            continue
        log(f'رندر بخش {name} ({nf / FPS:.1f}s)')
        seg = Seg(name)
        if name == 'intro':
            render_intro(seg, nf, plan)
        elif name == 'outro':
            render_outro(seg, nf, plan)
        else:
            render_picture(seg, int(name.split('_')[1]), plan)
        if seg.n != nf:
            log(f'هشدار: تعداد فریم {name} {seg.n} به جای {nf}')
        setp(f'انکود بخش {name}', 22 + 66 * RENDER['done'] / RENDER['total'])
        seg.encode(out, nf)
    setp('ساخت صدا (موسیقی + راوی + افکت‌ها)', 89)
    adir = os.path.join(JOB, 'audio')
    os.makedirs(adir, exist_ok=True)
    offset = 0
    peak = 1e-6
    apaths = []
    for si, (name, nf) in enumerate(plan['segments']):
        idx = int(name.split('_')[1]) if name.startswith('pic_') else -1
        a = segment_audio(name, nf, offset, plan, idx)
        peak = max(peak, float(np.abs(a).max()))
        ap = os.path.join(adir, name + '.wav')
        sf.write(ap, a, SR, subtype='FLOAT')
        apaths.append(ap)
        offset += nf * SPF
    gain = 0.92 / peak
    setp('ترکیب نهایی MP4', 93)
    vl = os.path.join(JOB, 'vlist.txt')
    al = os.path.join(JOB, 'alist.txt')
    with open(vl, 'w') as f:
        for name, _ in plan['segments']:
            f.write(f"file '{os.path.join(segdir, name + '.mp4')}'\n")
    with open(al, 'w') as f:
        for ap in apaths:
            f.write(f"file '{ap}'\n")
    final = os.path.join(JOB, 'video.mp4')
    tmp = os.path.join(JOB, 'video.tmp.mp4')
    cmd = [FFMPEG, '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', vl, '-f', 'concat', '-safe', '0', '-i', al,
           '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', f'volume={gain:.5f}', '-c:a', 'aac', '-b:a', '192k',
           '-ar', '44100', '-ac', '2', '-movflags', '+faststart', '-shortest', tmp]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('mux failed: ' + r.stderr[-800:])
    setp('بررسی سلامت فایل (ffprobe + decode کامل)', 96)
    info = ffprobe_json(tmp)
    dec = subprocess.run([FFMPEG, '-v', 'error', '-i', tmp, '-f', 'null', '-'], capture_output=True, text=True)
    if dec.returncode != 0:
        raise RuntimeError('decode check failed: ' + dec.stderr[-500:])
    os.replace(tmp, final)
    shutil.rmtree(adir, ignore_errors=True)
    vs = next((s for s in info.get('streams', []) if s.get('codec_type') == 'video'), {})
    dur = float(info.get('format', {}).get('duration', 0))
    # timestamps
    ts = [dict(t=0, label='Intro')]
    acc = 0
    for name, nf in plan['segments']:
        if name.startswith('pic_'):
            i = int(name.split('_')[1])
            ts.append(dict(t=acc / FPS, label=f"Picture {i + 1} – {plan['pictures'][i]['name']} ({len(plan['pictures'][i]['diffs'])} differences)"))
        elif name == 'outro':
            ts.append(dict(t=acc / FPS, label='Answers recap & outro'))
        acc += nf
    for t in ts:
        t['ts'] = fmt_ts(t['t'])
    status['report'] = dict(
        pictures=[dict(index=i + 1, name=p['name'], file=p['file'], diffs=[dict(n=k + 1, emoji=d['emoji'], text=d['text'], src=d.get('src')) for k, d in enumerate(p['diffs'])])
                  for i, p in enumerate(plan['pictures'])],
        analysis=plan['report_pics'], excluded=plan['excluded'], warnings=plan['warnings'], timestamps=ts,
        countdown=int(plan['C']), narration=plan['narration'], episode=plan.get('episode'),
        probe=dict(width=vs.get('width'), height=vs.get('height'), fps=vs.get('r_frame_rate'), duration=round(dur, 2),
                   size_mb=round(os.path.getsize(final) / 1e6, 1)),
    )
    status['output'] = final
    status['status'] = 'done'
    setp('تمام شد ✅', 100)
    log(f'ویدیو آماده است: {vs.get("width")}x{vs.get("height")} @ {vs.get("r_frame_rate")} — {dur:.1f}s')
    shutil.rmtree(os.path.join(JOB, 'frames'), ignore_errors=True)
    if CFG.get('cleanup_segments', True):
        shutil.rmtree(segdir, ignore_errors=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        status['status'] = 'error'
        status['error'] = str(e)
        status['stage'] = 'خطا'
        log('خطا: ' + str(e))
        sys.exit(1)
