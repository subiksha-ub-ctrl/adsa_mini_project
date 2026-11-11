/* Game engine for "108 Ambulance Dispatch Zones". All rules live in C;
 * the Python/Tkinter front end only draws state and forwards player actions.
 * Map: 1000 x 700 units, road grid every 50 units, Manhattan travel at 80 units/min. */
#ifndef GAME_H
#define GAME_H
#include "leftist_heap.h"

#define NZONES 4
#define NAMB 8
#define SHIFT_MINUTES 120
#define LAST_ARRIVAL 105

enum { ROOM_ONLINE = 0, ROOM_OFFLINE = 1, ROOM_MERGED = 2 };

typedef struct Game Game;

typedef struct { int id, severity, arrival, deadline, zone, rank, left, right, overdue; } TreeNode;
typedef struct { int id, severity, arrival, deadline, zone, room, x, y, rank, overdue; } CallInfo;

typedef struct {
    int time, over, generated, on_time, late, overdue_waiting, score, expired;
    int room_state[NZONES], room_size[NZONES], room_outage[NZONES], room_merged_into[NZONES];
    int room_heap_ok[NZONES], room_spine[NZONES];
    int amb_home[NAMB], amb_ctrl[NAMB], amb_busy[NAMB], amb_sev[NAMB];
    int amb_hx[NAMB], amb_hy[NAMB], amb_tx[NAMB], amb_ty[NAMB], amb_total[NAMB], amb_travel[NAMB], amb_pts[NAMB];
    int last_visits, last_binary, last_src, last_dst, merges;
    int trace_n, trace[32];
} Snapshot;

Game *game_new(unsigned seed);
void  game_free(Game *g);
void  game_tick(Game *g);                       /* advance one minute */
int   game_merge(Game *g, int src, int dst);    /* returns node visits, -1 if illegal */
int   game_restore(Game *g, int zone);          /* bring a merged room back, 0 ok / -1 illegal */
void  game_autopilot(Game *g);                  /* built-in failover + pooling policy */
void  game_snapshot(const Game *g, Snapshot *s);
int   game_heap_dump(const Game *g, int room, TreeNode *out, int max);  /* BFS, for drawing the tree */
int   game_waiting(const Game *g, CallInfo *out, int max);              /* every waiting call, for map pins */
int   game_pop_log(Game *g, char *buf, int n);  /* 1 if a message was returned */

#endif
