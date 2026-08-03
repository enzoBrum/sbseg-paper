# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Security research project exploring attacks against PDF signature fields, targeting vulnerabilities in how PDF readers and validation libraries handle signature field modifications. The goal is to generate, test, and document attack vectors systematically across multiple verifiers (Adobe Reader, Foxit, LibreOffice, PyHanko, DSS).

## Commands

`src/main.py` is a typer CLI. Pass `--db-path` before the subcommand to use a non-default database.

```bash
uv run python src/main.py --help                 # show all subcommands
uv run python src/main.py --db-path /tmp/x.db generate
```

### Typical flow

```bash
uv run python src/main.py generate               # generate all test cases → DB
uv run python src/main.py verify adobe           # run full batch through a verifier
uv run python src/main.py analyze                # evaluate screenshots, show stats
uv run python src/main.py analyze --verifier adobe  # stats for one verifier only
```

### Inspect subcommands

```bash
uv run python src/main.py list                   # table of all persisted tests
uv run python src/main.py show 42                # chain + verdicts for test #42
uv run python src/main.py save 42                # write test #42 PDF to cwd/42.pdf
uv run python src/main.py save 42 --out /tmp/t.pdf
```

### Verifiers

`verify` accepts: `adobe`, `foxit`, `libreoffice`, `pyhanko`, `dss`. The library tester passes the verifier name as `VerifierTest.name`.

### Library verifiers (PyHanko, DSS)

Both expose `POST /verify` returning `"VALID"` or `"INVALID"`. The CLI auto-starts the
server before testing and stops it (including all child processes) after. No manual
startup is needed:

```bash
uv run python src/main.py verify pyhanko   # gunicorn starts and stops automatically
uv run python src/main.py verify dss       # java -jar starts and stops automatically
```

**DSS prerequisite (one-time):** The jar must be built and committed before first use:

```bash
cd src/tester_scripts/library/dss
./mvnw -q package -DskipTests
# git add target/demo-0.0.1-SNAPSHOT.jar && git commit
```

To add a new library verifier, subclass `LibraryVerifier` in
`src/tester_scripts/library/verifiers.py` and add it to `REGISTRY`.

### Package management

```bash
uv sync                                          # syncs root + workspace member
uv run python src/main.py                        # run with project venv
```

The PyHanko sub-workspace lives at `src/tester_scripts/library/pyhanko/`.

## Architecture

### Data flow

```
src/unsigned-files/example-2-0.pdf  (preprocessed to 2 pages; see "Preprocessing" below)
    -> tester_scripts/generate_test_cases.py   (Pipeline instances per Algorithm 1)
    -> Pipeline.apply()                        (chains modifications sequentially on the PDF bytes)
    -> signed_files.db                         (modified PDFs as blobs + metadata)
    -> tester_scripts/gui/{verifier}/tester.py (applies a verifier, captures screenshot)
       OR tester_scripts/library/tester.py     (POSTs PDF to a library verifier, records boolean)
    -> tester_scripts/evaluate_results.py      (template-matches screenshots to valid/warn/invalid)
    -> verifier results back to DB
```

### Test generation

`tester_scripts/generate_test_cases.py` follows Algorithm 1 from the paper, sweeping `(mdp_level, is_cert_sig, is_field_protected, is_stamp)` plus a fifth dimension `change_page` for the two novel variants:

- **ASA `change_page=True`** appends a `ChangeSigFieldParentPage` step that rewrites the signed widget's `/P` and relocates it between page `/Annots` arrays.
- **SFDA `change_page=True`** passes `place_on_different_page=True` to `CreateNewSignatureFieldFromExistingField`, which places the duplicated widget on a different page.

`(is_cert_sig, mdp_level)` maps to concrete PDF structure as:

| is_cert_sig | mdp_level | Result |
|---|---|---|
| True  | P     | Certification signature with DocMDP `/P` |
| False | P     | Approval signature with SigFieldLock `/P` |
| False | None  | Approval signature, no permission control |
| True  | None  | Skipped (invalid) |

