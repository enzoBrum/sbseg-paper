import subprocess
from pathlib import Path

import pyautogui

from tester_scripts.gui.gui_tester import GuiReaderConfig, wait_for_img

IMG_DIR = Path(__file__).parent / "imgs"

_ADOBE_EXE = r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"

PROC: subprocess.Popen[bytes] | None = None


def _open(path: Path) -> None:
    global PROC
    PROC = subprocess.Popen([_ADOBE_EXE, str(path)])


def _pre_capture() -> None:
    print("[Pre-capture started]")

    bt = wait_for_img([IMG_DIR / "button_1.png"], 30)
    assert bt is not None
    pyautogui.moveTo(bt.x, bt.y)
    pyautogui.click()

    bt = wait_for_img([IMG_DIR / "verify_button.png"], 30)
    assert bt is not None
    pyautogui.moveTo(bt.x, bt.y)
    pyautogui.click()

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
