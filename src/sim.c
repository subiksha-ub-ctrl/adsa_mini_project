/* Headless benchmark: 30 random shifts, no merging vs. failover + pooling. */
#include <stdio.h>
#include "game.h"

static double run(unsigned seed, int use_merge) {
    Game *g = game_new(seed); Snapshot s;
    while (1) {
        if (use_merge) game_autopilot(g);
        game_tick(g);
        game_snapshot(g, &s);
        if (s.over) break;
    }
    double pct = 100.0 * s.on_time / s.generated;
    game_free(g);
    return pct;
}

int main(void) {
    double a = 0, b = 0; int wins = 0;
    for (unsigned seed = 1; seed <= 30; seed++) {
        double x = run(seed, 0), y = run(seed, 1);
        a += x; b += y; wins += y >= x;
    }
    printf("30 random shifts (120 min each)\n");
    printf("  no merging          : %.1f%% of calls reached in time\n", a / 30);
    printf("  failover + pooling  : %.1f%% of calls reached in time\n", b / 30);
    printf("  merging was at least as good in %d of 30 shifts\n", wins);
    return 0;
}
