import subprocess
import time
from pathlib import Path

import pyautogui

from tester_scripts.gui.gui_tester import (
    GuiReaderConfig,
    gui_action,
    open_maximized,
    wait_for_img,
)

IMG_DIR = Path(__file__).parent / "imgs"
POPUP_DIR = IMG_DIR / "popups"
SETUP_DIR = IMG_DIR / "setup"

_FOXIT_EXE = r"C:\Program Files\Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe"

PROC: subprocess.Popen[bytes] | None = None
_HANDLING_UNKNOWN_SIGNER = False
_SETUP_DONE = False

# Locate each ordinary popup across the desktop, then restrict its action
# searches to that dialog. This keeps generic controls such as OK and X safe.
_POPUPS = [
    (
        POPUP_DIR / "ai_news_dialog.png",
        [[POPUP_DIR / "ai_news_close.png"]],
    ),
    (
        POPUP_DIR / "default_pdf_reader_dialog.png",
        [
            [POPUP_DIR / "default_pdf_reader_dialog_check.png"],
            [POPUP_DIR / "default_pdf_reader_dialog_deny.png"],
        ],
    ),
    (
        POPUP_DIR / "opened_by_untrusted_dialog.png",
        [
            [POPUP_DIR / "opened_by_untrusted_dialog_check.png"],
            [
                POPUP_DIR / "opened_by_untrusted_dialog_ok.png",
                POPUP_DIR / "opened_by_untrusted_dialog_ok-2.png",
            ],
        ],
    ),
    (
        POPUP_DIR / "register_dialog.png",
        [[POPUP_DIR / "register_dialog_deny.png"]],
    ),
    (
        POPUP_DIR / "trust_certificate_dialog.png",
        [[POPUP_DIR / "trust_certificate_confirm.png"]],
    ),
    (
        POPUP_DIR / "trust_certificate_finished.png",
        [[POPUP_DIR / "trust_certificate_finished_btn.png"]],
    ),
]


def _find_dialog(path: Path):
    try:
        return pyautogui.locateOnScreen(str(path), confidence=0.8)
    except pyautogui.ImageNotFoundException:
        return None


def _find_action(paths: list[Path], region: tuple[int, int, int, int] | None = None):
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


def _handle_standard_popups() -> None:
    # Dismissing one popup can expose another, so restart the scan each time.
    for _ in range(6):
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
                    gui_action(pyautogui.press, "esc")
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
                            f"Could not dismiss Foxit popup: {dialog_path.name}"
                        )

                gui_action(pyautogui.moveTo, point.x, point.y)
                gui_action(pyautogui.click)
            break

        if not handled:
            return

    raise RuntimeError("Foxit popups did not settle")


def _click_when_visible(
    paths: list[Path], label: str, *, right_click: bool = False
) -> None:
    point = wait_for_img(
        paths,
        30,
        callback=_handle_standard_popups,
        confidence=0.8,
    )
    if point is None:
        raise RuntimeError(f"Could not find Foxit control: {label}")
    gui_action(pyautogui.moveTo, point.x, point.y)
    if right_click:
        gui_action(pyautogui.rightClick)
    else:
        gui_action(pyautogui.click)


def _handle_unknown_signer() -> None:
    # Opening the signature panel is enough; the small unknown-signer icon is
    # only the trigger that tells us this one-time trust flow is necessary.
    _click_when_visible([IMG_DIR / "ready/signature_panel.png"], "signature panel")
    _click_when_visible(
        [POPUP_DIR / "unknown_signer-panel.png"],
        "unknown signer row",
        right_click=True,
    )
    _click_when_visible(
        [POPUP_DIR / "unknown_signer-show.png"], "show signature properties"
    )
    _click_when_visible(
        [POPUP_DIR / "unknown_signer-show-cert.png"], "show certificate"
    )
    _click_when_visible([POPUP_DIR / "unknown_signer-trust.png"], "trust tab")
    _click_when_visible(
        [POPUP_DIR / "unknown_signer-add-trust.png"],
        "add to trusted certificates",
    )

    ok_images = [
        POPUP_DIR / "unknown_signer-add-trust-ok.png",
        POPUP_DIR / "unknown_signer-add-trust-ok-2.png",
    ]
    close_images = [
        POPUP_DIR / "unknown_signer-add-trust-close.png",
        POPUP_DIR / "unknown_signer-add-trust-close-2.png",
    ]
    ok_count = 0
    close_count = 0
    deadline = time.time() + 60

    # Foxit opens four successive trust dialogs. Prefer OK whenever it is
    # visible; otherwise consume a Close dialog, requiring two clicks of each.
    while ok_count < 2 or close_count < 2:
        _handle_standard_popups()
        point = _find_action(ok_images) if ok_count < 2 else None
        if point is not None:
            ok_count += 1
        elif close_count < 2:
            point = _find_action(close_images)
            if point is not None:
                close_count += 1

        if point is not None:
            gui_action(pyautogui.moveTo, point.x, point.y)
            gui_action(pyautogui.click)
            continue
        if time.time() >= deadline:
            raise RuntimeError(
                "Foxit trust flow did not produce two OK and two Close dialogs"
            )
        time.sleep(0.2)


