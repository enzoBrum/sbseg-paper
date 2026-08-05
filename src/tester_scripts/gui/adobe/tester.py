import subprocess
import time
from pathlib import Path

import pyautogui

from tester_scripts.gui.gui_tester import (
    GuiReaderConfig,
    open_maximized,
    wait_for_img,
)

IMG_DIR = Path(__file__).parent / "imgs"
POPUP_DIR = IMG_DIR / "popups"

_ADOBE_EXE = r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"

PROC: subprocess.Popen[bytes] | None = None

# Each popup is located across the desktop first. Its small, generic controls
# are then matched only inside the returned dialog rectangle.
_POPUPS = [
    (
        POPUP_DIR / "always_open_dialog.png",
        [[POPUP_DIR / "always_open_no.png"]],
    ),
    (
        POPUP_DIR / "always_open_alt_dialog.png",
        [
            [POPUP_DIR / "always_open_alt_checkbox.png"],
            [POPUP_DIR / "always_open_alt_no.png"],
        ],
    ),
    (
        POPUP_DIR / "free_trial_dialog.png",
        [[POPUP_DIR / "free_trial_close.png"]],
    ),
    (
        POPUP_DIR / "reopen_closed_pdfs_dialog.png",
        [[POPUP_DIR / "reopen_closed_pdfs_no_thanks.png"]],
    ),
    (
        POPUP_DIR / "validation_confirm_dialog.png",
        [
            [POPUP_DIR / "validation_checkbox.png"],
            [
                POPUP_DIR / "validation_ok_focused.png",
                POPUP_DIR / "validation_ok.png",
            ],
        ],
    ),
    (
        POPUP_DIR / "validation_complete_dialog.png",
        [
            [POPUP_DIR / "validation_checkbox.png"],
            [
                POPUP_DIR / "validation_ok_focused.png",
                POPUP_DIR / "validation_ok.png",
            ],
        ],
    ),
]


def _find_dialog(path: Path):
    try:
        return pyautogui.locateOnScreen(str(path), confidence=0.8)
    except pyautogui.ImageNotFoundException:
        return None


def _find_action(paths: list[Path], region: tuple[int, int, int, int]):
    for path in paths:
        try:
            point = pyautogui.locateCenterOnScreen(
                str(path), region=region, confidence=0.8
            )
        except pyautogui.ImageNotFoundException:
            continue
        if point is not None:
            return point
    return None


def _handle_popups() -> None:
    # Handling one dialog may reveal another, so rescan from the beginning.
    for _ in range(5):
        handled = False
        for dialog_path, actions in _POPUPS:
            dialog = _find_dialog(dialog_path)
            if dialog is None:
                continue

            handled = True
            region = (dialog.left, dialog.top, dialog.width, dialog.height)
            for action_paths in actions:
                point = _find_action(action_paths, region)
                if point is None:
                    # Escape may dismiss a dialog whose rendering no longer
                    # matches its captured button state.
                    pyautogui.press("esc")
                    time.sleep(0.2)
                    dialog = _find_dialog(dialog_path)
                    if dialog is None:
                        break
                    region = (
                        dialog.left,
                        dialog.top,
                        dialog.width,
                        dialog.height,
                    )
                    point = _find_action(action_paths, region)
                    if point is None:
                        raise RuntimeError(
                            f"Could not dismiss Adobe popup: {dialog_path.name}"
                        )

                pyautogui.moveTo(point.x, point.y)
                pyautogui.click()
                time.sleep(0.2)
            break

        if not handled:
            return

    raise RuntimeError("Adobe popups did not settle")


def _open(path: Path) -> None:
    global PROC
    PROC = open_maximized(_ADOBE_EXE, path)


def _pre_capture() -> None:
    print("[Pre-capture started]")

    bt = wait_for_img([IMG_DIR / "button_1.png"], 30, callback=_handle_popups)
    assert bt is not None
    pyautogui.moveTo(bt.x, bt.y)
    pyautogui.click()
    _handle_popups()

    bt = wait_for_img(
        [IMG_DIR / "verify_button.png"], 30, callback=_handle_popups
    )
    assert bt is not None
    pyautogui.moveTo(bt.x, bt.y)
    pyautogui.click()
    _handle_popups()

    print("[Pre-capture finished]")


def _capture(result_path: Path) -> bytes:
    pyautogui.screenshot(result_path)
    return result_path.read_bytes()


def _cleanup() -> None:
    if PROC is not None:
        PROC.terminate()


CONFIG = GuiReaderConfig(
    display_name="Adobe Reader DC",
    slug="adobe",
    open_pdf=_open,
    cleanup=_cleanup,
    ready_images=[
        IMG_DIR / "ready/valid_sig.png",
        IMG_DIR / "ready/invalid_sig.png",
        IMG_DIR / "ready/certified.png",
        IMG_DIR / "ready/valid_sig_2.png",
    ],
    capture_layer_1=_capture,
    capture_layer_2=_capture,  # stub: reuse L1 screenshot
    handle_popups=_handle_popups,
    imgs_dir=IMG_DIR,
    reference_imgs={
        1: {
            "valid": [
                "adobe_certification.png",
                "adobe_valid_signature.png",
            ],
            "invalid": [
                "adobe_invalid_signature.png",
            ],
            "warn": [
                "adobe_content_changed.png",
            ],
        },
        2: {
            "valid": [
                "adobe_valid_signature_2.png",
                "adobe_valid_but_changed.png",
                "adobe_certification_2.png",
            ],
            "invalid": [
                "adobe_invalid_signature_2.png",
            ],
            "warn": [
                "adobe_content_changed_2.png",
            ],
        },
    },
    ready_region=(1300, 50, 1920, 1080),
    pre_capture_layer_1=_pre_capture,
)
