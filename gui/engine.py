"""ctypes bridge to the C engine (build/libdispatch.so | .dylib | .dll)."""
import ctypes as C
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ints(names):
    return [(n, C.c_int) for n in names.split()]


class TreeNode(C.Structure):
    _fields_ = _ints("id severity arrival deadline zone rank left right overdue")


class CallInfo(C.Structure):
    _fields_ = _ints("id severity arrival deadline zone room x y rank overdue")


class Snap(C.Structure):          # must mirror Snapshot in src/game.h field for field
    _fields_ = (_ints("time over generated on_time late overdue_waiting score expired")
                + [(n, C.c_int * 4) for n in "room_state room_size room_outage room_merged_into room_heap_ok room_spine".split()]
                + [(n, C.c_int * 8) for n in "amb_home amb_ctrl amb_busy amb_sev amb_hx amb_hy amb_tx amb_ty amb_total amb_travel amb_pts".split()]
                + _ints("last_visits last_binary last_src last_dst merges trace_n")
                + [("trace", C.c_int * 32)])


def _load():
    ext = "dll" if os.name == "nt" else ("dylib" if sys.platform == "darwin" else "so")
    path = os.path.join(ROOT, "build", f"libdispatch.{ext}")
    if not os.path.exists(path):
        subprocess.check_call(["make", "-C", ROOT, "lib"])
    lib, P = C.CDLL(path), C.c_void_p
    lib.game_new.restype, lib.game_new.argtypes = P, [C.c_uint]
    lib.game_free.argtypes = [P]
    lib.game_tick.argtypes = [P]
    lib.game_autopilot.argtypes = [P]
    lib.game_merge.argtypes = [P, C.c_int, C.c_int]
    lib.game_restore.argtypes = [P, C.c_int]
    lib.game_snapshot.argtypes = [P, C.POINTER(Snap)]
    lib.game_heap_dump.argtypes = [P, C.c_int, C.POINTER(TreeNode), C.c_int]
    lib.game_waiting.argtypes = [P, C.POINTER(CallInfo), C.c_int]
    lib.game_pop_log.argtypes = [P, C.c_char_p, C.c_int]
    return lib


class Engine:
    def __init__(self):
        self.lib, self.g = _load(), None

    def new(self, seed):
        self.free()
        self.g = self.lib.game_new(seed)

    def free(self):
        if self.g:
            self.lib.game_free(self.g)
            self.g = None

    def tick(self): self.lib.game_tick(self.g)
    def autopilot(self): self.lib.game_autopilot(self.g)
    def merge(self, src, dst): return self.lib.game_merge(self.g, src, dst)
    def restore(self, z): return self.lib.game_restore(self.g, z)

    def snapshot(self):
        s = Snap()
        self.lib.game_snapshot(self.g, C.byref(s))
        return s

    def dump(self, room, limit=31):
        buf = (TreeNode * 64)()
        return list(buf[:self.lib.game_heap_dump(self.g, room, buf, limit)])

    def waiting(self):
        buf = (CallInfo * 300)()
        return list(buf[:self.lib.game_waiting(self.g, buf, 300)])

    def logs(self):
        out, buf = [], C.create_string_buffer(128)
        while self.lib.game_pop_log(self.g, buf, 128):
            out.append(buf.value.decode())
        return out
