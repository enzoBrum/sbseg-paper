from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from cv2.typing import MatLike


class NoTemplateMatchError(Exception):
    pass


def _match_img(template: MatLike, real: MatLike) -> bool:
    result = cv2.matchTemplate(real, template, cv2.TM_CCOEFF_NORMED)
    _, r, _, _ = cv2.minMaxLoc(result)
    return r >= 0.95


def has_reference_imgs(
    reference_imgs: dict[int, dict[str, list[str]]],
    layer: int,
) -> bool:
    layer_entry = reference_imgs.get(layer, {})
    return any(bool(imgs) for imgs in layer_entry.values())


def load_reference_imgs(
    imgs_dir: Path | None,
    reference_imgs: dict[int, dict[str, list[str]]],
) -> dict[int, dict[str, list[MatLike]]]:
    """Read all reference PNGs from disk once; returns cv2-decoded images."""
    if not reference_imgs or imgs_dir is None:
        raise Exception("A")
    loaded: dict[int, dict[str, list[MatLike]]] = {}
    for layer, classes in reference_imgs.items():
        loaded[layer] = {}
        layer_dir = imgs_dir / f"layer_{layer}"
        for outcome, filenames in classes.items():
            loaded[layer][outcome] = []
            for fname in filenames:
                img = cv2.imread(str(layer_dir / fname), cv2.IMREAD_COLOR)
                assert img is not None, f"could not load {layer_dir / fname}"
                loaded[layer][outcome].append(img)
    return loaded


def classify(
    loaded_imgs: dict[int, dict[str, list[MatLike]]],
    layer: int,
    screenshot: bytes,
) -> Literal["valid", "invalid", "warn"]:
    """Template-match screenshot against pre-loaded images.

    Raises NoTemplateMatchError if nothing matches.
    """
    img = cv2.imdecode(np.frombuffer(screenshot, np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, "could not decode screenshot bytes"

    layer_imgs = loaded_imgs[layer]
    for template in layer_imgs["invalid"]:
        if _match_img(template, img):
            return "invalid"
    for template in layer_imgs["warn"]:
        if _match_img(template, img):
            return "warn"
    for template in layer_imgs["valid"]:
        if _match_img(template, img):
            return "valid"
    raise NoTemplateMatchError(f"no template matched for layer={layer}")
