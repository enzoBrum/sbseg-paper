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
and authenticity of a document, so that any non-permitted change, for
example altering the value of a contract or a health prescription,
invalidates the signature. This paper introduces two novel attack classes
that abuse flaws in the PDF specification to visually modify a page of a
signed document without invalidating the signature or warning the user:
Appearance Substitution Attack (ASA) and Signature Field Duplication Attack
(SFDA). While previous work explored incremental updates, this paper taps
into modifications of the signature field itself, a kind of update that had
not been fully explored. The evaluation covered 18 verifiers: 13 of 16 GUI
applications and both programming libraries were at least partially vulnerable
to one of the attack classes, for 15 of 18 affected verifiers overall. The
paper also proposes countermeasures and specification improvements.

Both attacks require only access to an already-signed PDF; the attacker does
not need the signer's private key, a trusted certificate, or access before
signing. ASA changes an existing signature field's `/AP` appearance and
`/Rect` placement. SFDA adds a field whose `/V` points to an existing legitimate
signature dictionary, inheriting its signer and certificate while using an
attacker-controlled appearance. Both changes are appended as incremental PDF
updates, leaving the originally signed bytes intact.

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
├── Dockerfile, compose.yaml     reproducible container environment
├── examples/                    the paper's "$1 Yacht" demo PDFs
├── paper-example/               standalone Alice/Bob pyHanko signing demo
├── src/
│   ├── main.py                  the Typer CLI, all commands below
│   ├── detect_attacks.py        structural ASA/SFDA detector
│   ├── signed_files.db          SQLite results database
│   ├── certs/                   6 synthetic self-signed test cert/key pairs
│   ├── unsigned-files/          base PDF that attacks are built from
│   ├── screenshots/             screenshot corpus of the original GUI runs
│   ├── modification_pipeline/   attack building blocks, one module per step
│   └── tester_scripts/
│       ├── generate_test_cases.py  sweeps the paper's test parameters
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
are only partially reproducible. The paper evaluated 16 GUI applications
(4 desktop and 12 web); only the 4 desktop readers are automated in this
repository's Windows VM tooling.
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

The paper's reference evaluation ran desktop and web verifiers on Windows 11
and library verifiers on NixOS 26. The container path is provided to make the
library environment portable across Linux hosts.

GUI verifier reproduction is optional and needs considerably more: a Linux
host with hardware virtualization (KVM), Docker, several GB of free disk for
a persistent Windows VM, and reviewer supplied installer binaries for the
desktop readers. It can be launched natively or through the Compose service
and is not required for the library SeloR claim.

## Dependencies

