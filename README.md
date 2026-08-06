# $1 Yacht Sale: Tampering with Signed PDFs in Plain Sight (artifact)

This repository is the open source companion to the paper "$1 Yacht Sale:
Tampering with Signed PDFs in Plain Sight" (Enzo R. Brum, Frederico
Schardong, Ricardo Custódio), submitted to the Simpósio Brasileiro de
Segurança da Informação e de Sistemas Computacionais (SBSeg 2026). It
contains the tool that generates, applies, and detects the two PDF signature
attacks the paper introduces, plus the demo artifacts and recorded evidence
used in its evaluation.

## Project Title

$1 Yacht Sale: Tampering with Signed PDFs in Plain Sight.

The Portable Document Format (PDF) is a popular way of sharing electronic
documents, including official documents that require strong guarantees
against unauthorized modification. Digital signatures protect the integrity
and authenticity of a document, so that any non permitted change, for
example altering the value of a contract or a health prescription,
invalidates the signature. This paper introduces two novel attack classes
that abuse flaws in the PDF specification to visually modify a page of a
signed document without invalidating the signature or warning the user:
Appearance Substitution Attack (ASA) and Signature Field Duplication Attack
(SFDA). While previous work explored incremental updates, this paper taps
into modifications of the signature field itself, a kind of update that had
not been fully explored. The evaluation found that 12 out of 15 tested GUI
applications and 2 popular verification libraries were at least partially
vulnerable to one of the attack classes. The paper also proposes
countermeasures and specification improvements.

### What this artifact does

It builds tampered but still signed PDFs across the full parameter space of
both attacks, submits them to a set of signature verifiers, and records for
each verifier whether the tampering was accepted as valid and whether the
user was warned. Two verifiers, pyHanko and DSS, run fully automated and
headless in this repository. Four desktop GUI readers (Adobe Reader, Foxit,
Master PDF Editor, Microsoft Edge) can also be driven automatically inside a
Windows virtual machine. The `examples/` directory contains the paper's
headline "$1 Yacht" documents so a reviewer can see the attack in seconds.

## README Structure

This document follows the SBSeg 2026 Technical Artifact Committee (CTA)
minimal README requirements. All mandatory sections are present, in order:
Project Title, README Structure, Seals Considered, Basic Information,
Dependencies, Security Concerns, Installation, Minimal Test, Experiments,
and License.

Repository layout:

```
.
├── README.md                    this file
├── LICENSE                      MIT license
├── CITATION.cff                 citation metadata
├── CLAUDE.md                    internal architecture notes, not required reading
├── pyproject.toml, uv.lock      Python dependencies, uv managed
├── .python-version              pins Python 3.13
├── Dockerfile, .dockerignore    library verifier image (pyHanko + DSS)
├── docker/entrypoint.sh         container entrypoint
├── examples/                    the paper's "$1 Yacht" demo PDFs
├── paper-example/               standalone Alice/Bob pyHanko signing demo
├── src/
│   ├── main.py                  the Typer CLI, all commands below
│   ├── signed_files.db          SQLite results database
│   ├── certs/                   6 synthetic self signed test cert/key pairs
│   ├── unsigned-files/          base PDF that attacks are built from
│   ├── screenshots/             screenshot corpus of the original GUI runs
│   ├── modification_pipeline/   attack building blocks, one module per step
│   └── tester_scripts/
│       ├── generate_test_cases.py  sweeps Algorithm 1 to build all test cases
│       ├── library/                headless verifiers, pyHanko and DSS services
│       └── gui/                    GUI reader automation drivers
├── vm/                          Windows VM infrastructure (compose file, guest worker)
└── .vm/                         local, git ignored: proprietary installers and VM disk
```

## Seals Considered

This artifact pursues all four SBSeg seals: SeloD (Available), SeloF
(Functional), SeloS (Sustainable), and SeloR (Reproducible).

The repository is public and stable, with this README meeting the minimal
requirements (SeloD). Dependencies, versions, and the target environment are
documented below, install and run instructions are given, and a minimal
working example is included, see Minimal Test (SeloF). The code is modular:
each attack step is an independent `ChainItem` in
`src/modification_pipeline/`, verifiers are pluggable, and the CLI in
`src/main.py` is small and self describing. The map from paper claims to
code is given in Experiments (SeloS).

