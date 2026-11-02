"""Procedural cartoon scene generator for spot-the-difference pairs (ground truth known)."""
import math
import random
from PIL import Image, ImageDraw

HW, HH = 880, 760  # half size (1x)
GUT = 24
SS = 2  # supersample

BASECOL = {
    'red': (235, 60, 60), 'orange': (255, 140, 30), 'yellow': (255, 208, 40), 'green': (70, 190, 80),
    'blue': (50, 130, 240), 'purple': (150, 80, 230), 'pink': (255, 105, 180), 'white': (250, 250, 250),
    'brown': (150, 95, 55),
}
STYLES = {
    'pastel': dict(sky=((196, 228, 255), (238, 247, 255)), ground=(178, 226, 168), outline=(84, 62, 112), sat=0.6, light=0.22),
    'vivid': dict(sky=((80, 170, 255), (178, 224, 255)), ground=(96, 196, 90), outline=(35, 25, 50), sat=1.0, light=0.0),
    'night': dict(sky=((22, 26, 72), (74, 60, 132)), ground=(40, 86, 70), outline=(12, 10, 28), sat=0.95, light=0.0),
    'retro': dict(sky=((246, 214, 160), (255, 238, 206)), ground=(196, 168, 108), outline=(86, 54, 34), sat=0.62, light=0.06),
}
EMOJI = {'sun': '☀️', 'cloud': '☁️', 'tree': '🌳', 'pine': '🌲', 'house': '🏠', 'flower': '🌸', 'balloon': '🎈',
         'bird': '🐦', 'car': '🚗', 'fish': '🐟', 'star': '⭐', 'planet': '🪐', 'rocket': '🚀', 'moon': '🌕',
         'ufo': '🛸', 'boat': '⛵', 'mushroom': '🍄', 'apple': '🍎', 'snowman': '⛄', 'bubble': '🫧',
         'seaweed': '🌿', 'ball': '⚽', 'umbrella': '⛱️'}
DEFCOL = {'sun': ['yellow'], 'cloud': ['white'], 'tree': ['green'], 'pine': ['green'],
          'house': ['red', 'blue', 'yellow', 'pink', 'orange'], 'flower': ['red', 'pink', 'purple', 'yellow', 'orange', 'blue'],
          'balloon': ['red', 'blue', 'pink', 'purple', 'orange', 'green'], 'bird': ['blue', 'red', 'yellow'],
          'car': ['red', 'blue', 'yellow', 'green', 'orange'], 'fish': ['orange', 'yellow', 'blue', 'pink'],
          'star': ['yellow'], 'planet': ['purple', 'orange', 'blue', 'pink'], 'rocket': ['red', 'blue'],
          'moon': ['yellow'], 'ufo': ['green', 'purple'], 'boat': ['red', 'blue', 'yellow'], 'mushroom': ['red'],
          'apple': ['red', 'green'], 'snowman': ['red', 'blue'], 'bubble': ['blue'], 'seaweed': ['green'],
          'ball': ['red', 'blue', 'orange'], 'umbrella': ['pink', 'red', 'blue', 'yellow', 'purple']}
BASESIZE = {'sun': 58, 'cloud': 52, 'tree': 70, 'pine': 70, 'house': 72, 'flower': 34, 'balloon': 36, 'bird': 30,
            'car': 56, 'fish': 40, 'star': 34, 'planet': 56, 'rocket': 60, 'moon': 52, 'ufo': 54, 'boat': 56,
            'mushroom': 36, 'apple': 32, 'snowman': 56, 'bubble': 24, 'seaweed': 54, 'ball': 30, 'umbrella': 56}
SMALL_ADD = ['bird', 'star', 'flower', 'balloon', 'apple', 'ball', 'bubble', 'mushroom']

