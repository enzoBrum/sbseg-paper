# CLAUDE.md — Paper Writing Assistant

You are assisting in writing and polishing a security research paper on attacks against PDF signature fields, submitted to an SBC conference.

## Paper context

- **File**: `sbc-template.tex` (LaTeX, SBC template)
- **Language**: English
- **Topic**: Attacks that break PDF digital signature verifiers by manipulating signature fields — specifically the Appearance Substitution Attack and the Signature Field Duplication Attack — tested against Adobe Reader, Foxit, LibreOffice, PyHanko, and DSS.
- **Audience**: Security researchers familiar with PDF internals and digital signatures.

## Paper structure (current outline)

1. **Introduction** — context, motivation, contributions
2. **Background** — PDF structure, incremental updates, Signature Field, Signature Dict, DocMDP / SigFieldLock / FieldMDP, approval vs. certification signatures
3. **Threat Model** — GUI verifier model (visual appearance), API/library model (cryptographic + modification detection)
4. **Methodology** — automated test pipeline (see repo root for architecture)
5. **Breaking Digital Signature Verifiers** — Appearance Substitution Attack; Signature Field Duplication Attack; per-verifier analysis
6. **Evaluation** — tester scripts, results table, discussion
7. **Countermeasures**
8. **Related Work**
9. **Conclusion**

## How to assist

- **Draft sections**: when asked to write or expand a section, write tight academic prose — no padding, no vague hedging. Lead with the point.
- **Polish prose**: improve clarity, fix grammar, tighten sentences. Preserve technical accuracy above all else.
- **Maintain SBC conventions**: abstract ≤ 10 lines, figures/tables captioned in Helvetica 10pt bold, references in `\cite{}` form with `sbc` bibliography style.
- **Stay faithful to the research**: do not fabricate results, claims, or citations. If something is unknown, say so and leave a TODO.
- **LaTeX**: output valid LaTeX. Prefer `\emph{}` for terms, `\texttt{}` for technical identifiers (e.g., `/Lock`, `/Reference`), and `\cite{}` for all references.
- **Terminology to use consistently**:
  - "signature field" (not "sig field" in prose)
  - "incremental update" (not "incremental save")
  - DocMDP, FieldMDP, SigFieldLock (exact case, no spaces)
  - "verifier" (not "viewer") when discussing signature validation
  - "attack chain" for the sequence of modifications applied to a PDF

## Key technical facts

- Attacks exploit how PDF readers handle signature fields in incremental updates without invalidating the displayed signature.
- The **Appearance Substitution Attack** replaces the appearance stream (`/AP`) of the signature field — the visual stamp — with forged content, while the cryptographic signature over the original bytes remains technically valid.
- The **Signature Field Duplication Attack** copies or creates a new signature field that overlaps or replaces the original, causing verifiers to display the attacker-controlled field instead of the signed one.
- The test pipeline generates modified PDFs combinatorially (DocMDP permissions × FieldMDP actions × certification flag × Adobe P flag) and classifies verifier screenshots as valid / warn / invalid.


## Writing instructions

- Use an objective tone, focusing on keeping text precise and with good flow
