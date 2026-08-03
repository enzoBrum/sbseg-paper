# Feedback on `sbc-template.tex`

## Structure

### Things that work
- The Background → Threat Model → Attacks → Evaluation flow is the standard PDF-security paper shape and reviewers will read it easily.
- Splitting attacks into two named subsections (ASA, SFDA) with parallel internal structure (mechanism → spec ambiguity → ISO quote) gives the paper a clean spine.

### Things to fix

1. **Section 5 umbrella paragraph contradicts SFDA** (`sbc-template.tex:154`). It says the attacks "alter existing signature fields"; SFDA creates a *new* one. Reframe to something like "two underspecified aspects in how the PDF specification governs signature fields — how existing fields may be modified, and how new fields may reference existing signatures."

2. **Threat Model is doing nothing yet** (`sbc-template.tex:134`). The attack subsections keep saying "affected verifiers" without anchoring to a layered model. Decide now whether the GUI/API split is load-bearing — if yes, define it before Section 5 and have ASA/SFDA each say which layer they break; if no, fold one or two sentences into the Introduction and delete the section. A skeleton section before the meat of the paper is worse than no section.

3. **Countermeasures cannot stay empty.** SBC reviewers will flag it. Even three sentences ("verifiers should reject documents with duplicate `/V` references; spec should disambiguate filling; …") prevents the "no defense proposed" criticism.

4. **Related Work placement.** Both prior works (`pdf-insecurity`, `pdf-certification-attack`) are already load-bearing citations in Background and Section 5, but the reader has not been told what those papers contributed. Either (a) move Related Work right after Introduction so it lands before you lean on those citations, or (b) add a one-line orientation in Section 5's umbrella paragraph ("Prior work~\cite{pdf-insecurity,pdf-certification-attack} examined attacks on page content and on the signature dictionary; we examine the signature field itself.").

5. **`/Lock` family is on the architecture diagram of the project but missing from the paper.** The README mentions `remove_lock_from_sigfield.py` and `/SigFieldLock` is named in Background, but no subsection ties SigFieldLock-stripping into the attacks. If that's intentional (out of scope), fine; if not, it's a missing third attack subsection.

## Background

- **`\subsection{Pdf Structure}`** (`sbc-template.tex:64`) — "Pdf" → "PDF". Reviewer-irritant.
- **Broken forward reference** (`sbc-template.tex:95`): "discussed in sub section C". Replace with `Section~\ref{sec:doc-mod-perm}`.
- **§Signature Field attribute list** (`sbc-template.tex:95`) is a run-on. The inline list mixing semicolons works but `/SigFieldLock` is the only entry whose description is "discussed elsewhere," which is awkward — give it a one-clause gloss here too ("a field-level lock specification, detailed in §E").
- **§Modification Permission Mechanism** (`sbc-template.tex:113`) — rename to **Mechanisms** (plural); the subsection covers three.
- **"levels two and three"** is used in ASA (`sbc-template.tex:175`) without ever being defined. Either the placeholder Table~\ref{tab:mdp-placeholder} needs to enumerate levels 1/2/3 explicitly, or the prose needs to define them inline. Right now a reader hits "levels two and three" cold.
- **§Modification Permission Mechanisms opening** (`sbc-template.tex:117`) is the most important paragraph in Background and currently reads like a continuation of the previous subsection. Lead with a stronger framing sentence: "PDF signatures are sensitive only to changes within their signed byte range; incremental updates fall outside that range."
- **FieldMDP description** (`sbc-template.tex:119`) — "locks specific form fields" is slightly off; FieldMDP can lock all fields or a named subset via `/Fields` and `/Action`. Worth a half-sentence correction.

## Attack section (Section 5)

### ASA
- Solid. One issue: the ISO quote at `sbc-template.tex:178` is wrapped in `[...]` inside `\emph{}`. The brackets read as editorial insertion. If it's a verbatim quote, drop the brackets; if paraphrased, signal that outside the quote.
- **The "at least" argument is the paper's strongest spec-ambiguity claim.** Consider making the ASA closing sentence (`sbc-template.tex:181`) end with a sharper statement — currently it says "remaining within the class of changes that affected verifiers accept as non-invalidating," which is a mouthful. Try: "Under that reading, ASA is not a verifier bug but a specification gap."

