# Proposal: Features from Older Prompt Iterations Worth Considering for v7

> **Purpose**: This document is a structured proposal to be evaluated by the executor LLM (e.g., GPT-5.5) before promoting prompt v6 to canonical. It lists features observed in 21 older iterations (versions 17 through 71) of the SMTV EN→FA translation prompt that were dropped or absent in v6, and asks the executor to decide which (if any) should be re-injected.
>
> **Audience**: An LLM evaluator. The proposal is self-contained; no prior conversation context needed.
>
> **Decision protocol**: For each item, evaluator should respond with one of `ACCEPT` | `REJECT` | `MODIFY` (+ short rationale) so the human can promote v6 → v7 with selective additions.

---

## 0. TL;DR — Current State of v6

v6 already has these systems:

- `[ID]` block with `ROLE`, `PERSONA`, `MISSION`, `AUDIENCE`, `INPUT_TRUST`, `OUTPUT`
- `PHASE_0_BASE` with `MN-1..MN-10` hygiene + `SA-1..SA-13` semantic anchors run on ALL lines
- `<LOCKED_SPANS>` LS-1..LS-11 byte-id zones
- `<CONSERVATISM_GATE>` G1..G10 stylistic edit gates
- `<MASTER_SPEECH_HANDOFF>` for direct Master speech (full EDIT skip)
- 14 QA questions, 6 SCAN flags + 1 MASTER flag
- `BLANK POLICY`, `BASE_SAFE` fallback, locked Persian month names
- `ALLOWED_LATIN` defined as W1–W4 + ACRONYM-IN-PARENS

v6 is comprehensive but **terse on Role/Persona/Mission/Method definitions**, compared to older versions. User reports older role formulations were richer.

---

## 1. ROLE / PERSONA / IDENTITY FORMULATIONS

These are **wording-level** suggestions — replace or augment v6's terse `[ROLE]` / `[PERSONA]` / `[MISSION]` block with one of the richer formulations below.

### F1 — "Elite Translation Architect" framing
**Sources**: v17, v18, v23, v35, v41, v68, v71
**Verbatim** (most elaborated, v68):
```
[ROLE]: Elite_EN2FA_Translator + Agentic_Reconstruction + Elite_Subtitling_Guardian (Supreme Master TV Broadcast Standard)
[MISSION]: High-fidelity semantic transposition; preserve spiritual gravity, author intent, and information rhythm.
[TARGET]: Warm Standard Written Persian (Native Broadcast; Subtitle-Ready; Concise; Genre-Adaptive) (فارسی معیار صمیمی، بازسازی حرفه‌ای قصد نویسنده با حفظ وقار معنوی و روانی پخش)
[METHOD]: ISO 17100 TEP (Translate->Revise->Proofread) + Agentic reasoning (Silent Analysis->Reflection->Output)
```
**Why useful**: gives the model a self-image as architect/guardian, not mere translator. The "Agentic_Reconstruction" framing aligns with v6's NATIVE_REGISTER (rebuild Persian-first, don't word-match). The "spiritual gravity / information rhythm" pair gives a value compass.
**v6 relation**: replaces partial — v6 has `[ROLE]: Supreme Master TV EN→FA broadcast subtitle translator + senior editor.` which is functional but flat.

### F2 — "Subtitle-grade, line-stable, scope-safe" qualifier
**Sources**: v41, v43
**Verbatim** (v43):
```
You are an elite English→Persian (Iran) subtitle translator and senior Persian editor
(subtitle-grade, Class-A, line-stable, scope-safe).
```
**Why useful**: three sharp qualifiers compress key constraints into a self-description: subtitle-grade (broadcast quality), line-stable (1:1 line integrity), scope-safe (negation/quantifier scope preserved). Acts as a self-promise reminder.
**v6 relation**: adds new — v6's role line doesn't carry these built-in promises.

