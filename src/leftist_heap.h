/* Leftist heap: a mergeable priority queue (Unit III, Hierarchical Data Structures).
 * Key order: severity (0 = critical ... 3 = minor), then arrival time, then call id. */
#ifndef LEFTIST_HEAP_H
#define LEFTIST_HEAP_H

enum { SEV_CRITICAL = 0, SEV_SERIOUS = 1, SEV_MODERATE = 2, SEV_MINOR = 3 };

typedef struct Call {
    int id, severity, arrival, deadline, zone;
    int x, y, penalized;            /* map position (game), expiry-penalty flag */
    int rank;                       /* null-path length: NULL = 0, leaf = 1 */
    struct Call *left, *right;
} Call;

Call *lh_new(int id, int severity, int arrival, int deadline, int zone);
Call *lh_merge(Call *a, Call *b);              /* O(log n): walks right spines only */
Call *lh_insert(Call *h, Call *node);          /* insert = merge with a 1-node heap */
Call *lh_pop(Call *h, Call **min_out);         /* delete-min = merge(left, right)   */
const Call *lh_peek(const Call *h);
int   lh_size(const Call *h);
int   lh_validate(const Call *h);              /* 1 if heap order + leftist property + ranks hold */
int   lh_right_spine(const Call *h);           /* nodes on the right spine (<= log2(n+1)) */
void  lh_free(Call *h);
long  lh_visits(void);                         /* total node visits made by lh_merge so far */

/* Optional trace: while on, lh_merge records the id of every node it visits (for the UI). */
void  lh_trace(int on);
int   lh_trace_count(void);
int   lh_trace_id(int i);

#endif
