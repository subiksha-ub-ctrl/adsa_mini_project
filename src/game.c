#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include "game.h"

#define LOGQ 48
#ifndef SPEED
#define SPEED 120                                               /* map units per minute */
#endif
#ifndef POOLQ
#define POOLQ 3                                                 /* autopilot pools when a queue exceeds this */
#endif
static const char *ZNAME[NZONES] = {"Guindy", "Anna Nagar", "T. Nagar", "Tambaram"};
static const double RATE[NZONES] = {0.12, 0.08, 0.30, 0.07};   /* calls per minute */
static const int DEADLINE[4] = {10, 18, 30, 45};                /* minutes allowed to reach the scene */
static const int SEV_WEIGHT[4] = {15, 25, 35, 25};              /* percent */
static const int PTS[4] = {100, 60, 40, 20};
static const int ZX[NZONES] = {0, 0, 500, 500}, ZY[NZONES] = {350, 0, 0, 350};   /* zone rectangles 500x350 */
static const int HQX[NZONES] = {250, 250, 750, 750}, HQY[NZONES] = {500, 150, 150, 500};

struct Game {
    unsigned long long rng, rng2;
    int time, next_id;
    Call *heap[NZONES];
    int state[NZONES], outage[NZONES], merged_into[NZONES], route[NZONES];
    int pooled[NZONES], merged_at[NZONES];
    int amb_home[NAMB], amb_ctrl[NAMB], amb_busy[NAMB], amb_sev[NAMB];
    int amb_hx[NAMB], amb_hy[NAMB], amb_tx[NAMB], amb_ty[NAMB], amb_total[NAMB], amb_travel[NAMB], amb_pts[NAMB];
    int generated, on_time, late, score, expired;
    int last_visits, last_binary, last_src, last_dst, merges, trace_n, trace[32];
    char logq[LOGQ][96];
    int lq_start, lq_count;
};

static unsigned long long next64(unsigned long long *s) {
    *s ^= *s >> 12; *s ^= *s << 25; *s ^= *s >> 27;
    return *s * 2685821657736338717ULL;
}
static int rnd(Game *g, int n) { return (int)((next64(&g->rng) >> 33) % (unsigned)n); }
static int rnd2(Game *g, int n) { return (int)((next64(&g->rng2) >> 33) % (unsigned)n); }
static double rndf(Game *g) { return (double)(next64(&g->rng) >> 11) / 9007199254740992.0; }

static void say(Game *g, const char *fmt, ...) {
    if (g->lq_count == LOGQ) { g->lq_start = (g->lq_start + 1) % LOGQ; g->lq_count--; }
    char *dst = g->logq[(g->lq_start + g->lq_count++) % LOGQ];
    char body[88];
    va_list ap; va_start(ap, fmt); vsnprintf(body, sizeof body, fmt, ap); va_end(ap);
    snprintf(dst, 96, "[%03d] %s", g->time, body);
}

int game_pop_log(Game *g, char *buf, int n) {
    if (!g->lq_count) return 0;
    snprintf(buf, n, "%s", g->logq[g->lq_start]);
    g->lq_start = (g->lq_start + 1) % LOGQ; g->lq_count--;
    return 1;
}

Game *game_new(unsigned seed) {
    Game *g = calloc(1, sizeof *g);
    g->rng = 88172645463325252ULL ^ ((unsigned long long)seed * 0x9E3779B97F4A7C15ULL);
    g->rng2 = 1181783497276652981ULL ^ ((unsigned long long)seed * 0xC2B2AE3D27D4EB4FULL);
    if (!g->rng) g->rng = 1;
    for (int z = 0; z < NZONES; z++) { g->route[z] = z; g->merged_into[z] = -1; }
    for (int a = 0; a < NAMB; a++) {
        int z = a % NZONES, k = a / NZONES;
        g->amb_home[a] = g->amb_ctrl[a] = z;
        g->amb_hx[a] = HQX[z] + (k ? 100 : -100); g->amb_hy[a] = HQY[z] + (k ? 50 : -50);
        g->amb_sev[a] = -1;
    }
    say(g, "[SHIFT] 120-minute shift begins. 8 ambulances, 4 control rooms.");
    return g;
}

void game_free(Game *g) { for (int z = 0; z < NZONES; z++) lh_free(g->heap[z]); free(g); }

