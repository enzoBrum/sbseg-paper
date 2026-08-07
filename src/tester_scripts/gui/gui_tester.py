import glob
import subprocess
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
import traceback
from typing import Callable

import pyautogui

from modification_pipeline.model import FILE_PATH, ModificationTest, VerifierTest

SRC_ROOT = Path(__file__).parent.parent.parent
SCREENSHOTS_ROOT = SRC_ROOT / "screenshots"
PAGE_SIZE = 32
RETRIES = 10

_EVAL_MISS_RETRIES = 2
_SW_MAXIMIZE = 3
_ACTION_DELAY = 0.05
_POPUP_HANDLER: Callable[[], None] | None = None
_CHECKING_POPUPS = False
_READER_EXECUTABLE: str | None = None


def set_action_delay(seconds: float) -> None:
    global _ACTION_DELAY
    _ACTION_DELAY = seconds


def _check_popups() -> None:
    """Run the active popup handler without allowing recursive checks."""
    global _CHECKING_POPUPS
    if _POPUP_HANDLER is None or _CHECKING_POPUPS:
        return
    _CHECKING_POPUPS = True
    try:
        _POPUP_HANDLER()
    finally:
        _CHECKING_POPUPS = False


def gui_action(action, *args, check_popups: bool = True, **kwargs):
    """Give the desktop time to settle around every PyAutoGUI action."""
    time.sleep(_ACTION_DELAY)
    if check_popups:
        _check_popups()
    try:
        result = action(*args, **kwargs)
    finally:
        time.sleep(_ACTION_DELAY)
    return result


def open_maximized(
    executable: str, document: Path | None = None
) -> subprocess.Popen[bytes]:
    """Open a Windows desktop verifier with an initially maximized window."""
    global _READER_EXECUTABLE
    _READER_EXECUTABLE = Path(executable).name.casefold()
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = _SW_MAXIMIZE
    arguments = [executable]
    if document is not None:
        arguments.append(str(document.absolute()))
    return subprocess.Popen(arguments, startupinfo=startup)