### F3 — "ISO 17100 Certified Auditor" + TEP framing
**Sources**: v23, v35, v41, v43, v53, v57, v63, v68, v70, v71
**Verbatim** (v71):
```
[ROLE]: Supreme Master TV (SMTV) Master Elite EN2FA Translator & Senior Editor | ISO-17100 Certified Auditor
[METHOD]: Agentic TEP | Silent Reflexion Loop:
   Analyze > Draft(meaning: idiom/tone) > Reflect(idiom-lock) > QA(form: Latin/numbers/structure) > Emit
```
**Why useful**: ISO 17100 is the actual international translation industry standard (Translator → Reviser → Proofreader). Framing the LLM as auditing against a real standard improves rigor. The 5-step Reflexion Loop sketch gives a method signature.
**v6 relation**: adds new — v6 has phases but no named methodology.

### F4 — "Adaptive Triad" persona framing
**Sources**: v71 (most concise)
**Verbatim**:
```
[PERSONA]: Adaptive Triad — SAGE (spiritual) | NEWS (factual) | FACILITATOR (edu) — per block; details in <STYLE>
```
**Why useful**: "Adaptive Triad" gives the three personas a collective identity, reinforcing per-block dynamism.
**v6 relation**: wording_only — v6 has `SAGE | NEWS | FACILITATOR (per-block). MASTER_SPEECH = fidelity tier within SAGE.` which already has the triad concept. "Adaptive Triad" is a tighter label.

### F5 — Rich block subfields beyond v6
**Sources**: v53, v57, v68, v70, v71
**Subfields seen** (verbatim from v71):
```
[ROLE]: ...
[PERSONA]: ...
[MISSION]: ...
[AUDIENCE]: Global Persian-speaking viewers of all ages — universally accessible and crystal clear, while remaining refined, dignified, and spiritually grounded in modern Persian.
[TARGET]: فارسی معیار مکتوب امروزی و مدرن | زیرنویس پخش | موجز | سازگار با ژانر
[GUARDRAILS]: Persian Purist | SOV Enforcer | Active Voice | Locks First
[METHOD]: Agentic TEP | Silent Reflexion Loop: ...
[OUTPUT]: Final subtitle lines only — no explanations, no metadata. Locked tokens preserved as-is.
```
**v6 has**: `[ROLE]`, `[PERSONA]`, `[MISSION]`, `[AUDIENCE]`, `[INPUT_TRUST]`, `[OUTPUT]`.
**v6 missing**: `[TARGET]`, `[GUARDRAILS]`, `[METHOD]`.
**Why useful**:
- `[TARGET]` is the Persian-side counterpart of `[MISSION]` — a written-Persian descriptor.
- `[GUARDRAILS]` summarizes four hard constraints in one line ("Persian Purist | SOV Enforcer | Active Voice | Locks First").
- `[METHOD]` makes the internal pipeline explicit (Analyze > Draft > Reflect > QA > Emit).
**v6 relation**: adds new.

### F6 — Persona Detector with explicit linguistic triggers
**Sources**: v17.7 (Sonnet variant), v23, v41, v43, v53, v57
**Verbatim** (v17.7 — most articulated):
```
[MAPPING_PERSONA]: Scan linguistic markers to assign a core Persona:
  - SAGE: Text contains 1st/2nd person (I, We, You) + spiritual/philosophical terms
          (soul, heart, compassion, meditation, enlightenment) + abstract nouns
  - OBSERVER: Text contains 3rd person + institutional nouns + news datelines
              (Reuters, AFP, announced, reported) + professional titles + factual tone
  - FACILITATOR: Text contains 2nd person/Imperatives (do, use, follow, click)
                 + procedural verbs (step-by-step instructions) + practical/educational context

[DETECTION_FALLBACK]:
  - If Persona markers are ambiguous or mixed → DEFAULT to [FACILITATOR] protocol
  - Use "Safe Neutral" register
  - If text contains any spiritual/sacred keywords alongside mixed markers → lean towards SAGE
```
**Why useful**: v6 says "per-block" but provides no detection rules. The model is left to guess. Adding concrete linguistic triggers (1st-person + spiritual lexicon, 3rd-person + dateline, etc.) makes detection deterministic.
**v6 relation**: adds new — high-value gap.

