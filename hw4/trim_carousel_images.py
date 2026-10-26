"""Trim plain white borders (letterbox bars) off the home-page carousel photos in images/.

The carousel crops each photo to fill the banner, so a photo saved with white bars above and
below (like a wide picture inside a square file) would show white strips. This finds rows and
columns at the edges that are almost entirely near-white and cuts them off.

The untouched originals are saved first in images/originals/ (never overwritten), and the
script always reads from there, so it's safe to run again after adding new photos.

Run from the hw4 folder:  .venv/Scripts/python trim_carousel_images.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np

IMAGES = Path(__file__).parent / "images"
ORIGINALS = IMAGES / "originals"
NEAR_WHITE = 240        # a pixel this bright on every channel counts as white
WHITE_SHARE = 0.98      # an edge row/column this white is a border
MIN_BORDER_PX = 8       # ignore thinner edges (normal photos can have a light edge)


def border_rows(white: np.ndarray) -> tuple[int, int]:
    """How many all-white rows at the top and bottom of a white-pixel mask."""
    share = white.mean(axis=1)
    top = int(np.argmax(share < WHITE_SHARE)) if (share < WHITE_SHARE).any() else 0
    bottom = int(np.argmax(share[::-1] < WHITE_SHARE)) if (share < WHITE_SHARE).any() else 0
    return top, bottom


def trim(path: Path) -> str:
    original = ORIGINALS / path.name
    if not original.exists():
        shutil.copy2(path, original)
    image = cv2.imread(str(original))
    if image is None:
        return "not readable, skipped"
    white = (image >= NEAR_WHITE).all(axis=2)
    top, bottom = border_rows(white)
    left, right = border_rows(white.T)
    top, bottom, left, right = (n if n >= MIN_BORDER_PX else 0 for n in (top, bottom, left, right))
    height, width = image.shape[:2]
    if not any((top, bottom, left, right)):
        return f"{width}x{height}, no border"
    cropped = image[top:height - bottom, left:width - right]
    cv2.imwrite(str(path), cropped, [cv2.IMWRITE_JPEG_QUALITY, 92])
    return (f"{width}x{height} -> {cropped.shape[1]}x{cropped.shape[0]} "
            f"(trimmed top {top}, bottom {bottom}, left {left}, right {right})")


if __name__ == "__main__":
    ORIGINALS.mkdir(exist_ok=True)
    for photo in sorted(IMAGES.glob("*.jpg")):
        print(f"{photo.name}: {trim(photo)}")