def _handle_popups() -> None:
    global _HANDLING_UNKNOWN_SIGNER

    _handle_standard_popups()
    if _HANDLING_UNKNOWN_SIGNER:
        return
    if _find_action([POPUP_DIR / "unknown_signer.png"]) is None:
        return

    _HANDLING_UNKNOWN_SIGNER = True
    try:
        _handle_unknown_signer()
    finally:
        _HANDLING_UNKNOWN_SIGNER = False


def _kill_foxit() -> None:
    global PROC
    subprocess.run(
        ["taskkill", "/F", "/IM", "FoxitPDFReader.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    PROC = None


def _setup() -> None:
    global PROC, _SETUP_DONE
    PROC = open_maximized(_FOXIT_EXE)
    try:
        _click_when_visible([SETUP_DIR / "file.png"], "File")
        _click_when_visible([SETUP_DIR / "preferences.png"], "Preferences")
        _click_when_visible([SETUP_DIR / "search.png"], "preferences search")
        gui_action(pyautogui.write, "Signature")

        deadline = time.time() + 30
        search_results = None
        while time.time() < deadline:
            search_results = _find_dialog(
                SETUP_DIR / "signature_search_results.png"
            )
            if search_results is not None:
                break
            _handle_standard_popups()
            time.sleep(0.2)
        if search_results is None:
            raise RuntimeError("Could not find Foxit signature search results")

        region = (
            search_results.left,
            search_results.top,
            search_results.width,
            search_results.height,
        )
        point = _find_action([SETUP_DIR / "signature.png"], region)
        if point is None:
            raise RuntimeError("Could not find Signature in Foxit search results")
        gui_action(pyautogui.moveTo, point.x, point.y)
        gui_action(pyautogui.click)
        _click_when_visible(
            [SETUP_DIR / "change_settings.png"], "change signature settings"
        )

        deadline = time.time() + 30
        time.sleep(1)
        while time.time() < deadline:
            if _find_action([SETUP_DIR / "already_validating.png"]) is not None:
                break
            point = _find_action([SETUP_DIR / "validating_signatures.png"])
            if point is not None:
                gui_action(pyautogui.moveTo, point.x, point.y)
                gui_action(pyautogui.click)
                _click_when_visible(
                    [SETUP_DIR / "validating_certified.png"],
                    "validate certified documents",
                )
                break
            _handle_standard_popups()
            time.sleep(0.2)
        else:
            raise RuntimeError("Could not find Foxit signature validation settings")

        ok_images = [SETUP_DIR / "ok.png", SETUP_DIR / "ok-2.png"]
        _click_when_visible(ok_images, "signature settings OK")
        _click_when_visible(ok_images, "preferences OK")
        _SETUP_DONE = True
    finally:
        _kill_foxit()


def _open(path: Path) -> None:
    global PROC
    if not _SETUP_DONE:
        _setup()
    PROC = open_maximized(_FOXIT_EXE, path)


def _capture(result_path: Path) -> bytes:
    gui_action(
        pyautogui.screenshot,
        result_path,
        (1400, 0, 1920, 1080),
        check_popups=True,
    )
    return result_path.read_bytes()


def _pre_capture2() -> None:
    panel = IMG_DIR / "ready/digital_signatures_panel.png"
    if _find_action([panel]) is not None:
        return
    _click_when_visible(
        [IMG_DIR / "ready/signature_panel.png"], "signature panel"
    )
    wait_for_img(
        [panel],
        30,
        callback=_handle_standard_popups,
        confidence=0.8,
    )


def _capture2(result_path: Path) -> bytes:
    gui_action(
        pyautogui.screenshot,
        result_path,
        (0, 0, 1400, 1080),
        check_popups=True,
    )
    return result_path.read_bytes()


def _cleanup() -> None:
    gui_action(pyautogui.hotkey, "ctrl", "w", interval=0.2)
    wait_for_img([IMG_DIR / "foxit_icon.png"], 30, callback=_handle_standard_popups)


CONFIG = GuiReaderConfig(
    display_name="Foxit",
    slug="foxit",
    open_pdf=_open,
    cleanup=_cleanup,
    ready_images=list(Path(IMG_DIR / "layer_1").iterdir()),
    capture_layer_1=_capture,
    capture_layer_2=_capture2,
    pre_capture_layer_2=_pre_capture2,
    handle_popups=_handle_popups,
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
