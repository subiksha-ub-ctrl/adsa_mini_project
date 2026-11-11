/* Unit tests for the leftist heap. Run with: make test */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "leftist_heap.h"

static int fails = 0;
#define CHECK(c, msg) do { if (c) printf("  PASS  %s\n", msg); else { printf("  FAIL  %s\n", msg); fails++; } } while (0)

static Call *build(int n, int id0, unsigned seed) {
    Call *h = NULL; srand(seed);
    for (int i = 0; i < n; i++) h = lh_insert(h, lh_new(id0 + i, rand() % 4, rand() % 500, 0, 0));
    return h;
}

int main(void) {
    printf("Leftist heap unit tests\n");

    /* 1. ordering: severity first, then arrival time */
    Call *h = NULL, *m;
    h = lh_insert(h, lh_new(1, SEV_MINOR, 1, 0, 0));
    h = lh_insert(h, lh_new(2, SEV_CRITICAL, 5, 0, 0));
    h = lh_insert(h, lh_new(3, SEV_CRITICAL, 2, 0, 0));
    h = lh_insert(h, lh_new(4, SEV_SERIOUS, 0, 0, 0));
    int order[4], k = 0;
    while (h) { h = lh_pop(h, &m); order[k++] = m->id; free(m); }
    CHECK(order[0] == 3 && order[1] == 2 && order[2] == 4 && order[3] == 1, "delete-min order: critical (earliest first) -> serious -> minor");

    /* 2. merge two heaps of 2000 calls each */
    Call *a = build(2000, 1, 7), *b = build(2000, 5001, 11);
    CHECK(lh_validate(a) && lh_validate(b), "both 2000-call heaps valid before merge");
    int sa = lh_right_spine(a), sb = lh_right_spine(b);
    long v0 = lh_visits();
    Call *u = lh_merge(a, b);
    long used = lh_visits() - v0;
    printf("  INFO  right spines %d + %d, merge of 2000+2000 calls visited %ld nodes (binary heap: 4000)\n", sa, sb, used);
    CHECK(used <= sa + sb, "node visits <= sum of the two right-spine lengths");
    CHECK(lh_size(u) == 4000 && lh_validate(u), "merged heap has 4000 calls and stays valid");
    CHECK(lh_right_spine(u) <= (int)floor(log2(4001.0)), "right spine <= log2(n+1)");

    /* 3. drain in sorted order */
    int ok = 1, prev_s = -1, prev_a = -1, cnt = 0;
    while (u) {
        u = lh_pop(u, &m);
        if (m->severity < prev_s || (m->severity == prev_s && m->arrival < prev_a)) ok = 0;
        prev_s = m->severity; prev_a = m->arrival; cnt++; free(m);
    }
    CHECK(ok && cnt == 4000, "4000 delete-mins come out in non-decreasing priority");

    /* 4. leftist property survives random insert/pop mix */
    srand(3); h = NULL; ok = 1;
    for (int i = 0; i < 5000; i++) {
        if (rand() % 3 && h) h = lh_pop(h, &m), free(m);
        else h = lh_insert(h, lh_new(i, rand() % 4, rand() % 100, 0, 0));
        if (i % 250 == 0 && !lh_validate(h)) ok = 0;
    }
    CHECK(ok && lh_validate(h), "invariants hold through 5000 mixed insert/delete-min operations");
    lh_free(h);

    printf(fails ? "%d test(s) FAILED\n" : "All tests passed\n", fails);
    return fails != 0;
}