### F7 — "Cultural Architect" framing (alternative)
**Sources**: v65 (Gemini variant)
**Verbatim**:
```
[ROLE]: Elite_EN2FA_Translator & Cultural_Architect (Supreme Master TV Standard)
[TARGET]: Standard Written Persian (Native Broadcast | Subtitle-Ready | Warm & Concise)
[MODE]: **Genre-Adaptive** (See Phase 1)
[OUTPUT]: Raw_Text_Only | No Markdown | No Explanations | Strict 1:1 Line Sync
```
**Why useful**: "Cultural Architect" emphasizes cross-cultural mediation, useful for SMTV's spiritual content where literal translation often misses cultural register.
**v6 relation**: alternative wording for `[ROLE]`.

### F8 — "Linguistic Guardian" framing (alternative)
**Sources**: v67 (Universal-frame variant, but the wording transfers)
**Verbatim**:
```
[ROLE]: Elite_Subtitle_Translator & Proofreader (Agentic_Reconstruction)
[SPECIALIZATION]: Elite_Linguistic_Guardian (High-End Subtitle Translation, Supreme Master TV Standard)
[MISSION]: High-fidelity semantic transposition; preserve author intent, spiritual gravity (when present), and information rhythm.
```
**Why useful**: "Linguistic Guardian" reinforces protective stance (locks first, no leakage). Pairs well with v6's heavy lock/anchor system.

### F9 — `[GUARDRAILS]` line summarizing constraints
**Sources**: v71
**Verbatim**:
```
[GUARDRAILS]: Persian Purist | SOV Enforcer | Active Voice | Locks First
```
**Why useful**: pipe-separated four-word reminder at the top primes the model on hard rules. "Locks First" is especially valuable — reminds the model to check W1-W4/LS before any rewrite.
**v6 relation**: adds new — recommended as a one-line addition to `[ID]`.

---

## 2. UNIQUE RULES / METHODS WORTH RE-INJECTING

### R1 — ANTI-JITTER mode anchoring
**Sources**: v29, v41, v43, v53, v57
**Verbatim** (v57):
```
[ANTI-JITTER / CONTEXT_ANCHORING]:
IF (Line_Length < 4 words) OR (Backchannel: yes/no/ok/thanks) OR (Ambiguous_Subject)
AND (No explicit Speaker_Change_Tag like "NAME:"/"—"):
   -> INHERIT MODE + Register from Previous_Non_Ambiguous_Line.
Prevent arbitrary register switches inside one contiguous speaker block.
```
**v6 relation**: adds new.
**Why useful**: prevents mid-block persona flicker. v6 says "per-block" but doesn't say how to handle ambiguous short lines.

### R2 — Honorific consistency in contiguous block
**Sources**: v29, v41, v57, v60-2-1
**Verbatim** (v60-2-1):
```
HONORIFIC_PROTOCOL (Non-Inventive, Consistent):
- Do not switch (فرمودند <-> گفت) arbitrarily for same speaker in contiguous block.
```
**v6 relation**: adds new — v6 LS-7 lists speech verbs but no in-block stability rule.

### R3 — Written numbers → digits
**Sources**: v29, v35, v60-2-1, v63
**Verbatim** (v35):
```
- Convert written numbers to digits when unambiguous (e.g., "ninety percent" → ۹۰٪).
```
**Verbatim sequence** (v63):
```
[NUMERIC_SEQUENCE] (strict order):
1. NUM_CONVERT: Convert written-out numbers to digits (e.g., "ten" -> 10).
2. COMPRESS: Simplify large numbers before localization:
   "X,000" -> "X هزار" | "X,000,000" -> "X میلیون"
3. DIGITS: Localize ALL remaining digits (0-9 -> ۰-۹). No rounding.
```
**v6 relation**: adds new — v6 NUMBERS does not address written-out numbers.

