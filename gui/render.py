"""Pure drawing code (works on anything with Tk-canvas methods; no tkinter import here)."""
import math

ZONES = ["Guindy", "Anna Nagar", "T. Nagar", "Tambaram"]
SEV_NAMES = ["Critical", "Serious", "Moderate", "Minor"]
SEV_COL = ["#ff4d5e", "#ff9f43", "#ffd166", "#4cc9a7"]
ZONE_COL = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24"]
ZONE_TINT = ["#102a40", "#1d1a3a", "#0f3029", "#33280f"]
BG, PANEL, TREEBG = "#0a1020", "#121c30", "#0e1727"
INK, MUTED, CYAN = "#e6edf7", "#8b9ab5", "#38bdf8"
MAP_W, MAP_H = 1000, 700
ZX, ZY = [0, 0, 500, 500], [350, 0, 0, 350]            # zone rectangles are 500 x 350 (mirrors src/game.c)
HQ = [(250, 500), (250, 150), (750, 150), (750, 500)]
F = "Helvetica"


class View:
    """Maps city coordinates (1000 x 700) to canvas pixels, keeping the aspect ratio."""
    def __init__(self, w, h):
        self.sc = max(0.3, min(w / MAP_W, h / MAP_H))
        self.ox, self.oy = (w - MAP_W * self.sc) / 2, (h - MAP_H * self.sc) / 2

    def p(self, x, y): return self.ox + x * self.sc, self.oy + y * self.sc
    def inv(self, px, py): return (px - self.ox) / self.sc, (py - self.oy) / self.sc


def fnt(v, size, bold=False):
    s = max(7, int(size * v.sc))
    return (F, s, "bold") if bold else (F, s)