static void add_call_at(Game *g, int zone, int sev, int x, int y) {
    Call *c = lh_new(++g->next_id, sev, g->time, g->time + DEADLINE[sev], zone);
    c->x = x; c->y = y;
    int room = g->route[zone];
    g->heap[room] = lh_insert(g->heap[room], c);
    g->generated++;
}

static int roll_severity(Game *g) {
    int r = rnd(g, 100), acc = 0;
    for (int s = 0; s < 4; s++) { acc += SEV_WEIGHT[s]; if (r < acc) return s; }
    return 3;
}

static int any_outage(const Game *g) { for (int z = 0; z < NZONES; z++) if (g->outage[z] > 0) return 1; return 0; }
static int count_waiting(const Call *h) { return h ? 1 + count_waiting(h->left) + count_waiting(h->right) : 0; }
static int count_overdue(const Call *h, int t) {
    return h ? (h->deadline < t) + count_overdue(h->left, t) + count_overdue(h->right, t) : 0;
}
static void expire(Game *g, Call *h) {                          /* waiting past the deadline: one-time penalty */
    if (!h) return;
    if (h->deadline < g->time && !h->penalized) { h->penalized = 1; g->score -= PTS[h->severity] / 2; g->expired++; }
    expire(g, h->left); expire(g, h->right);
}

void game_tick(Game *g) {
    if (g->time >= SHIFT_MINUTES) return;
    g->time++;
    for (int a = 0; a < NAMB; a++)
        if (g->amb_busy[a] > 0 && --g->amb_busy[a] == 0) g->amb_sev[a] = -1;

    for (int z = 0; z < NZONES; z++)
        if (g->outage[z] > 0 && --g->outage[z] == 0) {
            if (g->state[z] == ROOM_OFFLINE) { g->state[z] = ROOM_ONLINE; say(g, "[ONLINE] %s control room is back online.", ZNAME[z]); }
            else say(g, "[ONLINE] %s power restored - you can RESTORE its room.", ZNAME[z]);
        }

    if (g->time <= LAST_ARRIVAL) {
        for (int z = 0; z < NZONES; z++)
            if (rndf(g) < RATE[z]) add_call_at(g, z, roll_severity(g), ZX[z] + 50 * (1 + rnd(g, 9)), ZY[z] + 50 * (1 + rnd(g, 6)));
        if (rndf(g) < 0.02) {                                   /* multi-vehicle pile-up: a cluster of urgent calls */
            int z = rnd(g, NZONES), n = 4 + rnd(g, 3);
            int cx = ZX[z] + 100 + 50 * rnd(g, 6), cy = ZY[z] + 100 + 50 * rnd(g, 3);
            for (int i = 0; i < n; i++) add_call_at(g, z, rnd(g, 2), cx + 50 * (rnd(g, 3) - 1), cy + 50 * (rnd(g, 3) - 1));
            say(g, "[PILE-UP] Multi-vehicle pile-up in %s: %d urgent calls!", ZNAME[z], n);
        }
        if (!any_outage(g) && rndf(g) < 0.012) {                /* control room outage */
            int z = rnd(g, NZONES);
            if (g->state[z] == ROOM_ONLINE) {
                g->state[z] = ROOM_OFFLINE; g->outage[z] = 12 + rnd(g, 9);
                say(g, "[OUTAGE] %s control room OFFLINE for ~%d min! Fail it over.", ZNAME[z], g->outage[z]);
            }
        }
    }

    for (int r = 0; r < NZONES; r++) {                          /* dispatch: most urgent call -> nearest idle ambulance */
        if (g->state[r] != ROOM_ONLINE) continue;
        while (g->heap[r]) {
            int any = 0;
            for (int i = 0; i < NAMB; i++) if (g->amb_ctrl[i] == r && g->amb_busy[i] == 0) any = 1;
            if (!any) break;
            Call *c;
            g->heap[r] = lh_pop(g->heap[r], &c);
            int best = -1, bd = 1 << 30;
            for (int i = 0; i < NAMB; i++) {
                if (g->amb_ctrl[i] != r || g->amb_busy[i] != 0) continue;
                int d = abs(g->amb_hx[i] - c->x) + abs(g->amb_hy[i] - c->y);
                if (d < bd) { bd = d; best = i; }
            }
            int tr = (bd + SPEED - 1) / SPEED; if (tr < 1) tr = 1;
            int ok = g->time + tr <= c->deadline;
            int pts = ok ? PTS[c->severity] : (c->penalized ? 0 : -PTS[c->severity] / 2);
            g->score += pts;
            if (ok) g->on_time++; else g->late++;
            g->amb_travel[best] = tr; g->amb_total[best] = g->amb_busy[best] = 2 * tr + 2 + rnd2(g, 3);
            g->amb_tx[best] = c->x; g->amb_ty[best] = c->y; g->amb_sev[best] = c->severity; g->amb_pts[best] = pts;
            free(c);
        }
    }
    for (int z = 0; z < NZONES; z++) expire(g, g->heap[z]);

    if (g->time == SHIFT_MINUTES) {                             /* calls still waiting count as late */
        for (int z = 0; z < NZONES; z++) g->late += count_waiting(g->heap[z]);
        say(g, "[SHIFT] Shift over. Reached in time: %d of %d calls. Score %d.", g->on_time, g->generated, g->score);
    }
}

