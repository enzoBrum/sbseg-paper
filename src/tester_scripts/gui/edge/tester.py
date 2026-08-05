import subprocess
from pathlib import Path

import pyautogui

from tester_scripts.gui.gui_tester import (
    GuiReaderConfig,
    gui_action,
    open_maximized,
    wait_for_img,
)

IMG_DIR = Path(__file__).parent / "imgs"
_EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PROC: subprocess.Popen[bytes] | None = None


def _open(path: Path) -> None:
    global PROC
    PROC = open_maximized(_EDGE_EXE, path)


def _pre_capture1():
    bt = wait_for_img([IMG_DIR / "sig_button.png"], 30, confidence=0.8)
    assert bt is not None
    gui_action(pyautogui.moveTo, bt.x, bt.y)
    gui_action(pyautogui.click, check_popups=True)
    gui_action(pyautogui.moveTo, 1, 1)


def _capture(result_path: Path) -> bytes:
    gui_action(pyautogui.screenshot, result_path, check_popups=True)
    return result_path.read_bytes()


def _cleanup() -> None:
    gui_action(pyautogui.hotkey, "ctrl", "w", interval=0.2)
    wait_for_img([IMG_DIR / "sbar.png"], 30)


CONFIG = GuiReaderConfig(
    display_name="Microsoft Edge",
    slug="edge",
    open_pdf=_open,
    cleanup=_cleanup,
    ready_images=[IMG_DIR / "sig_button.png"],
    capture_layer_1=_capture,
    capture_layer_2=_capture,
    pre_capture_layer_1=_pre_capture1,
    reference_imgs={
        1: {"valid": ["valid_sig.png"], "invalid": ["invalid_sig.png"], "warn": []},
        2: {"valid": ["valid_sig.png"], "invalid": ["invalid_sig.png"], "warn": []},
    },
    imgs_dir=IMG_DIR,
)
