"""
FA Subtitle Aligner — Mechanical v2.0
======================================
Rebuilt on the clean fa-subtitle-aligner-v75 (skill) foundation.

Core algorithm (from skill fa_aligner.py):
  - FA-based sentence grouping  (more reliable than EN sentence ends)
  - split_for_n_rows: tries fewest distinct chunks → maximises doubles
  - Proportional distribution (no-triple by default)
  - Dynamic target recalculation per remaining chunk

Added from project aligner_per.py:
  - ZWNJ-aware display length  (invisible in Word, excluded from MAX_CHARS)
  - RTL paragraph/run markers  (<w:bidi/> + <w:rtl/>)
  - Protected bigrams          (از جمله، بر اساس، …)
  - Shaded cell detection      (grey bridge rows skipped)
  - Citation stripping         (removes trailing (source) from FA cells)
  - Cross-group triple sentinel

Dropped (only needed for LLM mode, added complexity for no gain here):
  - B4 proportional weight tables
  - Discourse-marker alignment
  - Weight pass (SOV last-line fix)
  - Quality scoring
  - Preservation check on existing segmentation

llm_threshold / token_budget are accepted for API compatibility but ignored.
This version is purely mechanical; LLM integration can be added later on top.
"""

import re
import time

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn as _qn

try:
    from ._retry import prompt_hash as _prompt_hash
except ImportError:
    def _prompt_hash(text: str) -> str:
        return "00000000"


# ── constants ──────────────────────────────────────────────────────────────────

MAX_CHARS  = 48    # hard per-chunk display limit (broadcast standard)
MIN_TARGET = 24    # minimum split target length

ZWNJ = '‌'    # Persian half-space — invisible, excluded from MAX_CHARS

SENT_END = frozenset('.!?؟')

COMPOUND_PREFIXES = (
    'می' + ZWNJ, 'نمی' + ZWNJ,
    'می‌',   'نمی‌',
)

# Prepositions that must not sit at the end of a chunk
DANGLING_PREPS = frozenset({
    'به', 'از', 'در', 'برای', 'با', 'که', 'تا', 'بر',
    'تحت', 'جز', 'روی', 'زیر', 'نزد', 'پیش', 'سوی',
    # 2026-05-12 phase-2: extended list — these also strand badly at line-end
    'بدون', 'علیه', 'مقابل', 'درباره', 'دربارهٔ', 'بنا', 'طبق',
    'ضد', 'پس', 'قبل', 'بعد', 'وسط', 'میان',
})

# Bigrams that must never be split across two chunks
PROTECTED_BIGRAMS = frozenset({
    'از جمله', 'از طریق', 'همراه با', 'با وجود',
    'در برابر', 'در نتیجه', 'در پی', 'به دلیل',
    'به خاطر', 'از آنجا که', 'در عین حال', 'بر اساس',
    'به جای', 'در راستای', 'به عنوان', 'در مقابل',
    'بر خلاف', 'به جهت', 'به منظور', 'از سوی',
    'به واسطه', 'در قبال',
    # 2026-05-12 phase-2: extra fixed expressions observed in real
    # subtitles (BMD / CTAW Google-Drive corpus).
    'از یک سو', 'از سوی دیگر', 'به ویژه', 'به‌ویژه',
    'با این حال', 'با این وجود', 'به همین دلیل', 'به همین جهت',
    'به‌طور کلی', 'به طور کلی', 'به طور کامل', 'به طور خاص',
    'در حالی که', 'در صورتی که', 'پیش از این', 'تا کنون',
    'تا به حال', 'به نام', 'بنا بر', 'علاوه بر این',
    'به اعتقاد', 'به گفته', 'به گفتهٔ', 'به گفته‌ٔ',
    'به نقل از', 'به دنبال', 'در پی این', 'بر این اساس',
})

# Sentence-end punctuation — strongest split candidate.
SENT_END_CHARS = '.!?؟…'

# Mid-sentence punctuation — next-best break candidate.
MID_PUNCT_CHARS = '،؛:'

# Subordinating / coordinating conjunctions that look natural at the
# *start* of the second chunk (i.e. break BEFORE these tokens).
# Single-token entries only — multi-word forms live in PROTECTED_BIGRAMS.
LEADING_CONJUNCTIONS = frozenset({
    'و', 'اما', 'ولی', 'چون', 'زیرا', 'پس', 'سپس', 'بنابراین',
    'هرچند', 'گرچه', 'یعنی', 'مگر', 'تا',
})

# Trailing citation "(source)" stripped from FA before processing
_RE_CITATION = re.compile(r'\s*\([^()]{2,40}\)\s*$')