int game_merge(Game *g, int src, int dst) {
    if (src < 0 || src >= NZONES || dst < 0 || dst >= NZONES || src == dst) return -1;
    if (g->time >= SHIFT_MINUTES || g->state[src] == ROOM_MERGED || g->state[dst] != ROOM_ONLINE) return -1;
    int n1 = lh_size(g->heap[src]), n2 = lh_size(g->heap[dst]);
    long v0 = lh_visits();
    lh_trace(1);
    g->heap[dst] = lh_merge(g->heap[dst], g->heap[src]);
    lh_trace(0);
    int used = (int)(lh_visits() - v0);
    g->trace_n = lh_trace_count() < 32 ? lh_trace_count() : 32;
    for (int i = 0; i < g->trace_n; i++) g->trace[i] = lh_trace_id(i);
    g->heap[src] = NULL;
    g->pooled[src] = (g->state[src] == ROOM_ONLINE);
    g->state[src] = ROOM_MERGED; g->merged_into[src] = dst; g->merged_at[src] = g->time;
    for (int x = 0; x < NZONES; x++) {
        if (g->route[x] == src) g->route[x] = dst;
        if (x != src && g->state[x] == ROOM_MERGED && g->merged_into[x] == src) g->merged_into[x] = dst;
    }
    for (int a = 0; a < NAMB; a++) if (g->amb_ctrl[a] == src) g->amb_ctrl[a] = dst;
    g->last_visits = used; g->last_binary = n1 + n2; g->last_src = src; g->last_dst = dst; g->merges++;
    say(g, "[MERGE] %s -> %s: %d+%d calls, leftist %d visits vs binary %d.",
        ZNAME[src], ZNAME[dst], n1, n2, used, n1 + n2);
    return used;
}

int game_restore(Game *g, int z) {
    if (z < 0 || z >= NZONES || g->state[z] != ROOM_MERGED || g->outage[z] > 0) return -1;
    g->state[z] = ROOM_ONLINE; g->merged_into[z] = -1; g->route[z] = z; g->pooled[z] = 0;
    for (int a = 0; a < NAMB; a++) if (g->amb_home[a] == z) g->amb_ctrl[a] = z;
    say(g, "[RESTORE] %s control room restored with its own ambulances.", ZNAME[z]);
    return 0;
}

static int hosts_others(const Game *g, int r) {
    for (int x = 0; x < NZONES; x++) if (x != r && g->state[x] == ROOM_MERGED && g->merged_into[x] == r) return 1;
    return 0;
}