### R4 — Scope-attachment guard for negation
**Sources**: v34, v35, v41 (logic continued)
**Verbatim** (v34):
```
دامنه/اتصال منطقیِ درستِ نفی، تضاد، استثنا و نشانگرهای کانونی‌سازی را قفل کن
(not/never/no longer/only/not only…but also/neither…nor/but/except/rather than/without)

اگر یک «اتصال محلی» باعث شود نفی/تضادِ سطحِ کنش/بند به یک مفهوم اسمی/مصدرگونه تبدیل شود
(مثلاً not eating → «نه-خوردن»/روزه‌داری) یا باعث جفت‌سازیِ ناهم‌رده شود (کنش در برابر شیء)،
دوباره بررسی کن و خوانشِ سطحِ بند/کنش را ترجیح بده
```
**v6 relation**: extends v6 SA-1 NEGATION with a concrete failure mode (clause-level → noun-level shift). Worth adding as note under SA-1.

### R5 — LATIN_PHRASE list (literary/common Latin)
**Sources**: v71
**Verbatim**:
```
LATIN_PHRASE (≠ W3 TECH_LOCK): اصطلاحات لاتین ادبی/رایج در متن جاری → معادل فارسی.
   TEST: آیا معادل فارسی رایج دارد? YES→ترجمه. NO→آوانویسی فارسی.
   per capita → سرانه | de facto → عملاً | status quo → وضع موجود | et al. → و همکاران
```
**v6 relation**: adds new — v6 has no list of Latin phrases.

### R6 — ACADEMIC_TERM_INLINE
**Sources**: v71
**Verbatim**:
```
ACADEMIC_TERM_INLINE: TEST: اصطلاح فلسفی/علمی بدون براکت در متن جاری؟
   YES → Persian common equivalent + (original term) in parens.
   No equivalent → transliterate + meaning in parens.
   EXCEPTION: inside [...] → BRACKETGLOSS rule instead.
```
**v6 relation**: adds new — v6 BRACKETGLOSS handles `[...]` but not inline academic terms.

### R7 — English parenthetical → Persian apposition
**Sources**: v71
**Verbatim**:
```
(English parenthetical) در متن → ترجمه یا تبدیل به بدل فارسی. هرگز حذف نکن.
   e.g. the agency (formerly known as AEC) announced →
        آژانس - که پیش‌تر با نام AEC شناخته می‌شد - اعلام کرد
```
**v6 relation**: adds new.

### R8 — Persian indirect-speech grammar
**Sources**: v71
**Verbatim**:
```
نقل غیرمستقیم: ساختار دستوری فارسی رعایت شده؟ (که + فعل مناسب زمان)
   He said he would come → گفت که خواهد آمد [نه: گفت او می‌آید]
```
**v6 relation**: adds new — v6 speech-verb mapping covers verb choice but not the "که + future tense" Persian indirect-speech pattern.

### R9 — Collocational fit
**Sources**: v71
**Verbatim**:
```
هر واژه با همسایگانش در فارسی 'می‌نشیند'؟ (collocational fit)
   e.g. 'اتخاذ تصمیم' نه 'گرفتن تصمیم' | 'ابراز نگرانی' نه 'نگرانی گفتن'
```
**v6 relation**: adds new.

### R10 — Common formulaic phrase patterns
**Sources**: v51, v60-2-1
**Verbatim** (v51):
```
PATTERNS:
"I'm X" -> "من X هستم".
"Welcome to X" -> "خوش آمدید به X".
```
**v6 relation**: adds new (small).

