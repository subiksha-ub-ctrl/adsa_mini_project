#include <stdlib.h>
#include "leftist_heap.h"

static long visits = 0;
long lh_visits(void) { return visits; }

static int trace_on, trace_n, trace_ids[64];
void lh_trace(int on) { if (on) trace_n = 0; trace_on = on; }
int lh_trace_count(void) { return trace_n; }
int lh_trace_id(int i) { return trace_ids[i]; }

static int rk(const Call *n) { return n ? n->rank : 0; }

/* a has strictly higher priority than b */
static int before(const Call *a, const Call *b) {
    if (a->severity != b->severity) return a->severity < b->severity;
    if (a->arrival  != b->arrival)  return a->arrival  < b->arrival;
    return a->id < b->id;
}

Call *lh_new(int id, int severity, int arrival, int deadline, int zone) {
    Call *n = calloc(1, sizeof *n);
    n->id = id; n->severity = severity; n->arrival = arrival;
    n->deadline = deadline; n->zone = zone; n->rank = 1;
    return n;
}

Call *lh_merge(Call *a, Call *b) {
    if (!a) return b;
    if (!b) return a;
    visits++;
    if (before(b, a)) { Call *t = a; a = b; b = t; }   /* smaller key becomes the root */
    if (trace_on && trace_n < 64) trace_ids[trace_n++] = a->id;
    a->right = lh_merge(a->right, b);                  /* recurse down the RIGHT spine only */
    if (rk(a->left) < rk(a->right)) {                  /* restore the leftist property */
        Call *t = a->left; a->left = a->right; a->right = t;
    }
    a->rank = rk(a->right) + 1;
    return a;
}

Call *lh_insert(Call *h, Call *node) { return lh_merge(h, node); }

Call *lh_pop(Call *h, Call **min_out) {
    if (!h) { *min_out = NULL; return NULL; }
    Call *rest = lh_merge(h->left, h->right);
    h->left = h->right = NULL;
    *min_out = h;
    return rest;
}

const Call *lh_peek(const Call *h) { return h; }

int lh_size(const Call *h) { return h ? 1 + lh_size(h->left) + lh_size(h->right) : 0; }

int lh_validate(const Call *h) {
    if (!h) return 1;
    if (h->left  && before(h->left,  h)) return 0;     /* heap order */
    if (h->right && before(h->right, h)) return 0;
    if (rk(h->left) < rk(h->right)) return 0;          /* leftist property */
    if (h->rank != rk(h->right) + 1) return 0;         /* rank bookkeeping */
    return lh_validate(h->left) && lh_validate(h->right);
}

int lh_right_spine(const Call *h) { int n = 0; for (; h; h = h->right) n++; return n; }

void lh_free(Call *h) { if (h) { lh_free(h->left); lh_free(h->right); free(h); } }
