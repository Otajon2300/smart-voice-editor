"""Follow the reading along the script.

The reader moves forward through the text. A retake shows up as a jump
back: the path returns to a script position already read. Everything read
from that position up to the jump is the abandoned take; the last take is
kept. Words that are not in the script are "inserts" and are kept unless
they belong to an abandoned take.
"""
import numpy as np

MATCH = 62           # similarity (0-100) for a heard token to read a script token
BACK_PENALTY = 2.6   # a restart must be confirmed by several re-read words
BACK_LIMIT = 150     # a restart reaches back at most this many script tokens
SKIP = .35           # per script token skipped (or missed by ASR)
JUMP = 4.            # cost of a long forward jump (unvoiced standup, partial reading)
INSERT = .45         # per heard token that is not in the script
RETAKE_REACH = 120.  # seconds an abandoned take may extend back from the restart
MAX_CELLS = 100_000_000   # 4 bytes per cell (similarity, move, source): at most ~400 MB


def similarity(script, heard):
    """heard x script matrix, 0..100 (uint8). Digits must match exactly."""
    from rapidfuzz.process import cdist
    from rapidfuzz.fuzz import ratio
    sims = cdist(heard, script, scorer=ratio, dtype=np.uint8, workers=-1)
    digits_h = np.array([t.isdigit() for t in heard])
    digits_s = np.array([t.isdigit() for t in script])
    if digits_h.any() or digits_s.any():
        for i in np.flatnonzero(digits_h):
            sims[i] = np.where(np.array(script, dtype=object) == heard[i], 100, 0)
        for j in np.flatnonzero(digits_s):
            sims[:, j] = np.where(np.array(heard, dtype=object) == script[j], 100, 0)
    return sims


def _window_max(values, width):
    """max(values[j:j+width]) and its index for every j (doubling)."""
    best, where = values.copy(), np.arange(len(values))
    span = 1
    while span < width:
        step = min(span, width - span)
        other = np.full(len(values), -np.inf)
        other_where = where.copy()
        other[:-step] = best[step:]
        other_where[:-step] = where[step:]
        take = other > best
        best = np.where(take, other, best)
        where = np.where(take, other_where, where)
        span += step
    return best, where


def follow(script, heard):
    """Script position read by each heard token (-1: none) and whether it is a read (not an insert)."""
    m, n = len(script), len(heard)
    if not m or not n:
        return [-1] * n, [False] * n
    if m * n > MAX_CELLS:
        raise ValueError('Ssenariy va audio juda katta (%d × %d so‘z). Audioni qismlarga bo‘lib ishlang.' % (m, n))
    sims = similarity(script, heard)
    ramp = np.arange(m, dtype=np.float64) * SKIP
    columns = np.arange(m)
    score = np.full(m, -np.inf)
    kind = np.zeros((n, m), dtype=np.uint8)      # 0 forward, 1 back, 2 insert, 3 enter, 4 jump
    source = np.zeros((n, m), dtype=np.uint16 if m < 65535 else np.int32)   # -1 is never followed (see below)
    best = (0., -1, -1)
    for i in range(n):
        row = sims[i].astype(np.float32)
        gains = np.where(row >= MATCH, row / 50 - .7, -1.2)
        # Short forward step from k < j, paying for each skipped token.
        lifted = np.r_[-np.inf, score[:-1] + ramp[:-1]]
        running = np.maximum.accumulate(lifted)
        running_at = np.maximum.accumulate(np.where(lifted == running, columns - 1, -1))
        forward = running - ramp + SKIP
        # Long forward jump from any k < j at a fixed cost.
        prefix = np.r_[-np.inf, np.maximum.accumulate(score)[:-1]]
        prefix_at = np.r_[-1, np.maximum.accumulate(np.where(score == np.maximum.accumulate(score), columns, -1))[:-1]]
        jump = prefix - JUMP
        back, back_at = _window_max(score, BACK_LIMIT)
        back = back - BACK_PENALTY
        # Every move that reads the token earns its similarity gain; an insert does not.
        options = np.vstack([forward + gains, back + gains, score - INSERT, gains, jump + gains])
        choice = np.argmax(options, axis=0)
        new = options[choice, columns]
        kind[i] = choice
        source[i] = np.select([choice == 0, choice == 1, choice == 4], [running_at, back_at, prefix_at], columns)
        score = new
        j = int(np.argmax(score))
        if score[j] > best[0]:
            best = (float(score[j]), i, j)
    path, reads = [-1] * n, [False] * n
    _, i, j = best
    while i >= 0:
        c = kind[i, j]
        path[i] = j
        reads[i] = c != 2
        if c == 3:
            break
        j = int(source[i, j])
        i -= 1
    return path, reads


def abandoned(path, reads, times):
    """Heard tokens of abandoned takes.

    At every jump back to script position q, tokens read before it at
    positions >= q (and inserts among them) are the abandoned take.
    """
    n = len(path)
    reads = list(reads)
    # A single token read "back" that the reading does not continue from is a misheard
    # fragment, not a restart: treat it as an insert so the real restart is found.
    last = None
    for i in range(n):
        if path[i] < 0 or not reads[i]:
            continue
        if last is not None and path[i] < path[last]:
            following = next((k for k in range(i + 1, n) if path[k] >= 0 and reads[k]), None)
            if following is not None and path[following] not in (path[i], path[i] + 1):
                reads[i] = False
                continue
        last = i
    dropped = [False] * n
    previous = None
    for i in range(n):
        if path[i] < 0 or not reads[i]:
            continue
        q = path[i]
        if previous is not None and q <= path[previous]:
            k = i - 1
            while k >= 0 and times[i] - times[k] <= RETAKE_REACH:
                if not dropped[k]:
                    if path[k] < 0 or (reads[k] and path[k] < q):
                        break
                    dropped[k] = True
                k -= 1
        previous = i
    return dropped