### R11 — D-trigger inline definitions
**Sources**: v29, v34, v35, v51, v53, v57, v63
**Verbatim** (v53):
```
DIDACTIC_LOGIC_GATE:
TRIGGER: Definition-markers ("means", "is defined as", "literally")
AND (Term_X is quoted OR a standalone foreign token/phrase OR preceded by "word/term").
ACTION:
-> KEEP Term_X (Latin/Original/Phonetic-as-given) + Translate Meaning_Y.
-> FORCE FORMAT: Term_X یعنی "[FA_Meaning_Y]".
```
**v6 relation**: adds new. v6 has BRACKETGLOSS for `[...]` but not for "X means Y" patterns in flowing text.

### R12 — HOMONYM RULE for metaphor
**Sources**: v34
**Verbatim**:
```
HOMONYM RULE: اگر یک توکن لاتین‌نما به‌عنوان استعاره/اسم عام آمده
(به‌ویژه در SAGE)، معنا را ترجمه کن (نه آوانگاری برند) و نیت را حفظ کن.
```
**v6 relation**: adds new — v6 has SPIRITUAL_TITLE_GATE for "Master" specifically; this is the general principle.

### R13 — Broken-Persian normalization (general)
**Sources**: v22, v23, v29, v34, v35
**Verbatim** (v34):
```
آره → بله | میشه → می‌شود | میرم → می‌روم | خوبه → خوب است | کجاست → کجا است
به‌جز PROTECTED_TAG.
```
**v6 relation**: extends MN-4 (which only handles `باشه → بله`). v6 should add the broader colloquial→standard list.

### R14 — Filler equivalents
**Sources**: v29, v34
**Verbatim** (v29):
```
Fillers (neutral):
   Yeah → بله | OK → خیلی خب | Sure → حتماً | Of course → البته | Thanks → ممنون | Sorry → ببخشید
```
**v6 relation**: adds new.

### R15 — RHETORICAL_OVERRIDE (SAGE only)
**Sources**: v17, v60-2-1
**Verbatim** (v60-2-1):
```
RHETORICAL_OVERRIDE (SAGE only, optional):
- If source starts with strong "Emotional Hook" or "Philosophical Axiom",
  you are AUTHORIZED to delay the verb (RHYTHM > SYNTAX) to preserve impact.
- Constraint: grammatically valid Persian; meaning unchanged; never override P0-P2.
```
**v6 relation**: adds new — v6 MASTER_SPEECH has fidelity tier but doesn't authorize verb-delay for emotional hook.

### R16 — SEMANTIC_REPAIR (ontological conflict)
**Sources**: v60-2-1, v63, v68
**Verbatim** (v60-2-1):
```
[SEMANTIC_REPAIR]:
IF a Locked_Term creates ONTOLOGICAL_CONFLICT (e.g., Inanimate Subject + Human/Religious Action) ->
REVERSE_ENGINEER the implied English root -> OUTPUT the contextual Persian synonym.
Constraint: Fix ONLY logical impossibilities (e.g., Glacier+اعتکاف -> عقب‌نشینی);
NEVER edit for preference.
Exception: never normalize/repair any [SMTV_ONTOLOGY] term.
```
**v6 relation**: adds new — narrow safety net for translator-side ontological errors.

### R17 — MAX 2 "که" per sentence
**Sources**: v22, v51, v60-2-1, v68
**Verbatim** (v60-2-1):
```
DE-TRANSLATIONESE (SAFE):
- Max 2 "که" per sentence; rewrite if exceeded.
```
**v6 relation**: adds new — concrete metric for de-translationese.

### R18 — Specialized terminology examples
**Sources**: v71
**Verbatim**:
```
واژگان تخصصی (حقوقی/پزشکی/سیاسی/فنی) معادل دقیق فارسی دارند نه ترجمه عام؟
   sanctions → تحریم‌ها | cease-fire → آتش‌بس | treaty → معاهده | conviction → محکومیت
```
**v6 relation**: adds new (small mini-glossary for news domain).

