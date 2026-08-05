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
