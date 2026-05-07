"""
FA Subtitle Aligner — Score-then-LLM pipeline
==============================================
Reads a bilingual EN|FA subtitle DOCX, re-distributes Persian text
across TV rows using:
  Pass 1 — Mechanical split (no API, ~80% quality)
  Pass 2 — Quality scoring per group (no API)
  Pass 3 — LLM batch re-split for low-quality groups (gpt-5.4-mini)

Hard limits enforced in both passes:
  - Each FA chunk ≤ 48 characters
  - Triple (3 identical rows) only when every copy ≤ 20 characters
  - Token budget cap (default 40 000) — excess groups keep mechanical result

Usage from pipeline:
    from openai_tools.aligner import FASubtitleAligner
    aligner = FASubtitleAligner(model="gpt-5.4-mini")
    stats = aligner.align(input_docx, output_docx)
"""

import os
import re
import json
import time
import unicodedata
from collections import Counter
from docx import Document
from docx.oxml.ns import qn as _qn

try:
    from openai import OpenAI as _OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

try:
    import tiktoken as _tiktoken
    _HAS_TIKTOKEN = True
except ImportError:
    _HAS_TIKTOKEN = False


# ── constants ─────────────────────────────────────────────────────────────────

MAX_CHARS    = 48        # hard limit per chunk
TRIPLE_LIMIT = 20        # triple allowed only when each copy ≤ this
MIN_TARGET   = 24        # minimum target length when splitting
ZWNJ         = '‌'  # Persian half-space

SENT_END = frozenset('.!?؟')

COMPOUND_PREFIXES = {
    'می' + ZWNJ, 'نمی' + ZWNJ,
    'می ',       'نمی ',
}

# NOTE: dangling-preposition rule intentionally removed per project requirements.

BRIDGE_PATTERNS = [
    re.compile(r'^file:///'),
    re.compile(r'^\([^()]{2,40}\)\s*$'),
    re.compile(r'^https?://'),
    re.compile(r'^\d+:\d+'),                   # timecodes: "0:34 ~ 0:44", "1:10 ~ 1:24"
    re.compile(r'^\d+[\.\)]?\s*$'),
    re.compile(r'^[A-Z][A-Z\s]{2,}:\s*$'),     # ALL-CAPS labels: "YOUR LANGUAGE:", "ONSCREEN TEXT:"
    re.compile(r'^[A-Z][a-z]+\s*:$'),
    re.compile(r'^Narrator'),
    re.compile(r'^HOST:', re.I),
    re.compile(r'^SHOW:', re.I),
    re.compile(r'^CAPTION:', re.I),
    re.compile(r'^ONSCREEN', re.I),
    re.compile(r'^VO\s*[&:]', re.I),
    re.compile(r'^BMD\s'),
    re.compile(r'^Fix[12]'),
]

# Minimal built-in cues (project can supply alignment_cues.json alongside)
_BUILTIN_CUES = {
    'cause':      {'weight': 0.8, 'cues': {
        'because': ['چون', 'زیرا', 'چراکه'],
        'since':   ['چون', 'از آنجا که'],
    }},
    'result':     {'weight': 0.9, 'cues': {
        'therefore': ['بنابراین', 'ازاین‌رو'],
        'so':        ['پس', 'بنابراین'],
    }},
    'contrast':   {'weight': 0.7, 'cues': {
        'but':     ['اما', 'ولی'],
        'however': ['اما', 'با این حال'],
    }},
    'concession': {'weight': 0.8, 'cues': {
        'although':    ['اگرچه', 'هرچند'],
        'even though': ['با اینکه', 'هرچند'],
    }},
    'condition':  {'weight': 0.8, 'cues': {
        'if': ['اگر', 'در صورتی که'],
    }},
    'time':       {'weight': 0.6, 'cues': {
        'when':  ['وقتی', 'هنگامی که'],
        'while': ['در حالی که'],
    }},
}


# ── standalone helpers ────────────────────────────────────────────────────────

def _cell_text(cell) -> str:
    return ' '.join(p.text.strip() for p in cell.paragraphs if p.text.strip())


