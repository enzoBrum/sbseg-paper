from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from rich.console import Console
from rich.table import Table

from modification_pipeline.model import ChainItemSpec, ModificationTest, VerifierTest


def _chain_params(ci: ChainItemSpec) -> str:
    name = ci.item_name or ""
    if name == "CreateSignature":
        fields = [
            "field_mdp_action",
            "field_mdp_include_sigfield",
            "include_adobe_p",
            "mdp_perms",
            "certify",
            "stamp_enable",
            "signer_idx",
            "sig_field_name",
        ]
    elif name == "ASA":
        fields = ["place_on_different_page", "target_page_index"]
    elif name == "SFDA":
        fields = ["sig_field_name", "place_on_different_page", "target_page_index"]
    else:
        fields = []
    parts = [f"        [cyan]{f}[/cyan]={getattr(ci, f)}" for f in fields]
    return ("\n".join(parts)) if parts else ""


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


def _algorithm1_params(t: ModificationTest) -> dict:
    for a in t.associations:
        if a.chain_item.item_name == "CreateSignature":
            add_sig = a.chain_item
            break
    else:
        raise ValueError(f"test #{t.id} has no CreateSignature chain item")
    change_page = any(
        a.chain_item.item_name in ("ASA", "SFDA")
        and a.chain_item.place_on_different_page is True
        for a in t.associations
    )
    return {
        "mdp": add_sig.mdp_perms,
        "cert": add_sig.certify,
        "prot": add_sig.field_mdp_include_sigfield,
        "stamp": add_sig.stamp_enable,
        "chgpg": change_page,
    }


def _agg_layer_glyph(vts: list[VerifierTest], expected: bool, layer: int) -> str:
    result_attr = f"result_layer_{layer}"
    warn_attr = f"warn_modified_layer_{layer}"
    tested = [v for v in vts if getattr(v, result_attr) is not None]
    if not tested:
        return "[dim]-[/]"
    has_f = any(not getattr(v, result_attr) for v in tested)
    has_w = any(getattr(v, result_attr) and getattr(v, warn_attr) for v in tested)
    if has_f:
        return "[red]F[/]"
    if has_w:
        return "[yellow]W[/]"
    return "[green]T[/]"


def _layer_disagrees(vt: VerifierTest, expected: bool, layer: int) -> bool:
    r = getattr(vt, f"result_layer_{layer}")
    w = getattr(vt, f"warn_modified_layer_{layer}")
    if r is None:
        return False
    return r != expected or (r and bool(w))


def _is_disagreement_layered(t: ModificationTest, verifier_name: Optional[str]) -> bool:
    vts = [a.verifier_test for a in t.tested_verifiers_assoc]
    if verifier_name is not None:
        focal = next((v for v in vts if v.name == verifier_name), None)
        if focal is None:
            return False
        return _layer_disagrees(focal, t.expected_result, 1) or _layer_disagrees(
            focal, t.expected_result, 2
        )
    return any(
        _layer_disagrees(v, t.expected_result, 1)
        or _layer_disagrees(v, t.expected_result, 2)
        for v in vts
    )


def _rank_tuple(vt: VerifierTest) -> Optional[tuple[int, int]]:
    def _prio(result: Optional[bool], warn: Optional[bool]) -> int:
        if result is None:
            return 0
        if result and warn:
            return 1
        return 0 if result else 2

    if vt.result_layer_1 is None and vt.result_layer_2 is None:
        return None
    return (
        _prio(vt.result_layer_1, vt.warn_modified_layer_1),
        _prio(vt.result_layer_2, vt.warn_modified_layer_2),
    )


def _params_string(t: ModificationTest) -> str:
    p = _algorithm1_params(t)

    def _b(v: Optional[bool]) -> str:
        if v is None:
            return "-"
        return "T" if v else "F"

    def _mdp(v: Optional[int]) -> str:
        return "None" if v is None else str(v)

    return (
        f"id={t.id} mdp={_mdp(p['mdp'])} cert={_b(p['cert'])} "
        f"prot={_b(p['prot'])} stamp={_b(p['stamp'])} chgpg={_b(p['chgpg'])}"
    )


