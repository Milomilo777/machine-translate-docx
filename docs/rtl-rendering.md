# RTL Rendering in python-docx — Best Practice

> Research-only summary backing the implementation in `aligner_per.py`.
> Sources:
> [python-docx issue #1411 — w:bidi workaround](https://github.com/python-openxml/python-docx/issues/1411),
> [python-docx issue #387 — RTL in headers](https://github.com/python-openxml/python-docx/issues/387),
> [W3C — Internationalization Best Practices](https://www.w3.org/International/geo/html-tech/tech-bidi.html),
> [W3C — Bidirectional Algorithm basics](https://www.w3.org/International/articles/inline-bidi-markup/uba-basics).

---

## Why RTL has to be set explicitly in python-docx

`python-docx` does not surface RTL paragraph or run properties through
its public API. Until upstream adds support, the project must reach into
the underlying CT_P / CT_R XML elements directly. This is the documented
workaround pattern repeated by maintainers and users in issues #1411
and #387.

## What is required for Persian to render correctly in Word

Two distinct OOXML markers must be present on every paragraph that holds
Persian text:

| XML | Where | What it does |
|-----|-------|--------------|
| `<w:bidi/>` inside `<w:pPr>` | paragraph | Sets the paragraph's text direction to RTL — line wrapping, alignment, marker placement all flip |
| `<w:rtl/>` inside `<w:rPr>` | run | Sets the run's character direction; without it, English-mixed runs may keep LTR glyph order even inside an RTL paragraph |

Either marker alone is **not sufficient**. Without `w:bidi`, the
paragraph's right-anchor / line-direction is still LTR. Without `w:rtl`
on the run, the glyph order can be wrong inside that run.

## Two ways to add the markers

### Manual (older code, fragile)

```python
pPr = p._p.find(qn('w:pPr'))
if pPr is None:
    pPr = OxmlElement('w:pPr')
    p._p.insert(0, pPr)
pPr.append(OxmlElement('w:bidi'))
```

This was the form used by E10's Phase 1 fix. It works but:

- Hand-managed `insert(0)` may insert pPr at the wrong position
  relative to other paragraph elements in some templates.
- Doesn't benefit from python-docx's already-correct schema-aware
  insertion logic.

### Built-in (current — Phase recommended)

```python
pPr = p._p.get_or_add_pPr()
if pPr.find(qn('w:bidi')) is None:
    pPr.append(OxmlElement('w:bidi'))
```

`get_or_add_pPr` is a python-docx-internal helper that creates the
property element in the schema-correct position if missing and
returns the existing one otherwise. The same applies to
`get_or_add_rPr` on the run. This is the form referenced in
maintainer comments on issue #1411 and is what `aligner_per.py` now
uses.

## Why we don't use `python-bidi` / `arabic-reshaper`

Those libraries pre-process the *characters themselves* (reordering /
reshaping glyphs at the text-string level) for renderers like ReportLab
that lack a real bidi engine. Word has its own bidi engine — it just
needs the markers above to know the text is RTL. Pre-reshaping the
characters before writing to a `.docx` cell would actively corrupt the
text once Word applied its own bidi pass.

## Verification

After alignment runs, the FA cells in the output `.docx` must each
contain (somewhere in `word/document.xml`):

```xml
<w:p>
  <w:pPr><w:bidi/>...</w:pPr>
  <w:r>
    <w:rPr><w:rtl/>...</w:rPr>
    <w:t>...</w:t>
  </w:r>
</w:p>
```

A regression test that unzips the output `.docx` and greps the FA
cells is straightforward to add when needed; for now we rely on
visual verification + the regression test entry in `error-catalog.md`
for E10.

## Idempotency

Both helpers (`_ensure_rtl_paragraph`, `_ensure_rtl_run`) check for the
marker first and add it only when missing — calling them on a cell
that already has the markers is a no-op.
