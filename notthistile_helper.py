"""Not This Tile? helper for the Aion 2 Shugo Festival.

Watches the game screen. When the reveal turns most tiles red (the safe tiles stay blue), it keeps
the reddest frame, crops it to the grid, and shows it in up to two windows until the next reveal:
  - an always-on-top overlay on the game screen
  - a normal window, meant for the second monitor
It only reads pixels from the screen. It never touches the game process or sends any input.

  python notthistile_helper.py                    # watch the screen
  python notthistile_helper.py --video FILE.mkv   # replay a recording instead (for testing)
"""
import argparse
import base64
import ctypes
import json
import logging
import sys
import threading
import time
import tkinter as tk
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import ttk

import cv2
import mss
import numpy as np

# The folder the helper runs from: next to the script, or next to NotThisTile.exe in the packaged version.
APP_DIR = Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "helper.log"
SNAP_DIR = APP_DIR / "snapshots"  # newest raw snapshot of each reveal, for checking afterwards
STALLED_TEXT = "Screen capture stopped! See helper.log."
DEFAULTS = {
    "enabled": True,
    "overlay": True,
    "second": True,
    "monitor": 1,
    "overlay_geom": "480x320+40+40",
    "second_geom": "960x640+80+80",
}
RED_THRESHOLD = 0.04  # share of red pixels in the screen centre; ~0.005 normally, 0.11-0.46 in a reveal
CAPTURE_FPS = 15
# (columns, rows) per round, the same in all nine recorded games: rounds 1-8 are 6x6, 8x8, 10x8, 10x8, 10x10,
# 12x10, 12x10 and 14x10.
GRID_SIZES = [(6, 6), (8, 8), (10, 8), (10, 10), (12, 10), (14, 10)]
RECT = 960  # side of the flattened top-down grid used for measuring
LAYOUTS_FILE = APP_DIR / "layouts.json"


def load_layouts():
    """Known safe-tile layouts from layouts.json, as True/False grids [row, column] with row 0 at the back."""
    try:
        grids = []
        for entry in json.loads(LAYOUTS_FILE.read_text(encoding="utf-8"))["layouts"]:
            cols, rows = map(int, entry["size"].split("x"))
            grid = np.zeros((rows, cols), bool)
            for name in entry["safe"].split():
                grid[int(name[1:]) - 1, ord(name[0]) - 65] = True
            grids.append(grid)
        return grids
    except (OSError, ValueError, KeyError, IndexError):
        logging.exception("couldn't read %s, so no layouts are known", LAYOUTS_FILE.name)
        return []


def red_mask(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return ((h <= 10) | (h >= 170)) & (s >= 60) & (v >= 80)


def blue_mask(bgr, lo=95, hi=125):  # safe tiles themselves are hue 103-112; clothing spreads wider
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (h >= lo) & (h <= hi) & (s >= 60) & (v >= 80)


class RevealDetector:
    """Feed frames in; returns a cropped snapshot whenever a redder reveal frame is seen."""

    def __init__(self):
        self.active = False
        self.best_score = 0.0
        self.episode = 0  # counts reveals, so a reveal's labelled picture isn't replaced by an unlabelled one

    def feed(self, frame):
        small = cv2.resize(frame, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
        mask = red_mask(small)
        sh, sw = mask.shape
        score = mask[int(sh * .1):int(sh * .9), int(sw * .15):int(sw * .85)].mean()
        if score < RED_THRESHOLD:
            self.active = False
            return None
        if not self.active:
            self.active, self.best_score = True, 0.0
            self.episode += 1
        if score <= self.best_score:
            return None
        self.best_score = score
        return crop_to_grid(frame, mask)


def crop_to_grid(frame, small_mask):
    """Crop to the largest red blob (the grid) plus a margin, so the snapshot is mostly grid."""
    closed = cv2.morphologyEx(small_mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed)
    if n < 2:
        return frame
    x, y, w, h = stats[1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]), :4] * 4
    mx, my = int(w * .06), int(h * .06)
    fh, fw = frame.shape[:2]
    return frame[max(0, y - my):min(fh, y + h + my), max(0, x - mx):min(fw, x + w + mx)].copy()


