"""PDF Signature Attack Tester — CLI interface."""

from __future__ import annotations

from enum import Enum
import os
from pathlib import Path
import traceback
from typing import List, Optional

import typer
from rich.console import Console
from tester_scripts.gui.verifiers import REGISTRY as GUI_VERIFIERS
from tester_scripts.library.verifiers import REGISTRY as LIBRARY_VERIFIERS

from cli_render import (
    _is_disagreement_layered,
    _layer_disagrees,
    _render_matrix,
)

DEFAULT_DB = Path(
    os.environ.get("SBSEG_DB_PATH", Path(__file__).parent / "signed_files.db")
)

app = typer.Typer(
    help="Test PDF signature-field attack vectors across multiple verifiers.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    epilog=(
        "[bold]Typical flow:[/] [cyan]generate[/] → [cyan]run <verifier>[/] → [cyan]list[/]\n\n"
        "[bold]Examples:[/]\n\n"
        "  uv run python src/main.py generate\n\n"
        "  uv run python src/main.py run adobe --mode fast\n\n"
        "  uv run python src/main.py run pyhanko adobe --mode smoke\n\n"
        "  uv run python src/main.py list\n\n"
        "  uv run python src/main.py list --verifier adobe --disagree\n\n"
        "  uv run python src/main.py db export 42 --out /tmp/test.pdf\n\n"
        "  uv run python src/main.py --db-path /tmp/x.db generate"
    ),
)
vm_app = typer.Typer(
    help="Manage the Windows VM used by desktop GUI verifiers.",
    no_args_is_help=True,
)
db_app = typer.Typer(
    help="Export and manage persisted database results.",
    no_args_is_help=True,
)
app.add_typer(vm_app, name="vm", rich_help_panel="Windows VM")
app.add_typer(db_app, name="db", rich_help_panel="Database")

console = Console()

# Keep the VM command choices tied to the actual GUI verifier registry.
GUI_VERIFIER_HELP = (
    f"GUI verifier slugs: {', '.join(sorted(GUI_VERIFIERS))}; or 'all'."
)
AUTOMATED_VERIFIERS = frozenset(GUI_VERIFIERS) | frozenset(LIBRARY_VERIFIERS)
AUTOMATED_VERIFIER_HELP = (
    f"Automated verifier slugs: {', '.join(sorted(AUTOMATED_VERIFIERS))}; "
    "or 'all'."
)

# One expected-invalid case that each automated verifier has historically
# accepted. Foxit has no warning-free false acceptance, so it uses the closest
# available result instead.
FAST_TEST_IDS = {
    "adobe": 50,
    "foxit": 59,
    "master_pdf_editor": 18,
    "edge": 34,
    "pyhanko": 2,
    "dss": 55,
}


class Verifier(str, Enum):
    adobe = "adobe"
    foxit = "foxit"
    pyhanko = "pyhanko"
    dss = "dss"
    master_pdf_editor = "master_pdf_editor"
    edge = "edge"
    dss_web_demo = "dss_web_demo"
    iti = "iti"
    certisign = "certisign"
    digitalsign = "digitalsign"
    dvv = "dvv"
    bry = "bry"
    zapsign = "zapsign"
    clicksign = "clicksign"


class RunMode(str, Enum):
    full = "full"
    fast = "fast"
    smoke = "smoke"


