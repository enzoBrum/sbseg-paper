# sbseg-paper

## Windows desktop verifiers

Desktop verifiers can run in a persistent Windows VM using Docker, Dockur, and
KVM. The workflow is:

```bash
uv run python src/main.py vm start
uv run python src/main.py vm setup adobe
uv run python src/main.py run adobe --mode smoke
uv run python src/main.py vm stop
```

`setup` accepts multiple desktop verifier names or `all`. The root `run`
command also accepts multiple verifier names or `all`; desktop verifiers are
sent to the VM automatically, while library verifiers run locally. Run
`uv run python src/main.py vm setup --help` to list the GUI verifier slugs.

Place user-provided installers in `.vm/installers/` as `adobe.exe`, `foxit.exe`,
`master_pdf_editor.msi`, or `edge.exe`. Edge can use the copy included with
Windows, so its installer is optional. A different installed version produces a
warning.

The Windows worker exposes a synchronous HTTP API through
`127.0.0.1:${SBSEG_VM_API_PORT:-8765}`. Installer files, the SQLite database, and
screenshots use HTTP. The `Z:` share is only used to copy repository source and
refresh the supervised worker. The browser console is available at
`http://127.0.0.1:8006`.

## Docker (optional)

The native `uv run python src/main.py ...` workflow (above, and in
`CLAUDE.md`) remains the primary way to run this project and needs no
Docker. For the **library-verifier** workflow specifically
(`generate`, `run pyhanko`/`run dss`, `list`, `db ...`), a Dockerfile is
provided that bundles Python 3.13 + `uv`, a JRE, and a freshly built DSS jar,
so it can be run with no local toolchain setup beyond Docker itself:

```bash
docker build -t sbseg-verifiers .

docker run --rm -v sbseg-data:/data sbseg-verifiers generate
docker run --rm -v sbseg-data:/data sbseg-verifiers run pyhanko dss
docker run --rm -v sbseg-data:/data sbseg-verifiers list --disagree
docker run --rm -v sbseg-data:/data sbseg-verifiers db export 42
```

All commands run against `/data` inside the container — mount it (a named
volume, as above, or a host directory with `-v $(pwd)/data:/data`) to
persist `signed_files.db` and any exported/dumped files across runs. Set
`SBSEG_DB_PATH` to point at a different path inside `/data` if needed.

**Not supported in this image:** GUI verifiers (`adobe`, `foxit`,
`master_pdf_editor`, `edge`) and `vm ...` commands — those depend on the
separate Windows-VM infra described above (`vm/compose.yaml`), which this
image does not include.

Two pre-existing repo quirks the Dockerfile works around rather than relies
on: `src/tester_scripts/library/dss/target/demo-0.0.1-SNAPSHOT.jar` is
git-ignored (not actually committed, despite `CLAUDE.md`'s one-time build
instructions saying to commit it), and no `mvnw` wrapper exists in that
directory. The Docker build compiles the jar from source with a Maven base
image instead of depending on a host-built jar.