def _cell_has_shading(cell) -> bool:
    """Return True if the cell has a non-white / non-auto background fill."""
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


def _is_bridge(en: str) -> bool:
    en = en.strip()
    if not en:          # empty EN cell — never process
        return True
    return any(p.search(en) for p in BRIDGE_PATTERNS)


def _ends_sentence(text: str) -> bool:
    t = text.strip()
    return bool(t) and t[-1] in SENT_END and not t.endswith('...')


def _normalize_fa(text: str) -> str:
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = re.sub(r'[ًٌٍَُِّْ]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def _normalize_text(text: str) -> str:
    return re.sub(r'\s+', '', text)


def _estimate_tokens(text: str) -> int:
    if _HAS_TIKTOKEN:
        try:
            enc = _tiktoken.get_encoding('cl100k_base')
            return len(enc.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 3)


# ── main class ────────────────────────────────────────────────────────────────

class FASubtitleAligner:
    """
    Score-then-LLM subtitle aligner for Persian/English DOCX files.
    """

    _SYSTEM_PROMPT = (
        "You are a bilingual Persian/English subtitle aligner for TV broadcast.\n"
        "You receive a JSON array of sentence groups. Each group has:\n"
        "  id       — batch index (integer)\n"
        "  n_rows   — number of TV display rows to fill (integer)\n"
        "  en_rows  — English text for each row (array of strings)\n"
        "  full_fa  — complete Persian sentence to distribute (string)\n\n"
        "Task: split full_fa into exactly n_rows Persian chunks.\n\n"
        "HARD RULES — never violate:\n"
        "  1. Each chunk ≤ 48 characters (count carefully).\n"
        "  2. Chunks joined with single space must equal full_fa exactly.\n"
        "  3. Consecutive identical chunks = double (allowed, max 2 identical).\n"
        "  4. Triple (3 identical) ONLY when each copy ≤ 20 characters.\n"
        "  5. Never split compound verbs (می‌کند، نمی‌دهد، انجام می‌دهد …).\n"
        "  6. Never start a chunk with standalone 'را'.\n\n"
        "PREFERENCES — apply after hard rules:\n"
        "  • Split at clause boundaries: که، اما، ولی، زیرا، چون، بنابراین\n"
        "  • Align FA chunk to EN row: numbers and named entities in same row\n"
        "  • Discourse markers (because→چون, however→اما) aligned where possible\n"
        "  • Chunks roughly balanced in length\n\n"
        "Respond ONLY with JSON (no explanation):\n"
        '{"results": [{"id": <id>, "fa_rows": ["chunk1", "chunk2", ...]}, ...]}\n'
        "fa_rows must have exactly n_rows strings. Use identical strings for doubles."
    )

    def __init__(
        self,
        model:         str = 'gpt-5.4-mini',
        llm_threshold: int = 90,
        token_budget:  int = 40_000,
    ):
        self.model         = model
        self.llm_threshold = llm_threshold
        self.token_budget  = token_budget
        self.tokens_used   = 0
        self.last_stats    = {}
        self.client        = None
        self._cues         = _BUILTIN_CUES

        if _HAS_OPENAI:
            api_key = os.environ.get('OPENAI_API_KEY')
            if api_key:
                self.client = _OpenAI(api_key=api_key)

        self._load_cues()

    def _load_cues(self):
        """Load alignment_cues.json if available alongside this file."""
        cues_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'alignment_cues.json')
        if os.path.exists(cues_path):
            try:
                with open(cues_path, encoding='utf-8') as f:
                    data = json.load(f)
                self._cues = data.get('en_to_fa', _BUILTIN_CUES)
            except Exception:
                pass

    # ── DOCX I/O ──────────────────────────────────────────────────────────────

    def _read_rows(self, docx_path: str) -> list:
        doc = Document(docx_path)
        if not doc.tables:
            raise ValueError(f"No table in {docx_path}")
        rows = []
        for ri, row in enumerate(doc.tables[0].rows):
            cells = row.cells
            if len(cells) < 3:
                continue
            rows.append({
                'ri':     ri,
                'en':     _cell_text(cells[1]),
                'fa':     _cell_text(cells[2]),
                'shaded': _cell_has_shading(cells[1]),  # grey/colored EN cell = metadata
            })
        return rows

    def _parse_groups(self, rows: list) -> list:
        """
        Group consecutive non-bridge rows into sentence groups by EN endings.
        Returns list of groups:
          {row_indices, en_rows, full_fa, n_rows}
        """
        groups  = []
        current = []

        def flush():
            if not current:
                return
            unique_fa = []
            seen = set()
            for r in current:
                fa = r['fa'].strip()
                if fa and fa not in seen:
                    unique_fa.append(fa)
                    seen.add(fa)
            full_fa = ' '.join(unique_fa)
            groups.append({
                'row_indices': [r['ri'] for r in current],
                'en_rows':     [r['en'] for r in current],
                'full_fa':     full_fa,
                'n_rows':      len(current),
            })
            current.clear()

        for rd in rows:
            if _is_bridge(rd['en']) or rd.get('shaded', False):
                flush()
                continue
            current.append(rd)
            if _ends_sentence(rd['en']):
                flush()

        flush()
        return groups

    def _set_fa_cell(self, table, ri: int, text: str):
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
        else:
            p.add_run(text)

    def _write_docx(self, input_path: str, output_path: str,
                    groups: list, all_chunks: list):
        doc   = Document(input_path)
        table = doc.tables[0]
        for group, chunks in zip(groups, all_chunks):
            for ri, chunk in zip(group['row_indices'], chunks):
                self._set_fa_cell(table, ri, chunk)
        doc.save(output_path)

    # ── split point detection (from v7 script) ────────────────────────────────

    def _find_split_points(self, text: str) -> list:
        """Return list of (position, quality) sorted by quality desc."""
        candidates = []
        words = text.split()
        pos = 0
        boundaries = []
        for w in words:
            idx = text.find(w, pos)
            boundaries.append((idx, idx + len(w), w))
            pos = idx + len(w)

        for i, (start, end, word) in enumerate(boundaries):
            if i == 0:
                continue
            quality = 50
            prev = boundaries[i - 1][2]

            if prev and prev[-1] in SENT_END and not prev.endswith('...'):
                quality = 100
            elif prev and prev[-1] in ',;،؛':
                quality = 85

            # Discourse marker alignment bonus
            w_norm = _normalize_fa(word)
            for cat in self._cues.values():
                for fa_list in cat.get('cues', {}).values():
                    for fa_eq in fa_list:
                        if w_norm.startswith(_normalize_fa(fa_eq)):
                            quality = max(quality, 80)

            # Compound verb: never split before می‌ / نمی‌
            if any(word.startswith(pf) for pf in COMPOUND_PREFIXES):
                quality = 5

            # «را» stays with its noun
            if word.strip() == 'را':
                quality = 5

            candidates.append((start, quality))

        candidates.sort(key=lambda x: -x[1])
        return candidates

    # ── recursive split (adapted from v7) ─────────────────────────────────────

    def _recursive_split(self, text: str, n_parts: int, target: int) -> list:
        text = text.strip()
        if n_parts <= 1 or not text:
            return [text] if text else ['']
        # NOTE: do NOT short-circuit on len<=MAX_CHARS here.
        # Caller may need n_parts=2 even for short text (to enable doubling).

        candidates = self._find_split_points(text)
        best = None
        best_score = -1

        for pos, quality in candidates:
            left  = text[:pos].rstrip()
            right = text[pos:].lstrip()
            if not left or not right or len(left) > MAX_CHARS:
                continue
            ideal   = len(text) / n_parts
            balance = 1.0 - abs(len(left) - ideal) / max(len(text), 1)
            score   = quality * 0.6 + balance * 100 * 0.4
            if score > best_score:
                best_score = score
                best = (left, right)

        if best is None:
            sp = text.rfind(' ', 0, min(target, MAX_CHARS))
            if sp <= 0:
                sp = text.find(' ', min(target, MAX_CHARS))
            if sp <= 0:
                sp = MAX_CHARS
            best = (text[:sp].rstrip(), text[sp:].lstrip())

        left, right = best
        rest = self._recursive_split(right, n_parts - 1, target)
        return [left] + rest

    def _emergency_split(self, text: str, n_parts: int) -> list:
        chunks = []
        rem = text.strip()
        for i in range(n_parts):
            if i == n_parts - 1:
                chunks.append(rem)
                break
            if len(rem) <= MAX_CHARS:
                chunks.append(rem)
                rem = ''
                continue
            sp = rem.rfind(' ', 0, MAX_CHARS)
            if sp <= 0:
                sp = MAX_CHARS
            chunks.append(rem[:sp].rstrip())
            rem = rem[sp:].lstrip()
        while len(chunks) < n_parts:
            chunks.append('')
        return chunks

    def _split_distinct(self, text: str, n_distinct: int) -> list:
        """Split text into n_distinct chunks each ≤ MAX_CHARS."""
        text = text.strip()
        if not text:
            return [''] * n_distinct
        if n_distinct <= 1:
            return [text]

        target = max(MIN_TARGET, len(text) // n_distinct)
        chunks = self._recursive_split(text, n_distinct, target)

        # Safety: enforce MAX_CHARS
        for c in chunks:
            if len(c) > MAX_CHARS:
                return self._emergency_split(text, n_distinct)
        return chunks

    # ── distribute (doubles + triple rule) ────────────────────────────────────

    def _distribute(self, chunks: list, n_rows: int) -> list:
        """
        Map M distinct chunks → exactly N row slots.
        Strategy: double longest chunks first; triple only if chunk ≤ TRIPLE_LIMIT.
        """
        m = len(chunks)
        if m >= n_rows:
            return list(chunks[:n_rows])

        extra = n_rows - m
        by_len = sorted(range(m), key=lambda i: len(chunks[i]), reverse=True)
        double_set: set = set()
        triple_set: set = set()

        for i in by_len:
            if extra <= 0:
                break
            double_set.add(i)
            extra -= 1
            # Allow triple if this chunk is short enough
            if extra > 0 and len(chunks[i]) <= TRIPLE_LIMIT:
                triple_set.add(i)
                extra -= 1

        rows = []
        for i, ch in enumerate(chunks):
            rows.append(ch)
            if i in double_set:
                rows.append(ch)
            if i in triple_set:
                rows.append(ch)

        # If still short (e.g. needed more than 2-3× the chunks), pad with last row
        while len(rows) < n_rows:
            rows.append(rows[-1] if rows else '')
        return rows[:n_rows]

    def _enforce_no_bad_triple(self, rows: list) -> list:
        """Remove triples where each copy > TRIPLE_LIMIT."""
        counts: dict = {}
        result = []
        for ch in rows:
            counts[ch] = counts.get(ch, 0) + 1
            if counts[ch] > 2 and ch.strip() and len(ch) > TRIPLE_LIMIT:
                result.append(result[-1] if result else ch)
            else:
                result.append(ch)
        return result

    def _mechanical_align(self, group: dict) -> list:
        """Mechanical pass for one group. Returns list of len == n_rows."""
        full_fa = group['full_fa'].strip()
        n_rows  = group['n_rows']
        en_rows = group['en_rows']

        if not full_fa:
            return [''] * n_rows

        # ceil(len / MAX_CHARS) = minimum chunks to fit within char limit
        min_by_len  = max(1, -(-len(full_fa) // MAX_CHARS))
        # ceil(n_rows / 2) = minimum chunks so doubles can fill all rows
        min_by_rows = -(-n_rows // 2)
        min_dist    = max(min_by_len, min_by_rows)

        # Get distinct chunks
        chunks = self._split_distinct(full_fa, min_dist)

        # Try discourse-marker alignment to improve EN↔FA correspondence
        chunks = self._try_marker_align(full_fa, en_rows, chunks)

        # Distribute into n_rows slots
        rows = self._distribute(chunks, n_rows)

        # Remove bad triples
        rows = self._enforce_no_bad_triple(rows)

        # Final length guard (pad/trim to exact n_rows)
        if len(rows) < n_rows:
            rows.extend([''] * (n_rows - len(rows)))
        return rows[:n_rows]

    def _try_marker_align(self, full_fa: str, en_rows: list, chunks: list) -> list:
        """Try to shift split points to align discourse markers EN↔FA."""
        if len(chunks) < 2 or not en_rows:
            return chunks

        improved = list(chunks)
        for i, en in enumerate(en_rows):
            if i == 0 or i >= len(improved):
                continue
            en_lower = en.strip().lower()
            for cat in self._cues.values():
                for en_marker, fa_equivs in cat.get('cues', {}).items():
                    if not en_lower.startswith(en_marker.lower()):
                        continue
                    # Check if chunk[i] already starts with an FA equivalent
                    chunk_norm = _normalize_fa(improved[i])
                    if any(chunk_norm.startswith(_normalize_fa(eq)) for eq in fa_equivs):
                        break  # already aligned

                    # Search for FA equivalent in full_fa near the boundary
                    preceding = ' '.join(improved[:i])
                    search_near = len(preceding)
                    fa_norm = _normalize_fa(full_fa)
                    for fa_eq in fa_equivs:
                        eq_norm = _normalize_fa(fa_eq)
                        lo = max(0, search_near - 15)
                        hi = search_near + 25
                        pos = fa_norm.find(eq_norm, lo)
                        if pos < 0 or pos > hi:
                            continue
                        # Map normalized pos to original
                        orig_pos = self._norm_to_orig(full_fa, pos)
                        if orig_pos is None:
                            continue
                        left  = full_fa[:orig_pos].rstrip()
                        right = full_fa[orig_pos:].lstrip()
                        if not left or not right or len(left) > MAX_CHARS:
                            continue
                        if not _normalize_fa(right).startswith(eq_norm):
                            continue
                        # Rebuild with new split
                        left_ch  = self._split_distinct(left, i)
                        right_ch = self._split_distinct(right, len(improved) - i)
                        if (all(len(c) <= MAX_CHARS for c in left_ch) and
                                all(len(c) <= MAX_CHARS for c in right_ch)):
                            improved = left_ch + right_ch
                        break
        return improved

    def _norm_to_orig(self, orig: str, norm_pos: int) -> int:
        """Map position in normalized text back to original."""
        n = 0
        for i, ch in enumerate(orig):
            if unicodedata.category(ch) in ('Mn', 'Me'):
                continue
            if n >= norm_pos:
                return i
            if ch in ' \t\n':
                if i + 1 < len(orig) and orig[i + 1] in ' \t\n':
                    continue
            n += 1
        return len(orig)

    # ── quality scoring ───────────────────────────────────────────────────────

    def _quality_score(self, rows: list, group: dict) -> int:
        """
        Score a row assignment 0–100.
        Lower score → more benefit from LLM re-split.
        """
        score   = 100
        nonempty = [r for r in rows if r.strip()]

        if not nonempty:
            return 100

        # Hard violation: any chunk over limit
        for r in rows:
            if len(r) > MAX_CHARS:
                score -= 50
                break

        # Compound verb split: chunk B starts with می‌/نمی‌
        for i in range(len(rows) - 1):
            b = rows[i + 1].strip()
            if b and any(b.startswith(pf) for pf in COMPOUND_PREFIXES):
                score -= 40
                break

        # «را» orphan at start of chunk
        for r in rows:
            if r.strip().startswith('را ') or r.strip() == 'را':
                score -= 20
                break

        # Triple with long chunk
        cnt: dict = {}
        for r in rows:
            cnt[r] = cnt.get(r, 0) + 1
        for ch, c in cnt.items():
            if c >= 3 and ch.strip() and len(ch) > TRIPLE_LIMIT:
                score -= 40
                break

        # Length imbalance
        lengths = [len(r) for r in nonempty]
        if len(lengths) >= 2:
            rng = max(lengths) - min(lengths)
            if rng > 35:
                score -= 25
            elif rng > 22:
                score -= 12

        # Low alignment score (EN↔FA correspondence)
        align = self._alignment_score(group['en_rows'], rows)
        if align < 0.3:
            score -= 20
        elif align < 0.5:
            score -= 8

        # Double ratio too high
        n_total   = len(rows)
        n_doubles = sum(max(0, c - 1) for c in cnt.values() if c >= 2)
        if n_total > 2 and n_doubles / n_total > 0.60:
            score -= 15

        return max(0, score)

    def _alignment_score(self, en_rows: list, fa_chunks: list) -> float:
        """Fast EN↔FA alignment confidence 0–1."""
        if not en_rows or not fa_chunks:
            return 0.5
        parts = []

        # Number match (digits)
        en_nums = set(re.findall(r'\d+', ' '.join(en_rows)))
        fa_text = ' '.join(fa_chunks)
        fa_nums_raw = re.findall(r'[\d۰-۹]+', fa_text)
        fa_nums = set()
        for n in fa_nums_raw:
            for fa_d, en_d in zip('۰۱۲۳۴۵۶۷۸۹', '0123456789'):
                n = n.replace(fa_d, en_d)
            fa_nums.add(n)
        if en_nums or fa_nums:
            shared = en_nums & fa_nums
            parts.append(0.3 * (len(shared) / max(len(en_nums | fa_nums), 1)))
        else:
            parts.append(0.15)

        # Discourse marker alignment
        matched = total = 0
        for i, en in enumerate(en_rows):
            if i >= len(fa_chunks):
                break
            en_lower = en.strip().lower()
            for cat in self._cues.values():
                for en_m, fa_list in cat.get('cues', {}).items():
                    if en_lower.startswith(en_m.lower()):
                        total += 1
                        chunk_norm = _normalize_fa(fa_chunks[i])
                        if any(chunk_norm.startswith(_normalize_fa(eq)) for eq in fa_list):
                            matched += 1
        if total:
            parts.append(0.3 * (matched / total))
        else:
            parts.append(0.15)

        # Length ratio FA/EN
        en_len = sum(len(r) for r in en_rows)
        fa_len = sum(len(c) for c in fa_chunks)
        if en_len and fa_len:
            ratio = fa_len / en_len
            parts.append(0.2 if 0.5 <= ratio <= 2.5 else 0.05)
        else:
            parts.append(0.1)

        parts.append(0.1)  # base
        return min(1.0, sum(parts))

    # ── LLM batch ─────────────────────────────────────────────────────────────

    def _llm_batch(self, candidates: list) -> dict:
        """
        Re-split low-quality groups via LLM.
        candidates: list of (group_idx, group, mech_rows)
        Returns: {group_idx: new_rows}
        """
        if not self.client or not candidates:
            return {}

        corrections = {}
        BATCH_SIZE  = 20

        for b_start in range(0, len(candidates), BATCH_SIZE):
            batch = candidates[b_start : b_start + BATCH_SIZE]

            payload = [
                {
                    'id':      local_i,
                    'n_rows':  grp['n_rows'],
                    'en_rows': grp['en_rows'],
                    'full_fa': grp['full_fa'],
                }
                for local_i, (_, grp, _) in enumerate(batch)
            ]

            user_msg   = json.dumps(payload, ensure_ascii=False)
            est_tokens = _estimate_tokens(self._SYSTEM_PROMPT + user_msg)

            # Hard budget check
            if self.tokens_used + est_tokens > self.token_budget:
                remaining = len(candidates) - b_start
                print(
                    f"[WARN] Aligner: token budget {self.token_budget} reached — "
                    f"{remaining} group(s) will keep mechanical result."
                )
                break

            try:
                t0   = time.time()
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {'role': 'system', 'content': self._SYSTEM_PROMPT},
                        {'role': 'user',   'content': user_msg},
                    ],
                    response_format={'type': 'json_object'},
                    temperature=0,
                    timeout=120,
                    extra_body={'prompt_cache_retention': '24h'},
                )
                elapsed          = time.time() - t0
                used             = resp.usage.total_tokens
                self.tokens_used += used
                print(
                    f"[INFO] Aligner LLM batch {b_start // BATCH_SIZE + 1}: "
                    f"{len(batch)} groups — {used} tokens — {elapsed:.1f}s"
                )

                parsed = json.loads(resp.choices[0].message.content)
                for item in parsed.get('results', []):
                    local_i = item.get('id')
                    if local_i is None or local_i >= len(batch):
                        continue
                    group_idx, grp, mech_rows = batch[local_i]
                    fa_rows   = item.get('fa_rows', [])
                    validated = self._validate(fa_rows, grp)
                    if validated:
                        corrections[group_idx] = validated
                    else:
                        print(
                            f"[WARN] Aligner: LLM output for group {group_idx} "
                            f"failed validation — keeping mechanical."
                        )

            except Exception as e:
                print(
                    f"[ERROR] Aligner LLM batch {b_start // BATCH_SIZE + 1} "
                    f"failed: {e} — keeping mechanical for this batch."
                )

        return corrections

    def _validate(self, fa_rows: list, group: dict) -> list:
        """Validate LLM output. Returns rows list or None if invalid."""
        n = group['n_rows']
        if not isinstance(fa_rows, list) or len(fa_rows) != n:
            return None
        for ch in fa_rows:
            if not isinstance(ch, str) or len(ch) > MAX_CHARS:
                return None
        # Triple rule: triple allowed only if each copy ≤ TRIPLE_LIMIT
        cnt: dict = {}
        for ch in fa_rows:
            cnt[ch] = cnt.get(ch, 0) + 1
        for ch, c in cnt.items():
            if c >= 3 and ch.strip() and len(ch) > TRIPLE_LIMIT:
                return None
        # Text preservation (normalized join must match full_fa)
        joined = ' '.join(ch for ch in fa_rows if ch.strip())
        if _normalize_text(joined) != _normalize_text(group['full_fa']):
            return None
        return fa_rows

    # ── main entry point ──────────────────────────────────────────────────────

    def align(self, input_docx: str, output_docx: str) -> dict:
        """
        Full pipeline: read → mechanical → score → LLM → write.
        Returns stats dict.
        """
        self.tokens_used = 0
        t0 = time.time()

        rows   = self._read_rows(input_docx)
        groups = self._parse_groups(rows)
        print(f"[INFO] Aligner: {len(groups)} sentence groups parsed")

        # Pass 1 — mechanical
        mech_all = [self._mechanical_align(g) for g in groups]

        # Pass 2 — score
        scores = [
            self._quality_score(rows_out, grp)
            for rows_out, grp in zip(mech_all, groups)
        ]
        needs_llm = [
            (i, groups[i], mech_all[i])
            for i, s in enumerate(scores)
            if s < self.llm_threshold
        ]
        print(
            f"[INFO] Aligner: {len(needs_llm)}/{len(groups)} groups "
            f"below threshold {self.llm_threshold} → LLM"
        )

        # Pass 3 — LLM batch (with budget guard)
        corrections = self._llm_batch(needs_llm)

        # Merge
        final_chunks = list(mech_all)
        for idx, corrected in corrections.items():
            final_chunks[idx] = corrected

        # Write
        self._write_docx(input_docx, output_docx, groups, final_chunks)

        elapsed = time.time() - t0

        # Stats
        all_rows  = [r for fc in final_chunks for r in fc]
        n_total   = len(all_rows)
        cnt_all: dict = {}
        for r in all_rows:
            cnt_all[r.strip()] = cnt_all.get(r.strip(), 0) + 1
        n_doubles = sum(max(0, c - 1) for k, c in cnt_all.items() if k and c >= 2)
        n_triples = sum(max(0, c - 2) for k, c in cnt_all.items() if k and c >= 3)
        n_over    = sum(1 for r in all_rows if len(r) > MAX_CHARS)

        self.last_stats = {
            'groups':          len(groups),
            'llm_corrected':   len(corrections),
            'mechanical_only': len(groups) - len(corrections),
            'tokens_used':     self.tokens_used,
            'total_rows':      n_total,
            'doubles':         n_doubles,
            'triples':         n_triples,
            'over_limit':      n_over,
            'elapsed_seconds': round(elapsed, 1),
        }

        print(
            f"[INFO] Aligner done in {elapsed:.1f}s — "
            f"groups: {len(groups)} | LLM: {len(corrections)} | "
            f"tokens: {self.tokens_used} | "
            f"doubles: {n_doubles} | triples: {n_triples} | "
            f"over-{MAX_CHARS}: {n_over}"
        )
        return self.last_stats
