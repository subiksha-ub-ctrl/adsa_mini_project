#!/usr/bin/env python3
"""108 Ambulance Dispatch Zones - map game (Tkinter) on top of the C leftist-heap engine.

Main window : city map with control rooms, ambulances driving along roads and call pins.
Heap window : the selected control room's leftist heap drawn as a live tree.
"""
import math
import os
import random
import sys
import time
import tkinter as tk
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R                      # noqa: E402
from engine import Engine               # noqa: E402

LOG_COL = {"OUTAGE": "#ff4d5e", "PILE-UP": "#ff9f43", "MERGE": R.CYAN, "RESTORE": "#3ddc84",
           "ONLINE": "#3ddc84", "SHIFT": "#ffffff", "WARN": "#ffd166"}
STATE_TXT = {0: "ONLINE", 1: "OFFLINE", 2: "MERGED"}
F = R.F
HELP = ("HOW TO PLAY\nClick a control room (HQ), then click another HQ to MERGE its queue and ambulances "
        "into it (O(log n) leftist merge). Click a MERGED room to RESTORE it.\nSpace = start/pause, Esc = cancel.")


class Inspector(tk.Toplevel):
    """Separate window that draws the leftist heap of one control room."""
    def __init__(self, app):
        super().__init__(app)
        self.app, self.room = app, 2
        self.title("Leftist Heap Inspector")
        self.configure(bg=R.BG)
        self.geometry("960x640+90+70")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        bar = tk.Frame(self, bg=R.BG)
        bar.pack(fill="x", padx=10, pady=8)
        tk.Label(bar, text="Control room:", bg=R.BG, fg=R.MUTED, font=(F, 10)).pack(side="left")
        self.btns = []
        for z in range(4):
            b = tk.Button(bar, text=R.ZONES[z], command=lambda z=z: self.show(z), font=(F, 10, "bold"))
            b.pack(side="left", padx=3)
            self.btns.append(b)
        self.cv = tk.Canvas(self, bg=R.TREEBG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True, padx=10)
        self.info = tk.Label(self, bg=R.BG, fg=R.INK, font=(F, 10, "bold"), anchor="w", justify="left")
        self.info.pack(fill="x", padx=12, pady=(6, 0))
        self.ana = tk.Label(self, bg=R.BG, fg=R.CYAN, font=(F, 10), anchor="w", justify="left")
        self.ana.pack(fill="x", padx=12)
        tk.Label(self, bg=R.BG, fg=R.MUTED, font=(F, 9), anchor="w", justify="left",
                 text="Node = call (#id), colour = severity, rN = leftist rank, tN = arrival minute.  Cyan edges = right spine "
                      "(merge only walks these).  White rings = nodes visited by the last merge.  Red ring = overdue."
                 ).pack(fill="x", padx=12, pady=(0, 8))

    def show(self, z):
        self.room = z
        self.deiconify()
        self.redraw()

    def redraw(self):
        app, s, z = self.app, self.app.snap, self.room
        nodes = app.eng.dump(z, 31)
        n = s.room_size[z]
        trace = set(s.trace[:s.trace_n]) if (s.merges and s.last_dst == z and time.monotonic() < app.trace_until) else set()
        note = {0: "", 1: "CONTROL ROOM OFFLINE - this queue is frozen until power returns or you fail it over.",
                2: f"Queue was merged into {R.ZONES[max(0, s.room_merged_into[z])]} - see that room's heap."}[s.room_state[z]]
        if n > len(nodes):
            note = (note + "   " if note else "") + f"Showing the top {len(nodes)} of {n} calls (BFS order)."
        R.draw_tree(self.cv, self.cv.winfo_width() or 900, self.cv.winfo_height() or 460, nodes, trace,
                    f"{R.ZONES[z].upper()}  -  leftist heap of {n} waiting calls", note)
        for i, b in enumerate(self.btns):
            b.config(bg=R.ZONE_COL[i] if i == z else "#2b3b58", fg="#0a1020" if i == z else R.INK)
        self.info.config(text=f"Right spine: {s.room_spine[z]} nodes (bound log2(n+1) = {math.log2(n + 1):.1f})     "
                              f"Heap order + leftist property: {'OK' if s.room_heap_ok[z] else 'VIOLATED'}")
        if s.merges:
            self.ana.config(text=f"Last merge {R.ZONES[s.last_src]} -> {R.ZONES[s.last_dst]}: leftist visited {s.last_visits} nodes, "
                                 f"a binary-heap merge would touch {s.last_binary}.   All {s.merges} merges: "
                                 f"{app.tot_v} visits vs {app.tot_b}.")
        else:
            self.ana.config(text="No merge yet - merge two control rooms on the map and watch the visited nodes light up here.")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("108 Ambulance Dispatch Zones")
        self.configure(bg=R.BG)
        self.geometry("1300x740+20+20")
        self.minsize(1000, 620)
        self.eng = Engine()
        self.auto = tk.BooleanVar(value=False)
        self.speed, self.running, self.sel = 1, False, None
        self.popups, self.banner, self.arrived = [], None, [False] * 8
        self.tot_v = self.tot_b = self.seen = self.frame = 0
        self.trace_until, self.t_tick, self.frac = 0.0, time.monotonic(), 0.0
        self.snap, self.calls = None, []
        self.build_ui()
        self.inspector = Inspector(self)
        self.bind("<space>", lambda e: self.toggle())
        self.bind("<Escape>", lambda e: setattr(self, "sel", None))
        self.new_game()
        self.after(33, self.frame_loop)

    # ---------------------------------------------------------------- UI
    def build_ui(self):
        side = tk.Frame(self, bg=R.PANEL, width=310)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        self.map = tk.Canvas(self, bg=R.BG, highlightthickness=0)
        self.map.pack(side="left", fill="both", expand=True)
        self.map.bind("<Button-1>", self.on_click)
        tk.Label(side, text="108 AMBULANCE\nDISPATCH ZONES", bg=R.PANEL, fg=R.INK, font=(F, 16, "bold"), justify="left").pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(side, text="leftist-heap control rooms", bg=R.PANEL, fg=R.CYAN, font=(F, 10)).pack(anchor="w", padx=12)
        self.hud = tk.Label(side, bg=R.PANEL, fg=R.INK, font=("Courier", 11, "bold"), justify="left", anchor="w")
        self.hud.pack(fill="x", padx=12, pady=(8, 2))
        self.prog = tk.Canvas(side, height=8, bg="#16233a", highlightthickness=0)
        self.prog.pack(fill="x", padx=12, pady=(0, 6))
        self.cards = []
        for z in range(4):
            f = tk.Frame(side, bg="#16233a")
            f.pack(fill="x", padx=10, pady=2)
            tk.Label(f, text=R.ZONES[z], bg="#16233a", fg=R.ZONE_COL[z], font=(F, 10, "bold"), width=10, anchor="w").grid(row=0, column=0, padx=4)
            lab = tk.Label(f, bg="#16233a", fg=R.INK, font=(F, 9), width=18, anchor="w")
            lab.grid(row=0, column=1)
            b = tk.Button(f, text="Restore", font=(F, 8), command=lambda z=z: self.do_restore(z))
            b.grid(row=0, column=2, padx=4, pady=2)
            self.cards.append(lab)
        row = tk.Frame(side, bg=R.PANEL)
        row.pack(fill="x", padx=10, pady=6)
        self.btn_run = tk.Button(row, text="Start", width=7, command=self.toggle)
        self.btn_run.pack(side="left")
        self.btn_speed = tk.Button(row, text="Speed 1x", width=8, command=self.cycle_speed)
        self.btn_speed.pack(side="left", padx=3)
        tk.Button(row, text="New shift", command=self.new_game).pack(side="left")
        row2 = tk.Frame(side, bg=R.PANEL)
        row2.pack(fill="x", padx=10)
        tk.Checkbutton(row2, text="Autopilot", variable=self.auto, bg=R.PANEL, fg=R.INK, selectcolor=R.BG,
                       activebackground=R.PANEL, activeforeground=R.INK).pack(side="left")
        tk.Button(row2, text="Heap window", command=lambda: self.inspector.show(self.inspector.room)).pack(side="right")
        lg = tk.Frame(side, bg=R.PANEL)
        lg.pack(fill="x", padx=10, pady=6)
        for i in range(4):
            tk.Label(lg, text=R.SEV_NAMES[i], bg=R.SEV_COL[i], fg="#10131a", font=(F, 8, "bold"), padx=4).pack(side="left", padx=2)
        tk.Label(side, text=HELP, bg=R.PANEL, fg=R.MUTED, font=(F, 9), wraplength=285, justify="left").pack(padx=12, anchor="w")
        self.logbox = tk.Text(side, height=10, bg=R.TREEBG, fg=R.INK, relief="flat", font=("Courier", 8), wrap="word")
        self.logbox.pack(fill="both", expand=True, padx=10, pady=8)
        for tag, col in LOG_COL.items():
            self.logbox.tag_config(tag, foreground=col)
        self.overlay = tk.Frame(self.map, bg=R.BG, highlightthickness=2, highlightbackground=R.CYAN)
        self.ov_title = tk.Label(self.overlay, bg=R.BG, fg=R.INK, font=(F, 22, "bold"), padx=40, pady=8)
        self.ov_title.pack()
        self.ov_text = tk.Label(self.overlay, bg=R.BG, fg=R.MUTED, font=(F, 12), padx=40)
        self.ov_text.pack()
        tk.Button(self.overlay, text="Play again", command=self.new_game).pack(pady=12)

    # ----------------------------------------------------------- control
    def new_game(self):
        self.eng.new(random.randrange(1, 10 ** 6))
        self.running, self.sel, self.frac = False, None, 0.0
        self.popups, self.banner, self.arrived = [], None, [False] * 8
        self.tot_v = self.tot_b = self.seen = 0
        self.btn_run.config(text="Start")
        self.overlay.place_forget()
        self.logbox.delete("1.0", "end")
        self.log("[WARN] Press START or SPACE. Keep every call's countdown ring from running out!")
        self.sync()

    def toggle(self):
        if self.snap.over:
            return
        self.running = not self.running
        self.t_tick = time.monotonic() - self.frac / self.speed
        self.btn_run.config(text="Pause" if self.running else "Start")

    def cycle_speed(self):
        self.speed = {1: 2, 2: 4, 4: 1}[self.speed]
        self.t_tick = time.monotonic() - self.frac / self.speed
        self.btn_speed.config(text=f"Speed {self.speed}x")

    def hit_hq(self, px, py):
        x, y = R.View(self.map.winfo_width() or 990, self.map.winfo_height() or 700).inv(px, py)
        for z, (hx, hy) in enumerate(R.HQ):
            if abs(x - hx) <= 36 and abs(y - hy) <= 36:
                return z
        return None

    def on_click(self, e):
        if self.snap.over:
            return
        z = self.hit_hq(e.x, e.y)
        if z is None:
            self.sel = None
        elif self.sel is None:
            if self.snap.room_state[z] == 2:
                self.do_restore(z)
            else:
                self.sel = z
                self.inspector.show(z)
        elif self.sel == z:
            self.sel = None
        else:
            self.do_merge(self.sel, z)
            self.sel = None

    def do_merge(self, src, dst):
        if self.eng.merge(src, dst) < 0:
            self.log(f"[WARN] Cannot merge {R.ZONES[src]} into {R.ZONES[dst]} (target must be online).")
        else:
            self.trace_until = time.monotonic() + 6
            self.inspector.show(dst)
        self.sync()

    def do_restore(self, z):
        if not self.snap.over and self.eng.restore(z) < 0:
            self.log(f"[WARN] {R.ZONES[z]} cannot be restored (not merged, or power still down).")
        self.sync()

    # -------------------------------------------------------------- loop
    def frame_loop(self):
        now, tick_s = time.monotonic(), 1.0 / self.speed
        if self.running and not self.snap.over:
            if now - self.t_tick >= tick_s:
                self.t_tick = now
                if self.auto.get():
                    self.eng.autopilot()
                self.eng.tick()
                self.frac = 0.0
                self.sync()
            else:
                self.frac = (now - self.t_tick) / tick_s
        self.draw(now)
        self.frame += 1
        if self.frame % 3 == 0:
            self.inspector.redraw()
        self.after(33, self.frame_loop)

    def draw(self, now):
        w, h = self.map.winfo_width() or 990, self.map.winfo_height() or 700
        self.popups = [p for p in self.popups if now - p["t0"] < 2.0]
        st = SimpleNamespace(snap=self.snap, calls=self.calls, frac=self.frac, now=now, sel=self.sel,
                             popups=self.popups, banner=self.banner)
        R.draw_map(self.map, R.View(w, h), st)

    # -------------------------------------------------- engine -> screen
    def log(self, msg):
        tag = next((p.strip("[]") for p in msg.split()[:2] if p.strip("[]") in LOG_COL), "")
        self.logbox.insert("end", msg + "\n", tag)
        self.logbox.see("end")
        if tag in ("OUTAGE", "PILE-UP"):
            self.banner = {"text": msg.split("] ", 2)[-1][:56], "col": LOG_COL[tag], "t0": time.monotonic()}

    def sync(self):
        s = self.snap = self.eng.snapshot()
        self.calls = self.eng.waiting()
        for m in self.eng.logs():
            self.log(m)
        if s.merges > self.seen:
            self.seen = s.merges
            self.tot_v += s.last_visits
            self.tot_b += s.last_binary
            self.trace_until = time.monotonic() + 6
        for a in range(8):                                   # score popup when an ambulance reaches its call
            busy = s.amb_busy[a]
            arrived = busy > 0 and s.amb_total[a] - busy >= s.amb_travel[a]
            if arrived and not self.arrived[a]:
                pts = s.amb_pts[a]
                self.popups.append({"x": s.amb_tx[a], "y": s.amb_ty[a], "t0": time.monotonic(),
                                    "text": f"+{pts}" if pts > 0 else ("LATE" if pts == 0 else f"LATE {pts}"),
                                    "col": "#3ddc84" if pts > 0 else "#ff4d5e"})
            self.arrived[a] = arrived
        done = s.on_time + s.late
        pct = 100.0 * s.on_time / done if done else 100.0
        self.hud.config(text=f"TIME   {s.time:3d} / 120 min\nSCORE  {s.score}\nIN TIME {pct:5.1f}%\n"
                             f"served {s.on_time}  late {s.late}\noverdue now {s.overdue_waiting}")
        self.prog.delete("all")
        self.prog.create_rectangle(0, 0, max(1, (self.prog.winfo_width() or 286) * s.time / 120), 8, fill=R.CYAN, outline="")
        for z, lab in enumerate(self.cards):
            extra = f" -> {R.ZONES[s.room_merged_into[z]]}" if s.room_state[z] == 2 else (f" {s.room_outage[z]}m" if s.room_state[z] == 1 else "")
            lab.config(text=f"{STATE_TXT[s.room_state[z]]}{extra}  q={s.room_size[z]}")
        if s.over:
            pct = 100.0 * s.on_time / max(1, s.generated)
            grade = "S  Chief Dispatcher" if pct >= 95 else "A  Senior Dispatcher" if pct >= 90 else "B  Dispatcher" if pct >= 80 else "C  Trainee"
            self.running = False
            self.btn_run.config(text="Start")
            self.ov_title.config(text="SHIFT COMPLETE")
            self.ov_text.config(text=f"Score {s.score}\n{s.on_time} of {s.generated} calls reached in time ({pct:.1f}%)\n"
                                     f"Merges used: {s.merges}\nGrade: {grade}")
            self.overlay.place(relx=0.5, rely=0.5, anchor="center")

    def destroy(self):
        self.eng.free()
        super().destroy()


if __name__ == "__main__":
    App().mainloop()