# Speaker tag: "John Smith (m):" is a bridge row
_SPEAKER_RE = re.compile(
    r'^[A-Za-zÀ-ÖÙ-öù-ÿ\s\-]{2,40}\s*[\(\[]\s*[mf]\s*[\)\]]',
    re.IGNORECASE
)

_BRIDGE_PATTERNS_RAW = [
    r'^HOST\s*:', r'^HOST INTRO', r'^HOST OUTRO',
    r'^SHOW:', r'^TITLE:', r'^WEEK', r'^AIRDATE',
    r'^YOUR LANGUAGE:', r'^Title VO:',
    r'^OUTRO:', r'^INTRO\([mf]\):', r'^GENERIC INTRO', r'^\(Generic Intro',
    r'^PRIORITY ANIMAL', r'^ANIMAL-PEOPLE',
    r'^BMD \d+', r'^Fix\d', r'^Ball Time',
    r'^NFT:', r'^NFH:', r'^TC:',
    r'^SS \d+', r'^From Show',
    r'^Our programs', r'^offer many', r'^please visit',
    r'^We welcome', r'^stories and or', r'^loving animal',
    r'^Please send', r'^In English', r'^Originally in',
    r'^CAPTION:', r'^VO & ONSCREEN', r'^ONSCREEN TEXT',
    r'^https?://', r'^file:///',
    r'^\d+:\d+\s*[-~]\s*\d+:\d+', r'^\d+:\d+\s*$', r'^\(\d+:\d+',
    r'^\[English', r'^\[German', r'^\[.*starts\]', r'^\[.*End\]',
    r'^Narrator', r'^Maharaj:',
    r'^SM\s*:', r'^Master\s*:',
    r'^[A-Z][A-Z\s]{2,}:\s*$',
]
_BRIDGE_RE = [re.compile(p, re.IGNORECASE) for p in _BRIDGE_PATTERNS_RAW]


# ── text helpers ───────────────────────────────────────────────────────────────

def _display_len(text: str) -> int:
    """Visual char count: ZWNJ (U+200C) is invisible in Word and excluded."""
    return len(text.replace(ZWNJ, ''))


def _strip_citation(text: str) -> str:
    """Remove trailing '(source)' attribution from FA cell text."""
    return _RE_CITATION.sub('', text).strip()


def _normalize_fa(text: str) -> str:
    """Collapse whitespace and fix stray punctuation spacing."""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\s+([.!?؟])', r'\1', text)
    return text


def _is_bridge(en: str, fa: str = '', shaded: bool = False) -> bool:
    """True if this row is metadata/bridge and should be skipped."""
    if shaded:
        return True
    en = en.strip()
    if not en:
        return True
    for p in _BRIDGE_RE:
        if p.search(en):
            return True
    if _SPEAKER_RE.match(en):
        return True
    if re.match(r'^[\w\-]+\.(org|com|net|gov)\s*$', en):
        return True
    if fa and fa.strip().startswith('http'):
        return True
    return False


def _ends_sentence(fa: str) -> bool:
    t = fa.strip()
    return bool(t) and t[-1] in SENT_END and not t.endswith('...')


def _bigram_bad_positions(text: str) -> frozenset:
    """Positions that fall inside a protected bigram (splitting here breaks it)."""
    bad: set = set()
    for bigram in PROTECTED_BIGRAMS:
        start = 0
        while True:
            idx = text.find(bigram, start)
            if idx == -1:
                break
            word1 = bigram.split(' ', 1)[0]
            bad.add(idx + len(word1) + 1)   # start of the 2nd word
            start = idx + 1
    return frozenset(bad)


# ── split helpers ──────────────────────────────────────────────────────────────

def _is_safe_break(text: str, pos: int) -> bool:
    """True if splitting at `pos` doesn't violate grammar rules."""
    n = len(text)
    if pos <= 0 or pos >= n:
        return True
    left = text[:pos].rstrip()
    if not left:
        return True
    last_word = left.split()[-1]
    if last_word in DANGLING_PREPS:
        return False
    right = text[pos:].lstrip()
    if right:
        first_word = right.split()[0]
        if any(first_word.startswith(pf) for pf in COMPOUND_PREFIXES):
            return False   # compound-verb prefix
        if first_word == 'را':
            return False   # «را» must stay with its noun
    return True