@app.callback()
def setup(
    ctx: typer.Context,
    db_path: Path = typer.Option(
        DEFAULT_DB,
        "--db-path",
        help=(
            "SQLite database shared by all subcommands. "
            f"Defaults to [dim]{DEFAULT_DB}[/dim]."
        ),
        show_default=False,
    ),
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = db_path

    # VM lifecycle commands do not need to open the research database.
    if ctx.invoked_subcommand != "vm":
        from modification_pipeline.model import init

        init(db_path)


def _db_path(ctx: typer.Context) -> Path:
    root = ctx.find_root()
    assert isinstance(root.obj, dict)
    return Path(root.obj["db_path"])


def _vm_call(function, *args):
    try:
        return function(*args)
    except Exception as error:
        console.print(f"[red]VM error:[/] {error}\n{traceback.format_exc()}")
        raise typer.Exit(1)


@vm_app.command("start")
def vm_start(
    timeout: float = typer.Option(
        1800,
        "--timeout",
        min=1,
        help="Seconds to wait for unattended Windows setup and the guest worker.",
    ),
) -> None:
    """Start the persistent VM and wait for its interactive desktop."""
    from windows_vm.vm import create_vm, init_vm

    _vm_call(create_vm)
    console.print(
        "[green]Windows VM started.[/] Installation/boot progress: "
        "[link=http://127.0.0.1:8006]http://127.0.0.1:8006[/link]"
    )
    ready = _vm_call(init_vm, timeout)
    console.print(
        f"[green]Windows guest ready.[/] user={ready.get('user')} "
        f"display={ready.get('screen_width')}x{ready.get('screen_height')} "
        f"dpi={ready.get('dpi')}"
    )


@vm_app.command("setup", no_args_is_help=True)
def vm_setup(
    targets: List[str] = typer.Argument(..., help=GUI_VERIFIER_HELP),
    timeout: float = typer.Option(
        3600, "--timeout", min=1, help="Seconds to wait for preparation."
    ),
) -> None:
    """Install and configure selected desktop verifiers in Windows."""
    from windows_vm.vm import prepare_vm

    warnings = _vm_call(prepare_vm, targets, timeout)
    for warning in warnings:
        console.print(f"[yellow]Warning:[/] {warning}")
    console.print("[green]VM setup complete.[/]")


@vm_app.command("stop")
def vm_stop() -> None:
    """Stop Windows while preserving its installed state and disk."""
    from windows_vm.vm import stop_vm

    _vm_call(stop_vm)
    console.print("[green]Windows VM stopped; persistent state was retained.[/]")


# ---------------------------------------------------------------------------
# Workflow commands
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Workflow")
def generate() -> None:
    """Generate all test cases and persist to DB.

    Sweeps the full parameter space from Algorithm 1 (mdp_level ×
    is_cert_sig × is_field_protected × is_stamp × change_page) and writes
    one [ModificationTest] row per pipeline. Run this before [cyan]run[/].
    """
    from rich.progress import track

    from tester_scripts.generate_test_cases import gen_test_cases

    cases = gen_test_cases()
    for pipeline in track(cases, description="Generating..."):
        pipeline.apply(None)
    console.print(f"[green]Done.[/] {len(cases)} test cases generated.")


@app.command(rich_help_panel="Workflow", no_args_is_help=True)
def run(
    ctx: typer.Context,
    targets: List[str] = typer.Argument(..., help=AUTOMATED_VERIFIER_HELP),
    mode: RunMode = typer.Option(
        RunMode.full,
        "--mode",
        help="Test selection: full batch, verifier-specific fast case, or smoke tests.",
    ),
    action_delay: float = typer.Option(
        0.05,
        "--action-delay",
        min=0,
        help="Seconds before and after each desktop GUI action.",
    ),
    timeout: float = typer.Option(
        14400,
        "--timeout",
        min=1,
        help="Seconds to wait when desktop verifiers run in the VM.",
    ),
) -> None:
    """Run one or more desktop or library verifiers."""
    from modification_pipeline.model import ModificationTest
    from tester_scripts.tester import test

    if targets == ["all"]:
        targets = sorted(AUTOMATED_VERIFIERS)
    if not targets or "all" in targets or set(targets) - AUTOMATED_VERIFIERS:
        raise typer.BadParameter(AUTOMATED_VERIFIER_HELP)
    # NOTE: not `list(...)` — the `list` CLI command defined below shadows
    # the builtin at module scope, so a real `list()` call here would
    # actually invoke the typer command instead.
    targets = [*dict.fromkeys(targets)]

    local_targets = targets if os.name == "nt" else [
        target for target in targets if target in LIBRARY_VERIFIERS
    ]
    vm_targets = [] if os.name == "nt" else [
        target for target in targets if target in GUI_VERIFIERS
    ]

    if os.name == "nt" and any(
        target in GUI_VERIFIERS for target in local_targets
    ):
        from tester_scripts.gui.gui_tester import set_action_delay

        set_action_delay(action_delay)

    for target in local_targets:
        where_clause = None
        description = "full batch"
        if mode == RunMode.fast:
            test_id = FAST_TEST_IDS[target]
            where_clause = ModificationTest.id == test_id
            description = f"fast test #{test_id}"
        elif mode == RunMode.smoke:
            where_clause = ModificationTest.attack_name.like("SMOKE_TEST_%")
            description = "smoke tests"
        console.print(f"Starting [bold]{target}[/] run ({description})...")
        try:
            test(target, where_clause=where_clause)
        except Exception as error:
            console.print(f"[red]{target} failed:[/] {error}")
            raise typer.Exit(1)

    if vm_targets:
        from windows_vm.vm import run_vm

        console.print(
            f"Desktop action delay: {action_delay:g}s before and after each action."
        )
        _vm_call(
            run_vm,
            vm_targets,
            _db_path(ctx),
            mode.value,
            action_delay,
            timeout,
        )
        console.print("[green]VM verifier run complete.[/]")


# ---------------------------------------------------------------------------
# Inspect commands
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Inspect")
def list(
    verifier: Optional[Verifier] = typer.Option(
        None,
        "--verifier",
        "-v",
        help="Show only this verifier and add its match column.",
    ),
    disagree: bool = typer.Option(
        False,
        "--disagree",
        "-d",
        help="Show only tests whose recorded result disagrees with the expected result.",
    ),
) -> None:
    """Show recorded test results as a matrix."""
    from sqlalchemy import select

    from modification_pipeline.model import ModificationTest, get_session

    with get_session() as session:
        rows = (
            session.execute(select(ModificationTest).order_by(ModificationTest.id))
            .scalars()
            .all()
        )
        _render_matrix(
            rows,
            verifier.value if verifier else None,
            disagree,
            [item.value for item in Verifier],
            console,
        )


@db_app.command("record-web")
def db_record_web(
    verifier: Verifier = typer.Argument(
        ..., help="Web verifier slug (web-category verifiers only)."
    ),
    test_id: int = typer.Argument(..., help="ModificationTest id."),
    l1_valid: bool = typer.Option(
        ...,
        "--l1-valid/--no-l1-valid",
        help="Layer 1: top-bar banner reported the signature valid.",
    ),
    l1_warn: bool = typer.Option(
        False,
        "--l1-warn/--no-l1-warn",
        help="Layer 1: banner flagged a post-signing modification.",
    ),
    l2_valid: bool = typer.Option(
        ...,
        "--l2-valid/--no-l2-valid",
        help="Layer 2: detail panel reported the signature valid.",
    ),
    l2_warn: bool = typer.Option(
        False,
        "--l2-warn/--no-l2-warn",
        help="Layer 2: detail panel flagged a post-signing modification.",
    ),
) -> None:
    """Manually record a result from a web verifier (no automation).

    Web verifiers are tested in a browser; this command persists one verdict
    into the DB so it shows up in [cyan]list[/] alongside automated verifiers.
    """
    from sqlalchemy import select

    from modification_pipeline.model import (
        ModificationTest,
        ModificationVerifierAssociation,
        Verifier as VerifierRow,
        VerifierTest,
        get_session,
    )

    with get_session() as session:
        v_row = session.execute(
            select(VerifierRow).where(VerifierRow.name == verifier.value)
        ).scalar_one_or_none()
        if v_row is None:
            console.print(f"[red]Verifier '{verifier.value}' not seeded in DB.[/]")
            raise typer.Exit(1)
        if v_row.category != "web":
            console.print(
                f"[red]'{verifier.value}' is not a web verifier "
                f"(category={v_row.category!r}). Use `run` instead.[/]"
            )
            raise typer.Exit(1)

        t = session.get(ModificationTest, test_id)
        if t is None:
            console.print(f"[red]Test {test_id} not found.[/]")
            raise typer.Exit(1)

        vt = VerifierTest(
            name=verifier.value,
            verifier_id=v_row.id,
            result_layer_1=l1_valid,
            warn_modified_layer_1=l1_warn,
            result_layer_2=l2_valid,
            warn_modified_layer_2=l2_warn,
        )
        session.add(vt)
        session.add(
            ModificationVerifierAssociation(verifier_test=vt, modification_test=t)
        )
        session.commit()

    console.print(
        f"Recorded {verifier.value} verdict for test #{test_id}: "
        f"L1=(valid={l1_valid}, warn={l1_warn}), "
        f"L2=(valid={l2_valid}, warn={l2_warn})."
    )


@db_app.command("version")
def db_version(
    verifier: Verifier = typer.Argument(..., help="Verifier slug."),
    version: str = typer.Argument(..., help="Version string to store (e.g. '6.3')."),
) -> None:
    """Set the version string for a verifier in the DB."""
    from sqlalchemy import select

    from modification_pipeline.model import Verifier as VerifierRow, get_session

    with get_session() as session:
        row = session.execute(
            select(VerifierRow).where(VerifierRow.name == verifier.value)
        ).scalar_one_or_none()
        if row is None:
            console.print(f"[red]Verifier '{verifier.value}' not found in DB.[/]")
            raise typer.Exit(1)
        row.version = version
        session.commit()
    console.print(f"Set [bold]{verifier.value}[/] version → [cyan]{version}[/].")


@db_app.command("export")
def db_export(
    test_id: int = typer.Argument(
        ..., help="ID of the test whose PDF to save (see [cyan]list[/])."
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        help="Destination path. Defaults to [dim]<cwd>/<id>.pdf[/dim].",
        show_default=False,
    ),
) -> None:
    """Save a test's PDF to disk for manual inspection."""
    from modification_pipeline.model import ModificationTest, get_session

    with get_session() as session:
        t = session.get(ModificationTest, test_id)
        if t is None:
            console.print(f"[red]Test {test_id} not found.[/]")
            raise typer.Exit(1)
        blob = t.fileblob

    dest = out or Path.cwd() / f"{test_id}.pdf"
    dest.write_bytes(blob)
    console.print(f"Wrote [cyan]{dest}[/]")


@db_app.command("dump")
def db_dump(
    verifier: Verifier = typer.Argument(
        ..., help="Verifier slug whose disagreements to dump."
    ),
    out: Path = typer.Option(
        Path("failures"),
        "--out",
        help="Root output directory. Per-test subdirs are created inside.",
    ),
) -> None:
    """Dump screenshots, chain description, and PDF for each failing test.

    A test is 'failing' when the verifier's verdict disagrees with the
    expected result. For each such test a subdirectory
    [dim]{out}/{verifier}/{test_id}/[/dim] is created containing:

      l1.png      — layer-1 screenshot (if captured)
      l2.png      — layer-2 screenshot (if captured)
      chain.txt   — attack chain steps, parameters, and verdict summary
      test.pdf    — the modified PDF blob
    """
    from sqlalchemy import select

    from modification_pipeline.model import ModificationTest, get_session

    slug = verifier.value
    count = 0

    with get_session() as session:
        rows = (
            session.execute(select(ModificationTest).order_by(ModificationTest.id))
            .scalars()
            .all()
        )

        for t in rows:
            if not _is_disagreement_layered(t, slug):
                continue

            vt = next(
                (
                    a.verifier_test
                    for a in t.tested_verifiers_assoc
                    if a.verifier_test.name == slug
                ),
                None,
            )
            if vt is None:
                continue

            dest = out / slug / str(t.id)
            dest.mkdir(parents=True, exist_ok=True)

            if vt.screenshot_layer_1 is not None:
                (dest / "l1.png").write_bytes(vt.screenshot_layer_1)
            if vt.screenshot_layer_2 is not None:
                (dest / "l2.png").write_bytes(vt.screenshot_layer_2)

            (dest / "test.pdf").write_bytes(t.fileblob)

            lines = [
                f"test_id:    {t.id}",
                f"attack:     {t.attack_name or '-'}",
                f"expected:   {'valid' if t.expected_result else 'invalid'}",
                f"l1_result:  {vt.result_layer_1}  warn={vt.warn_modified_layer_1}",
                f"l2_result:  {vt.result_layer_2}  warn={vt.warn_modified_layer_2}",
                f"l1_disagree:{_layer_disagrees(vt, t.expected_result, 1)}",
                f"l2_disagree:{_layer_disagrees(vt, t.expected_result, 2)}",
                "",
                "chain:",
            ]
            for a in sorted(t.associations, key=lambda a: a.chain_item.idx):
                ci = a.chain_item
                lines.append(f"  {ci.idx}. {ci.item_name}")
                for field in (
                    "mdp_perms",
                    "certify",
                    "field_mdp_action",
                    "field_mdp_include_sigfield",
                    "stamp_enable",
                    "place_on_different_page",
                    "target_page_index",
                    "sig_field_name",
                ):
                    val = getattr(ci, field)
                    if val is not None:
                        lines.append(f"       {field}={val}")

            (dest / "chain.txt").write_text("\n".join(lines), encoding="utf-8")
            count += 1

    console.print(f"Dumped [bold]{count}[/] failing test(s) to [cyan]{out / slug}[/].")


@db_app.command("clear")
def db_clear(
    verifier: Verifier = typer.Argument(
        ..., help="Verifier slug whose results to delete."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompt."
    ),
) -> None:
    """Delete all stored results for a verifier from the DB.

    Removes every [VerifierTest] row (and its association rows) recorded
    under the given verifier slug. Useful before re-running a verifier with
    a new version, or to discard a bad batch.
    """
    from sqlalchemy import delete, select

    from modification_pipeline.model import (
        ModificationVerifierAssociation,
        VerifierTest,
        get_session,
    )

    with get_session() as session:
        vt_ids = (
            session.execute(
                select(VerifierTest.id).where(VerifierTest.name == verifier.value)
            )
            .scalars()
            .all()
        )

        if not vt_ids:
            console.print(f"[yellow]No results found for '{verifier.value}'.[/]")
            raise typer.Exit(0)

        console.print(
            f"Will delete [bold]{len(vt_ids)}[/] result(s) for '{verifier.value}'."
        )
        if not yes:
            typer.confirm("Proceed?", abort=True)

        session.execute(
            delete(ModificationVerifierAssociation).where(
                ModificationVerifierAssociation.idB.in_(vt_ids)
            )
        )
        session.execute(
            delete(VerifierTest).where(VerifierTest.id.in_(vt_ids))
        )
        session.commit()

    console.print(f"[green]Deleted {len(vt_ids)} result(s) for '{verifier.value}'.[/]")


if __name__ == "__main__":
    app()