For SeloR, the reproduction scope is split:

Library verifiers, pyHanko and DSS, are fully and automatically
reproducible. They run headlessly with no GUI and no proprietary software.
Generating the attacks, running both libraries, and printing the result
matrix is a handful of commands, or one Docker image, and is the primary
reproducible claim of this artifact.

GUI verifiers, Adobe Reader, Foxit, Master PDF Editor, and Microsoft Edge,
are only partially reproducible. The paper evaluated 15 GUI applications,
only these 4 are automated in this repository's Windows VM tooling.
Reproduction on application versions other than the ones originally tested
is not guaranteed, since vendors change signature verification behavior
between releases. The installer binaries for these proprietary applications
also cannot be redistributed with this repository, so a reviewer who wants
to attempt GUI reproduction must supply their own installers, see
Experiments, GUI verifiers. For reviewers who cannot or do not want to
source installers and licenses, the original GUI verifier evidence is
committed under `src/screenshots/`, the per verifier, per test screenshots
captured during the runs reported in the paper.

## Basic Information

The library verifier reproduction, the core reproducible claim, is
lightweight:

- OS: Linux (x86-64) is the tested platform. macOS should also work for the
  native library path. Windows is only needed for the GUI path.
- CPU and RAM: any modern machine is enough. 2 cores and 4 GB RAM are ample.
  The library run is light on both CPU and I/O.
- Disk: about 2 GB for the Python environment plus the DSS Java runtime and
  jar.
- Network: needed once, to download dependencies during installation.
  Verification itself runs entirely on `localhost`.

GUI verifier reproduction is optional and needs considerably more: a Linux
host with hardware virtualization (KVM), Docker, several GB of free disk for
a persistent Windows VM, and reviewer supplied installer binaries for the
desktop readers. This path is not covered by the Docker image and is not
required for the library SeloR claim.

## Dependencies