def path_pos(a, b, f):
    """Point a fraction f along the L-shaped road route a -> b (horizontal first, then vertical)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = abs(dx) + abs(dy)
    if length == 0:
        return a
    d = max(0.0, min(1.0, f)) * length
    if d <= abs(dx):
        return a[0] + (d if dx > 0 else -d), a[1]
    d -= abs(dx)
    return b[0], a[1] + (d if dy > 0 else -d)


def amb_state(s, a, frac):
    """-> ((x, y), phase, target); phase is idle | out | scene | back."""
    home, total, busy = (s.amb_hx[a], s.amb_hy[a]), s.amb_total[a], s.amb_busy[a]
    if busy <= 0 or total <= 0:
        return home, "idle", None
    tgt, tr = (s.amb_tx[a], s.amb_ty[a]), s.amb_travel[a]
    e = min(float(total), (total - busy) + frac)
    if e < tr:
        return path_pos(home, tgt, e / tr), "out", tgt
    if e < total - tr:
        return tgt, "scene", tgt
    return path_pos(tgt, home, (e - (total - tr)) / tr), "back", tgt


def _pin(cv, v, x, y, sev, left, overdue, pulse, tag=""):
    px, py = v.p(x, y)
    r = (8 + (3 * pulse if overdue else 0)) * v.sc + 1
    if overdue:
        cv.create_oval(px - r - 4, py - r - 4, px + r + 4, py + r + 4, outline="#ff2d55", width=2)
    elif left is not None:
        cv.create_arc(px - r - 4, py - r - 4, px + r + 4, py + r + 4, start=90,
                      extent=max(2.0, 359.0 * left), style="arc", outline=INK, width=2)
    cv.create_oval(px - r, py - r, px + r, py + r, fill=SEV_COL[sev], outline=BG, width=1)
    cv.create_text(px, py, text="!", fill="#10131a", font=fnt(v, 10, True))
    if tag:
        cv.create_text(px + r + 3, py - r - 2, text=tag, anchor="nw", fill=INK, font=fnt(v, 7))


def _ambulance(cv, v, st, a):
    s = st.snap
    (x, y), ph, _ = amb_state(s, a, st.frac)
    px, py = v.p(x, y)
    u, hw, hh = v.sc, 14 * v.sc, 7.5 * v.sc
    foreign = s.amb_ctrl[a] != s.amb_home[a]
    cv.create_rectangle(px - hw, py - hh, px + hw, py + hh, fill="#f4f7fb",
                        outline=CYAN if foreign else ZONE_COL[s.amb_home[a]], width=2)
    cv.create_rectangle(px - 1.5 * u, py - 5 * u, px + 1.5 * u, py + 5 * u, fill="#e11d48", outline="")
    cv.create_rectangle(px - 5 * u, py - 1.5 * u, px + 5 * u, py + 1.5 * u, fill="#e11d48", outline="")
    siren = ("#ff2d55" if int(st.now * 6) % 2 == 0 else "#3b82f6") if ph in ("out", "back") else "#64748b"
    cv.create_oval(px - 3 * u, py - hh - 5 * u, px + 3 * u, py - hh + 1 * u, fill=siren, outline="")
    cv.create_text(px + hw + 3 * u, py, anchor="w", text=f"A{a + 1}", fill=MUTED, font=fnt(v, 8))


def draw_map(cv, v, st):
    """st needs: snap, calls, frac (0..1 inside the current minute), now (seconds), sel, popups, banner."""
    s, now = st.snap, st.now
    cv.delete("all")
    pulse = abs(math.sin(now * 4))
    for z in range(4):                                                   # districts
        x0, y0 = v.p(ZX[z], ZY[z]); x1, y1 = v.p(ZX[z] + 500, ZY[z] + 350)
        off = s.room_state[z] == 1
        cv.create_rectangle(x0, y0, x1, y1, fill="#3a1219" if off else ZONE_TINT[z], outline=ZONE_COL[z], width=2)
        if off:                                                          # red hatching = no power
            for k in range(-350, 500, 70):
                sx, sy, ex, ey = ZX[z] + k, ZY[z] + 350, ZX[z] + k + 350, ZY[z]
                if sx < ZX[z]: sy -= ZX[z] - sx; sx = ZX[z]
                if ex > ZX[z] + 500: ey += ex - (ZX[z] + 500); ex = ZX[z] + 500
                if sx < ex:
                    (ax, ay), (bx, by) = v.p(sx, sy), v.p(ex, ey)
                    cv.create_line(ax, ay, bx, by, fill="#5a1f2b", width=1)
    for gx in range(0, MAP_W + 1, 50):                                   # road grid
        a, b = v.p(gx, 0), v.p(gx, MAP_H)
        cv.create_line(a[0], a[1], b[0], b[1], fill="#33466b" if gx % 250 == 0 else "#22324f", width=2 if gx % 250 == 0 else 1)
    for gy in range(0, MAP_H + 1, 50):
        a, b = v.p(0, gy), v.p(MAP_W, gy)
        cv.create_line(a[0], a[1], b[0], b[1], fill="#33466b" if gy % 250 == 0 else "#22324f", width=2 if gy % 250 == 0 else 1)
    for z in range(4):
        x0, y0 = v.p(ZX[z] + 10, ZY[z] + 8)
        cv.create_text(x0, y0, anchor="nw", text=ZONES[z].upper(), fill=ZONE_COL[z], font=fnt(v, 14, True))
    for z in range(4):                                                   # merge links
        if s.room_state[z] == 2:
            a, b = v.p(*HQ[z]), v.p(*HQ[s.room_merged_into[z]])
            cv.create_line(a[0], a[1], b[0], b[1], fill=CYAN, width=3)
            cv.create_text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 10, text="LINKED", fill=CYAN, font=fnt(v, 9, True))
    for a in range(8):                                                   # stations
        px, py = v.p(s.amb_hx[a], s.amb_hy[a]); r = 6 * v.sc
        cv.create_rectangle(px - r, py - r, px + r, py + r, fill=PANEL, outline=ZONE_COL[s.amb_home[a]])
    for z in range(4):                                                   # control rooms
        cx, cy = v.p(*HQ[z]); h = 22 * v.sc; stt = s.room_state[z]
        if st.sel == z:
            m = h + (5 + 4 * pulse) * v.sc
            cv.create_rectangle(cx - m, cy - m, cx + m, cy + m, outline="#ffffff", width=3)
        cv.create_rectangle(cx - h, cy - h, cx + h, cy + h, fill="#7a2432" if stt == 1 else ZONE_COL[z], outline=BG, width=2)
        cv.create_text(cx, cy, text="HQ", fill="#0a1020" if stt != 1 else "#ffffff", font=fnt(v, 12, True))
        if stt == 1:
            cv.create_line(cx - h, cy - h, cx + h, cy + h, fill="#ff4d5e", width=3)
            cv.create_line(cx - h, cy + h, cx + h, cy - h, fill="#ff4d5e", width=3)
        label, col = {0: (f"{s.room_size[z]} waiting", INK), 1: (f"OFFLINE {s.room_outage[z]}m  ({s.room_size[z]} stuck)", "#ff4d5e"),
                      2: ("MERGED", "#ffb020")}[stt]
        cv.create_text(cx, cy + h + 11 * v.sc, text=label, fill=col, font=fnt(v, 10, True))
    for c in st.calls:                                                   # waiting calls
        span = max(1, c.deadline - c.arrival)
        _pin(cv, v, c.x, c.y, c.severity, max(0.0, min(1.0, (c.deadline - (s.time + st.frac)) / span)), c.overdue, pulse, f"#{c.id}")
    for a in range(8):                                                   # calls being attended
        _, ph, tgt = amb_state(s, a, st.frac)
        if ph == "out":
            _pin(cv, v, tgt[0], tgt[1], max(0, s.amb_sev[a]), None, False, 0)
        elif ph == "scene":
            px, py = v.p(*tgt); r = 12 * v.sc
            cv.create_oval(px - r, py - r, px + r, py + r, outline="#3ddc84", width=3)
            cv.create_text(px, py, text="+", fill="#3ddc84", font=fnt(v, 12, True))
    for a in range(8):
        _ambulance(cv, v, st, a)
    for p in st.popups:                                                  # floating score text
        age = now - p["t0"]
        if age < 2.0:
            px, py = v.p(p["x"], p["y"])
            cv.create_text(px, py - 16 * v.sc - age * 26, text=p["text"], fill=p["col"], font=fnt(v, 14, True))
    if st.banner and now - st.banner["t0"] < 3.5:                        # event banner
        bx, by = v.p(500, 350); w, h = 270 * v.sc, 20 * v.sc
        cv.create_rectangle(bx - w, by - h, bx + w, by + h, fill=BG, outline=st.banner["col"], width=3)
        cv.create_text(bx, by, text=st.banner["text"], fill=st.banner["col"], font=fnt(v, 13, True))


def draw_tree(cv, W, H, nodes, trace=(), title="", note=""):
    """One leftist heap as a tree. Cyan thick edges = right spine; white rings = nodes the last merge visited."""
    cv.delete("all")
    cv.create_text(14, 10, anchor="nw", text=title, fill=INK, font=(F, 13, "bold"))
    if note:
        cv.create_text(14, 34, anchor="nw", text=note, fill=MUTED, font=(F, 10))
    if not nodes:
        cv.create_text(W / 2, H / 2, text="empty queue", fill=MUTED, font=(F, 14))
        return
    pos, counter = {}, [0]

    def walk(i, d):                                   # in-order layout: x = visit order, y = depth
        if nodes[i].left >= 0: walk(nodes[i].left, d + 1)
        pos[i] = (counter[0], d); counter[0] += 1
        if nodes[i].right >= 0: walk(nodes[i].right, d + 1)

    walk(0, 0)
    spine, i = set(), 0
    while i >= 0:
        spine.add(i); i = nodes[i].right
    n, maxd = counter[0], max(d for _, d in pos.values())
    step = min(64.0, (W - 70) / max(1, n - 1)) if n > 1 else 0
    x0, top = (W - step * (n - 1)) / 2, 90
    dy = min(80.0, (H - top - 50) / max(1, maxd))
    r = max(9.0, min(18.0, step * 0.42)) if n > 1 else 18.0
    xy = lambda i: (x0 + pos[i][0] * step, top + pos[i][1] * dy)
    for i, nd in enumerate(nodes):
        for ch in (nd.left, nd.right):
            if ch >= 0:
                (ax, ay), (bx, by) = xy(i), xy(ch)
                on = i in spine and ch in spine and ch == nd.right
                cv.create_line(ax, ay, bx, by, fill=CYAN if on else "#3a4a68", width=4 if on else 1)
    for i, nd in enumerate(nodes):
        x, y = xy(i)
        if nd.id in trace:
            cv.create_oval(x - r - 6, y - r - 6, x + r + 6, y + r + 6, outline="#ffffff", width=3)
        cv.create_oval(x - r, y - r, x + r, y + r, fill=SEV_COL[nd.severity],
                       outline="#ff2d55" if nd.overdue else BG, width=3 if nd.overdue else 1)
        cv.create_text(x, y, text=f"#{nd.id}", fill="#10131a", font=(F, max(7, int(r * 0.62)), "bold"))
        cv.create_text(x + r * 0.7, y - r * 1.45, text=f"r{nd.rank}", anchor="nw", fill=MUTED, font=(F, 8))
        cv.create_text(x, y + r + 8, text=f"t{nd.arrival}", fill="#5f6f8d", font=(F, 7))
