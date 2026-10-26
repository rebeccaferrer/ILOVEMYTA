"""Turn the black backgrounds and black side bars in product photos white.

Many photos were transparent PNGs flattened onto black, and some were padded
with black bars. A pixel counts as background if it is near-black AND connected
to the photo's edge, so dark details inside a garment are never touched. Small
specks not attached to the garment (JPEG noise) count as background too.

Smooth edges: along the garment's outline each pixel is part garment, part black
("coverage"). Coverage is estimated by comparing the pixel with the garment color
just inside the outline, then the black part is replaced with white, so edges
fade cleanly into white instead of leaving a dark or jagged rim.

The untouched originals are kept in data/data/products_original/. Every run
reads from there and rewrites data/data/products/, so it's safe to re-run, and
the image paths in the database stay the same.

Run with the hw4 virtual environment:  .venv/Scripts/python fix_product_photos.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
PRODUCTS = HERE / "data" / "data" / "products"
ORIGINALS = HERE / "data" / "data" / "products_original"

DARK = 12           # max(R, G, B) at or below this is "near-black" (the backgrounds are pure 0,0,0)
NEUTRAL = 4         # ...and max - min at or below this, so navy shadows (bluish) aren't mistaken for background
FRAME_PX = 2        # dark pixels this close to the photo's edge always count (thin black frames)
EDGE_PX = 6         # width of the outline band where coverage is estimated
MIX_TOLERANCE = 15  # how far (0-255) a pixel may differ from "garment color x coverage" and still count as a mix
MIN_PIECE = 0.002   # garment pieces smaller than this share of the photo are specks
MIN_PIXELS = 50     # ignore photos with fewer edge-connected black pixels than this (JPEG noise)
JPEG_QUALITY = 92


def background_mask(img: np.ndarray) -> np.ndarray:
    """True where a pixel is neutral near-black and connected to the image border."""
    hi, lo = img.max(axis=2).astype(int), img.min(axis=2).astype(int)
    dark = ((hi <= DARK) & (hi - lo <= NEUTRAL)).astype(np.uint8)
    # Cut 1-2px bridges first, so the fill can't leak through small gaps in a
    # garment's outline into dark shadows inside it.
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
    _, labels = cv2.connectedComponents(opened, connectivity=4)
    border = np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])
    edge_labels = np.unique(border[border > 0])
    core = np.isin(labels, edge_labels).astype(np.uint8)
    frame = np.zeros_like(dark)
    frame[:FRAME_PX], frame[-FRAME_PX:], frame[:, :FRAME_PX], frame[:, -FRAME_PX:] = 1, 1, 1, 1
    core |= dark & frame
    # Grow back over the dark pixels the opening trimmed along the garment edge.
    return (cv2.dilate(core, kernel, iterations=2) & dark).astype(bool) | core.astype(bool)


def garment_mask(background: np.ndarray) -> np.ndarray:
    """Everything that isn't background, minus small specks not attached to the garment."""
    pieces = (~background).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(pieces, connectivity=8)
    min_area = MIN_PIECE * background.size
    keep = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= min_area]
    return np.isin(labels, keep)


def whiten(img: np.ndarray, background: np.ndarray) -> np.ndarray:
    garment = garment_mask(background)
    pixel = img.astype(np.float32)

    # Garment color just inside the outline: average of nearby pixels at least EDGE_PX deep.
    depth = cv2.distanceTransform(garment.astype(np.uint8), cv2.DIST_L2, 3)
    inner = (depth > EDGE_PX).astype(np.float32)
    window = (4 * EDGE_PX + 1,) * 2
    weight = cv2.boxFilter(inner, -1, window, normalize=False)
    inner_color = cv2.boxFilter(pixel * inner[..., None], -1, window, normalize=False)
    inner_color = np.where(weight[..., None] > 0, inner_color / np.maximum(weight, 1)[..., None], pixel)

    # Coverage: 0 = background, 1 = solid garment, in between along the outline,
    # where the pixel is a mix of garment color and black.
    brightness = pixel.mean(axis=2)
    inner_brightness = inner_color.mean(axis=2)
    edge_coverage = np.clip(brightness / np.maximum(inner_brightness, 1), 0, 1)
    # Only a pixel that looks like the garment color darkened toward black is a mix. A real
    # detail in a different color (navy trim on a cream sweatshirt) keeps full coverage.
    predicted = edge_coverage[..., None] * inner_color
    mismatch = np.abs(pixel - predicted).mean(axis=2)
    is_mix = (mismatch < MIX_TOLERANCE) | (mismatch < 0.35 * brightness)
    edge_coverage = np.where(is_mix & (inner_brightness >= 8), edge_coverage, 1.0)  # black on black: can't tell, keep it
    coverage = np.where(depth > EDGE_PX, 1.0, np.where(garment, edge_coverage, 0.0)).astype(np.float32)
    # Soften the stair-steps of the pixel grid, on the garment side only: background stays pure white.
    coverage = np.where(garment, cv2.GaussianBlur(coverage, (3, 3), 0.6), 0.0)

    # The black part of each pixel becomes white: pixel = coverage * color + (1 - coverage) * black.
    out = pixel + (1 - coverage[..., None]) * 255
    return np.clip(out, 0, 255).round().astype(np.uint8)


def main() -> None:
    if not ORIGINALS.exists():
        shutil.copytree(PRODUCTS, ORIGINALS)
        print(f"Saved original photos to {ORIGINALS.relative_to(HERE)}")

    fixed, unchanged = [], []
    for src in sorted(ORIGINALS.glob("*.jpg")):
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        background = background_mask(img)
        if background.sum() < MIN_PIXELS:
            shutil.copy2(src, PRODUCTS / src.name)
            unchanged.append(src.stem)
            continue
        cv2.imwrite(str(PRODUCTS / src.name), whiten(img, background), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        fixed.append((src.stem, background.mean()))

    print(f"Whitened {len(fixed)} photos, left {len(unchanged)} unchanged.")
    for stem, share in fixed:
        print(f"  {stem:50} {share:6.1%} background")


if __name__ == "__main__":
    main()
