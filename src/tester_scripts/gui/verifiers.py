REGISTRY: frozenset[str] = frozenset(
    {
        "adobe",
        "foxit",
        "master_pdf_editor",
        "edge",
    }
)


# (slug, display_name, version)
SEED_DATA: list[tuple[str, str, str | None]] = [
    ("adobe", "Adobe Acrobat", "26.1.21563.0"),
    ("foxit", "Foxit PDF Reader", "2026.1.1.36485"),
    ("master_pdf_editor", "Master PDF Editor 5", "5.9.9.8"),
    ("edge", "Microsoft Edge", "148.0.3967.83"),
]


def test(name: str, where_clause=None) -> None:
    from importlib import import_module

    from tester_scripts.gui.gui_tester import run_gui_tester

    module = import_module(f"tester_scripts.gui.{name}.tester")
    run_gui_tester(module.CONFIG, where_clause=where_clause)