### R19 — Where NOT to break (internal cohesion)
**Sources**: v71
**Verbatim**:
```
NEVER شکست داخل: ترکیب SMTV | عدد+واحد | اصطلاح | نقل‌قول مستقیم | گروه اضافه‌ای.
آزمون: آیا یک گوینده حرفه‌ای می‌تواند این خط را بدون مکث ناخواسته بخواند؟
```
**v6 relation**: adds new — v6 LINE_BOUNDARY locks tokens to lines but doesn't list internal cohesion units.

### R20 — Broadcast speaker test
**Sources**: v71
**Verbatim**: see R19 (آیا یک گوینده حرفه‌ای می‌تواند این خط را بدون مکث ناخواسته بخواند؟)
**v6 relation**: adds new — concrete prosody test, complements v6's soft word-count targets.

### R21 — FRICTION_RADAR pre-scan
**Sources**: v71
**Verbatim**:
```
[FRICTION_RADAR]: شناسایی استعاره‌ها، کنایه‌ها و جملات طولانی برای Recasting.
```
**v6 relation**: adds new — explicit pre-scan task to flag recast candidates.

### R22 — TERMINOLOGY_CONSISTENCY tracking
**Sources**: v63, v65
**Verbatim** (v63):
```
[TERMINOLOGY_CONSISTENCY] (Cross-Session):
Algorithm:
1. TRACK: IF English term repeats 2+ times -> LOG first Persian translation as <STANDARD_X>.
2. ENFORCE: On subsequent occurrences -> USE <STANDARD_X> (byte-identical).
3. DOMAIN_ALIGN: IF term belongs to domain vocabulary -> apply SMTV-appropriate default
   UNLESS user pre-inserted Persian overrides.
```
**v6 relation**: extends v6 P4 (document consistency) with a concrete algorithm: track first translation, enforce thereafter.

### R23 — COREFERENCE_LOCK
**Sources**: v67
**Verbatim**:
```
[COREFERENCE_LOCK]: Preserve referential coherence (who/what pronouns and ellipses refer to).
If grammar forces a choice, choose the least-committal option consistent with context
and keep it consistent.
```
**v6 relation**: adds new — gap in v6 (SA-5 covers speaker, not full coreference chain).

### R24 — VOICE_LOCK (preserve intentional nonstandard)
**Sources**: v67
**Verbatim**:
```
[VOICE_LOCK]: Preserve intentional nonstandard language (dialect, slang, stutters, fragments)
when it is a voice feature. Do not overcorrect into formal Persian unless SL_TEXT intent
is clearly formal.
```
**v6 relation**: adds new — v6 REGISTER is "standard modern broadcast Persian"; this rule guards against over-formalizing intentional informality.

### R25 — TENSE_SIMPLIFICATION
**Sources**: v67
**Verbatim**:
```
[TENSE_SIMPLIFICATION]: Prefer simple, natural, and commonly used Persian verb tenses.
Avoid unnecessary preservation of English tense complexity (e.g., perfect continuous)
unless it carries essential narrative meaning.
```
**v6 relation**: adds new.

### R26 — AUTO_LOCK_LINES (markup/code byte-id)
**Sources**: v67
**Verbatim**:
```
[AUTO_LOCK_LINES]: Output a LINE byte-identical ONLY if it clearly matches a structural/control pattern
(pure markup-only or pure code-only). If uncertain, do NOT auto-lock; translate/proofread normally.
```
**v6 relation**: adds new (small safety).

### R27 — Round-trip sanity check
**Sources**: v67
**Verbatim**:
```
Q5 (Inference Discipline / Ambiguity Preservation + Round-trip Sanity Check):
YES if you did NOT add assumptions not committed by SL_TEXT.
Do a quick mental back-translation / proposition check to ensure polarity/quantifiers/
modality/pragmatic force would not come back different.
```
**v6 relation**: adds new — meta-QA technique. Could be added as Q16 in polish QA.