def _maximize_reader_window() -> None:
    """Maximize the reader window even when it reused an existing process."""
    import ctypes
    from ctypes import wintypes

    import psutil

    if _READER_EXECUTABLE is None:
        raise RuntimeError("Reader executable was not recorded")

    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
    )
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    ]
    user32.GetWindowRect.argtypes = [
        wintypes.HWND,
        ctypes.POINTER(wintypes.RECT),
    ]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    windows: list[tuple[int, int]] = []

    def collect(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            process_name = psutil.Process(pid.value).name().casefold()
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            return True
        if process_name != _READER_EXECUTABLE:
            return True

        rect = wintypes.RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            area = max(0, rect.right - rect.left) * max(
                0, rect.bottom - rect.top
            )
            if area:
                windows.append((area, hwnd))
        return True

    user32.EnumWindows(callback_type(collect), 0)
    if not windows:
        raise RuntimeError(
            f"Could not find a visible window for {_READER_EXECUTABLE}"
        )

    hwnd = max(windows)[1]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.ShowWindow(hwnd, _SW_MAXIMIZE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(_ACTION_DELAY)


CHECKING_POPUPS = False
def wait_for_img(
    paths: list[Path],
    timeout: float,
    region: tuple[int, int, int, int] | None = None,
    callback: Callable[[], None] | None = None,
    should_exist: bool = True,
    confidence: float = 0.6,
    check_popups: bool = True
):
    global CHECKING_POPUPS
    end = time.time() + timeout
    while time.time() < end:
        for img in paths:
            try:
                print("MAtchiing: ", paths)
                result = pyautogui.locateCenterOnScreen(
                    str(img), region=region, confidence=confidence
                )
                if result is not None and should_exist:
                    return result
            except pyautogui.ImageNotFoundException:
                if not should_exist:
                    return None
                continue
        if callback is not None:
            callback()
        time.sleep(0.20)

    raise TimeoutError("AWA")


@dataclass(frozen=True)
class Verdict:
    valid: bool
    warn_modified: bool


_VERDICT_FROM_LABEL: dict[str, Verdict] = {
    "valid": Verdict(True, False),
    "invalid": Verdict(False, False),
    "warn": Verdict(True, True),
}


@dataclass
class GuiReaderConfig:
    # Human-readable display name, e.g. "Adobe Reader DC". Used in
    # screenshot directory names and surfaced in the UI/reports.
    display_name: str
    # CLI identifier — the registry key and Verifier.name column value,
    # e.g. "adobe". Used by `run <slug>` and to look up the FK to the
    # seeded Verifier row. Must match the entry in gui/verifiers.REGISTRY.
    slug: str
    open_pdf: Callable[[Path], None]
    cleanup: Callable[[], None]
    ready_images: list[Path]
    # Layer 1: top-bar validation banner (always captured).
    capture_layer_1: Callable[[Path], bytes]
    # Layer 2: detail panel — stub by setting equal to capture_layer_1.
    capture_layer_2: Callable[[Path], bytes]
    # Optional verifier-specific cleanup for dialogs that obstruct automation.
    handle_popups: Callable[[], None] | None = None
    imgs_dir: Path | None = None
    reference_imgs: dict[int, dict[str, list[str]]] = field(default_factory=dict)
    ready_region: tuple[int, int, int, int] | None = None
    pre_capture_layer_1: Callable[[], None] | None = None
    pre_capture_layer_2: Callable[[], None] | None = None
    version: str | None = None


def _execute_reader(
    config: GuiReaderConfig, test_id: int, fileblob: bytes
) -> tuple[bytes, bytes]:
    file_to_test = SRC_ROOT / "cur.pdf"
    file_to_test.write_bytes(fileblob)

    screenshot_dir = SCREENSHOTS_ROOT / config.display_name.lower().replace(" ", "_")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    begin = time.time()
    gui_action(pyautogui.moveTo, 10, 10)

    def handle_popups() -> None:
        _check_popups()

    try:
        print("OPEN")
        config.open_pdf(file_to_test)
        handle_popups()
        print("WAIT READY")
        wait_for_img(config.ready_images, 60, callback=handle_popups)
        handle_popups()
        # Single-instance applications can ignore the startup window state,
        # so maximize their actual top-level window instead of relying on focus.
        _maximize_reader_window()

        if config.pre_capture_layer_1 is not None:
            print("PRE 1")
            handle_popups()
            config.pre_capture_layer_1()
            handle_popups()
        print("1")
        handle_popups()
        l1 = config.capture_layer_1(screenshot_dir / f"{test_id}_l1.png")

        if config.pre_capture_layer_2 is not None:
            print("PRE 2")
            handle_popups()
            config.pre_capture_layer_2()
            handle_popups()
        print("2")
        handle_popups()
        l2 = config.capture_layer_2(screenshot_dir / f"{test_id}_l2.png")

        return l1, l2
    finally:
        config.cleanup()
        print(f"took {time.time() - begin}")


def run_gui_tester(config: GuiReaderConfig, where_clause=None) -> None:
    global _POPUP_HANDLER

    from sqlalchemy import func, select

    from modification_pipeline.model import get_session
    from tester_scripts._runner import run_paginated
    from tester_scripts.gui.inline_evaluator import (
        NoTemplateMatchError,
        classify,
        has_reference_imgs,
        load_reference_imgs,
    )
    from tester_scripts.gui.verifiers import SEED_DATA as _GUI_SEED

    _POPUP_HANDLER = config.handle_popups
    _version = config.version or next(
        (v for slug, _, v in _GUI_SEED if slug == config.slug), None
    )
    print(f"{config.slug} version: {_version or 'unknown'}")

    loaded_imgs = load_reference_imgs(config.imgs_dir, config.reference_imgs)

    with get_session() as _s:
        _stmt = select(func.count()).select_from(ModificationTest)
        if where_clause is not None:
            _stmt = _stmt.where(where_clause)
        total = _s.execute(_stmt).scalar_one()

    done = 0

    def _already_tested(t: ModificationTest) -> bool:
        return any(
            a.verifier_test.name == config.slug
            and a.verifier_test.screenshot_layer_1 is not None
            for a in t.tested_verifiers_assoc
        )

    def process_page(
        tests: list[ModificationTest], verifier_id: int
    ) -> list[tuple[ModificationTest, VerifierTest | None]]:
        nonlocal done
        results = []
        for t in tests:
            done += 1
            print(f"test #{t.id}")
            screenshot_1 = screenshot_2 = None
            layer_results: dict[int, Verdict | None] = {1: None, 2: None}
            eval_miss_count = 0

            for _ in range(RETRIES):
                try:
                    screenshot_1, screenshot_2 = _execute_reader(
                        config, t.id, t.fileblob
                    )
                except Exception:
                    traceback.print_exc()
                    gui_action(pyautogui.hotkey, "alt", "f4", interval=0.1)
                    time.sleep(5)
                    continue

                eval_ok = True
                for layer, scr in ((1, screenshot_1), (2, screenshot_2)):
                    if scr is None or not has_reference_imgs(
                        config.reference_imgs, layer
                    ):
                        continue
                    try:
                        verdict = classify(loaded_imgs, layer, scr)
                        layer_results[layer] = _VERDICT_FROM_LABEL[verdict]
                    except NoTemplateMatchError:
                        eval_ok = False
                        print(
                            f"eval miss: test={t.id}"
                            f" verifier={config.display_name} layer={layer}"
                        )

                if eval_ok:
                    break

                eval_miss_count += 1
                if eval_miss_count >= _EVAL_MISS_RETRIES:
                    print(
                        f"eval miss budget exhausted for test={t.id}"
                        f" verifier={config.display_name}, not persisting results"
                    )
                    raise Exception("Could not validate")

                gui_action(pyautogui.hotkey, "alt", "f4", interval=0.1)
                time.sleep(5)
            else:
                raise RuntimeError(f"Could not complete test {t.id}")

            r1, r2 = layer_results[1], layer_results[2]
            results.append(
                (
                    t,
                    VerifierTest(
                        name=config.slug,
                        verifier_id=verifier_id,
                        screenshot_layer_1=screenshot_1,
                        screenshot_layer_2=screenshot_2,
                        result_layer_1=r1.valid if r1 is not None else None,
                        warn_modified_layer_1=(
                            r1.warn_modified if r1 is not None else None
                        ),
                        result_layer_2=r2.valid if r2 is not None else None,
                        warn_modified_layer_2=(
                            r2.warn_modified if r2 is not None else None
                        ),
                    ),
                )
            )

        return results

    run_paginated(
        config.slug,
        process_page,
        already_tested=_already_tested,
        on_page_committed=lambda: shutil.copyfile(
            FILE_PATH, FILE_PATH.parent / "backup.db"
        ),
        where_clause=where_clause,
    )