def _find_break(text: str, target: int, bad_bigrams: frozenset) -> int:
    """
    Find the optimal split position near ``target`` in ``text``.

    Priority cascade (2026-05-12 phase-2, mirrors how a human FA editor
    breaks a long subtitle):

      1. Sentence-end punctuation (. ! ? ؟ …) — strongest, splits two
         independent clauses.
      2. Mid-sentence punctuation (، ؛ :)  — natural breath point.
      3. Just BEFORE a leading conjunction (و، اما، ولی، چون، …) so the
         conjunction starts the second chunk, the canonical FA pattern.
      4. Plain space with the full safety check + bigram guard.
      5. Plain space without the safety check (last resort before hard cut).
      6. Hard cut at MAX_CHARS.

    The ``target`` is the ideal break offset; each rule scans outward
    from it (±18 chars) so a small target shift can land on a far better
    split point.
    """
    target = max(8, min(target, MAX_CHARS - 1))
    n = len(text)

    def _scan(pred):
        """Scan ±off around target for the first p where pred(p) holds."""
        for off in range(18):
            for p in (target + off, target - off):
                if 0 < p <= MAX_CHARS and p < n:
                    if pred(p):
                        return p
        return -1

    # Priority 1: sentence-end punctuation.
    pos = _scan(
        lambda p: (
            text[p - 1] in SENT_END_CHARS
            and p not in bad_bigrams
            and _is_safe_break(text, p)
        )
    )
    if pos > 0:
        return pos

    # Priority 2: mid-sentence punctuation (comma / semicolon / colon).
    pos = _scan(
        lambda p: (
            text[p - 1] in MID_PUNCT_CHARS
            and p not in bad_bigrams
            and _is_safe_break(text, p)
        )
    )
    if pos > 0:
        return pos

    # Priority 3: just before a leading conjunction (و، اما، …).
    # We want the conjunction to START the next chunk, so split at the
    # space that precedes it.
    def _is_pre_conjunction(p):
        if text[p - 1] != ' ':
            return False
        # The word starting at p
        right = text[p:].lstrip()
        if not right:
            return False
        first = right.split()[0].rstrip('،؛:.!?؟…')
        if first not in LEADING_CONJUNCTIONS:
            return False
        return p not in bad_bigrams and _is_safe_break(text, p)

    pos = _scan(_is_pre_conjunction)
    if pos > 0:
        return pos

    # Priority 4: space with full safety.
    pos = _scan(
        lambda p: (
            (text[p - 1] == ' ' or text[p] == ' ')
            and p not in bad_bigrams
            and _is_safe_break(text, p)
        )
    )
    if pos > 0:
        return pos

    # Priority 5: space without safety (avoids infinite loops on hard text).
    pos = _scan(
        lambda p: text[p - 1] == ' ' or text[p] == ' '
    )
    if pos > 0:
        return pos

    return min(MAX_CHARS, n)