void game_autopilot(Game *g) {
    if (g->time >= SHIFT_MINUTES) return;
    for (int z = 0; z < NZONES; z++) {                          /* restore recovered / calm rooms */
        if (g->state[z] != ROOM_MERGED || g->outage[z] > 0) continue;
        int d = g->merged_into[z];
        if (!g->pooled[z] || (lh_size(g->heap[d]) <= 1 && g->time - g->merged_at[z] >= 8)) game_restore(g, z);
    }
    for (int z = 0; z < NZONES; z++) {                          /* fail over offline rooms */
        if (g->state[z] != ROOM_OFFLINE) continue;
        int best = -1, bs = 1 << 30;
        for (int d = 0; d < NZONES; d++)
            if (d != z && g->state[d] == ROOM_ONLINE && lh_size(g->heap[d]) < bs) { bs = lh_size(g->heap[d]); best = d; }
        if (best >= 0) { game_merge(g, z, best); return; }
    }
    int pooled_n = 0;                                           /* pool the nearest quiet room into the busiest one */
    for (int z = 0; z < NZONES; z++) if (g->state[z] == ROOM_MERGED && g->pooled[z]) pooled_n++;
    if (pooled_n >= 2) return;
    int d = -1, dq = POOLQ;
    for (int r = 0; r < NZONES; r++) if (g->state[r] == ROOM_ONLINE && lh_size(g->heap[r]) > dq) { dq = lh_size(g->heap[r]); d = r; }
    if (d < 0) return;
    int s = -1, sd = 1 << 30;
    for (int r = 0; r < NZONES; r++) {
        int dist = abs(HQX[r] - HQX[d]) + abs(HQY[r] - HQY[d]);
        if (r != d && g->state[r] == ROOM_ONLINE && lh_size(g->heap[r]) <= 2 && !hosts_others(g, r) && dist < sd) { sd = dist; s = r; }
    }
    if (s >= 0) game_merge(g, s, d);
}

void game_snapshot(const Game *g, Snapshot *s) {
    memset(s, 0, sizeof *s);
    s->time = g->time; s->over = g->time >= SHIFT_MINUTES;
    s->generated = g->generated; s->on_time = g->on_time; s->late = g->late;
    s->score = g->score; s->expired = g->expired;
    for (int z = 0; z < NZONES; z++) {
        s->room_state[z] = g->state[z]; s->room_size[z] = lh_size(g->heap[z]);
        s->room_outage[z] = g->outage[z]; s->room_merged_into[z] = g->merged_into[z];
        s->room_heap_ok[z] = lh_validate(g->heap[z]); s->room_spine[z] = lh_right_spine(g->heap[z]);
        s->overdue_waiting += count_overdue(g->heap[z], g->time);
    }
    for (int a = 0; a < NAMB; a++) {
        s->amb_home[a] = g->amb_home[a]; s->amb_ctrl[a] = g->amb_ctrl[a];
        s->amb_busy[a] = g->amb_busy[a]; s->amb_sev[a] = g->amb_sev[a];
        s->amb_hx[a] = g->amb_hx[a]; s->amb_hy[a] = g->amb_hy[a];
        s->amb_tx[a] = g->amb_tx[a]; s->amb_ty[a] = g->amb_ty[a];
        s->amb_total[a] = g->amb_total[a]; s->amb_travel[a] = g->amb_travel[a]; s->amb_pts[a] = g->amb_pts[a];
    }
    s->last_visits = g->last_visits; s->last_binary = g->last_binary;
    s->last_src = g->last_src; s->last_dst = g->last_dst; s->merges = g->merges;
    s->trace_n = g->trace_n; memcpy(s->trace, g->trace, sizeof s->trace);
}

int game_heap_dump(const Game *g, int room, TreeNode *out, int max) {
    const Call *q[64]; int head = 0, tail = 0;
    if (max > 64) max = 64;
    if (room < 0 || room >= NZONES || !g->heap[room] || max < 1) return 0;
    q[tail++] = g->heap[room];
    while (head < tail) {
        const Call *c = q[head]; TreeNode *t = &out[head];
        t->id = c->id; t->severity = c->severity; t->arrival = c->arrival; t->deadline = c->deadline;
        t->zone = c->zone; t->rank = c->rank; t->overdue = c->deadline < g->time; t->left = t->right = -1;
        if (c->left  && tail < max) { t->left  = tail; q[tail++] = c->left; }
        if (c->right && tail < max) { t->right = tail; q[tail++] = c->right; }
        head++;
    }
    return tail;
}

static void collect(const Game *g, const Call *h, int room, CallInfo *out, int *n, int max) {
    if (!h || *n >= max) return;
    CallInfo *o = &out[(*n)++];
    o->id = h->id; o->severity = h->severity; o->arrival = h->arrival; o->deadline = h->deadline;
    o->zone = h->zone; o->room = room; o->x = h->x; o->y = h->y; o->rank = h->rank; o->overdue = h->deadline < g->time;
    collect(g, h->left, room, out, n, max); collect(g, h->right, room, out, n, max);
}

int game_waiting(const Game *g, CallInfo *out, int max) {
    int n = 0;
    for (int z = 0; z < NZONES; z++) collect(g, g->heap[z], z, out, &n, max);
    return n;
}