SCENES = {
    'park': ('Sunny Park', 'grass', [('sun', 'sky'), ('cloud', 'sky'), ('cloud', 'sky'), ('bird', 'sky'), ('balloon', 'sky'),
                                      ('tree', 'land'), ('house', 'land'), ('tree', 'land'), ('flower', 'front'),
                                      ('flower', 'front'), ('mushroom', 'front'), ('ball', 'front')]),
    'beach': ('Beach Day', 'beach', [('sun', 'sky'), ('cloud', 'sky'), ('bird', 'sky'), ('cloud', 'sky'), ('boat', 'sea'),
                                      ('fish', 'sea'), ('boat', 'sea'), ('umbrella', 'front'), ('ball', 'front'),
                                      ('star', 'front'), ('umbrella', 'front')]),
    'space': ('Outer Space', 'space', [('planet', 'sky'), ('moon', 'sky'), ('star', 'sky'), ('star', 'sky'),
                                        ('rocket', 'land'), ('ufo', 'land'), ('planet', 'land'), ('star', 'front'),
                                        ('rocket', 'front'), ('planet', 'front'), ('star', 'front')]),
    'city': ('Busy City', 'city', [('sun', 'sky'), ('cloud', 'sky'), ('balloon', 'sky'), ('bird', 'sky'),
                                    ('house', 'land'), ('tree', 'land'), ('house', 'land'), ('house', 'land'),
                                    ('car', 'front'), ('car', 'front'), ('car', 'front')]),
    'farm': ('Happy Farm', 'grass', [('sun', 'sky'), ('cloud', 'sky'), ('bird', 'sky'), ('cloud', 'sky'), ('house', 'land'),
                                      ('tree', 'land'), ('tree', 'land'), ('apple', 'front'), ('flower', 'front'),
                                      ('mushroom', 'front'), ('apple', 'front'), ('flower', 'front')]),
    'underwater': ('Under the Sea', 'water', [('fish', 'sky'), ('bubble', 'sky'), ('fish', 'sky'), ('bubble', 'sky'),
                                               ('fish', 'land'), ('fish', 'land'), ('fish', 'land'), ('star', 'front'),
                                               ('seaweed', 'front'), ('mushroom', 'front'), ('seaweed', 'front')]),
    'winter': ('Winter Wonderland', 'snow', [('moon', 'sky'), ('cloud', 'sky'), ('star', 'sky'), ('bird', 'sky'),
                                             ('pine', 'land'), ('house', 'land'), ('pine', 'land'), ('snowman', 'front'),
                                             ('pine', 'front'), ('ball', 'front')]),
}
ZONES = {'sky': (0.10, 0.34), 'land': (0.47, 0.60), 'sea': (0.50, 0.58), 'front': (0.74, 0.88)}


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def col(name, st):
    c = BASECOL[name]
    g = sum(c) / 3
    c = tuple(int(g + (v - g) * st['sat']) for v in c)
    return mix(c, (255, 255, 255), st['light'])


def lighter(c, t=0.45):
    return mix(c, (255, 255, 255), t)


def darker(c, t=0.35):
    return mix(c, (0, 0, 0), t)


# ---------------- object drawing (coordinates already supersampled) ----------------
def E(d, x, y, rx, ry, fill, o, w):
    d.ellipse([x - rx, y - ry, x + rx, y + ry], fill=fill, outline=o, width=w)


def P(d, pts, fill, o, w):
    d.polygon(pts, fill=fill, outline=o, width=w)


def R(d, x0, y0, x1, y1, fill, o, w, r=0):
    if r:
        d.rounded_rectangle([x0, y0, x1, y1], r, fill=fill, outline=o, width=w)
    else:
        d.rectangle([x0, y0, x1, y1], fill=fill, outline=o, width=w)