def longest_line(pts, tol):
    """The largest set of points lying on one straight line (RANSAC)."""
    rng = np.random.default_rng(0)
    best = pts
    best_n = 0
    for _ in range(150):
        a, b = pts[rng.choice(len(pts), 2, replace=False)]
        d = b - a
        norm = np.linalg.norm(d)
        if norm < 1:
            continue
        on = np.abs((pts - a) @ np.array([-d[1], d[0]]) / norm) < tol
        if on.sum() > best_n:
            best, best_n = pts[on], on.sum()
    return best if best_n >= 10 else pts


def grid_corners(snap):
    """The grid's outer corners (TL, TR, BR, BL) in the snapshot, or None."""
    m = red_mask(snap).astype(np.uint8)  # red only: teal UI panels would join the grid blob
    k = max(3, snap.shape[1] // 80)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2 * k, 2 * k), np.uint8))  # cut thin bridges to UI
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return None
    blob = (lab == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
    cnt = max(cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
    hull = cv2.convexHull(cnt)
    peri = cv2.arcLength(hull, True)
    for eps in np.linspace(0.005, 0.1, 80):
        approx = cv2.approxPolyDP(hull, eps * peri, True).reshape(-1, 2).astype(np.float32)
        if len(approx) == 5:
            # A corner is cut off, e.g. a red corner tile boxed in by blue ones drops out of the red mask. Drop
            # the shortest side and extend its neighbours to where they meet.
            i = np.linalg.norm(np.roll(approx, -1, 0) - approx, axis=1).argmin()
            a, b, c, d = (approx[(i + k) % 5] for k in (-1, 0, 1, 2))
            m = np.array([b - a, c - d]).T
            if abs(np.linalg.det(m)) > 1e-6:
                approx = np.insert(np.delete(approx, [i, (i + 1) % 5], 0), min(i, (i + 1) % 5),
                                   a + np.linalg.solve(m, c - a)[0] * (b - a), 0)
        if len(approx) == 4:
            break
    else:
        return None
    p = approx
    s, d = p.sum(1), p[:, 1] - p[:, 0]
    q = np.float32([p[s.argmin()], p[d.argmin()], p[s.argmax()], p[d.argmax()]])
    pts = cnt.reshape(-1, 2).astype(np.float32)
    # Fit a robust straight line to each side; the corners are where the lines meet. This places a corner
    # correctly even when a UI panel or player hides it.
    for _ in range(3):
        lines = []
        for i in range(4):
            p0, p1 = q[i], q[(i + 1) % 4]
            length = np.linalg.norm(p1 - p0)
            if length < 1:
                return None
            u = (p1 - p0) / length
            t, dist = (pts - p0) @ u, np.abs((pts - p0) @ np.array([-u[1], u[0]]))
            side = pts[(t > .1 * length) & (t < .9 * length) & (dist < .03 * length + 3)]
            if len(side) < 10:
                return None
            side = longest_line(side, 2 + .003 * length)  # skip stretches that follow a panel's outline
            vx, vy, x0, y0 = cv2.fitLine(side, cv2.DIST_L2, 0, .01, .01).ravel()
            lines.append((np.array([x0, y0]), np.array([vx, vy])))
        corners = []
        for i in range(4):
            (a0, ad), (b0, bd) = lines[i - 1], lines[i]
            a = np.array([ad, -bd]).T
            if abs(np.linalg.det(a)) < 1e-6:
                return None
            corners.append(a0 + np.linalg.solve(a, b0 - a0)[0] * ad)
        q = np.float32(corners)
    return q


def hidden_edge(snap, q, cw, rh):
    """True if red tiles carry on past the back or a side of the outline: the real edge is hidden (e.g. behind a
    panel), so the outline is a row or column short and the names would be wrong. Outside a real edge there's
    floor. The front edge doesn't matter: rows are counted from the back, so front rows may be hidden."""
    m = RECT // 4  # room for the bands below even when there are only 4-5 rows (rows up to ~400 px)
    flat =cv2.getPerspectiveTransform(q, np.float32([[m, m], [m + RECT, m], [m + RECT, m + RECT], [m, m + RECT]]))
    size = (RECT + 2 * m, RECT + 2 * m)
    red = cv2.warpPerspective(red_mask(snap).astype(np.uint8), flat, size)
    seen = cv2.warpPerspective(np.ones(snap.shape[:2], np.uint8), flat, size)
    inner, a = slice(m, m + RECT), m + RECT
    bands = [(slice(int(m - .6 * rh), int(m - .15 * rh)), inner),
             (inner, slice(int(m - .6 * cw), int(m - .15 * cw))), (inner, slice(int(a + .15 * cw), int(a + .6 * cw)))]
    # Off a real edge the red share is at most ~0.05 (glow, effects); a hidden row of tiles gives 0.1 or more.
    return any(seen[band].sum() > 50 and red[band].sum() / seen[band].sum() > .07 for band in bands)


def level_front(q):
    """Replace the front edge with a true row line. The outline's front edge is often the screen's bottom or the
    skill bar's top, which would skew every row. The game camera doesn't roll, so the horizon is level: it is the
    horizontal line through the point where the sides meet, and every row line passes through the point where the
    back edge meets the horizon. The new front edge goes through that point and the higher front corner."""
    line = lambda a, b: np.cross([*a, 1.], [*b, 1.])
    left, right = line(q[0], q[3]), line(q[1], q[2])
    horizon = np.cross(np.cross(left, right), [1., 0, 0])
    front = np.cross(np.cross(line(q[0], q[1]), horizon), [*q[2 if q[2, 1] < q[3, 1] else 3], 1.])
    br, bl = np.cross(front, right), np.cross(front, left)
    return np.float32([q[0], q[1], br[:2] / br[2], bl[:2] / bl[2]])


def read_grid(snap):
    """Returns (corners, cols, row height, visible rows, safe cells as (col, row-from-back)), or a note saying why
    not. The flattened grid spans RECT x RECT; rows start at the back edge. The front rows may be missing (behind
    the skill bar or below the screen), so the row height comes from the blue tiles, not from a row count."""
    q = grid_corners(snap)
    if q is None:
        return "Couldn't read the grid"
    w = snap.shape[1]
    # crop_to_grid leaves a margin unless the grid hits the screen edge. Only the back corners must show: the
    # front edge is rebuilt below, so the front may be off-screen or behind the skill bar.
    if (q[:2, 0] < 3).any() or (q[:2, 0] > w - 4).any() or (q[:2, 1] < 3).any():
        return "Grid cut off - zoom out"
    q = level_front(q)
    flat = cv2.getPerspectiveTransform(q, np.float32([[0, 0], [RECT, 0], [RECT, RECT], [0, RECT]]))
    blue = cv2.warpPerspective(blue_mask(snap).astype(np.uint8) * 255, flat, (RECT, RECT)) > 0
    closed = cv2.morphologyEx(blue.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(closed)
    ids = 1 + np.flatnonzero(stats[1:, cv2.CC_STAT_AREA] > (RECT / 25) ** 2 * .3)
    stats = stats[ids]
    if not len(stats):
        return "Couldn't read the grid"
    # Each blue tile is one tile, so its flattened width gives the column count (the sides are always visible).
    est_c = RECT / np.median(stats[:, cv2.CC_STAT_WIDTH])
    sizes = GRID_SIZES + [(r, c) for c, r in GRID_SIZES]  # the camera may be turned, e.g. 10x8 seen as 8x10
    cols = min({c for c, _ in sizes}, key=lambda c: abs(c - est_c))
    max_rows = max(r for c, r in sizes if c == cols)
    if abs(cols - est_c) > .8:
        return "Couldn't read the grid"
    cw = RECT / cols
    # Row height from tile-wide blobs, leaving out flat ones (blue skill-bar icons, UI strips) and tiles cut by
    # the outline's back or front edge.
    wide = (stats[:, cv2.CC_STAT_WIDTH] > .6 * cw) & (stats[:, cv2.CC_STAT_WIDTH] < 1.4 * cw)
    whole = (stats[:, 1] > 2) & (stats[:, 1] + stats[:, 3] < RECT - 2)
    hs = stats[wide & whole if (wide & whole).any() else wide, cv2.CC_STAT_HEIGHT]
    if not len(hs):
        return "Couldn't read the grid"
    rh = np.median(hs[hs >= .5 * hs.max()])
    # Blobs much smaller than a tile are blue clothing, effects or UI strips, not tiles.
    tile_like = (stats[:, cv2.CC_STAT_WIDTH] > .6 * cw) & (stats[:, cv2.CC_STAT_HEIGHT] > .6 * rh)
    if not tile_like.any():
        return "Couldn't read the grid"
    # Row height: the one that puts the tiles' top and bottom edges on row boundaries (edges cut off by the
    # front of the outline don't count).
    ys = np.concatenate([stats[tile_like, 1], stats[tile_like, 1] + stats[tile_like, 3]]).astype(float)
    ys = ys[(ys > 2) & (ys < RECT - 2)]
    if len(ys):
        rh = min(np.linspace(.85, 1.15, 61) * rh, key=lambda s: np.abs(ys - np.round(ys / s) * s).mean())
    rows = int(RECT / rh + .5)  # rows at least half visible
    if rows > max_rows or rows < 2:
        return "Couldn't read the grid"
    if hidden_edge(snap, q, cw, rh):
        return "Grid edge hidden - move camera or UI"
    # The blue tiles' edges must sit on cell boundaries; if many don't, the grid was misread: label nothing.
    # A few may be off where a player in blue clothes stands on or next to a safe tile.
    off = [abs(v / size - round(v / size)) > .25 for x, y, bw, bh, _ in stats[tile_like]
           for v, size in ((x, cw), (x + bw, cw), (y, rh), (y + bh, rh)) if v < RECT - 2]
    if np.mean(off) > .2:
        return "Couldn't read the grid"
    # Only tile-blue that belongs to a tile-sized blob counts.
    tight = cv2.warpPerspective(blue_mask(snap, 100, 114).astype(np.uint8), flat, (RECT, RECT)) > 0
    tiles = tight & np.isin(lab, ids[tile_like])

    def is_safe(c, r):
        # Mostly tile-blue, and in at least 3 of 4 quarters: a player hides one quarter, a UI strip covers two.
        inner = tiles[int((r + .2) * rh):int((r + .8) * rh), int((c + .2) * cw):int((c + .8) * cw)]
        quarters = [tiles[int((r + y0) * rh):int((r + y0 + .3) * rh), int((c + x0) * cw):int((c + x0 + .3) * cw)]
                    for y0 in (.2, .5) for x0 in (.2, .5)]
        return inner.mean() > .5 and sum(qr.mean() > .3 for qr in quarters) >= 3
    safe = [(c, r) for r in range(rows) for c in range(cols) if is_safe(c, r)]
    if not safe:
        return "Couldn't read the grid"
    # Tiles that are clearly red (traps). A player standing on a tile can hide its colour, so this is kept strict.
    red_flat = cv2.warpPerspective(red_mask(snap).astype(np.uint8), flat, (RECT, RECT))
    red = {(c, r) for r in range(rows) for c in range(cols)
           if red_flat[int((r + .2) * rh):int((r + .8) * rh), int((c + .2) * cw):int((c + .8) * cw)].mean() > .5}
    return q, cols, rh, rows, safe, red


def match_layout(layouts, cols, rows, safe, red):
    """The safe cells (col, row-from-back) of the one known layout that fits this reading, or None. A layout fits
    when it has every safe tile that was read and none on a tile read as red. The camera may be turned, so each
    layout is tried in all four directions. Front rows that weren't seen can't rule a layout out."""
    if len(safe) < 2:
        return None
    fits = set()
    for grid in layouts:
        for turn in range(4):
            view = np.rot90(grid, turn)
            if view.shape[1] != cols or view.shape[0] < rows:
                continue
            cells = frozenset((c, r) for r, c in zip(*np.nonzero(view)))
            if set(safe) <= cells and not cells & red:
                fits.add(cells)
    return next(iter(fits)) if len(fits) == 1 else None


WHITE, YELLOW = (255, 255, 255), (0, 220, 255)


def put_text(img, text, center, size, color=WHITE):
    """Text with a dark outline, centred on `center`, about `size` pixels wide."""
    scale = max(.4, size / 45)
    thick = max(1, int(scale * 2))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thick)
    org = (int(center[0] - tw / 2), int(center[1] + th / 2))
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thick, cv2.LINE_AA)


def with_bar(img, text, color=WHITE):
    """The picture with `text` in a black bar above it, so the text never covers the grid."""
    bar = max(24, img.shape[0] // 14)
    out = cv2.copyMakeBorder(img, bar, 0, 0, 0, cv2.BORDER_CONSTANT)
    width = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][0]
    size = 45 * min(out.shape[1] * .9 / width, bar * .6 / 22)  # put_text uses scale = size / 45
    put_text(out, text, (out.shape[1] / 2, bar / 2), size, color)
    return out


def cell_name(c, r):
    return f"{chr(65 + c)}{r + 1}"


def label_grid(snap, layouts=()):
    """Name the tiles like a spreadsheet: columns A.. left to right along the back edge, rows 1.. from the back.
    If the reading fits one known layout, the safe tiles it adds (e.g. under players) are named in yellow and the
    whole layout is listed above the picture. Returns (picture, None, column count, what was read, for the log), or
    (picture with a note above it, the note, None, None) when the grid couldn't be read."""
    found = read_grid(snap)
    if isinstance(found, str):
        return with_bar(snap, found), found, None, None
    q, cols, rh, rows, safe, red = found
    layout = match_layout(layouts, cols, rows, safe, red)
    pad = int(snap.shape[1] * .04)  # room for the edge labels
    out = cv2.copyMakeBorder(snap, pad, 0, pad, 0, cv2.BORDER_CONSTANT)
    back = cv2.getPerspectiveTransform(np.float32([[0, 0], [RECT, 0], [RECT, RECT], [0, RECT]]),
                                       q + np.float32([pad, pad]))
    cw = RECT / cols

    def to_img(x, y):
        return cv2.perspectiveTransform(np.float32([[[x, y]]]), back)[0, 0]

    def width_at(x, y):  # on-screen width of one tile around a flattened point
        return np.linalg.norm(to_img(x + cw / 2, y) - to_img(x - cw / 2, y))

    for c in range(cols):  # letters along the back edge
        x, y = (c + .5) * cw, -.45 * rh
        put_text(out, chr(65 + c), to_img(x, y), .45 * width_at(x, y))
    for r in range(rows):  # numbers along the left edge, row 1 at the back
        x, y = -.45 * cw, (r + .5) * rh
        put_text(out, str(r + 1), to_img(x, y), .45 * width_at(x, y))
    for c, r in safe:
        x, y = (c + .5) * cw, (r + .5) * rh
        put_text(out, cell_name(c, r), to_img(x, y), .6 * width_at(x, y))
    if layout is None:
        read = " ".join(cell_name(c, r) for c, r in safe)
        return out, None, cols, f"no known layout, read {cols} columns: {read}"
    for c, r in layout - set(safe):  # from the layout: hidden under a player, behind the skill bar or off-screen
        x, y = (c + .5) * cw, (r + .5) * rh
        px, py = to_img(x, y)
        if 0 <= px < out.shape[1] and 0 <= py < out.shape[0]:
            put_text(out, cell_name(c, r), (px, py), .6 * width_at(x, y), YELLOW)
    names = " ".join(cell_name(c, r) for r, c in sorted((r, c) for c, r in layout))
    return with_bar(out, "Known layout: " + names, YELLOW), None, cols, "known layout " + names


def screen_frames(app):
    sct = None
    while not app.stopping.is_set():
        if not app.enabled:  # helper switched off: don't capture at all
            time.sleep(0.25)
            continue
        try:
            sct = sct or mss.MSS()
            mon = sct.monitors[app.monitor]
            frame = cv2.cvtColor(np.asarray(sct.grab(mon)), cv2.COLOR_BGRA2BGR)
        except Exception:  # e.g. the display changes while the game starts: log it and keep trying
            logging.exception("screen capture failed, retrying")
            if sct:
                sct.close()
            sct = None
            time.sleep(1)
            continue
        # Black out our own windows so a red snapshot on screen can't trigger the detector.
        for left, top, right, bottom in app.own_rects:
            l, t = max(0, left - mon["left"]), max(0, top - mon["top"])
            r, b = right - mon["left"], bottom - mon["top"]
            if r > l and b > t:
                frame[t:b, l:r] = 0
        yield frame


def video_frames(app, path, start):
    cap = cv2.VideoCapture(path)
    cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    step = max(1, round(cap.get(cv2.CAP_PROP_FPS) / CAPTURE_FPS))
    i = 0
    while not app.stopping.is_set():
        if not cap.grab():
            return
        i += 1
        if i % step == 0:
            yield cap.retrieve()[1]


class App:
    def __init__(self, root, video=None, start=0.0):
        self.root = root
        saved = self._load()
        self.cfg = {**DEFAULTS, **saved}
        self.stopping = threading.Event()
        self.own_rects = []
        self.snapshot = None
        self.new_snapshot = None
        self.enabled = self.cfg["enabled"]
        self.source_done = False
        self.video = video
        self.last_frame = time.time()
        self.stalled = False
        with mss.MSS() as sct:
            self.monitors = sct.monitors[1:]
        self.monitor = min(self.cfg["monitor"], len(self.monitors))
        if "second_geom" not in saved and len(self.monitors) > 1:  # first run: open it on another monitor
            other = next(m for i, m in enumerate(self.monitors, 1) if i != self.monitor)
            self.cfg["second_geom"] = f"960x640+{other['left'] + 80}+{other['top'] + 80}"

        root.title("Not This Tile? helper")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        frm = ttk.Frame(root, padding=10)
        frm.pack()
        self.var_enabled = tk.BooleanVar(value=self.cfg["enabled"])
        self.var_overlay = tk.BooleanVar(value=self.cfg["overlay"])
        self.var_second = tk.BooleanVar(value=self.cfg["second"])
        ttk.Checkbutton(frm, text="Helper on", variable=self.var_enabled,
                        command=self.apply).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(frm, text="Overlay on game screen (always on top)", variable=self.var_overlay,
                        command=self.apply).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(frm, text="Window for second monitor", variable=self.var_second,
                        command=self.apply).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(frm, text="Game is on:").grid(row=3, column=0, sticky="w", pady=(8, 0))
        names = [f"{i}: {m['width']}x{m['height']}" + (" (primary)" if m.get("is_primary") else "")
                 for i, m in enumerate(self.monitors, 1)]
        self.combo = ttk.Combobox(frm, values=names, state="readonly", width=24)
        self.combo.current(self.monitor - 1)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self.apply())
        self.combo.grid(row=3, column=1, sticky="w", pady=(8, 0))
        if video:
            self.combo.configure(state="disabled")
        self.status = ttk.Label(frm, text="Waiting for a reveal...")
        self.status.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

        self.overlay = self._make_view("Tile snapshot", self.cfg["overlay_geom"], self.var_overlay)
        self.overlay.attributes("-topmost", True)
        self.second = self._make_view("Tile snapshot (2nd monitor)", self.cfg["second_geom"], self.var_second)

        self.lock = threading.Lock()
        self.to_label = None  # (reveal number, snapshot): the newest snapshot waiting for tile names
        self.labelled = 0  # the reveal number whose snapshot already has tile names
        self.labelled_cols = None  # and its column count
        self.results = {}  # reveal number -> last logged result
        self.layouts = load_layouts()
        logging.info("%d known layouts", len(self.layouts))
        for old in SNAP_DIR.glob("reveal*.jpg"):  # reveal numbers restart at 1: drop the last run's pictures
            old.unlink()
        self.label_wanted = threading.Event()
        source = video_frames(self, video, start) if video else screen_frames(self)
        threading.Thread(target=self._capture, args=(source,), daemon=True).start()
        threading.Thread(target=self._label, daemon=True).start()
        self.apply()
        self._tick()

    # --- windows -------------------------------------------------------------------------------
    def _make_view(self, title, geom, var):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry(geom)
        win.configure(bg="black")
        label = tk.Label(win, bg="black", fg="#aaa", text="Waiting for a reveal...")
        label.pack(fill="both", expand=True)
        win.label = label
        win.bind("<Configure>", lambda e: self._render(win))

        def closed():
            var.set(False)
            self.apply()
        win.protocol("WM_DELETE_WINDOW", closed)
        return win

    def _render(self, win):
        if self.snapshot is None or not win.winfo_viewable():
            return
        w, h = max(1, win.winfo_width()), max(1, win.winfo_height())
        sh, sw = self.snapshot.shape[:2]
        scale = min(w / sw, h / sh)
        img = cv2.resize(self.snapshot, (max(1, int(sw * scale)), max(1, int(sh * scale))),
                         interpolation=cv2.INTER_AREA)
        win.label.image = tk.PhotoImage(data=base64.b64encode(cv2.imencode(".png", img)[1]).decode())
        win.label.configure(image=win.label.image, text="")

    def apply(self):
        self.monitor = self.combo.current() + 1
        on = self.var_enabled.get()
        if on and not self.enabled:
            self.last_frame = time.time()  # capture was paused on purpose, not stalled
        self.enabled = on
        for win, var in ((self.overlay, self.var_overlay), (self.second, self.var_second)):
            if on and var.get():
                win.deiconify()
            else:
                win.withdraw()
        if not on:
            self.status.configure(text="Helper is off.")
        elif self.status.cget("text") == "Helper is off.":
            self.status.configure(text="Waiting for a reveal...")
        self._save()

    # --- capture -------------------------------------------------------------------------------
    def _capture(self, source):
        detector = RevealDetector()
        try:
            for frame in source:
                t0 = time.perf_counter()
                self.last_frame = time.time()
                if self.enabled:
                    snap = detector.feed(frame)
                    if snap is not None:
                        with self.lock:  # show it right away; the label thread adds tile names after
                            if self.labelled != detector.episode:
                                self.new_snapshot = snap
                            self.to_label = (detector.episode, snap)
                        self.label_wanted.set()
                time.sleep(max(0.0, 1 / CAPTURE_FPS - (time.perf_counter() - t0)))
        except Exception:
            logging.exception("capture thread crashed")  # _tick shows the stalled warning
            return
        self.source_done = True

    def _label(self):
        """Names the tiles on the newest snapshot. Runs apart from capture, so it never delays a snapshot."""
        while not self.stopping.is_set():
            if not self.label_wanted.wait(0.5):
                continue
            self.label_wanted.clear()
            with self.lock:
                job, self.to_label = self.to_label, None
            if job is None:
                continue
            episode, snap = job
            try:
                out, note, cols, read = label_grid(snap, self.layouts)
                ok = note is None
                # A later frame of a named reveal must agree on the column count. A panel over a side can make
                # the outline stop short, which gives the wrong count and wrong names.
                if ok and self.labelled == episode and cols != self.labelled_cols:
                    note, ok = "column count changed", False
            except Exception:  # never lose the snapshot (or this thread) over labels
                logging.exception("labelling failed")
                continue
            # Keep the newest raw snapshot of each reveal on disk, and log how reading it went, so a round can
            # be checked afterwards without a recording.
            result = note or "tile names added, " + read
            if result != self.results.get(episode):
                self.results[episode] = result
                logging.info("reveal %d: %s", episode, result)
            SNAP_DIR.mkdir(exist_ok=True)
            cv2.imwrite(str(SNAP_DIR / f"reveal{episode:02d}.jpg"), snap)
            # Red things outside the minigame count as reveals too: keep only the newest 40.
            (SNAP_DIR / f"reveal{episode - 40:02d}.jpg").unlink(missing_ok=True)
            with self.lock:
                if ok:  # a picture with tile names is kept for the rest of this reveal
                    self.labelled, self.labelled_cols = episode, cols
                    self.new_snapshot = out
                elif self.labelled != episode:
                    self.new_snapshot = out

    def _tick(self):
        with self.lock:
            snap, self.new_snapshot = self.new_snapshot, None
        if snap is not None:
            self.snapshot = snap
            self.status.configure(text="Reveal captured at " + time.strftime("%H:%M:%S"))
            self._render(self.overlay)
            self._render(self.second)
        if self.source_done:
            self.source_done = False
            self.status.configure(text="Video finished.")
        stalled = self.enabled and not self.video and time.time() - self.last_frame > 3
        if stalled != self.stalled:
            self.stalled = stalled
            self.status.configure(text=STALLED_TEXT if stalled else
                                  "Capture running again." if self.enabled else "Helper is off.")
        self.own_rects = [(w.winfo_rootx(), w.winfo_rooty(),
                           w.winfo_rootx() + w.winfo_width(), w.winfo_rooty() + w.winfo_height())
                          for w in (self.root, self.overlay, self.second) if w.winfo_viewable()]
        self.root.after(50, self._tick)

    # --- settings ------------------------------------------------------------------------------
    def _load(self):
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (OSError, ValueError):
            return {}

    def _save(self):
        self.cfg.update(enabled=self.var_enabled.get(), overlay=self.var_overlay.get(),
                        second=self.var_second.get(), monitor=self.monitor)
        for key, win in (("overlay_geom", self.overlay), ("second_geom", self.second)):
            if win.winfo_viewable():
                self.cfg[key] = win.geometry()
        SETTINGS_FILE.write_text(json.dumps(self.cfg, indent=2))

    def quit(self):
        self._save()
        self.stopping.set()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--video", help="replay a recording instead of watching the screen")
    parser.add_argument("--start", type=float, default=0.0, help="seconds into the video to start from")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=1)])
    try:  # real pixel coordinates, so window positions match what mss captures
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    root.report_callback_exception = lambda *exc: logging.error("UI error", exc_info=exc)
    app = App(root, args.video, args.start)
    logging.info("started, watching %s", args.video or f"monitor {app.monitor}")
    root.mainloop()


if __name__ == "__main__":
    main()