def _render_sum_matrix(
    rows: Sequence[ModificationTest],
    all_slugs: list[str],
    console: Console,
    verifier_meta: dict[str, tuple[str | None, str | None, str | None]] | None = None,
) -> None:
    attacks = ("ASA", "SFDA")
    buckets: dict[
        str,
        dict[str, list[tuple[tuple[int, int], int, VerifierTest, ModificationTest]]],
    ] = {slug: {a: [] for a in attacks} for slug in all_slugs}

    for t in rows:
        if t.attack_name not in attacks:
            continue
        for assoc in t.tested_verifiers_assoc:
            vt = assoc.verifier_test
            if vt.name not in buckets:
                continue
            rank = _rank_tuple(vt)
            if rank is None:
                continue
            buckets[vt.name][t.attack_name].append((rank, t.id, vt, t))

    show_url = verifier_meta is not None and any(
        url for _, _, url in verifier_meta.values()
    )

    table = Table(title="Best ASA / SFDA per verifier")
    table.add_column("verifier")
    table.add_column("category", style="dim")
    table.add_column("version", style="dim")
    if show_url:
        table.add_column("web-url", style="dim")
    table.add_column("ASA")
    table.add_column("SFDA")

    for slug in all_slugs:
        best_per_attack: dict[
            str, tuple[Optional[VerifierTest], Optional[ModificationTest]]
        ] = {}
        for attack in attacks:
            entries = buckets[slug][attack]
            if not entries:
                best_per_attack[attack] = (None, None)
            else:
                entries.sort(key=lambda e: (e[0], e[1]))
                _, _, vt, t = entries[0]
                best_per_attack[attack] = (vt, t)

        asa_vt, asa_t = best_per_attack["ASA"]
        sfda_vt, sfda_t = best_per_attack["SFDA"]

        category, version, url = verifier_meta.get(slug, (None, None, None)) if verifier_meta else (None, None, None)

        row_values = [
            slug,
            category or "[dim]-[/]",
            version or "[dim]-[/]",
        ]
        if show_url:
            row_values.append(url or "[dim]-[/]")
        row_values += [
            _matrix_cell(asa_vt) if asa_vt is not None else "[dim]-[/]",
            _matrix_cell(sfda_vt) if sfda_vt is not None else "[dim]-[/]",
        ]
        table.add_row(*row_values)

    console.print(table)


def _render_matrix(
    rows: Sequence[ModificationTest],
    verifier_name: Optional[str],
    disagree: bool,
    all_slugs: list[str],
    console: Console,
) -> None:
    def _b(v: Optional[bool]) -> str:
        if v is None:
            return "-"
        return "T" if v else "F"

    def _mdp(v: Optional[int]) -> str:
        return "None" if v is None else str(v)

    title = (
        "Tests (matrix)"
        if verifier_name is None
        else f"Tests (matrix) — {verifier_name}"
    )
    table = Table(title=title)
    table.add_column("id", style="dim")
    table.add_column("attack")
    table.add_column("mdp")
    table.add_column("cert")
    table.add_column("prot")
    table.add_column("stamp")
    table.add_column("chgpg")
    table.add_column("expected")

    if verifier_name is not None:
        table.add_column(verifier_name)
        table.add_column("match")
    else:
        for slug in all_slugs:
            table.add_column(slug)

    shown = 0
    for t in rows:
        if disagree and not _is_disagreement_layered(t, verifier_name):
            continue

        params = _algorithm1_params(t)
        row = [
            str(t.id),
            t.attack_name or "-",
            _mdp(params["mdp"]),
            _b(params["cert"]),
            _b(params["prot"]),
            _b(params["stamp"]),
            _b(params["chgpg"]),
            "valid" if t.expected_result else "invalid",
        ]

        vt_by_name = {
            a.verifier_test.name: a.verifier_test for a in t.tested_verifiers_assoc
        }

        if verifier_name is not None:
            vt = vt_by_name.get(verifier_name)
            row.append(_matrix_cell(vt))
            if vt is None:
                row.append("[dim]-[/]")
            else:
                l1_dis = _layer_disagrees(vt, t.expected_result, 1)
                l2_dis = _layer_disagrees(vt, t.expected_result, 2)
                has_any = vt.result_layer_1 is not None or vt.result_layer_2 is not None
                if l1_dis or l2_dis:
                    row.append("[yellow]disagree[/]")
                elif has_any:
                    row.append("[green]agree[/]")
                else:
                    row.append("[dim]-[/]")
        else:
            for slug in all_slugs:
                row.append(_matrix_cell(vt_by_name.get(slug)))

        table.add_row(*row)
        shown += 1

    console.print(table)
    if disagree:
        if shown == 0:
            suffix = f" for '{verifier_name}'" if verifier_name else ""
            console.print(f"[green]No disagreements{suffix}.[/]")
        else:
            console.print(f"[dim]{shown} disagreement(s).[/]")