`is_field_protected=True` places the signed field itself in the FieldMDP/SigFieldLock `/Fields` list.

### Preprocessing the unsigned input

`src/unsigned-files/example-2-0.pdf` has been preprocessed to two pages (via `pymupdf`) so the `change_page` variants have a target page to move to. If you replace the unsigned input, do the same.

### Core modules

- **`src/modification_pipeline/chain_item.py`** — Abstract base class `ChainItem`. All attack steps implement `apply(BytesIO) -> BytesIO`. Contains `find_sig_field_ref()` for locating signature fields.
- **`src/modification_pipeline/pipeline.py`** — Orchestrator that chains `ChainItem` instances sequentially and persists results to the database. Accepts an `attack_name` ("ASA" / "SFDA") that lands on `ModificationTest.attack_name`.
- **`src/modification_pipeline/model.py`** — SQLAlchemy ORM models for `signed_files.db`:
  - `ModificationTest`: PDF blob + expected validity + attack_name
  - `ChainItemSpec`: serialized attack-step specification (parameters per step)
  - `VerifierTest`: per-verifier result (screenshot blob + classification)
  - Association tables link tests to their chains and to verifier results

### Attack modules (all in `src/modification_pipeline/`)

| Module | Attack |
|--------|--------|
| `add_new_signature.py` | Adds a signature with configurable DocMDP/FieldMDP/SigFieldLock |
| `alter_page_content.py` | Injects a black rectangle into a page content stream |
| `add_new_annotation.py` | Injects a FreeText annotation |
| `add_new_ap_to_sigfield.py` | Replaces a signature field's `/AP` (appearance stream) |
| `add_new_rect_to_sigfield.py` | Modifies a signature field's `/Rect` |
| `change_sigfield_parent_page.py` | Rewrites `/P` of a sig widget + moves it between page `/Annots` arrays |
| `create_new_signature_field_from_scratch.py` | Creates a new unsigned sig field with lock specifications |
| `create_new_signature_field_from_existing_field.py` | Duplicates a sig field; supports `place_on_different_page` |
| `remove_lock_from_sigfield.py` | Strips `/Lock` from the sig field (FieldMDP/SigFieldLock bypass) |
| `remove_reference_from_sig_dict.py` | Removes `/Reference` from the signature dict |

### Tester scripts (`src/tester_scripts/`)

```
tester_scripts/
  tester.py                      # unified entry point; routes by registry lookup
  evaluate_results.py
  generate_test_cases.py
  gui/
    gui_tester.py                # shared driver (screenshots, retries, pagination)
    verifiers.py                 # REGISTRY (CLI name → GuiReaderConfig) + test(name)
    adobe/tester.py + imgs/      # CONFIG + private helpers; ready/reference images
    foxit/tester.py + imgs/
    libreoffice/tester.py + imgs/
  library/
    tester.py                    # auto-starts verifier, POSTs PDFs, stops on exit
    verifiers.py                 # LibraryVerifier ABC + PyHanko/DSS impls + REGISTRY
    pyhanko/                     # Flask app
    dss/                         # Spring Boot app (requires pre-built jar)
```

- Each GUI tester defines an `IMG_DIR = Path(__file__).parent / "imgs"` and resolves all ready/reference images from there.
- Run-time screenshots land in `src/screenshots/{verifier_slug}/{test_id}.png` and are also stored as blobs on `VerifierTest.screenshot`.
- `evaluate_results.py` maps each verifier name to its per-verifier `imgs/` directory.

### CLI entry point (`src/main.py`)

```
src/main.py    # typer app; --db-path global option; subcommands: generate, verify,
               # analyze, list, show, save
```

### Certificates

Six self-signed cert/key pairs live in `src/certs/` (`cert-1.pem` through `cert-6.pem`, `key-1.pem` through `key-6.pem`). These are used by `add_new_signature.py` for the test signatures. The same certificates are mirrored under `src/tester_scripts/library/pyhanko/cert-*.pem` and `src/tester_scripts/library/dss/src/main/resources/cert-*.pem` so the verifier services trust them.
