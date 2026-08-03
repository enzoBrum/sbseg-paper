"""PDF Signature Attack Tester — CLI interface."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cli_render import (
    _agg_layer_glyph,
    _chain_params,
    _is_disagreement_layered,
    _layer_disagrees,
    _layer_glyph,
    _matrix_cell,
    _render_matrix,
    _render_sum_matrix,
)

DEFAULT_DB = Path(__file__).parent / "signed_files.db"

app = typer.Typer(
    help="Test PDF signature-field attack vectors across multiple verifiers.",
    no_args_is_help=True,
    rich_markup_mode="rich",
    epilog=(
        "[bold]Typical flow:[/] [cyan]generate[/] → [cyan]verify <verifier>[/] → [cyan]analyze[/]\n\n"
        "[bold]Examples:[/]\n\n"
        "  uv run python src/main.py generate\n\n"
        "  uv run python src/main.py verify adobe\n\n"
        "  uv run python src/main.py analyze\n\n"
        "  uv run python src/main.py analyze --verifier adobe\n\n"
        "  uv run python src/main.py list\n\n"
        "  uv run python src/main.py list --verifier adobe --disagree\n\n"
        "  uv run python src/main.py list --matrix --disagree\n\n"
        "  uv run python src/main.py list --sum-matrix\n\n"
        "  uv run python src/main.py save 42 --out /tmp/test.pdf\n\n"
        "  uv run python src/main.py --db-path /tmp/x.db generate"
    ),
)

console = Console()


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


@app.callback()
def setup(
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
    from modification_pipeline.model import init

    init(db_path)


# ---------------------------------------------------------------------------
# Workflow commands
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Workflow")
def generate() -> None:
    """Generate all test cases and persist to DB.

    Sweeps the full parameter space from Algorithm 1 (mdp_level ×
    is_cert_sig × is_field_protected × is_stamp × change_page) and writes
    one [ModificationTest] row per pipeline. Run this before [cyan]verify[/].
    """
    from rich.progress import track

    from tester_scripts.generate_test_cases import gen_test_cases

    cases = gen_test_cases()
    for pipeline in track(cases, description="Generating..."):
        pipeline.apply(None)
    console.print(f"[green]Done.[/] {len(cases)} test cases generated.")


@app.command(rich_help_panel="Workflow")
def verify(
    verifier: Verifier = typer.Argument(
        ...,
        help="PDF verifier to run the full test batch through.",
    ),
    smoke: bool = typer.Option(
        False,
        "--smoke",
        help="Run only the 3 SMOKE_TEST_* tests instead of the full batch.",
    ),
) -> None:
    """Run every test in the DB through a verifier and record the results.

    GUI verifiers (adobe, foxit, etc) drive the reader via
    pyautogui and capture screenshots. Library verifiers (pyhanko, dss)
    POST each PDF to the service running on localhost:8080.

    Use [cyan]--smoke[/] for a fast 3-test sanity check (SMOKE_TEST_1/2/3).
    """
    from tester_scripts.tester import test

    if smoke:
        from modification_pipeline.model import ModificationTest

        console.print(f"Starting [bold]{verifier.value}[/] run (smoke tests only)...")
        test(
            verifier.value,
            where_clause=ModificationTest.attack_name.like("SMOKE_TEST_%"),
        )
    else:
        console.print(f"Starting [bold]{verifier.value}[/] run (full batch)...")
        test(verifier.value)


# ---------------------------------------------------------------------------
# Inspect commands
# ---------------------------------------------------------------------------


@app.command(rich_help_panel="Inspect")
def list(
    verifier: Optional[Verifier] = typer.Option(
        None,
        "--verifier",
        "-v",
        help="Show verdict for this verifier; add result/match columns.",
    ),
    disagree: bool = typer.Option(
        False,
        "--disagree",
        "-d",
        help="Print one panel per disagreement with full chain and all verifier results.",
    ),
    matrix: bool = typer.Option(
        False,
        "--matrix",
        "-m",
        help="Wide table: Algorithm-1 params + one column per verifier (filterable with --disagree).",
    ),
    extras: bool = typer.Option(
        False,
        "--extras",
        "-x",
        help="Show only the EXTRA_P1/P2/P3 DocMDP probe tests in a simple table.",
    ),
    sum_matrix: bool = typer.Option(
        False,
        "--sum-matrix",
        "-s",
        help="One row per verifier with the best-ranked ASA and SFDA outcome and its params.",
    ),
) -> None:
    """List all persisted tests with their attack type and current verdicts.

    Without flags: prints a summary table (EXTRA_P* tests hidden).
    With [cyan]--verifier[/]: adds result and match columns for that verifier.
    With [cyan]--disagree[/]: prints one panel per failing test showing the full
    modification chain and all verifier results. Combine with [cyan]--verifier[/]
    to restrict panels to tests that disagree with a specific verifier.
    With [cyan]--matrix[/]: wide table with one row per test, columns for every
    Algorithm-1 parameter (mdp, cert, prot, stamp, chgpg) and one column per
    verifier. Combine with [cyan]--disagree[/] to filter rows to disagreements,
    and [cyan]--verifier[/] to narrow verifier columns to a single focal one
    plus a match column.
    With [cyan]--extras[/]: simple table showing only the three DocMDP probe tests.
    With [cyan]--sum-matrix[/]: one row per verifier, showing the best-ranked
    ASA and SFDA outcome (rank order TT>TW>TF>WT>WW>WF>FT>FW>FF, missing
    layer ignored) and the params of the winning test. Mutually exclusive with
    the other flags.
    """
    from sqlalchemy import select

    from modification_pipeline.model import ModificationTest, get_session

    if sum_matrix and (matrix or extras or disagree or verifier is not None):
        console.print(
            "[red]--sum-matrix cannot be combined with "
            "--matrix, --extras, --disagree, or --verifier.[/]"
        )
        raise typer.Exit(1)

    with get_session() as session:
        if extras:
            stmt = (
                select(ModificationTest)
                .where(ModificationTest.attack_name.like("EXTRA_%"))
                .order_by(ModificationTest.id)
            )
        elif sum_matrix:
            stmt = (
                select(ModificationTest)
                .where(ModificationTest.attack_name.in_(["ASA", "SFDA"]))
                .order_by(ModificationTest.id)
            )
        else:
            stmt = (
                select(ModificationTest)
                .where(~ModificationTest.attack_name.like("EXTRA_%"))
                .order_by(ModificationTest.id)
            )
        rows = session.execute(stmt).scalars().all()

        if sum_matrix:
            from modification_pipeline.model import Verifier as VerifierRow
            v_rows = session.execute(select(VerifierRow)).scalars().all()
            meta = {r.name: (r.category, r.version, r.url) for r in v_rows}
            _render_sum_matrix(rows, [v.value for v in Verifier], console, verifier_meta=meta)
            return

        if extras:
            all_slugs = [v.value for v in Verifier]
            table = Table(title="DocMDP Probe Tests")
            table.add_column("id", style="dim")
            table.add_column("attack")
            table.add_column("expected")
            for slug in all_slugs:
                table.add_column(slug)
            table.add_column("match")

            for t in rows:
                expected_str = "valid" if t.expected_result else "invalid"
                vt_by_name = {
                    a.verifier_test.name: a.verifier_test
                    for a in t.tested_verifiers_assoc
                }
                any_tested = bool(vt_by_name)
                any_disagree = any(
                    _layer_disagrees(vt, t.expected_result, 1)
                    or _layer_disagrees(vt, t.expected_result, 2)
                    for vt in vt_by_name.values()
                )
                if not any_tested:
                    match_str = "[dim]-[/]"
                elif any_disagree:
                    match_str = "[red]F[/]"
                else:
                    match_str = "[green]T[/]"

                row = [str(t.id), t.attack_name or "-", expected_str]
                for slug in all_slugs:
                    row.append(_matrix_cell(vt_by_name.get(slug)))
                row.append(match_str)
                table.add_row(*row)

            console.print(table)
            return

        if matrix:
            _render_matrix(
                rows,
                verifier.value if verifier else None,
                disagree,
                [v.value for v in Verifier],
                console,
            )
            return

        focal_name = verifier.value if verifier else None

        if not disagree:
            title = "Tests" if verifier is None else f"Tests — {verifier.value}"
            table = Table(title=title)
            table.add_column("id", style="dim")
            table.add_column("attack")
            table.add_column("expected")
            if verifier is not None:
                table.add_column("L1")
                table.add_column("L2")
                table.add_column("match")
            else:
                table.add_column("tested", justify="right")
                table.add_column("L1", justify="center")
                table.add_column("L2", justify="center")

            for t in rows:
                expected_str = "valid" if t.expected_result else "invalid"
                if verifier is not None:
                    vt = next(
                        (
                            a.verifier_test
                            for a in t.tested_verifiers_assoc
                            if a.verifier_test.name == verifier.value
                        ),
                        None,
                    )
                    l1_str = _layer_glyph(
                        vt.result_layer_1 if vt else None,
                        vt.warn_modified_layer_1 if vt else None,
                    )
                    l2_str = _layer_glyph(
                        vt.result_layer_2 if vt else None,
                        vt.warn_modified_layer_2 if vt else None,
                    )
                    if vt is None:
                        match_str = "[dim]-[/]"
                    else:
                        l1_dis = _layer_disagrees(vt, t.expected_result, 1)
                        l2_dis = _layer_disagrees(vt, t.expected_result, 2)
                        has_any = (
                            vt.result_layer_1 is not None
                            or vt.result_layer_2 is not None
                        )
                        if l1_dis or l2_dis:
                            match_str = "[red]F[/]"
                        elif has_any:
                            match_str = "[green]T[/]"
                        else:
                            match_str = "[dim]-[/]"
                    table.add_row(
                        str(t.id),
                        t.attack_name or "-",
                        expected_str,
                        l1_str,
                        l2_str,
                        match_str,
                    )
                else:
                    vts = [a.verifier_test for a in t.tested_verifiers_assoc]
                    l1_str = _agg_layer_glyph(vts, t.expected_result, 1)
                    l2_str = _agg_layer_glyph(vts, t.expected_result, 2)
                    table.add_row(
                        str(t.id),
                        t.attack_name or "-",
                        expected_str,
                        str(len(vts)) if vts else "[dim]0[/]",
                        l1_str,
                        l2_str,
                    )

            console.print(table)
            return

        # --disagree: one panel per failing test
        count = 0
        for t in rows:
            if not _is_disagreement_layered(t, focal_name):
                continue

            all_vts = [a.verifier_test for a in t.tested_verifiers_assoc]

            expected_display = (
                "[green]valid[/]" if t.expected_result else "[red]invalid[/]"
            )
            lines: list[str] = [f"expected: {expected_display}"]  # type: ignore

            if verifier is not None:
                focal = next(vt for vt in all_vts if vt.name == verifier.value)
                l1 = _layer_glyph(focal.result_layer_1, focal.warn_modified_layer_1)
                l2 = _layer_glyph(focal.result_layer_2, focal.warn_modified_layer_2)
                lines.append(f"result:   L1 {l1}  L2 {l2}")

            if all_vts:
                lines += ["", "verifiers:"]
                for vt in sorted(all_vts, key=lambda v: v.name):
                    l1 = _layer_glyph(vt.result_layer_1, vt.warn_modified_layer_1)
                    l2 = _layer_glyph(vt.result_layer_2, vt.warn_modified_layer_2)
                    lines.append(f"  {vt.name:<16} L1 {l1}  L2 {l2}")

            chain_lines: list[str] = []  # type: ignore
            for a in sorted(t.associations, key=lambda a: a.chain_item.idx):
                ci = a.chain_item
                chain_lines.append(f"  {ci.idx}. {ci.item_name}")
                params = _chain_params(ci)
                if params:
                    chain_lines.append(params)

            lines += ["", "chain:"]
            lines += chain_lines if chain_lines else ["  (none)"]

            console.print(
                Panel(
                    "\n".join(lines),
                    title=f"[bold]#{t.id}[/] {t.attack_name or ''}",
                    expand=False,
                )
            )
            count += 1

        if count == 0:
            suffix = f" for '{focal_name}'" if focal_name else ""
            console.print(f"[green]No disagreements{suffix}.[/]")
        else:
            console.print(f"[dim]{count} disagreement(s).[/]")


@app.command("enter-web-result", rich_help_panel="Workflow")
def enter_web_result(
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
    into the DB so it shows up in [cyan]list[/] / [cyan]analyze[/] alongside
    automated verifiers.
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
                f"(category={v_row.category!r}). Use `verify` instead.[/]"
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


@app.command("set-verifier-version", rich_help_panel="Workflow")
def set_verifier_version(
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


@app.command(rich_help_panel="Inspect")
def save(
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


@app.command("dump-failures", rich_help_panel="Inspect")
def dump_failures(
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

    from cli_render import _is_disagreement_layered, _layer_disagrees
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


@app.command("clear-verifier", rich_help_panel="Workflow")
def clear_verifier(
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