Runtime toolchain: Python 3.13, pinned in `.python-version`, and
[uv](https://docs.astral.sh/uv/), the package and environment manager used
throughout. It reads `pyproject.toml` and `uv.lock` and creates a fully
pinned virtual environment. Java 21 is required only for DSS natively; a
fresh clone also needs Maven and a JDK to build its jar. Neither is needed for
pyHanko or the Docker path, which builds DSS and bundles its own JRE.

Python packages are declared in `pyproject.toml`, exact versions locked in
`uv.lock`. Key ones: `pyhanko` (version 0.32.0 in the artifact lockfile;
the paper's evaluation records 0.32.1), `pyhanko-certvalidator`,
`pyhanko-cli`, `pymupdf` for PDF
preprocessing, `sqlalchemy` for the results database, `typer` and `rich`
for the CLI, `flask` and `requests` for the library verifier service and
client. GUI automation libraries (`pyautogui`, `opencv-python`, `mss`,
`pillow`, `pyscreeze`, `keyboard`, `psutil`) are also pulled in but are only
used by the Windows VM GUI path.

The DSS verifier is a small Spring Boot application in
`src/tester_scripts/library/dss/`. Its `target/` directory is git-ignored, so
a fresh clone needs either a native Maven build or the Docker image. Build it
natively with `mvn -q package -DskipTests` from that directory; there is no
`mvnw` wrapper. The Docker image compiles the jar from source automatically.

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
installation already has. The Compose service mounts the Docker socket so it
can manage the Windows VM; this gives the container control of the host Docker
daemon, so run only the repository image and code you trust.

## Installation

### Option A: native 

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
   It fetches Python 3.13 automatically if not already present.
2. Clone this repository and enter it:

   ```bash
   git clone https://github.com/enzoBrum/sbseg-paper.git sbseg-artifact
   cd sbseg-artifact
   ```

3. Create the pinned virtual environment from the lockfile:

   ```bash
   uv sync
   ```

4. Only if you intend to run DSS natively, install Maven and a Java 21 JDK,
   then build its jar once:

   ```bash
   java -version   # should report 21.x
   cd src/tester_scripts/library/dss
   mvn -q package -DskipTests
   cd ../../../..
   ```

   Java 21 is required at runtime as well. Docker users do not need a host JDK
   or Maven.

### Option B: Docker (no local toolchain beyond Docker)

For the library verifier workflow, a self contained image bundles Python
3.13, uv, a JRE, and a freshly built DSS jar:

```bash
docker compose build verifier
```

The build compiles the DSS jar from source in a Maven stage, so you do not
need Java, Maven, or a host built jar. It also includes the Docker CLI and
Compose plugin so GUI verifier commands can manage the Windows VM through the
mounted host socket. Arguments after the service name map directly to the
native CLI: replace `uv run python src/main.py` with the
`docker compose run --rm verifier` prefix.

## Minimal Test

This quick test proves the installation is sound and surfaces most setup
problems (missing environment, port conflicts, DSS jar or Java issues). It
uses three small curated cases, and finishes in
seconds. Use a throwaway database path so the committed results database is
left untouched.

Native:

```bash
# 1. Build the test corpus into a scratch database
uv run python src/main.py --db-path /tmp/minimal.db generate

# 2. Run the two headless library verifiers over the fast tests only
uv run python src/main.py --db-path /tmp/minimal.db run pyhanko dss --mode fast

# 3. Print the result matrix
uv run python src/main.py --db-path /tmp/minimal.db list
```

Expected: step 1 reports `Done. 118 test cases generated.`: 112 ASA/SFDA
attack cases plus 3 permission-baseline cases and 3 smoke cases. Step 2 prints,
for each library, a `Starting ... run (fast test #N)` line, the library's
version, and a short progress bar; `--mode fast` runs a single curated case per
verifier (test #2 for pyHanko, test #55 for DSS). Step 3 prints the result
matrix, in which only those two tests carry a filled in cell, each in its own
verifier column, and every other cell is blank. A table with no traceback means
the toolchain, database, and verifier services all work.

If you only installed pyHanko, without Java 21, run `run pyhanko --mode
fast` instead, dropping `dss`.

Docker equivalent:

```bash
docker compose run --rm verifier --db-path .sbseg-minimal.db generate
docker compose run --rm verifier --db-path .sbseg-minimal.db run pyhanko dss --mode fast
docker compose run --rm verifier --db-path .sbseg-minimal.db list
rm .sbseg-minimal.db
```

### See the attack visually

No tooling required. Open the paper's headline example in any PDF viewer:
`examples/yatch-original.pdf` (unsigned), `examples/yatch-signed.pdf`
(legitimately signed), and `examples/yatch-asa.pdf` / `yatch-sfda.pdf` (the
same document after tampering). Their visible content differs from the
signed original, yet both still verify as validly signed. These four files
are static demo artifacts, there is no script that regenerates them.

### Detect ASA and SFDA

The structural detector reports signature fields and PDF objects affected by
an Appearance Substitution Attack (ASA) or Signature Field Duplication Attack
(SFDA):

```bash
uv run python src/detect_attacks.py examples/yatch-signed.pdf \
    examples/yatch-asa.pdf examples/yatch-sfda.pdf
```

The signed PDF is reported as clean, while the other two files produce their
respective ASA and SFDA findings. Multiple PDFs can be checked in one command.
The process exits with status `0` when every file is clean, `1` when any attack
is detected, and `2` when no input files are supplied.

The detector identifies the structural mechanisms used by the attacks, not
malicious intent, so false positives are possible. A legitimate post-signing
change to a signature field's `/AP` or `/Rect` can be reported as ASA. A
legitimate producer that creates multiple fields referencing the same signature
dictionary can be reported as SFDA. Treat a finding as a reason for manual
inspection rather than standalone proof that a document was maliciously
altered.

## Experiments

The paper's central claim: for both attack classes, across a systematic
sweep of PDF permission configurations, a number of verifiers accept the
tampered document as valid, and some do so without warning the user. The
artifact reproduces this by generating every configuration, recording each
verifier's verdict, and surfacing the disagreements between the expected
result and what the verifier reported.

The paper separates GUI output into UI-Layer 1 (the prominent top-bar status)
and UI-Layer 2 (the per-signature details panel). Libraries expose one
API-Layer containing the verdict and modification report. In the CLI matrix,
`T` means valid without a modification warning, `W` means valid with a
modification warning, `F` means invalid, and `-` means that a layer does not
apply. GUI cells show Layer 1 followed by Layer 2; library cells use only the
first position. For ASA and SFDA rows, whose expected result is invalid, these
correspond respectively to the paper's vulnerable, partially vulnerable, and
secure classifications.

The aggregate paper snapshot is:

| Attack | GUI UI-Layer 1 vulnerable/partial | GUI UI-Layer 2 vulnerable/partial | Library API-Layer vulnerable/partial |
|---|---:|---:|---:|
| ASA | 13/16 | 13/16 | 1/2 |
| SFDA | 8/16 | 7/16 | 1/2 |

### Traceability

`src/tester_scripts/generate_test_cases.py` implements the paper's automated
test sweep across five dimensions (`mdp_level`, `is_cert_sig`,
`is_field_protected`, `is_stamp`, `change_page`) and emits one test PDF
per combination for each attack (`attack_name` is `ASA` or `SFDA`). This
produces the 112 crafted PDFs evaluated in the paper. Three `EXTRA_*`
permission baselines and three `SMOKE_TEST_*` sanity cases bring the repository
total to 118. The `is_cert_sig` and `mdp_level` pair maps
onto concrete PDF signature structure:

| is_cert_sig | mdp_level | Resulting PDF structure |
|---|---|---|
| True  | P    | Certification signature with DocMDP `/P` |
| False | P    | Approval signature with SigFieldLock `/P` |
| False | None | Approval signature, no permission control |

Generated signatures use the repository's self-issued certificates with
2048-bit RSA keys and SHA-256 signatures. These trust anchors are test-only and
must not be reused outside the artifact.

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
The paper's result table records pyHanko 0.32.1 and DSS 6.4; the artifact
currently pins pyHanko 0.32.0 and DSS 6.4, so reproduced results should be
treated as version-specific.

Native:

```bash
uv run python src/main.py --db-path /tmp/sbseg-full.db generate
uv run python src/main.py --db-path /tmp/sbseg-full.db run pyhanko dss --mode full
uv run python src/main.py --db-path /tmp/sbseg-full.db list
uv run python src/main.py --db-path /tmp/sbseg-full.db list --disagree
```

Docker:

```bash
docker compose run --rm verifier --db-path .sbseg-full.db generate
docker compose run --rm verifier --db-path .sbseg-full.db run pyhanko dss --mode full
docker compose run --rm verifier --db-path .sbseg-full.db list --disagree
```

The explicit database paths keep the committed result snapshot unchanged.
Remove `.sbseg-full.db` after the Compose run if you do not want to retain the
new results.

`--mode full`, the default, runs the entire sweep. `--mode fast` runs a
single curated case per verifier for a quick signal.

Expected result: the `list` matrix has one column per verifier and one row
per test, tagged with the attack and the paper's sweep parameters. `list
--disagree` isolates the cases where a library accepted an expected invalid
tampered document, and whether it warned, the concrete instances of the
vulnerability the paper reports for pyHanko and DSS. To inspect an
individual case, export its PDF or dump the full evidence bundle:

```bash
uv run python src/main.py --db-path /tmp/sbseg-full.db db export 42 --out /tmp/case-42.pdf
uv run python src/main.py --db-path /tmp/sbseg-full.db db dump pyhanko
```

### Experiment 2: GUI verifiers (partial reproduction, see SeloR scope)

This reproduces the desktop reader portion for the four automated readers
(Adobe Reader, Foxit, Master PDF Editor, Microsoft Edge) inside a
persistent Windows VM (Docker, Dockur, and KVM). This path is optional, and
its results are not guaranteed to match the paper on reader versions other
than those originally tested, since vendors change verification behavior
between releases.

NOTE: GUI automation is best-effort. Unattended completion is not guaranteed.
Adobe Reader/Acrobat in particular can display many installation-, account-,
trial-, update-, default-app-, and state-dependent popups, especially shortly
after installation. The scripts attempt to dismiss known dialogs through
screenshot matching, but cannot reliably map every possible popup. Vendor UI
and application-version updates may also invalidate the supplied image
templates. If automation becomes blocked, inspect the VM, dismiss the unknown
popup manually, and retry the verifier. These limitations apply only to the
optional GUI path, not the headless pyHanko and DSS workflow.

Because the reader installers are proprietary and cannot be redistributed,
you must supply your own. Place them in `.vm/installers/`, git ignored,
named exactly `adobe.exe`, `foxit.exe`, `master_pdf_editor.msi`, and
`edge.exe`. Edge can reuse the copy bundled with Windows, so its installer
is optional. A different installed version than expected produces a
warning rather than an error.

The desktop versions recorded in the paper are Adobe Acrobat 26.1.21662.0,
Foxit PDF Reader 2026.1.2.36540, Master PDF Editor 5.9.9.8, and Microsoft Edge
150.0.4078.105. Results from newer or older releases are not directly
comparable to that snapshot.

```bash
uv run python src/main.py vm start            # boot the persistent Windows VM
uv run python src/main.py vm setup adobe      # install/configure a reader, accepts several names or 'all'
uv run python src/main.py run adobe --action-delay 0.5   # routed to the VM automatically
uv run python src/main.py vm stop             # stop, retaining installed state
```

The same commands can use the Compose prefix, for example `docker compose run
--rm verifier run adobe --mode smoke`.

`vm setup` and `run` accept multiple GUI slugs or `all`. On Linux, desktop
verifiers are sent to the VM automatically while library verifiers run
locally. A GUI run starts the VM when necessary, waits for its worker health
check, and leaves it running until `vm stop`. `--action-delay` controls the
seconds waited both before and after each desktop GUI action; it defaults to
`0.2` and does not affect library verifiers. Run
`uv run python src/main.py vm setup --help` for the exact slug list.
Installation and boot progress is viewable at
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
