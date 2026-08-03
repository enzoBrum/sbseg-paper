from tester_scripts.gui.verifiers import REGISTRY as _GUI_REGISTRY
from tester_scripts.gui.verifiers import test as _gui_test
from tester_scripts.library.tester import test as _lib_test
from tester_scripts.library.verifiers import REGISTRY as _LIB_REGISTRY
from tester_scripts.web.verifiers import REGISTRY as _WEB_REGISTRY


_RUNNERS = (
    (_GUI_REGISTRY, _gui_test),
    (_LIB_REGISTRY, _lib_test),
)


def test(name: str, where_clause=None) -> None:
    for registry, run in _RUNNERS:
        if name in registry:
            return run(name, where_clause=where_clause)
    if name in _WEB_REGISTRY:
        raise ValueError(
            f"{name!r} is a web verifier (tested manually). "
            f"Use `main.py enter-web-result {name} <test_id> "
            "--l1-valid|--no-l1-valid [--l1-warn] "
            "--l2-valid|--no-l2-valid [--l2-warn]`."
        )
    raise ValueError(f"Unknown verifier: {name!r}")