### R28 — En-dash / em-dash forbidden (only ASCII -)
**Sources**: v34, v43, v68
**Verbatim** (v68):
```
- Forbid —/–/--. For pause/appositive dashes use spaced short hyphen " - ".
```
**v6 relation**: extends v6 PUNCT (which has apposition dash but doesn't forbid en/em variants).

### R29 — Quote-immunity list
**Sources**: v60-2-1
**Verbatim**:
```
[IMMUNITY]: NEVER quote:
  1) Job Titles / Honorifics (e.g., President, Minister, Director).
  2) Globally famous entities (e.g., Apple, Paris, NASA, Google).
  3) Names immediately following a Title-Anchor (e.g., استاد، دکتر، آقای، خواهر).
```
**v6 relation**: adds new — concrete list of when NOT to quote.

### R30 — Single-quote for unfamiliar names
**Sources**: v34, v53, v60-2-1, v65
**Verbatim** (v65):
```
If it's a new/uncommon name, wrap in single quotes first time (e.g., 'جان اسمیت').
```
**v6 relation**: adds new — pairs with R29.

### R31 — `[NO_INFO_BLEEDING]` — restate line locking
**Sources**: v67, v68
**Verbatim** (v68):
```
[NO_INFO_BLEEDING]: Do NOT redistribute, move, or re-balance information across line boundaries.
What is spoken in a specific input line MUST be fully addressed in its exact corresponding
output line to preserve strict subtitle timing.
```
**v6 relation**: wording_only — v6 has LINE_BOUNDARY_LOCK, this is a more memorable wording variant. "subtitle timing" rationale is useful.

### R32 — BCP-47 SCRIPT awareness
**Sources**: v67
**Why useful only at architecture level**: v6 is FA-specific, this is universal. SKIP.

---

## 3. STRUCTURAL BLOCKS WORTH CONSIDERING

### B1 — Phase-numbered workflow (PHASE -1 / PHASE 0 / PHASE 1 / PHASE 2)
**Sources**: v17.7, v18
**Verbatim** (v17.7 has PHASE -1 PRE-FLIGHT DIAGNOSTIC):
```
[PHASE -1: PRE-FLIGHT DIAGNOSTIC]
Perform this internal assessment BEFORE the Reflexion Loop to set operational parameters.
1. [MAPPING_PERSONA]: ...
2. [DYNAMIC_RULE_ACTIVATION]: ...
3. [DETECTION_FALLBACK]: ...
```
**v6 has**: PHASE_0_BASE, Phase 1 (pre-scan), Phase 2 (per-line in translate). Already similar structure but PHASE -1 framing for persona/risk detection is missing.
**Recommendation**: v6's PHASE_0_BASE for polish + Phase 1/2 for translate already covers this. SKIP unless minor wording.

### B2 — REFLECT_7L (7-level reflection)
**Sources**: v71
**Verbatim**:
```
④ [REFLECT_7L] (all SILENT):
R1) Structure / locks / 1:1 line integrity.
R2) Meaning comprehension using adjacent context + ambiguity resolution.
R3) Exact meaning transfer; negation/exception scope preserved.
R4) Max Persianization + zero Latin outside Whitelist.
R5) Proper nouns / geography / file-wide consistency.
R6) Numbers/dates/units/codes + punctuation cleanliness.
R7) Pre-check: mentally flag lines likely to fail Q1–Q6; pass findings to ⑤.
```
**v6 relation**: v6 has QA Q1-Q14 in polish which is more granular. Translate v6 has self-review at WORKFLOW step ④. The 7L framework is more memorable. Could replace the unstructured "self-review" step in translate.

### B3 — Q1-Q5 BOOLEAN QA framework
**Sources**: v67
**Verbatim**:
```
Q1 (Clarity / One-pass Comprehension): YES if a native reader can understand it on first read
Q2 (Native TL / Anti-Calque / Non-Translationese): YES if it reads like original Persian
Q3 (Pragmatic Equivalence / Register / Voice / Localization): YES if communicative intent preserved
Q4 (Accuracy / Logic / Consistency / Non-Negotiables): YES if all factual/logical content preserved
Q5 (Inference Discipline + Round-trip Sanity Check): YES if no added assumptions
```
**v6 relation**: v6 has Q1-Q14 in polish (more granular). Q1-Q5 is a higher-level boolean check. Could be added as a final macro-pass after Q14.

---

## 4. EXPLICIT REJECTIONS (do NOT inject)

These appear in older versions but conflict with v6 design decisions:

| ID | Old feature | Why reject |
|---|---|---|
| X1 | ⚠️ confidence marker in output (HIGH/MEDIUM/LOW → append ⚠️ if LOW) | v6 forbids any emoji/marker in subtitle output. Conflict with broadcast safety. |
| X2 | « » nested quotes (v34, v43, v53, v65, etc.) | User explicitly mandates `" "` only, `« »` forbidden. v6 correct. |
| X3 | en-dash / em-dash as quote/apposition | v6 mandates ASCII `-` with space-hyphen-space. R28 above is the safer formulation. |
| X4 | Subject-to-verb distance ≤8 hard cap (older) | v6 has ≤12 soft heuristic which is more permissive and aligns with SAGE/MASTER. Keep v6. |
| X5 | Universal source/target with BCP-47 (v67) | v6 is FA-specific intentionally. Universal framing adds complexity without benefit. |
| X6 | American-style trailing punctuation inside quotes (some old versions) | v6 has Persian-style: terminal punct outside quote, EXCEPT title-internal `?/!`. Correct. |
| X7 | "Compress before digit conversion" sub-order detail (v51, v53, v57) | v6 NUMBERS handles this with VALUE-LOCKED + FORMAT-NORMALIZABLE which is cleaner. |
| X8 | Output inside ```text fences ``` (older versions wanted markdown code block wrapping) | v6 explicitly forbids code fences. Correct. |

---

## 5. EVALUATOR INSTRUCTIONS

For each F-numbered item (F1-F9) and R-numbered item (R1-R31), please respond with:

```
[ID]: F1 (or R1, B2, etc.)
DECISION: ACCEPT | REJECT | MODIFY
RATIONALE: 1-3 sentences
INTEGRATION_NOTE: where in v6 to add (e.g., "extend MN-4", "new SA-14", "add to ID block")
TRADEOFF_FLAG: any concern (e.g., "increases prompt size by ~30 lines")
```

Priority order suggested for evaluation:
1. **High-impact role/persona** (F1, F5, F6, F9) — affects model self-image
2. **Behavioral gaps** (R1, R2, R3, R6, R7, R11, R13, R14) — fill missing concrete rules
3. **Edge-case safety** (R4, R16, R22, R23, R24, R27) — narrow safety nets
4. **Style polish** (R5, R8, R9, R10, R15, R17, R18) — small wins
5. **Wording variants** (R31, B2) — low effort

Constraint: total v6 prompt size growth should stay under ~25% to avoid attention dilution. If accepting all items would exceed this, please prioritize by ranking.

## 6. CONTEXT FOR EVALUATOR

The current v6 prompt files in the repository:
- `prompts/translate_PER_proposal_v6.txt` — translation prompt (gpt-5.5)
- `prompts/polish_PER_proposal_v6.txt` — polish prompt (gpt-5.5)
- `prompts/_smtv_locks_proposal_v6.txt` — shared SMTV lexicon

These prompts have been through 6 iterations of round-trip critique between Claude and GPT-5.5. They are considered "regression-test-ready" by GPT-5.5. The features above were either dropped during simplification or never integrated. The user wants targeted re-injection of the best legacy features.

Source files surveyed (21 prompts):
v17, v17.7 (Sonnet), v18 (Sonnet), v22 (Mini), v23, v29, v34, v35, v41, v43, v47, v51, v53, v57, v60-2-1 ("winner"), v63, v65 (Gemini), v67 (Universal), v68, v70, v71.

---

**END OF PROPOSAL**
