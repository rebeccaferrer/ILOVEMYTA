"""Generate the home-page banner photo from a family photo.

Sends data/banner_source.jpg plus photos of the two shop items they should wear
to gpt-image-2 (via Portkey) as an image edit, and saves:
  - output/banner_generated.png          the image exactly as returned
  - frontend/src/assets/banner.jpg       a web-sized copy the home page uses

Model note: AGENTS.md says to use gpt-5.6-luna, but its built-in image tool has no
image deployment behind it on this Portkey/Azure account. The user approved
gpt-image-2 for this banner only; everything else stays on gpt-5.6-luna.

Run with the hw4 virtual environment:  .venv/Scripts/python generate_banner.py
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import cv2
from dotenv import load_dotenv
from openai import OpenAI

HERE = Path(__file__).parent
SOURCE = HERE / "data" / "banner_source.jpg"
PRODUCTS = HERE / "data" / "data" / "products"
RAW_OUT = HERE / "output" / "banner_generated.png"
WEB_OUT = HERE / "frontend" / "src" / "assets" / "banner.jpg"

IMAGE_MODEL = "gpt-image-2"
SON_ITEM = "basic-hoodie-big-yale"   # Basic Big Yale Hoodie: navy, big white YALE
MOM_ITEM = "yale-mom-crewneck"       # Yale Mom Crewneck: heather gray, navy YALE ... MOM

PROMPT = """Create a photorealistic, landscape banner photo for a Yale apparel shop's website.

The first image is a real mother and her son. Keep both of them clearly recognizable:
same faces, skin tones, hair, and the mother's glasses.
- Age the son up to look 18 years old, a young man about to start college. He is
  smiling, excited and eager, looking ahead at the campus.
- The mother looks the same age as in the photo. She is looking at her son with a
  proud, warm smile, her arm around him.

Clothing (from the shop; match these product photos closely):
- Son: the navy pullover hoodie with large white YALE lettering (second image).
- Mother: the heather-gray crewneck sweatshirt with navy "YALE UNIVERSITY MOM"
  lettering (third image).

Setting: a sunny late-summer day on the Yale University campus in New Haven: a
green quad framed by Collegiate Gothic stone buildings and tall elm trees. Many
other visiting families with new students walk and talk in the background, softly
out of focus. Natural light, candid documentary style, eye-level camera.

Composition: wide 3:2 frame. Place the mother and son in the right third of the
frame, waist-up, so the left half has calmer background where a headline can sit.
No added text, watermarks or other brand logos."""


def jpeg_file(path: Path, max_side: int = 1536) -> tuple[str, bytes, str]:
    """A downsized JPEG upload, as (filename, bytes, content type)."""
    img = cv2.imread(str(path))
    scale = max_side / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return (path.stem + ".jpg", buf.tobytes(), "image/jpeg")


def main() -> None:
    load_dotenv(HERE / ".env")         # hw4/.env (see .env.example)
    load_dotenv(HERE.parent / ".env")  # or the course folder's root .env
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise SystemExit("Set PORTKEY_API_KEY in hw4/.env (copy .env.example) or the course folder's .env.")
    client = OpenAI(api_key=key, base_url="https://api.portkey.ai/v1",
                    default_headers={"x-portkey-api-key": key}, timeout=600)

    result = client.images.edit(
        model=IMAGE_MODEL,
        image=[jpeg_file(SOURCE), jpeg_file(PRODUCTS / f"{SON_ITEM}.jpg"), jpeg_file(PRODUCTS / f"{MOM_ITEM}.jpg")],
        prompt=PROMPT,
        size="1536x1024",
        quality="high",
    )
    RAW_OUT.parent.mkdir(exist_ok=True)
    RAW_OUT.write_bytes(base64.b64decode(result.data[0].b64_json))
    img = cv2.imread(str(RAW_OUT))
    WEB_OUT.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(WEB_OUT), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"Saved {RAW_OUT.relative_to(HERE)} ({img.shape[1]}x{img.shape[0]}) and {WEB_OUT.relative_to(HERE)}")


if __name__ == "__main__":
    main()