### SFDA
- **"two signers now appear in the verifier interface"** (`sbc-template.tex:192`) — overstated. Some verifiers show a single line per `/V`; "two signature fields are visible" is safer.
- **TODO marker at `sbc-template.tex:202`** ("not exactly true") tags the right sentence — the "every signature field that references the dictionary is rendered valid" claim is probably true for *some* affected verifiers but not all. Soften to "the verifier renders the duplicated field as valid alongside the original" and let the evaluation table provide the precision.
- **ST/DT paragraph could be tighter to spec ambiguity.** Right now it's framed as an implementation-detail axis, but it's also a *second* spec gap: ISO 32000-2 doesn't define what happens when two fields share a `/T`. Add a half-sentence: "The specification does not prescribe behavior when two signature fields share `/T`, leaving each verifier to resolve the collision on its own."
- **Comparison to Sneaky Signature Attack** (`sbc-template.tex:190`) — "Whereas the Sneaky Signature Attack appends an attacker-controlled signature dictionary" — verify this against `pdf-certification-attack`. If the cited attack actually replaces an entry rather than appending, the contrast needs to be reworded. Worth fact-checking before submission.

### Cross-cutting
- Both subsections end with the figure as the last element. That's fine, but in ASA the figure is *after* the closing prose paragraph (good) and in SFDA the figure is after the ST/DT paragraph (also fine), so they're parallel — keep it that way.
- Neither attack subsection currently says **whether the attack requires a certification signature, an approval signature, or both**. The pipeline tests both; the paper should be explicit about which signature type each attack targets. This is one of the most likely reviewer questions.

---

# Round 2 — review of current `sbc-template.tex`

Reviewed sections with prose: Background, Threat Model, Breaking Digital Signature Verifiers (ASA + SFDA), Methodology. Skipped Abstract, Introduction, Evaluation, Countermeasures, Related Work, Conclusion (per instructions: empty or bullet-only).

## Progress since Round 1
- Threat Model is now load-bearing: UI-Layer 1/2, API-Layer 1/2, and the winning-conditions taxonomy with `\CIRCLE`/`\LEFTcircle`/`\Circle` resolve the prior "skeleton section" criticism.
- Methodology now exists with an algorithm and a separate manual-probe subsection.
- ASA's "at least" argument is sharper and now stands on its own.

## Carryover from Round 1 — still unaddressed

These are the same defects as before, with updated line refs:

1. **`Pdf Structure`** (`sbc-template.tex:66`) — still lowercase; should be `PDF Structure`.
2. **`sub section C`** (`sbc-template.tex:97`) — still a broken forward reference; use `Section~\ref{sec:doc-mod-perm}`.
3. **`Modification Permission Mechanism`** (`sbc-template.tex:115`) — still singular; the subsection covers three mechanisms.
4. **"permission levels two and three"** (`sbc-template.tex:208`) — still undefined when ASA reaches for it. Either enumerate levels in the (still placeholder) Table~\ref{tab:mdp-placeholder} or inline-define them in §Modification Permission Mechanism. A reader hits this term cold today.
5. **ISO quote wrapped in `[...]`** (`sbc-template.tex:211`) — brackets still inside `\emph{}`; either drop them (verbatim) or move the editorial signal outside the quote.
6. **TODO at SFDA closing** (`sbc-template.tex:235`, "not exactly true") still flags the right sentence — the universal "every signature field that references the dictionary is rendered valid" claim needs softening before submission.
7. **Signature type each attack targets** — still unspecified. Pipeline sweeps `is_cert_sig ∈ {true, false}` for both attacks, but neither ASA nor SFDA prose tells the reader which signature class each is meant against. Add one sentence per subsection.
8. **Front matter** — title is `TODO` (`sbc-template.tex:24`), abstract is `TODO` (`sbc-template.tex:45`), affiliation block is still the template placeholder (`sbc-template.tex:30-38`). Tracking them here so they aren't forgotten near submission.

## Threat Model (new content)

