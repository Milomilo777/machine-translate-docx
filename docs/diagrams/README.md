# Architecture diagrams

The repository ships three hand-coded SVG diagrams, each in a
light + dark theme variant. The variants pair up via a `<picture>`
block in the project [`README.md`](../../README.md) so the right one
fires automatically on GitHub depending on the visitor's preferred
theme.

| Diagram | Light | Dark | Used in |
|---|---|---|---|
| High-level architecture | [`architecture-light.svg`](architecture-light.svg) | [`architecture-dark.svg`](architecture-dark.svg) | top of `README.md` |
| Translation pipeline workflow | [`pipeline-light.svg`](pipeline-light.svg) | [`pipeline-dark.svg`](pipeline-dark.svg) | `README.md` + [`docs/architecture.md`](../architecture.md) |
| Failure path (alerts + archive) | [`failure-path-light.svg`](failure-path-light.svg) | [`failure-path-dark.svg`](failure-path-dark.svg) | [`docs/telegram-alerts-setup.md`](../telegram-alerts-setup.md) |

## How they were drawn

Each SVG is hand-coded — no Figma / Inkscape round-trip needed. They
all share the project's warm Anthropic-inspired palette:

| Role | Light | Dark |
|---|---|---|
| Background | `#FAF9F5` | `#1B1A17` |
| Card fill | `#FFFFFF` | `#26241F` |
| Card border | `#E8E4D9` | `#34312A` |
| Accent (clay) | `#D97757` | `#E08A6E` |
| Failure accent | `#B5613E` | `#E89878` |
| Heading ink | `#1F1E1B` | `#F4F2EC` |
| Body ink | `#3F3E3A` | `#D8D5CC` |
| Muted ink | `#6E6C66` | `#A4A199` |

Each `<svg>` carries a `<title>` and a `<desc>` so screen readers
get a one-paragraph plaintext summary. The `aria-labelledby` on
the root `<svg>` points at both ids.

The dark variants are mechanically generated from the light ones
by a colour-swap pass (see the inline Python snippet in the
session's CHANGES entry); editing one and re-running the swap
keeps the pair in sync.

## How to edit

1. Open the `*-light.svg` in any text editor (or an SVG editor like
   Inkscape — the file is plain XML).
2. Save it.
3. Run the palette swap in the repo root:

   ```python
   src = open('docs/diagrams/X-light.svg', encoding='utf-8').read()
   swap = {  # light → dark
       '#FAF9F5': '#1B1A17',
       '#FFFFFF': '#26241F',
       '#E8E4D9': '#34312A',
       '#FBEFE9': '#3A2A22',
       '#E4A382': '#C46847',
       '#F4F2EC': '#2C2A24',
       '#D8D3C5': '#45413A',
       '#1F1E1B': '#F4F2EC',
       '#3F3E3A': '#D8D5CC',
       '#6E6C66': '#A4A199',
       '#D97757': '#E08A6E',
       '#B5613E': '#E89878',
   }
   for k in sorted(swap, key=len, reverse=True):
       src = src.replace(k, swap[k])
   open('docs/diagrams/X-dark.svg', 'w', encoding='utf-8').write(src)
   ```

4. Commit both files together. The diff lives in the light variant;
   the dark one is mechanical.

## Embedding rule (for documentation files)

Always use a `<picture>` block so the visitor's theme is respected:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/diagrams/X-dark.svg">
  <img alt="…descriptive alt text…" src="docs/diagrams/X-light.svg">
</picture>
```

GitHub renders this natively on both Markdown and the README.
Always include a meaningful `alt` — every diagram has its full
`<desc>` available too, so prefer a short caption in `alt` and let
screen readers fall through to the SVG's own description.
