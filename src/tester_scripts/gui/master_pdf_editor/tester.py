import subprocess
from pathlib import Path
from time import sleep

import pyautogui

from tester_scripts.gui.gui_tester import (
    GuiReaderConfig,
    gui_action,
    open_maximized,
    wait_for_img,
)

IMG_DIR = Path(__file__).parent / "imgs"
POPUP_DIR = IMG_DIR / "popups"
_MASTER_PDF_EXE = (
    r"C:\Program Files\Code Industry\Master PDF Editor 5\MasterPDFEditor.exe"
)
PROC: subprocess.Popen[bytes] | None = None
_SETUP_DONE = False


def _handle_popups() -> None:
    try:
        dialog = pyautogui.locateOnScreen(
            str(POPUP_DIR / "default_pdf_dialog.png"), confidence=0.8
        )
    except pyautogui.ImageNotFoundException:
        return
    if dialog is None:
        return

    sleep(0.5)
    region = (dialog.left, dialog.top, dialog.width, dialog.height)
    for image in ("default_pdf_checkbox.png", "default_pdf_no.png"):
        try:
            point = pyautogui.locateCenterOnScreen(
                str(POPUP_DIR / image), region=region, confidence=0.8
            )
        except pyautogui.ImageNotFoundException:
            point = None
        if point is None:
            raise RuntimeError(f"Could not handle Master PDF popup: {image}")
        gui_action(pyautogui.moveTo, point.x, point.y)
        gui_action(pyautogui.click)


def _setup() -> None:
    global PROC, _SETUP_DONE
    PROC = open_maximized(_MASTER_PDF_EXE)
    try:
        sleep(5)
        _handle_popups()
        _SETUP_DONE = True
    finally:
        if PROC is not None and PROC.poll() is None:
            PROC.kill()
            PROC.wait()
        PROC = None


def _open(path: Path) -> None:
    global PROC
    if not _SETUP_DONE:
        _setup()
        sleep(0.5)
    if PROC is not None and PROC.poll() is None:
        PROC.kill()
        sleep(0.2)
    PROC = open_maximized(_MASTER_PDF_EXE, path)


def _pre_capture1():
    bt = wait_for_img([IMG_DIR / "sig_btn.png", IMG_DIR / "sig_btn-2.png"], 30, (0, 100, 1920, 1080))
    assert bt is not None
    gui_action(pyautogui.moveTo, bt.x, bt.y)
    gui_action(pyautogui.click, check_popups=True)
    bt = wait_for_img([IMG_DIR / "sig_identified.png"], 30)
    gui_action(pyautogui.moveTo, bt.x, bt.y)
    gui_action(pyautogui.click, check_popups=True)
    gui_action(pyautogui.click, check_popups=True)


def _capture(result_path: Path) -> bytes:
    gui_action(pyautogui.screenshot, result_path, check_popups=True)
    return result_path.read_bytes()


def _cleanup() -> None:
    gui_action(pyautogui.press, "esc")
    gui_action(pyautogui.hotkey, "ctrl", "w", interval=0.2)
    gui_action(pyautogui.move, 1, 1)
    #wait_for_img([IMG_DIR / "trash.png"], 30)


CONFIG = GuiReaderConfig(
    display_name="Master PDF Editor",
    slug="master_pdf_editor",
    open_pdf=_open,
    cleanup=_cleanup,
    ready_images=[IMG_DIR / "sig_btn.png", IMG_DIR / "sig_btn-2.png"],
    capture_layer_1=_capture,
    capture_layer_2=_capture,
    pre_capture_layer_1=_pre_capture1,
    handle_popups=_handle_popups,
    reference_imgs={
        1: {"valid": ["valid_sig.png"], "invalid": ["invalid_sig.png"], "warn": []},
        2: {"valid": ["valid_sig.png"], "invalid": ["invalid_sig.png"], "warn": []},
    },
    imgs_dir=IMG_DIR,
)
