import subprocess
from pathlib import Path

import pyautogui

from tester_scripts.gui.gui_tester import GuiReaderConfig, wait_for_img

IMG_DIR = Path(__file__).parent / "imgs"

_FOXIT_EXE = r"C:\Program Files\Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe"

PROC: subprocess.Popen[bytes] | None = None


def _open(path: Path) -> None:
    global PROC
    PROC = subprocess.Popen([_FOXIT_EXE, str(path.absolute())])


def _capture(result_path: Path) -> bytes:
    pyautogui.screenshot(result_path, (1400, 0, 1920, 1080))
    return result_path.read_bytes()


def _capture2(result_path: Path) -> bytes:
    pyautogui.screenshot(result_path, (0, 0, 1400, 1080))
    return result_path.read_bytes()


def _cleanup() -> None:
    pyautogui.hotkey("ctrl", "w", interval=0.2)
    wait_for_img([IMG_DIR / "foxit_icon.png"], 30)


CONFIG = GuiReaderConfig(
    display_name="Foxit",
    slug="foxit",
    open_pdf=_open,
    cleanup=_cleanup,
    ready_images=list(Path(IMG_DIR / "layer_1").iterdir()),
    capture_layer_1=_capture,
    capture_layer_2=_capture2,  # stub: reuse L1 screenshot
    imgs_dir=IMG_DIR,
    reference_imgs={
        1: {
            "valid": ["foxit_valid_signature.png", "foxit_certification.png"],
            "invalid": ["foxit_invalid.png"],
            "warn": [
                "foxit_changed.png",
            ],
        },
        2: {
            "valid": ["foxit_valid_sig.png", "foxit_certification.png"],
            "invalid": ["foxit_invalid.png"],
            "warn": [
                "foxit_changed.png",
                "foxit_changed2.png",
            ],
        },
    },
)