def draw_obj(d, kind, x, y, s, c, o, w, st):
    if kind == 'sun':
        for k in range(12):
            a = k * math.pi / 6
            d.line([x + math.cos(a) * s * 1.15, y + math.sin(a) * s * 1.15, x + math.cos(a) * s * 1.5, y + math.sin(a) * s * 1.5], fill=c, width=int(w * 1.6))
        E(d, x, y, s, s, c, o, w)
        d.arc([x - s * .5, y - s * .3, x + s * .5, y + s * .55], 20, 160, fill=o, width=w)
    elif kind == 'cloud':
        parts = [(-0.55, 0.1, 0.5), (0.0, -0.2, 0.62), (0.55, 0.1, 0.5), (0.0, 0.25, 0.5)]
        for px, py, pr in parts:
            E(d, x + px * s * 1.4, y + py * s, pr * s + w, pr * s + w, o, None, 0)
        for px, py, pr in parts:
            E(d, x + px * s * 1.4, y + py * s, pr * s, pr * s, c, None, 0)
    elif kind == 'tree':
        R(d, x - s * .16, y + s * .1, x + s * .16, y + s * 1.0, BASECOL['brown'], o, w)
        E(d, x, y - s * .2, s * .75, s * .7, c, o, w)
        E(d, x - s * .25, y - s * .35, s * .18, s * .14, lighter(c), None, 0)
    elif kind == 'pine':
        R(d, x - s * .13, y + s * .55, x + s * .13, y + s * 1.0, BASECOL['brown'], o, w)
        for k, (yy, ww) in enumerate([(0.6, .75), (0.15, .6), (-0.3, .45)]):
            P(d, [(x - s * ww, y + s * yy), (x + s * ww, y + s * yy), (x, y + s * (yy - .75))], c, o, w)
    elif kind == 'house':
        R(d, x - s * .7, y - s * .2, x + s * .7, y + s * .9, c, o, w)
        P(d, [(x - s * .9, y - s * .15), (x + s * .9, y - s * .15), (x, y - s * .95)], darker(c, .3), o, w)
        R(d, x - s * .17, y + s * .38, x + s * .17, y + s * .9, BASECOL['brown'], o, w)
        R(d, x - s * .55, y + s * .05, x - s * .27, y + s * .33, (190, 230, 255), o, w)
        R(d, x + s * .27, y + s * .05, x + s * .55, y + s * .33, (190, 230, 255), o, w)
    elif kind == 'flower':
        d.line([x, y, x, y + s * 1.8], fill=(60, 150, 60), width=int(w * 1.4))
        E(d, x + s * .45, y + s * 1.2, s * .35, s * .16, (80, 180, 80), o, max(1, w // 2))
        for k in range(5):
            a = k * 2 * math.pi / 5 - math.pi / 2
            E(d, x + math.cos(a) * s * .55, y + math.sin(a) * s * .55, s * .42, s * .42, c, o, w)
        E(d, x, y, s * .33, s * .33, BASECOL['yellow'], o, w)
    elif kind == 'balloon':
        d.line([x, y + s * 1.2, x + s * .2, y + s * 2.4], fill=o, width=max(2, w // 2))
        E(d, x, y, s * .85, s * 1.1, c, o, w)
        E(d, x - s * .3, y - s * .4, s * .17, s * .25, lighter(c, .6), None, 0)
    elif kind == 'bird':
        E(d, x, y, s, s * .7, c, o, w)
        P(d, [(x + s * .9, y - s * .1), (x + s * 1.5, y + s * .1), (x + s * .9, y + s * .3)], BASECOL['orange'], o, w)
        P(d, [(x - s * .4, y), (x + s * .2, y), (x - s * .2, y - s * .9)], darker(c, .2), o, w)
        E(d, x + s * .45, y - s * .2, s * .12, s * .12, o, None, 0)
    elif kind == 'car':
        R(d, x - s * .55, y - s * .75, x + s * .45, y - s * .1, c, o, w, int(s * .2))
        R(d, x - s * 1.1, y - s * .25, x + s * 1.1, y + s * .4, c, o, w, int(s * .2))
        R(d, x - s * .42, y - s * .65, x + s * .32, y - s * .22, (190, 230, 255), o, max(1, w // 2), int(s * .1))
        for wx in (-0.6, 0.6):
            E(d, x + wx * s, y + s * .42, s * .3, s * .3, (50, 50, 60), o, w)
            E(d, x + wx * s, y + s * .42, s * .12, s * .12, (200, 200, 210), None, 0)
    elif kind == 'fish':
        P(d, [(x - s * .8, y), (x - s * 1.5, y - s * .6), (x - s * 1.5, y + s * .6)], darker(c, .15), o, w)
        E(d, x, y, s, s * .65, c, o, w)
        E(d, x + s * .5, y - s * .15, s * .14, s * .14, (255, 255, 255), o, max(1, w // 2))
    elif kind == 'star':
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            r = s if k % 2 == 0 else s * .45
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        P(d, pts, c, o, w)
    elif kind == 'planet':
        d.arc([x - s * 1.6, y - s * .45, x + s * 1.6, y + s * .45], 180, 360, fill=o, width=int(w * 2.2))
        E(d, x, y, s, s, c, o, w)
        d.arc([x - s * 1.6, y - s * .45, x + s * 1.6, y + s * .45], 0, 180, fill=o, width=int(w * 2.2))
        E(d, x - s * .3, y - s * .3, s * .2, s * .15, lighter(c), None, 0)
    elif kind == 'rocket':
        P(d, [(x - s * .35, y + s * .5), (x - s * .75, y + s * 1.0), (x - s * .35, y + s * .1)], BASECOL['orange'], o, w)
        P(d, [(x + s * .35, y + s * .5), (x + s * .75, y + s * 1.0), (x + s * .35, y + s * .1)], BASECOL['orange'], o, w)
        R(d, x - s * .38, y - s * .5, x + s * .38, y + s * .9, (245, 245, 250), o, w, int(s * .2))
        P(d, [(x - s * .38, y - s * .45), (x + s * .38, y - s * .45), (x, y - s * 1.2)], c, o, w)
        E(d, x, y, s * .2, s * .2, (120, 200, 255), o, w)
    elif kind == 'moon':
        E(d, x, y, s, s, c, o, w)
        for cx, cy, cr in [(-.35, -.2, .18), (.3, .25, .22), (.1, -.45, .1)]:
            E(d, x + cx * s, y + cy * s, cr * s, cr * s, darker(c, .15), None, 0)
    elif kind == 'ufo':
        E(d, x, y - s * .25, s * .5, s * .45, (170, 230, 255), o, w)
        E(d, x, y + s * .1, s * 1.2, s * .38, c, o, w)
        for k in (-0.6, 0, 0.6):
            E(d, x + k * s, y + s * .12, s * .1, s * .1, BASECOL['yellow'], None, 0)
    elif kind == 'boat':
        d.line([x, y + s * .2, x, y - s * 1.2], fill=o, width=w)
        P(d, [(x + s * .08, y - s * 1.1), (x + s * .08, y), (x + s * .85, y)], (255, 255, 255), o, w)
        P(d, [(x - s * 1.1, y + s * .05), (x + s * 1.1, y + s * .05), (x + s * .75, y + s * .55), (x - s * .75, y + s * .55)], c, o, w)
    elif kind == 'mushroom':
        R(d, x - s * .3, y, x + s * .3, y + s * .9, (250, 238, 220), o, w, int(s * .1))
        d.chord([x - s, y - s * .75, x + s, y + s * .55], 180, 360, fill=c, outline=o, width=w)
        for cx, cy in [(-.45, -.2), (.1, -.5), (.5, -.15)]:
            E(d, x + cx * s, y + cy * s, s * .13, s * .13, (255, 255, 255), None, 0)
    elif kind == 'apple':
        d.line([x, y - s * .8, x + s * .1, y - s * 1.2], fill=BASECOL['brown'], width=w)
        E(d, x + s * .35, y - s * 1.0, s * .28, s * .13, (80, 180, 80), o, max(1, w // 2))
        E(d, x, y, s, s * .92, c, o, w)
        E(d, x - s * .35, y - s * .35, s * .16, s * .2, lighter(c, .6), None, 0)
    elif kind == 'snowman':
        E(d, x, y + s * .45, s * .65, s * .6, (255, 255, 255), o, w)
        E(d, x, y - s * .45, s * .45, s * .42, (255, 255, 255), o, w)
        R(d, x - s * .5, y - s * .12, x + s * .5, y + s * .05, c, o, max(1, w // 2), int(s * .05))
        R(d, x - s * .3, y - s * 1.2, x + s * .3, y - s * .8, (40, 40, 50), o, w)
        P(d, [(x, y - s * .45), (x + s * .4, y - s * .38), (x, y - s * .33)], BASECOL['orange'], None, 0)
    elif kind == 'bubble':
        E(d, x, y, s, s, lighter(c, .7), c, w)
        E(d, x - s * .35, y - s * .35, s * .2, s * .2, (255, 255, 255), None, 0)
    elif kind == 'seaweed':
        pts_l, pts_r = [], []
        for k in range(9):
            t = k / 8
            yy = y + s * 1.0 - t * s * 2.0
            xx = x + math.sin(t * 6) * s * .25
            ww = s * .22 * (1 - t * .8)
            pts_l.append((xx - ww, yy))
            pts_r.append((xx + ww, yy))
        P(d, pts_l + pts_r[::-1], c, o, w)
    elif kind == 'ball':
        E(d, x, y, s, s, c, o, w)
        d.arc([x - s * 1.4, y - s * .6, x + s * .6, y + s * 1.4], 270, 360, fill=(255, 255, 255), width=int(w * 1.5))
        d.line([x - s * .95, y, x + s * .95, y], fill=(255, 255, 255), width=int(w * 1.2))
    elif kind == 'umbrella':
        d.line([x, y - s * .2, x, y + s * 1.2], fill=o, width=w)
        d.pieslice([x - s * 1.1, y - s * .95, x + s * 1.1, y + s * .45], 180, 360, fill=c, outline=o, width=w)


def draw_background(d, ground, st, rng_seed):
    W, H = HW * SS, HH * SS
    sky = st['sky']
    if ground in ('space',):
        sky = ((14, 16, 48), (52, 34, 96))
    if ground == 'water':
        sky = ((80, 190, 235), (24, 96, 170)) if st is not STYLES['night'] else ((20, 60, 120), (8, 24, 60))
    for yy in range(0, H, 4):
        d.rectangle([0, yy, W, yy + 4], fill=mix(sky[0], sky[1], yy / H))
    r = random.Random(rng_seed)
    if ground == 'space' or st is STYLES['night']:
        for _ in range(70):
            x, y = r.randint(0, W), r.randint(0, int(H * (0.95 if ground == 'space' else 0.5)))
            rr = r.choice([2, 3, 4])
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 255, 230))
    g = st['ground']
    if ground == 'grass':
        d.ellipse([-W * .2, H * .48, W * .7, H * .9], fill=lighter(g, .15))
        d.rectangle([0, H * .62, W, H], fill=g)
    elif ground == 'beach':
        d.rectangle([0, H * .44, W, H * .66], fill=col('blue', st))
        for k in range(8):
            d.arc([k * W / 8, H * .5, (k + 1) * W / 8, H * .56], 200, 340, fill=lighter(col('blue', st), .5), width=6)
        d.rectangle([0, H * .66, W, H], fill=(246, 220, 160) if st is not STYLES['night'] else (120, 110, 90))
    elif ground == 'city':
        for k in range(6):
            bx = k * W / 6
            d.rectangle([bx + 10, H * (.3 + .05 * (k % 3)), bx + W / 6 - 10, H * .66], fill=mix(sky[1], (120, 130, 160), .45))
        d.rectangle([0, H * .64, W, H * .7], fill=(205, 205, 210))
        d.rectangle([0, H * .7, W, H], fill=(95, 98, 110))
        for k in range(7):
            d.rectangle([k * W / 7 + 20, H * .84, k * W / 7 + 120, H * .855], fill=(250, 250, 250))
    elif ground == 'water':
        d.rectangle([0, H * .86, W, H], fill=(236, 210, 150) if st is not STYLES['night'] else (90, 84, 70))
    elif ground == 'snow':
        d.ellipse([W * .3, H * .5, W * 1.3, H * .9], fill=(236, 244, 255))
        d.rectangle([0, H * .63, W, H], fill=(248, 251, 255))
    elif ground == 'space':
        d.ellipse([-W * .2, H * .78, W * 1.2, H * 1.5], fill=(150, 140, 170))
        for cx, cy, cr in [(.2, .9, 30), (.6, .86, 22), (.85, .93, 34)]:
            d.ellipse([W * cx - cr, H * cy - cr * .5, W * cx + cr, H * cy + cr * .5], fill=(120, 110, 145))


def render_half(objs, ground, st, seed):
    img = Image.new('RGB', (HW * SS, HH * SS), (255, 255, 255))
    d = ImageDraw.Draw(img)
    draw_background(d, ground, st, seed)
    ow = 4 * SS
    order = {'sky': 0, 'land': 1, 'sea': 1, 'front': 2, 'add': 2}
    for ob in sorted(objs, key=lambda o: (order.get(o['zone'], 1), o['y'])):
        draw_obj(d, ob['kind'], ob['x'] * SS, ob['y'] * SS, ob['s'] * SS, col(ob['color'], st), st['outline'], ow, st)
    return img.resize((HW, HH), Image.LANCZOS)


def area_word(x, y):
    v = 'top' if y < HH * .38 else ('bottom' if y > HH * .68 else 'middle')
    h = 'left' if x < HW * .33 else ('right' if x > HW * .66 else 'center')
    if v == 'middle' and h == 'center':
        return 'in the middle'
    if v == 'middle':
        return f'on the {h} side'
    if h == 'center':
        return f'at the {v}'
    return f'in the {v} {h}'


def generate_pair(scene_key, style_key, n_diffs, seed):
    rng = random.Random(seed)
    title, ground, layout = SCENES[scene_key]
    st = STYLES.get(style_key, STYLES['vivid'])
    objs = []
    byzone = {}
    for kind, zone in layout:
        byzone.setdefault(zone, []).append(kind)
    for zone, kinds in byzone.items():
        rng.shuffle(kinds)
        n = len(kinds)
        cw = HW / n
        y0, y1 = ZONES[zone]
        for i, kind in enumerate(kinds):
            s = BASESIZE[kind] * rng.uniform(0.88, 1.12) * (1.08 if zone == 'front' else 1.0)
            s = min(s, cw / 3.2)
            x = cw * (i + 0.5) + rng.uniform(-cw * .12, cw * .12)
            y = HH * rng.uniform(y0, y1)
            objs.append(dict(kind=kind, zone=zone, x=x, y=y, s=s, color=rng.choice(DEFCOL[kind])))
    right = [dict(o) for o in objs]
    diffs = []
    candidates = list(range(len(objs)))
    rng.shuffle(candidates)
    kinds_count = {}
    for o in objs:
        kinds_count[o['kind']] = kinds_count.get(o['kind'], 0) + 1
    types = ['color', 'remove', 'size', 'add', 'color', 'remove', 'color', 'size', 'add', 'color']
    rng.shuffle(types)
    used = set()
    ti = 0
    while len(diffs) < n_diffs and ti < len(types) * 2:
        typ = types[ti % len(types)]
        ti += 1
        if typ == 'add':
            added = {dd.get('kind') for dd in diffs}
            opts_k = [k for k in SMALL_ADD if k not in added] or SMALL_ADD
            kind = rng.choice(opts_k)
            s = BASESIZE[kind] * 0.95
            placed = None
            for _ in range(300):
                x, y = rng.uniform(s * 1.8, HW - s * 1.8), rng.uniform(s * 1.8, HH - s * 2.2)
                if all(math.hypot(x - o['x'], y - o['y']) > (s + o['s']) * 1.7 for o in right):
                    placed = (x, y)
                    break
            if not placed:
                continue
            c = rng.choice(DEFCOL[kind])
            nob = dict(kind=kind, zone='add', x=placed[0], y=placed[1], s=s, color=c)
            right.append(nob)
            diffs.append(dict(emoji=EMOJI[kind], kind=kind,
                              text=f'No {kind} {area_word(placed[0], placed[1])} on the left, but a {c} {kind} on the right',
                              x=placed[0], y=placed[1], r=s * 1.35))
            continue
        idx = next((i for i in candidates if i not in used), None)
        if idx is None:
            break
        used.add(idx)
        o = objs[idx]
        ro = right[idx]
        name = o['kind']
        qual = f' {area_word(o["x"], o["y"])}' if kinds_count[name] > 1 else ''
        if typ == 'color':
            opts = [c for c in BASECOL if c != o['color'] and c not in ('white',) and not (o['color'] in ('yellow', 'orange') and c in ('yellow', 'orange'))]
            if name in ('cloud', 'snowman') or not opts:
                opts = ['pink', 'blue', 'yellow'] if name == 'cloud' else opts
            c2 = rng.choice(opts)
            ro['color'] = c2
            text = f'The {name}{qual} is {o["color"]} on the left, but {c2} on the right'
        elif typ == 'remove':
            ro['removed'] = True
            text = f'There is a {name}{qual} on the left, but it is missing on the right'
        else:
            big = rng.random() < 0.5
            ro['s'] = o['s'] * (1.45 if big else 0.6)
            text = f'The {name}{qual} is {"small" if big else "big"} on the left, but {"big" if big else "small"} on the right'
        diffs.append(dict(emoji=EMOJI[name], text=text, x=o['x'], y=o['y'], r=max(o['s'], ro['s']) * 1.4))
    right = [o for o in right if not o.get('removed')]
    seedbg = rng.randint(0, 10 ** 6)
    L = render_half(objs, ground, st, seedbg)
    Rimg = render_half(right, ground, st, seedbg)
    pair = Image.new('RGB', (HW * 2 + GUT, HH), (255, 255, 255))
    pair.paste(L, (0, 0))
    pair.paste(Rimg, (HW + GUT, 0))
    return pair, title, diffs, (HW + GUT, 0)