Runtime toolchain: Python 3.13, pinned in `.python-version`, and
[uv](https://docs.astral.sh/uv/), the package and environment manager used
throughout. It reads `pyproject.toml` and `uv.lock` and creates a fully
pinned virtual environment. Java 21 (JRE) is required only to run the DSS
verifier natively, not for pyHanko, and not at all if you use the Docker
image, which bundles its own JRE.

Python packages are declared in `pyproject.toml`, exact versions locked in
`uv.lock`. Key ones: `pyhanko` (tested with version 0.36.0 from the
lockfile), `pyhanko-certvalidator`, `pyhanko-cli`, `pymupdf` for PDF
preprocessing, `sqlalchemy` for the results database, `typer` and `rich`
for the CLI, `flask` and `requests` for the library verifier service and
client. GUI automation libraries (`pyautogui`, `opencv-python`, `mss`,
`pillow`, `pyscreeze`, `keyboard`, `psutil`) are also pulled in but are only
used by the Windows VM GUI path.

The DSS verifier is a small Spring Boot application in
`src/tester_scripts/library/dss/`. A pre built jar
(`target/demo-0.0.1-SNAPSHOT.jar`) is included, so native `run dss` works
out of the box. To rebuild it, use a system Maven (`mvn -q package
-DskipTests` from that directory, there is no `mvnw` wrapper), or use the
Docker image, which compiles the jar from source during the build.

The proprietary desktop readers (Adobe Reader, Foxit, Master PDF Editor,
Edge) are third party licensed software and are not distributed here. They
are only needed for the optional GUI path.

## Security Concerns

Running this artifact is low risk, but reviewers should be aware of the
following. The committed private keys are synthetic: `src/certs/` and its
mirrored copies under the pyHanko and DSS service directories hold six self
signed test certificate and key pairs, and `paper-example/` has a throwaway
CA plus Alice and Bob keys. None of these protect anything real, do not
reuse them.

The tool intentionally produces forged, tampered signed PDFs. Its purpose
is to create documents whose visible content was altered after signing
without invalidating the signature, so treat generated PDFs and the
`examples/` files as attack samples, not trustworthy documents.

The library verifiers start a local HTTP service on `localhost:8080` for
the duration of a run and stop it afterward. Nothing is exposed outside the
host machine, but port 8080 should be free before running.

The GUI/VM path executes reviewer supplied Windows installers inside a
virtual machine and requires KVM. None of this applies if you skip the
optional GUI path. No elevated privileges are required for the library
reproduction. The Docker path needs whatever privileges your Docker
installation already has.

## Installation

### Option A: native (recommended for the library reproduction)

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
   It fetches Python 3.13 automatically if not already present.
2. Clone this repository and enter it:

   ```bash
   git clone <repository-url> sbseg-artifact
   cd sbseg-artifact
   ```

3. Create the pinned virtual environment from the lockfile:

   ```bash
   uv sync
   ```

4. Only if you intend to run DSS natively, make sure a Java 21 JRE is on
   your `PATH`:

   ```bash
   java -version   # should report 21.x
   ```

   The pre built DSS jar is already in the repository, so no build step is
   normally needed.

### Option B: Docker (no local toolchain beyond Docker)

For the library verifier workflow, a self contained image bundles Python
3.13, uv, a JRE, and a freshly built DSS jar:

```bash
docker build -t sbseg-verifiers .
```

The build compiles the DSS jar from source in a Maven stage, so you do not
need Java, Maven, or a host built jar. This image supports `generate`, `run
pyhanko`, `run dss`, `list`, and `db ...`. It does not support the GUI
verifiers or the `vm ...` commands.

## Minimal Test

This quick test proves the installation is sound and surfaces most setup
problems (missing environment, port conflicts, DSS jar or Java issues). It
uses the built in smoke tests, three small curated cases, and finishes in
seconds. Use a throwaway database path so the committed results database is
left untouched.

Native:

```bash
# 1. Build the test corpus into a scratch database
uv run python src/main.py --db-path /tmp/minimal.db generate

# 2. Run the two headless library verifiers over the smoke tests only
uv run python src/main.py --db-path /tmp/minimal.db run pyhanko dss --mode smoke

# 3. Print the result matrix
uv run python src/main.py --db-path /tmp/minimal.db list
```

Expected: step 1 reports `Done. 118 test cases generated.`. Step 2 prints
each library's version and a short progress bar. Step 3 prints a table
whose last rows are `SMOKE_TEST_1`, `SMOKE_TEST_2`, `SMOKE_TEST_3` with a
filled in column per verifier that was run. A table with no traceback means
the toolchain, database, and verifier services all work.

If you only installed pyHanko, without Java 21, run `run pyhanko --mode
smoke` instead, dropping `dss`.

Docker equivalent:

```bash
docker run --rm -v sbseg-data:/data sbseg-verifiers generate
docker run --rm -v sbseg-data:/data sbseg-verifiers run pyhanko dss --mode smoke
docker run --rm -v sbseg-data:/data sbseg-verifiers list
```

### See the attack visually

No tooling required. Open the paper's headline example in any PDF viewer:
`examples/yatch-original.pdf` (unsigned), `examples/yatch-signed.pdf`
(legitimately signed), and `examples/yatch-asa.pdf` / `yatch-sfda.pdf` (the
same document after tampering). Their visible content differs from the
signed original, yet both still verify as validly signed. These four files
are static demo artifacts, there is no script that regenerates them.

## Experiments

The paper's central claim: for both attack classes, across a systematic
sweep of PDF permission configurations, a number of verifiers accept the
tampered document as valid, and some do so without warning the user. The
artifact reproduces this by generating every configuration, recording each
verifier's verdict, and surfacing the disagreements between the expected
result and what the verifier reported.

### Traceability

`src/tester_scripts/generate_test_cases.py` implements Algorithm 1 from the
paper, sweeping five dimensions (`mdp_level`, `is_cert_sig`,
`is_field_protected`, `is_stamp`, `change_page`) and emitting one test PDF
per combination for each attack (`attack_name` is `ASA` or `SFDA`), plus the
`SMOKE_TEST_*` sanity cases. The `is_cert_sig` and `mdp_level` pair maps
onto concrete PDF signature structure:

| is_cert_sig | mdp_level | Resulting PDF structure |
|---|---|---|
| True  | P    | Certification signature with DocMDP `/P` |
| False | P    | Approval signature with SigFieldLock `/P` |
| False | None | Approval signature, no permission control |

Each `ChainItem` in `src/modification_pipeline/` is one modification step
(add a signature, replace an appearance stream, move a widget to another
page, duplicate a field, strip a lock, and so on). A `Pipeline` chains them
and stores the resulting PDF plus its expected validity in the database,
the direct link from a paper claim to the bytes that exercise it.

### Experiment 1: library verifiers (fully automated, the reproducible claim)

Configuration and resources: Linux, or the Docker image, no GUI, no
licenses. Java 21 is needed only for DSS natively. Expected runtime:
generation takes about 10 to 20 seconds. `run pyhanko dss --mode full` (118
PDFs posted to each of two local services, 16 in parallel) took well under
a minute in verification, allow a couple of minutes on slower hardware.

Native:

```bash
uv run python src/main.py generate
uv run python src/main.py run pyhanko dss --mode full
uv run python src/main.py list
uv run python src/main.py list --disagree      # only rows where a verifier disagreed with the expected result
```

Docker:

```bash
docker run --rm -v sbseg-data:/data sbseg-verifiers generate
docker run --rm -v sbseg-data:/data sbseg-verifiers run pyhanko dss --mode full
docker run --rm -v sbseg-data:/data sbseg-verifiers list --disagree
```

`--mode full`, the default, runs the entire sweep. `--mode fast` runs a
single curated case per verifier for a quick signal.

Expected result: the `list` matrix has one column per verifier and one row
per test, tagged with the attack and the Algorithm 1 parameters. `list
--disagree` isolates the cases where a library accepted an expected invalid
tampered document, and whether it warned, the concrete instances of the
vulnerability the paper reports for pyHanko and DSS. To inspect an
individual case, export its PDF or dump the full evidence bundle:

```bash
uv run python src/main.py db export 42 --out /tmp/case-42.pdf   # write one test PDF
uv run python src/main.py db dump pyhanko                        # dump disagreements
```

### Experiment 2: GUI verifiers (partial reproduction, see SeloR scope)

This reproduces the desktop reader portion for the four automated readers
(Adobe Reader, Foxit, Master PDF Editor, Microsoft Edge) inside a
persistent Windows VM (Docker, Dockur, and KVM). This path is optional, is
not covered by the `sbseg-verifiers` Docker image, and its results are not
guaranteed to match the paper on reader versions other than those
originally tested, since vendors change verification behavior between
releases.

> **GUI automation is best-effort.** Unattended completion is not guaranteed.
> Adobe Reader/Acrobat in particular can display many installation-, account-,
> trial-, update-, default-app-, and state-dependent popups, especially shortly
> after installation. The scripts attempt to dismiss known dialogs through
> screenshot matching, but cannot reliably map every possible popup. Vendor UI
> and application-version updates may also invalidate the supplied image
> templates. If automation becomes blocked, inspect the VM, dismiss the unknown
> popup manually, and retry the verifier. These limitations apply only to the
> optional GUI path, not the headless pyHanko and DSS workflow.

Because the reader installers are proprietary and cannot be redistributed,
you must supply your own. Place them in `.vm/installers/`, git ignored,
named exactly `adobe.exe`, `foxit.exe`, `master_pdf_editor.msi`, and
`edge.exe`. Edge can reuse the copy bundled with Windows, so its installer
is optional. A different installed version than expected produces a
warning rather than an error.

```bash
uv run python src/main.py vm start            # boot the persistent Windows VM
uv run python src/main.py vm setup adobe      # install/configure a reader, accepts several names or 'all'
uv run python src/main.py run adobe --mode smoke --action-delay 0.5   # routed to the VM automatically
uv run python src/main.py vm stop             # stop, retaining installed state
```

`vm setup` and `run` accept multiple GUI slugs or `all`. On Linux, desktop
verifiers are sent to the VM automatically while library verifiers run
locally. `--action-delay` controls the seconds waited both before and after
each desktop GUI action; it defaults to `0.15` and does not affect library
verifiers. Run `uv run python src/main.py vm setup --help` for the exact
slug list. Installation and boot progress is viewable at
`http://127.0.0.1:8006`, the guest worker exposes a local HTTP API on
`127.0.0.1:${SBSEG_VM_API_PORT:-8765}`.

If you cannot run this path, the paper's GUI verifier evidence is already
committed under `src/screenshots/` (per verifier subdirectories with layer
1 and layer 2 screenshots for each recorded test), documenting the original
runs.

## License

This project is licensed under the MIT License. See the
[`LICENSE`](LICENSE) file at the repository root for the full text.
Citation metadata is provided in [`CITATION.cff`](CITATION.cff).
