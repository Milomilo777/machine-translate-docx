"""
tests/test_aligner_only.py — Standalone aligner test runner
=============================================================
Lets you iterate on the aligner without re-translating.

Usage
-----
# Run on a translated DOCX (e.g. a *_PER_TranslatePolish.docx):
    python tests/test_aligner_only.py path/to/file_PER_TranslatePolish.docx

# Explicit output path (optional):
    python tests/test_aligner_only.py input.docx --output my_test.docx

# Inspect per-group stats:
    python tests/test_aligner_only.py input.docx --verbose

The output file is written next to the input as:
    {stem}_Double_TEST.docx
(never overwrites the real _PER_Double.docx)

Exit codes
----------
    0  — success, zero triples, zero over-48 chars
    1  — triples or over-limit found (print tells you how many)
    2  — usage error / file not found
"""

import sys
import os
import argparse
import textwrap

# Allow running from the project root or from tests/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_PROJ_ROOT, 'src'), _PROJ_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from machine_translate_docx.openai_tools.aligner_per import FASubtitleAligner   # noqa: E402


def _default_output(input_path: str) -> str:
    stem, _ = os.path.splitext(input_path)
    # e.g.  file_PER_TranslatePolish.docx  → file_PER_TranslatePolish_Double_TEST.docx
    # (keeps it clearly separate from the production _PER_Double.docx)
    return stem + '_Double_TEST.docx'


def main():
    parser = argparse.ArgumentParser(
        description='Run the FA subtitle aligner on a translated DOCX without the full pipeline.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python tests/test_aligner_only.py MyShow_PER_TranslatePolish.docx
              python tests/test_aligner_only.py input.docx --output out.docx --verbose
        """),
    )
    parser.add_argument('input', help='Path to translated DOCX (*_PER_TranslatePolish.docx)')
    parser.add_argument('--output', '-o', default=None, help='Output path (default: <input>_Double_TEST.docx)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Print per-group breakdown (doubles/triples/over-limit)')
    args = parser.parse_args()

    inp = os.path.abspath(args.input)
    if not os.path.isfile(inp):
        print(f"ERROR: File not found: {inp}", file=sys.stderr)
        sys.exit(2)

    out = os.path.abspath(args.output) if args.output else _default_output(inp)

    print(f"Input:  {inp}")
    print(f"Output: {out}")
    print()

    aligner = FASubtitleAligner(model='gpt-5.4-mini', llm_threshold=0)

    if args.verbose:
        # Monkey-patch to print per-group info
        _orig = aligner._align_group

        def _verbose_align(group):
            result = _orig(group)
            n_rows = len(group['row_indices'])
            doubles = sum(1 for i in range(1, len(result)) if result[i] == result[i-1] and result[i])
            triples = sum(1 for i in range(2, len(result))
                          if result[i] == result[i-1] == result[i-2] and result[i])
            over = sum(1 for r in result if r and len(r.replace('‌', '')) > 48)
            fa_preview = ' '.join(group['fa_parts'])[:40] + ('…' if len(' '.join(group['fa_parts'])) > 40 else '')
            print(f"  group rows={n_rows:2d} | doubles={doubles} | triples={triples} | over48={over} | «{fa_preview}»")
            return result

        aligner._align_group = _verbose_align
        print("Per-group breakdown:")
        print("-" * 72)

    stats = aligner.align(inp, out)

    if args.verbose:
        print("-" * 72)
        print()

    # ── summary ────────────────────────────────────────────────────────────────
    print("=" * 56)
    print(f"  Groups           : {stats['groups']}")
    print(f"  Total rows       : {stats['total_rows']}")
    doubles_pct = (stats['doubles'] / stats['total_rows'] * 100) if stats['total_rows'] else 0
    print(f"  Double rows      : {stats['doubles']}  ({doubles_pct:.1f}%)")
    print(f"  Triple rows      : {stats['triples']}  {'✓' if stats['triples'] == 0 else '✗  ← BAD'}")
    print(f"  Over-48 chunks   : {stats['over_limit']}  {'✓' if stats['over_limit'] == 0 else '✗  ← BAD'}")
    print(f"  Elapsed          : {stats['elapsed_seconds']} s")
    print("=" * 56)

    if stats['triples'] == 0 and stats['over_limit'] == 0:
        print(f"\nOK — output saved to:\n  {out}")
        sys.exit(0)
    else:
        msg = []
        if stats['triples'] > 0:
            msg.append(f"{stats['triples']} triple(s)")
        if stats['over_limit'] > 0:
            msg.append(f"{stats['over_limit']} over-48 chunk(s)")
        print(f"\nWARNING: {', '.join(msg)} found — output saved anyway:\n  {out}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
