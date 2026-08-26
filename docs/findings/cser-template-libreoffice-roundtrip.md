# Finding — the CSER template survives LibreOffice, with two losses

**Date:** 2026-08-26 · **Status:** MEASURED, not inferred · **Risk:** downgraded from unknown to bounded

The Intro Report (due **18 SEP**) must be submitted on the CSER 2022 / Elsevier Procedia **MS Word**
template. We develop on Ubuntu with LibreOffice and no Word. Whether the template survives a LibreOffice
round-trip was listed as an open risk in [../todo.md](../todo.md) — *"cheap now, expensive on 17 SEP."*

**It was cheap. Here is the answer.**

## What was done

```bash
cp "docs/course/source-material/cser_template_cser2022 (7).docx" cser_test.docx
libreoffice --headless --convert-to docx --outdir out cser_test.docx
# then unzip both and diff the OOXML
```

LibreOffice 7.3.7.2, headless, on this machine, 2026-08-26.

## Result: usable, with two real losses

| Check | Before | After | Verdict |
|---|---|---|---|
| `Els-*` paragraph styles | 20 | **20** | ✅ all present |
| Style **display names** (`w:name`) | `Els-1storder-head`, … | **identical** | ✅ preserved |
| Style **internal IDs** (`w:styleId`) | `Els-1storder-head` | `Els1storderhead` | ⚠ **hyphens stripped** |
| Page trim size (`w:pgSz`) | `10886 × 14855` twips | **identical** | ✅ preserved |
| `w:code="161"` paper-size hint | present | **dropped** | ⚠ cosmetic |
| Embedded media | 2 | **1** | ❌ **one lost** |
| Embedded OLE objects | 1 | **0** | ❌ **lost** |
| File size | 3,257,862 B | 3,010,492 B | consistent with the losses |

## What this means in practice

**The formatting is safe.** All twenty `Els-*` styles survive with their human-readable names intact, so
they still appear correctly in the style gallery and still apply the right fonts and sizes. The trim size
— the thing that would visibly break a print layout — is byte-identical.

**The styleId rename is almost certainly harmless.** Word matches styles for display by `w:name`, which
is preserved. The internal ID change would only matter to something referencing IDs programmatically,
which a hand-written paper does not do. **`[ASSUMED]`** — not verified in real Word, because we have none.

**The losses are in the template's own example content**, not its structure: one WMF image and one OLE
object, which are the sample figure and the sample equation. **We replace those with our own content
anyway**, so losing them costs nothing — *provided nobody needs the sample equation as a formatting
reference.* If an equation is needed in the report, build it fresh rather than editing the template's.

## Recommendation

1. **Draft in markdown** in [../course/report/](../course/report/) — unchanged, that was always the plan.
2. **Assemble in LibreOffice.** It works. Do not let this become a blocker or a reason to find a Windows machine.
3. **Before submitting, open the final `.docx` in real Word if anyone on the team has it** — a teammate,
   a lab machine, or Word Online. This is a five-minute check against the one thing we cannot verify here,
   and 18 SEP is the wrong day to discover a surprise.
4. **Keep the pristine original.** `docs/course/source-material/` is read-only for exactly this reason —
   always start a fresh copy from it, never from a previously round-tripped file. **Losses compound**: a
   file round-tripped twice loses whatever the first pass degraded, again.

## What is still unverified

- Behaviour in **real Microsoft Word** — we have none. The styleId rename is judged harmless on reasoning,
  not observation.
- Whether the instructor's submission process cares about anything beyond visual conformance.
- Whether the lost OLE object matters — only if the report needs an equation.

**Risk status:** was *unknown, potentially blocking on 17 SEP*. Now *bounded, with a five-minute
mitigation*. Related: [../course/report/INDEX.md](../course/report/INDEX.md).
