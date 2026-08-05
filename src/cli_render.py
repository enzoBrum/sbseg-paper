from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from rich.console import Console
from rich.table import Table

from modification_pipeline.model import ModificationTest, VerifierTest


def _layer_glyph(result: Optional[bool], warn_modified: Optional[bool]) -> str:
    if result is None:
        return "[dim]-[/]"
    if result and warn_modified:
        return "[yellow]W[/]"
    return "[green]T[/]" if result else "[red]F[/]"


def _matrix_cell(vt: Optional[VerifierTest]) -> str:
    if vt is None:
        return "[dim]--[/]"
    return _layer_glyph(vt.result_layer_1, vt.warn_modified_layer_1) + _layer_glyph(
        vt.result_layer_2, vt.warn_modified_layer_2
    )


def _has_result(vt: Optional[VerifierTest]) -> bool:
    return vt is not None and (
        vt.result_layer_1 is not None or vt.result_layer_2 is not None
    )


def _algorithm1_params(t: ModificationTest) -> dict:
    add_sig = next(
        a.chain_item
        for a in t.associations
        if a.chain_item.item_name == "CreateSignature"
    )
    return {
        "mdp": add_sig.mdp_perms,
        "cert": add_sig.certify,
        "prot": add_sig.field_mdp_include_sigfield,
        "stamp": add_sig.stamp_enable,
        "chgpg": any(
            a.chain_item.item_name in ("ASA", "SFDA")
            and a.chain_item.place_on_different_page is True
            for a in t.associations
        ),
    }


def _layer_disagrees(vt: VerifierTest, expected: bool, layer: int) -> bool:
    result = getattr(vt, f"result_layer_{layer}")
    warning = getattr(vt, f"warn_modified_layer_{layer}")
    if result is None:
        return False
    return result != expected or (result and bool(warning))


def _is_disagreement_layered(
    test: ModificationTest, verifier_name: Optional[str]
) -> bool:
    results = [a.verifier_test for a in test.tested_verifiers_assoc]
    if verifier_name is not None:
        results = [result for result in results if result.name == verifier_name]
    return any(
        _layer_disagrees(result, test.expected_result, 1)
        or _layer_disagrees(result, test.expected_result, 2)
        for result in results
    )


def _render_matrix(
    rows: Sequence[ModificationTest],
    verifier_name: Optional[str],
    disagree: bool,
    all_slugs: list[str],
    console: Console,
) -> None:
    prepared: list[tuple[ModificationTest, dict[str, VerifierTest]]] = []
    for test in rows:
        results = {
            association.verifier_test.name: association.verifier_test
            for association in test.tested_verifiers_assoc
        }
        visible = (
            [results.get(verifier_name)]
            if verifier_name is not None
            else list(results.values())
        )
        if not any(_has_result(result) for result in visible):
            continue
        if disagree and not _is_disagreement_layered(test, verifier_name):
            continue
        prepared.append((test, results))

    if verifier_name is not None:
        slugs = [verifier_name]
    else:
        slugs = [
            slug
            for slug in all_slugs
            if any(_has_result(results.get(slug)) for _, results in prepared)
        ]

    if not prepared or not slugs:
        if disagree:
            suffix = f" for '{verifier_name}'" if verifier_name else ""
            console.print(f"[green]No disagreements{suffix}.[/]")
        else:
            suffix = f" for '{verifier_name}'" if verifier_name else ""
            console.print(f"[yellow]No recorded results{suffix}.[/]")
        return

    table = Table(
        title=(
            "Tests"
            if verifier_name is None
            else f"Tests — {verifier_name}"
        )
    )
    table.add_column("id", style="dim")
    table.add_column("attack")
    table.add_column("mdp")
    table.add_column("cert")
    table.add_column("prot")
    table.add_column("stamp")
    table.add_column("chgpg")
    table.add_column("expected")
    for slug in slugs:
        table.add_column(slug)
    if verifier_name is not None:
        table.add_column("match")

    def boolean(value: Optional[bool]) -> str:
        if value is None:
            return "-"
        return "T" if value else "F"

    for test, results in prepared:
        params = _algorithm1_params(test)
        row = [
            str(test.id),
            test.attack_name or "-",
            "None" if params["mdp"] is None else str(params["mdp"]),
            boolean(params["cert"]),
            boolean(params["prot"]),
            boolean(params["stamp"]),
            boolean(params["chgpg"]),
            "valid" if test.expected_result else "invalid",
        ]
        row.extend(_matrix_cell(results.get(slug)) for slug in slugs)
        if verifier_name is not None:
            result = results[verifier_name]
            mismatch = _layer_disagrees(
                result, test.expected_result, 1
            ) or _layer_disagrees(result, test.expected_result, 2)
            row.append(
                "[yellow]disagree[/]" if mismatch else "[green]agree[/]"
            )
        table.add_row(*row)

    console.print(table)