- **"TODO: fact check APIs"** (`sbc-template.tex:160`) — the API-Layer 1/2 split needs a concrete grounding example from at least one tested library (PyHanko or DSS). Right now the reader has to take the binary-verdict + detailed-report dichotomy on faith. One example sentence ("PyHanko, for instance, returns a `valid` boolean and a `SignatureStatus` object…") would close this.
- **API-Layer 1 vs API-Layer 2 asymmetry with UI layers.** UI-Layer 1 admits three outcomes (valid / warn / invalid) via `\LEFTcircle`. API-Layer 1 is described as a *binary* verdict ("valid or invalid", `sbc-template.tex:163`). So how does the partial-vulnerability case map onto API verifiers? Either Layer 1 admits warnings on APIs too (then it isn't binary) or it doesn't (then partial vulnerability is impossible for libraries, which should be stated). The current text leaves this ambiguous and §3.3 then defines "partially successful" without saying whether it applies to both verifier classes.
- **Web verifiers are missing from the threat model entirely.** Methodology §4 introduces "web verifiers" as a distinct evaluation regime (`sbc-template.tex:244`), but §3 only knows two classes (GUI, library). Either add a third subsection ("Web Verifiers") or fold web verifiers into one of the two existing classes and say so explicitly. As written, the reader meets web verifiers for the first time in Methodology with no model for them.
- **"Most GUI verifiers display this banner immediately"** (`sbc-template.tex:152`) — universal-ish quantifier. "Display this banner on opening" without "most/typically" reads cleaner; the qualifier reads as hedge.
- **Reference to the cited layered model.** `sbc-template.tex:150` correctly attributes only the GUI portion to `pdf-certification-attack`, which respects the memory note on that paper's scope. Keep it that way; do not extend the citation to API-Layer wording.

## Methodology (new content)

- **"TODO GUI verifiers and TODO library verifiers"** (`sbc-template.tex:242`) — obvious placeholder; surface count once locked in.
- **Algorithm 1: `\KwIn` is misused.** `create_asa_test_case` and `create_sfda_test_case` are helper procedures, not inputs. Either drop the `\KwIn` and rely on the surrounding prose, or restructure as a procedure with explicit calls and no `\KwIn`. Conference reviewers familiar with algorithm2e will trip on this.
- **Sweep degeneracy not acknowledged.** `mdp_level ∈ {null,1,2,3}` × `is_cert_sig ∈ {true,false}` produces eight combinations, but `DocMDP` is exclusive to certification signatures (per the paper's own §Background, `sbc-template.tex:134`). So `is_cert_sig=false ∧ mdp_level ∈ {1,2,3}` is a degenerate configuration. Either skip those iterations in the algorithm or add a one-line caveat ("infeasible combinations — DocMDP without certification — are omitted") so the reader doesn't trust the Cartesian product literally.
- **Test-case count is implicit.** $4 \times 2 \times 2 \times 2 \times 2 = 64$ tests (after multiplying by ASA/SFDA), or fewer if degenerate combinations are dropped. Stating the total once in prose ("the sweep yields N test cases per verifier") sizes the evaluation for the reader.
- **`is_field_protected` is ambiguous.** §Background introduced both FieldMDP and SigFieldLock as field-protection mechanisms. Which one does `is_field_protected` enable in the pipeline, or does it sweep over the choice? A half-sentence ("we use SigFieldLock for field protection, the PDF 2.0 form") removes the ambiguity.
- **Only the *signature* config is swept, not the *attack* config.** The algorithm enumerates how the trusted signature is built but says nothing about what the ASA/SFDA chains vary internally — e.g., for ASA, does `/Rect` always expand to full page, or sweep across sizes? For SFDA, is the duplicated field's name a sweep dimension (same `/T` vs different `/T`)? A reviewer will ask whether the result table is one cell per attack or one cell per attack-variant. Either state the variants up front or say each attack is realized as a single fixed chain.
- **Test-execution paragraph is library-then-GUI but ignores web.** `sbc-template.tex:295` describes the library and GUI flows but never describes how the web manual flow is conducted (one PDF? per attack? per configuration?). The reader was told in `sbc-template.tex:244` that a single document is used per attack; restate or cross-reference that here so §4 is self-contained.
- **Manual probes need rationale.** §4.2's three probes are stated but not justified. The reader is supposed to understand *why* "approval signature" probes P=1 and P=2 and "annotation" probes P=3. Add one sentence on the principle: each probe is the operation whose permitted/forbidden status is the discriminator between adjacent DocMDP levels (e.g., adding an approval signature flips between P=1 and P=2; adding an annotation flips between P=2 and P=3). Right now the choices look arbitrary.
- **§4.2 scope is broader than its title.** Title says "Manual Tests for Modification-Permission Support," but the test it runs is "does the verifier behave like the spec says at each DocMDP level." That isn't quite a *support* test; it's a *conformance* test. Consider renaming to "Manual DocMDP Conformance Probes" or similar so the contribution is unambiguous.
- **Reproducibility hook missing.** Methodology never names the test certificates, the unsigned input PDF, or the database persistence layer. One-line callout to a public artifact (or a TODO to add one before submission) would help.

## Misc nits

- **`\placeholderfigure` is used 7 times.** Fine for drafting, but the camera-ready will need real figures for at least: the PDF object tree (`sbc-template.tex:72`), the ASA /Rect-expansion diagram (`sbc-template.tex:217`), and the SFDA two-field example (`sbc-template.tex:238`). Those three are the ones a reviewer will want to see.
- **`\sloppy`** (`sbc-template.tex:9`) is enabled globally. With the SBC template's narrow columns and your long `\texttt{}` identifiers, leave it on, but expect to hand-tune the worst overfull boxes near submission.
- **`\textbf{UI-Layer 1}` / `\textbf{API-Layer 1}` as inline labels** — consider `\paragraph{UI-Layer 1.}` instead; it semantically marks them as sub-headings and avoids the inline-bold tic.

---

# Round 3 — comparison to `pdf-certification-attack` (pdf-insecurity.org)

Comparison prompt was "their paper looks more verbose than mine, what gives." Honest decomposition: roughly 40% legitimate extra scope, 30% scaffolding *you* are missing and should add, 30% padding *they* indulge in that you should not emulate.

## Scaffolding to add (cheap credibility wins, not "verbosity for its own sake")

1. **A real Introduction.** Replace the `\begin{itemize}` outline at `sbc-template.tex:53` with prose covering: (a) PDF signatures are a load-bearing legal/business primitive, (b) prior work covered approval signatures and certification signatures, (c) the signature *field itself* is the unexamined surface, (d) we present ASA and SFDA. Single tight paragraph, not a page.
2. **One motivating scenario.** A two- to three-sentence forged-contract / forged-invoice example up front. The pdf-insecurity paper's contract scenario is overlong but the *device* works — reviewers latch onto a concrete victim.
3. **Contributions bullet list at the end of the Introduction.** Five bullets max: novel attacks (ASA, SFDA), automated pipeline, evaluation across N verifiers, countermeasures + detection tool, responsible disclosure if applicable. This is a near-mandatory rhetorical move for security venues and it costs ~10 lines.
4. **Limitations subsection** at the end of §5 (Breaking Digital Signature Verifiers). Candidates: hidden content surfaces via text search; verifiers that surface all UI layers by default; self-signed vs. PKI-trusted certs; SFDA's visible-second-field tell. Two paragraphs.
5. **Responsible Disclosure paragraph** if any vendor was contacted. Even "we have notified vendors X, Y, Z; CVE assignment is pending" is enough. If no disclosure has happened, flag as TODO — reviewers will ask.
6. **Inline `\paragraph{Label.}` headers inside ASA and SFDA.** Same content, more visual density. Suggested labels for ASA: *Mechanism.*, *Spec ambiguity.*, *Why "filling" is the wedge.*, *Variants.* For SFDA: *Mechanism.*, *Contrast with Sneaky Signature.*, *Spec gap.*, *Variants.* This addresses the "feels thin" perception without adding any new claims.

## Padding from their paper to *not* emulate

- **Methodology-defense detours.** Their §IV-B explains why they didn't use NLP-on-the-spec and didn't fuzz. You don't need a column defending techniques you didn't use; one sentence — or silence — suffices.
- **"It's Not a Bug, It's a Feature" / discussion sections that restate the spec-ambiguity claim.** They make this claim in the intro, in §V's umbrella, in §V-D, and again in §VIII. You make it once in §5 and once in Countermeasures — keep it that way.
- **Citation-stuffing to establish "people use this."** Their "certification signatures in the wild" runs through eleven citations (GPO, BC Legislature, ETSI, "multiple commercial and governmental services [14–24]"). One concrete example plus eIDAS carries the same evidential weight at a fraction of the column-inches.
- **Restating the attack scenario twice.** Their Fig. 1 *and* their Fig. 2 + Use Case section convey the same idea. Pick one.
- **Process narration ("we wondered…", "this was the most time-consuming step…", "surprisingly we found…").** Informationally empty, atmospherically expensive.
- **Rigor-theater taxonomies.** Their High/Medium/Low/None danger-level scheme is defined across half a column and then mostly used to say "FreeText, Redact, Stamp are dangerous; the rest aren't." Your `\CIRCLE`/`\LEFTcircle`/`\Circle` scheme is already doing the same work in a quarter of the space — keep it.

## Net takeaway

Your prose density is fine. The "less verbose" feeling comes from missing *scaffolding* (intro, motivation, contributions, limitations, disclosure, inline `\paragraph{}` labels), not from missing *padding*. Add the scaffolding; resist the temptation to inflate the technical sections to match the reference paper's length.