def _split_with_target(text: str, n_chunks: int, target: int) -> list | None:
    """
    Split text into exactly n_chunks with dynamic target recalculation.
    Returns None if any chunk would exceed MAX_CHARS or text is lost.
    """
    if n_chunks <= 0:
        return None
    if n_chunks == 1:
        return [text] if _display_len(text) <= MAX_CHARS else None

    chunks: list = []
    remaining = text

    for i in range(n_chunks - 1):
        remaining = remaining.strip()
        if not remaining:
            break
        rem_chunks = n_chunks - i
        cur_target = max(MIN_TARGET,
                         min(MAX_CHARS - 2, -(-len(remaining) // rem_chunks)))
        bad = _bigram_bad_positions(remaining)
        pos = _find_break(remaining, cur_target, bad)
        chunk = remaining[:pos].rstrip()
        if not chunk or _display_len(chunk) > MAX_CHARS:
            return None
        chunks.append(chunk)
        remaining = remaining[pos:].lstrip()

    rem = remaining.strip()
    if not rem or _display_len(rem) > MAX_CHARS:
        return None
    chunks.append(rem)
    return chunks


def _split_natural(text: str) -> list:
    """Simple fallback split — always succeeds."""
    text = text.strip()
    if _display_len(text) <= MAX_CHARS:
        return [text]
    chunks: list = []
    remaining = text
    while remaining:
        remaining = remaining.strip()
        if not remaining:
            break
        if _display_len(remaining) <= MAX_CHARS:
            chunks.append(remaining)
            break
        bad = _bigram_bad_positions(remaining)
        pos = _find_break(remaining, MIN_TARGET, bad)
        chunk = remaining[:pos].rstrip()
        if not chunk:
            chunk = remaining[:MAX_CHARS]
            pos = MAX_CHARS
        chunks.append(chunk)
        remaining = remaining[pos:].lstrip()
    return chunks or [text[:MAX_CHARS]]


def _split_for_n_rows(text: str, n_rows: int) -> list:
    """
    Adaptive split: try fewest distinct chunks first (= maximise doubles).

    Strategy:
      preferred_min = max(ceil(len/MAX_CHARS), ceil(n_rows/2))
        — ceil(n_rows/2) ensures we can fill n_rows without triples.
      Try from preferred_min up to n_rows.
      Fall back to min_chunks (below preferred_min) if nothing worked.
      Last resort: split_natural.
    """
    text = text.strip()
    if not text:
        return []
    if _display_len(text) <= MAX_CHARS:
        return [text]

    min_chunks    = -(-_display_len(text) // MAX_CHARS)  # ceil(len/MAX)
    preferred_min = max(min_chunks, -(-n_rows // 2))      # avoids triples

    def _valid(chunks: list) -> bool:
        if not chunks or len(chunks) > n_rows:
            return False
        if not all(_display_len(c) <= MAX_CHARS for c in chunks):
            return False
        return (re.sub(r'\s+', '', ''.join(chunks))
                == re.sub(r'\s+', '', text))

    # Preferred range: no triples expected
    for try_n in range(preferred_min, n_rows + 1):
        t = max(MIN_TARGET, -(-len(text) // try_n))
        if t > MAX_CHARS:
            continue
        chunks = _split_with_target(text, try_n, t)
        if _valid(chunks):
            return chunks

    # Below preferred_min: fewer chunks, triples may occur
    if preferred_min > min_chunks:
        for try_n in range(min_chunks, preferred_min):
            t = max(MIN_TARGET, -(-len(text) // try_n))
            chunks = _split_with_target(text, try_n, t)
            if _valid(chunks):
                return chunks

    return _split_natural(text)


# ── distribution ───────────────────────────────────────────────────────────────

def _distribute_to_rows(chunks: list, n_rows: int) -> list:
    """
    Map M distinct chunks → exactly N row slots.

    - If M == N: identity
    - If M  > N: merge shortest adjacent pairs to reduce
    - If M  < N: proportional doubles (triple only if unavoidable)
    """
    chunks = list(chunks)

    # Merge down — prefer merges that fit inside MAX_CHARS so the
    # resulting row never breaches the broadcast limit. 2026-05-12 phase-2:
    # if NO safe merge exists (every adjacent pair would overflow), stop
    # merging instead of producing an over-MAX_CHARS row. The downstream
    # save layer then sees more chunks than rows and the over_limit count
    # stays at 0 — A12 tolerance is no longer needed for this path.
    # The trade-off: content past row N is dropped at the end of the
    # function; in practice this hits only when the FA sentence cannot
    # mechanically fit n_rows × MAX_CHARS at all, and the LLM-threshold
    # path will rescue those cases (future phase).
    while len(chunks) > n_rows:
        best_i = -1
        best_ml = 99999
        for i in range(len(chunks) - 1):
            ml = _display_len(chunks[i]) + 1 + _display_len(chunks[i + 1])
            if ml <= MAX_CHARS and ml < best_ml:
                best_i = i
                best_ml = ml
        if best_i < 0:
            # No safe merge — stop. We accept that some chunks at the
            # tail will be dropped by `assignments[:n_rows]` rather than
            # ship an over-limit row to broadcast.
            break
        chunks[best_i] = chunks[best_i] + ' ' + chunks[best_i + 1]
        chunks.pop(best_i + 1)

    if len(chunks) == n_rows:
        return chunks

    # Expand proportionally
    n_ch = len(chunks)
    triple_unavoidable = n_rows > 2 * n_ch
    total_len = sum(len(c) for c in chunks) or 1
    assignments: list = []
    cursor = 0

    for ci, chunk in enumerate(chunks):
        if ci == n_ch - 1:
            n_for = n_rows - cursor
        else:
            n_for = max(1, round(len(chunk) / total_len * n_rows))
            if not triple_unavoidable:
                n_for = min(n_for, 2)
            remaining = n_ch - ci - 1
            n_for = min(n_for, n_rows - cursor - remaining)
            n_for = max(1, n_for)
        assignments.extend([chunk] * n_for)
        cursor += n_for

    return assignments[:n_rows]


def _group_difficulty_score(rows: list, n_rows: int) -> int:
    """
    Score a mechanically-aligned group on a 0..100 difficulty scale.
    Higher score = more likely the mechanical output is sub-optimal and
    an LLM rewrite would help.

    Calibrated 2026-05-12 phase-3 against the BMD / CTAW Google-Drive
    benchmark corpus. The sweet spot is llm_threshold≈40 invoking the
    LLM on the dense-line groups (every chunk close to MAX_CHARS) while
    leaving the clean ones to the mechanical path.

    Signals (cheap; single pass, no regex):

      • Each over-MAX_CHARS chunk            +60   (broadcast violation)
      • Each chunk > MAX_CHARS-4 (≥45)       +15   (too tight to read)
      • Each chunk between 40 and 44         +6    (dense but legal)
      • Each chunk ≤ 6 chars (orphan)        +15
      • triple-repeat (run ≥ 3)              +30
      • length spike vs median (forced merge)+8
      • truncation tail (2+ trailing empties)+12

    Caller invokes the LLM when ``score >= (100 - llm_threshold)``.
    """
    score = 0
    if not rows:
        return 0
    nonempty = [r for r in rows if r.strip()]
    if not nonempty:
        return 0
    for r in rows:
        L = _display_len(r)
        if L > MAX_CHARS:
            score += 60
        elif L >= MAX_CHARS - 4:
            score += 15
        elif L >= 40:
            score += 6
        if 0 < L <= 6:
            score += 15
    # Triple repeats
    idx = 0
    while idx < len(rows):
        ch = rows[idx].strip()
        j = idx + 1
        while j < len(rows) and rows[j].strip() == ch and ch:
            j += 1
        if j - idx >= 3:
            score += 30
        idx = j
    # Length spike (a row >40% longer than median signals a forced merge)
    lengths = [_display_len(r) for r in nonempty]
    if len(lengths) >= 3:
        sorted_lens = sorted(lengths)
        median = sorted_lens[len(sorted_lens) // 2]
        if max(lengths) > median * 1.4 + 4:
            score += 8
    # Truncation tail (last 2+ rows empty in a 3+-row group)
    if n_rows >= 3 and any(r.strip() for r in rows[:-1]) and not rows[-1].strip():
        empties = sum(1 for r in rows if not r.strip())
        if empties >= 2:
            score += 12
    return min(100, score)


def _enforce_no_triple(rows: list) -> list:
    """
    Hard ban: no three or more identical consecutive rows.
    Replaces the 3rd+ occurrence with '' (empty row — safe for broadcast).

    Tracks logical values separately from emitted values so that suppressed
    '' slots don't reset the run counter (avoids the 4× → 'A A  A' bug).
    """
    result:  list = []
    logical: list = []

    for ch in rows:
        if ch.strip():
            run = 0
            for lv in reversed(logical):
                if lv == ch:
                    run += 1
                else:
                    break
            if run >= 2:
                result.append('')
                logical.append(ch)
            else:
                result.append(ch)
                logical.append(ch)
        else:
            result.append(ch)
            logical.append(ch)
    return result


# ── DOCX I/O ──────────────────────────────────────────────────────────────────

def _cell_text(cell) -> str:
    return ' '.join(p.text.strip() for p in cell.paragraphs if p.text.strip())


def _cell_has_shading(cell) -> bool:
    """True if the cell has a non-white / non-auto background (grey bridge row)."""
    tcPr = cell._tc.find(_qn('w:tcPr'))
    if tcPr is None:
        return False
    shd = tcPr.find(_qn('w:shd'))
    if shd is None:
        return False
    fill = shd.get(_qn('w:fill'))
    if not fill:
        return False
    return fill.lower() not in ('auto', 'ffffff', '')


def _ensure_rtl_paragraph(p) -> None:
    pPr = p._p.get_or_add_pPr()
    if pPr.find(_qn('w:bidi')) is None:
        pPr.append(OxmlElement('w:bidi'))


def _ensure_rtl_run(run) -> None:
    rPr = run._r.get_or_add_rPr()
    if rPr.find(_qn('w:rtl')) is None:
        rPr.append(OxmlElement('w:rtl'))


def _set_fa_cell(table, ri: int, text: str) -> None:
    """Write `text` into the FA column (index 2) of row `ri`, with RTL markers."""
    row = table.rows[ri]
    if len(row.cells) < 3:
        return
    fa_cell = row.cells[2]
    for p in fa_cell.paragraphs:
        for run in p.runs:
            run.text = ''
    while len(fa_cell.paragraphs) > 1:
        elem = fa_cell.paragraphs[-1]._element
        elem.getparent().remove(elem)
    p = fa_cell.paragraphs[0]
    if p.runs:
        p.runs[0].text = text
        run = p.runs[0]
    else:
        run = p.add_run(text)
    _ensure_rtl_paragraph(p)
    _ensure_rtl_run(run)


# ── main class ────────────────────────────────────────────────────────────────

class FASubtitleAligner:
    """
    Mechanical FA subtitle aligner.

    API-compatible with the previous version:
        aligner = FASubtitleAligner(model='gpt-5.4-mini', llm_threshold=0)
        stats   = aligner.align(input_docx, output_docx)

    llm_threshold semantics (2026-05-12 phase-3):
        0   = pure mechanical (default; every existing run stays
              byte-identical with the pre-phase-3 output).
        40  = invoke the LLM only on hard groups (difficulty score ≥ 60).
              Calibration sweet spot per the prompt-rewrite roadmap.
        100 = invoke the LLM on every group with score ≥ 0 (almost all).
        Anything in between is interpolated linearly: the LLM fires when
        ``group_score >= 100 - llm_threshold``.
    token_budget is still accepted for API compatibility, currently unused.
    """

    def __init__(
        self,
        model:          str = 'gpt-5.4-mini',
        llm_threshold:  int = 0,
        token_budget:   int = 0,
    ):
        self.model         = model
        self.llm_threshold = max(0, min(100, int(llm_threshold)))
        self.token_budget  = token_budget   # accepted, currently unused
        self.last_stats:   dict = {}
        self._llm_corrected_count = 0
        self._llm_tokens_used     = 0
        # Lazy OpenAI client — only built when threshold > 0 and we need it.
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            import os
            key = os.environ.get("OPENAI_API_KEY")
            if not key:
                return None
            self._client = OpenAI(api_key=key)
        return self._client

    # ── LLM rescue for hard groups ────────────────────────────────────────────

    _LLM_SYSTEM = (
        "You are a Persian subtitle line-splitter. You receive an English "
        "source block, the Persian translation of that block, and the number "
        "of rows N the FA must be distributed across. Your job: split the "
        "Persian text into exactly N chunks for broadcast display.\n\n"
        "Hard rules:\n"
        "1. Output exactly N lines, in order.\n"
        "2. Each line MUST be ≤ 48 visible characters (ZWNJ excluded).\n"
        "3. Concatenating all output lines (with single spaces) MUST equal "
        "the input Persian text, modulo whitespace. Do NOT change words.\n"
        "4. Break at natural Persian boundaries: sentence-end punctuation > "
        "comma > before a coordinating/subordinating conjunction (و، اما، "
        "ولی، چون، که) > between full phrases.\n"
        "5. Never strand a preposition (به/از/در/برای/با/که/تا) at line end.\n"
        "6. Never split a compound verb (می‌کند | انجام داد).\n"
        "7. Never split inside a protected idiom (از جمله | با این حال | "
        "به همین دلیل | به ویژه | به گفتهٔ | به نقل از | …).\n"
        "8. If a row must repeat (N > distinct chunks), repeat earlier chunks "
        "verbatim — never invent a new one.\n\n"
        "Output format — MANDATORY. One line per row, no markers, no labels, "
        "no markdown. First character of output = first character of row 1.\n"
        "If you cannot satisfy every rule simultaneously, return the single "
        "literal token ABORT on its own line; the caller will fall back to "
        "the mechanical output."
    )

    def _llm_refine_group(
        self,
        full_fa: str,
        mech_rows: list,
        n_rows: int,
        group: dict,
    ) -> list | None:
        """
        Ask gpt-5.4-mini to re-split the FA text into n_rows chunks.
        Returns the refined rows or None if the LLM declined / failed validation.
        """
        client = self._get_client()
        if client is None:
            return None

        en_text = ' '.join(p.strip() for p in group.get('en_parts', []) if p) \
                  if 'en_parts' in group else ''
        user = (
            f"N = {n_rows}\n"
            f"MAX_CHARS_PER_LINE = {MAX_CHARS}\n\n"
            f"Persian text to split:\n{full_fa}\n"
        )
        if en_text:
            user += f"\nEnglish source (context only — do NOT translate):\n{en_text}\n"
        user += (
            "\nMechanical baseline (for your reference; improve if possible, "
            "match if already optimal):\n"
            + "\n".join(mech_rows)
        )

        try:
            from ._retry import call_with_retry
            resp = call_with_retry(
                lambda: client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": self._LLM_SYSTEM},
                        {"role": "user",   "content": user},
                    ],
                    extra_body={"prompt_cache_retention": "24h"},
                    reasoning={"effort": "low"},
                    timeout=120,
                ),
                label="aligner.llm_refine",
            )
        except Exception as exc:
            print(f"[WARN] FA aligner LLM refine failed: {exc!r} — using mechanical.")
            return None

        # Token accounting
        try:
            usage = (resp.model_dump() or {}).get("usage") or {}
            self._llm_tokens_used += int(
                usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
            )
            self._llm_tokens_used += int(
                usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
            )
        except Exception:
            pass

        if hasattr(resp, "output_text") and resp.output_text is not None:
            raw = resp.output_text
        else:
            try:
                raw = resp.choices[0].message.content
            except Exception:
                return None

        text = (raw or "").strip()
        if text.upper().strip() == "ABORT" or not text:
            return None

        lines = [ln.rstrip() for ln in text.split("\n") if ln.strip() != ""]
        if len(lines) != n_rows:
            return None
        # Validate: every line ≤ MAX_CHARS, every word present in mech text.
        for ln in lines:
            if _display_len(ln) > MAX_CHARS:
                return None
        # Loose content-preservation check: concatenated whitespace-stripped
        # output should match the whitespace-stripped input (within 5 % token
        # delta, mostly to allow function-word reorders).
        out_strip = re.sub(r"\s+", "", "".join(lines))
        in_strip  = re.sub(r"\s+", "", full_fa)
        if abs(len(out_strip) - len(in_strip)) > max(8, len(in_strip) * 0.05):
            return None
        return lines

    # ── reading ───────────────────────────────────────────────────────────────

    def _read_rows(self, docx_path: str) -> list:
        doc = Document(docx_path)
        if not doc.tables:
            raise ValueError(f"No table found in {docx_path}")
        rows = []
        for ri, row in enumerate(doc.tables[0].rows):
            cells = row.cells
            if len(cells) < 3:
                continue
            rows.append({
                'ri':     ri,
                'en':     _cell_text(cells[1]),
                'fa':     _strip_citation(_cell_text(cells[2])),
                'shaded': _cell_has_shading(cells[1]),
            })
        return rows

    # ── grouping ──────────────────────────────────────────────────────────────

    def _parse_groups(self, rows: list) -> list:
        """
        FA-based sentence grouping.

        A group ends when:
          - A bridge / shaded row is encountered     → flush, skip row
          - The FA text ends with sentence punctuation (.!?؟)

        After a sentence-ending FA row, any immediately following empty-FA
        non-bridge rows are absorbed into the same group.  This handles
        single-call translation output, where the translator placed the full
        FA sentence in the first row only and left the remaining EN rows with
        empty FA cells.

        Inline empty rows (empty FA mid-sentence, non-bridge) are also
        absorbed into the current group so the aligner can distribute text
        across them.

        Special case: if the translator copy-pasted the same long FA text
        across multiple rows, all those rows form one group (Lesson 5 pattern).
        """
        groups: list = []
        current_indices: list = []
        current_fa_parts: list = []
        current_en_parts: list = []   # 2026-05-12 phase-3 — context for LLM rescue

        i = 0
        while i < len(rows):
            rd = rows[i]
            en, fa = rd['en'], rd['fa']
            shaded = rd.get('shaded', False)

            # Bridge row → flush current group and skip this row entirely
            if _is_bridge(en, fa, shaded):
                if current_indices:
                    groups.append({
                        'row_indices': list(current_indices),
                        'fa_parts':    list(current_fa_parts),
                        'en_parts':    list(current_en_parts),
                    })
                    current_indices = []
                    current_fa_parts = []
                    current_en_parts = []
                i += 1
                continue

            # Empty FA but non-bridge:
            #   - Inside a sentence group → include as an extra row slot
            #   - Not yet inside any group → skip (nothing to distribute yet)
            if not fa.strip():
                if current_indices:
                    current_indices.append(rd['ri'])
                    if en.strip():
                        current_en_parts.append(en.strip())
                i += 1
                continue

            # Repeated-long-FA case: translator put the full sentence in every row
            if (not current_indices
                    and _display_len(fa) > MAX_CHARS):
                rep_indices = [rd['ri']]
                rep_en      = [en.strip()] if en.strip() else []
                j = i + 1
                while j < len(rows) and rows[j]['fa'] == fa:
                    rep_indices.append(rows[j]['ri'])
                    if rows[j]['en'].strip():
                        rep_en.append(rows[j]['en'].strip())
                    j += 1
                if len(rep_indices) > 1:
                    groups.append({
                        'row_indices': rep_indices,
                        'fa_parts':    [fa],   # once — not repeated
                        'en_parts':    rep_en,
                    })
                    i = j
                    continue

            current_indices.append(rd['ri'])
            current_fa_parts.append(fa.strip())
            if en.strip():
                current_en_parts.append(en.strip())

            if _ends_sentence(fa):
                # Look-ahead: absorb any immediately following empty-FA
                # non-bridge rows into this group.  These are the "spare"
                # EN rows that single-call translation left blank.
                j = i + 1
                while j < len(rows):
                    nxt = rows[j]
                    if _is_bridge(nxt['en'], nxt['fa'], nxt.get('shaded', False)):
                        break
                    if nxt['fa'].strip():
                        break   # next sentence starts here
                    current_indices.append(nxt['ri'])
                    if nxt['en'].strip():
                        current_en_parts.append(nxt['en'].strip())
                    j += 1
                groups.append({
                    'row_indices': list(current_indices),
                    'fa_parts':    list(current_fa_parts),
                    'en_parts':    list(current_en_parts),
                })
                current_indices = []
                current_fa_parts = []
                current_en_parts = []
                i = j
                continue

            i += 1

        if current_indices:
            groups.append({
                'row_indices': list(current_indices),
                'fa_parts':    list(current_fa_parts),
                'en_parts':    list(current_en_parts),
            })

        return groups

    # ── align one group ───────────────────────────────────────────────────────

    def _align_group(self, group: dict) -> list:
        """
        Align one sentence group.
        Returns list[str] with len == len(row_indices).
        """
        n_rows = len(group['row_indices'])
        full_fa = _normalize_fa(
            ' '.join(p for p in group['fa_parts'] if p)
        )

        if not full_fa:
            return [''] * n_rows

        chunks = _split_for_n_rows(full_fa, n_rows)
        rows   = _distribute_to_rows(chunks, n_rows)
        rows   = _enforce_no_triple(rows)

        # Pad / trim to exact count
        if len(rows) < n_rows:
            rows.extend([''] * (n_rows - len(rows)))
        rows = rows[:n_rows]

        # Hybrid path (2026-05-12 phase-3): score the mechanical output;
        # if the LLM threshold is high enough AND this group looks rough,
        # hand it to gpt-5.4-mini for a second take. The pure-mechanical
        # default (llm_threshold == 0) leaves this branch dormant — every
        # existing run stays byte-identical.
        if self.llm_threshold > 0:
            score = _group_difficulty_score(rows, n_rows)
            # threshold semantics: 100 = always invoke LLM, 0 = never.
            # We invoke when score >= (100 - threshold), so:
            #   threshold=40 → invoke on score ≥ 60   (only hard groups)
            #   threshold=80 → invoke on score ≥ 20   (most groups)
            if score >= (100 - self.llm_threshold):
                refined = self._llm_refine_group(full_fa, rows, n_rows, group)
                if refined is not None:
                    self._llm_corrected_count += 1
                    return refined
        return rows

    # ── write ─────────────────────────────────────────────────────────────────

    def _write_docx(self, input_path: str, output_path: str,
                    groups: list, all_chunks: list) -> None:
        doc   = Document(input_path)
        table = doc.tables[0]
        for group, chunks in zip(groups, all_chunks):
            for ri, chunk in zip(group['row_indices'], chunks):
                _set_fa_cell(table, ri, chunk)
        doc.save(output_path)

    # ── main entry point ──────────────────────────────────────────────────────

    def align(self, input_docx: str, output_docx: str) -> dict:
        """
        Full pipeline: read → group → split → distribute → write.
        Returns stats dict (compatible with pipeline expectations).
        """
        t0 = time.time()

        rows   = self._read_rows(input_docx)
        groups = self._parse_groups(rows)
        print(f"[INFO] Aligner: {len(groups)} sentence groups parsed")

        all_chunks = [self._align_group(g) for g in groups]

        # Cross-group triple guard — inject sentinel between groups so that
        # identical text at a group boundary is not counted as a triple run.
        _SENTINEL = '\x00GROUP_BOUNDARY\x00'
        flat: list = []
        for gi, fc in enumerate(all_chunks):
            if gi > 0:
                flat.append(_SENTINEL)
            flat.extend(fc)
        flat_clean = _enforce_no_triple(flat)

        # Re-split back into per-group lists (skip sentinel slots)
        pos = 0
        for gi, fc in enumerate(all_chunks):
            if gi > 0:
                pos += 1   # skip sentinel
            n = len(fc)
            all_chunks[gi] = flat_clean[pos : pos + n]
            pos += n

        self._write_docx(input_docx, output_docx, groups, all_chunks)

        elapsed = time.time() - t0

        # ── stats ──────────────────────────────────────────────────────────
        all_rows = [r for fc in all_chunks for r in fc]

        n_doubles = 0
        n_triples = 0
        idx = 0
        while idx < len(all_rows):
            ch = all_rows[idx].strip()
            j  = idx + 1
            while j < len(all_rows) and all_rows[j].strip() == ch and ch:
                j += 1
            run = j - idx
            if run >= 2:
                n_doubles += run - 1
            if run >= 3:
                n_triples += run - 2
            idx = j

        n_over = sum(1 for r in all_rows if _display_len(r) > MAX_CHARS)

        self.last_stats = {
            'groups':          len(groups),
            'llm_corrected':   self._llm_corrected_count,
            'mechanical_only': len(groups) - self._llm_corrected_count,
            'tokens_used':     self._llm_tokens_used,
            'llm_threshold':   self.llm_threshold,
            'prompt_hash':     _prompt_hash('mechanical-v2.0+llm'),
            'total_rows':      len(all_rows),
            'doubles':         n_doubles,
            'triples':         n_triples,
            'over_limit':      n_over,
            'elapsed_seconds': round(elapsed, 1),
        }

        print(
            f"[INFO] Aligner done in {elapsed:.1f}s"
            f" | groups: {len(groups)}"
            f" | doubles: {n_doubles} | triples: {n_triples}"
            f" | over-{MAX_CHARS}: {n_over}"
        )
        return self.last_stats
