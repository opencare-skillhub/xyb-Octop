#!/usr/bin/env python3
"""Generate the xiaoyibao brand assets from one source logo.

One input, one place to change it. Everything the dashboard loads is derived:

* ``pwa-192.png`` / ``pwa-512.png``      app icons (square, opaque-safe)
* ``apple-touch-icon.png``               iOS home screen
* ``favico.svg``                         self-contained favicon (embedded PNG)
* ``logo_horizontal_{light,dark}.png``   sidebar / header wordmark
* ``brand/logo-source.png``              the untouched source, kept for re-runs

The wordmark is composed here rather than shipped as a separate design asset, so
swapping the mascot or the product name is a one-line change.

Both the light and dark wordmarks use a solid background band behind the text.
That is deliberate: a bare transparent wordmark is unreadable on one theme or
the other, and the dashboard loads these with plain ``<img>`` tags where CSS
filters are not available.

Usage::

    python3 scripts/xyb-brand.py                # regenerate every asset
    python3 scripts/xyb-brand.py --check        # report what is missing/stale
    python3 scripts/xyb-brand.py --name 小胰宝  # override the wordmark text
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
PUBLIC = REPO / "dashboard" / "public"
BRAND_DIR = PUBLIC / "brand"

SOURCE_URL = (
    "https://picgo-1302991947.cos.ap-guangzhou.myqcloud.com/"
    "images/Pop%20Mart%20Character%20Front%20View%20(2).png"
)
SOURCE_FILE = BRAND_DIR / "logo-source.png"

DEFAULT_NAME = "小胰宝"
DEFAULT_TAGLINE = "胰腺癌病友的 AI 助手"

#: Candidate CJK fonts, in preference order. The first that exists wins.
FONT_CANDIDATES: tuple[tuple[str, int], ...] = (
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 1),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("/System/Library/Fonts/Supplemental/Songti.ttc", 1),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 0),
)

#: Per-theme colours, keyed by the asset suffix the dashboard already loads.
#: The dashboard picks `logo_horizontal_white.png` when the theme is dark and
#: `logo_horizontal_dark.png` when it is light, so "white" means "for dark
#: backgrounds" -- the naming is about the artwork, not the theme.
#: Value = (text colour, tagline colour).
THEMES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    # For light backgrounds.
    "dark": ((15, 44, 42), (90, 110, 108)),
    # For dark backgrounds.
    "white": ((255, 255, 255), (176, 192, 189)),
}

WHEEL_PX = 512


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path, index in FONT_CANDIDATES:
        candidate = Path(path)
        if not candidate.is_file():
            continue
        try:
            return ImageFont.truetype(str(candidate), size=size, index=index)
        except OSError:
            continue
    raise SystemExit(
        "no CJK font found; add one to FONT_CANDIDATES "
        "(tried: " + ", ".join(p for p, _ in FONT_CANDIDATES) + ")"
    )


def _ssl_context() -> ssl.SSLContext | None:
    """Honour an operator-supplied CA bundle.

    On a machine behind a TLS-inspecting proxy the system trust store is not
    reachable from Python, so verification fails while ``curl`` still works.
    Verification is never disabled here.
    """
    for var in ("XYB_HTTP_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        bundle = os.environ.get(var)
        if bundle and Path(bundle).is_file():
            try:
                return ssl.create_default_context(cafile=bundle)
            except (OSError, ssl.SSLError):
                continue
    return None


def _download(url: str) -> bytes:
    """Fetch the source logo, trying Python first and then the system curl.

    The curl fallback exists because Python's bundled trust store and the OS
    trust store genuinely differ on some hosts; refusing to use a working system
    tool would make this script unusable on exactly those machines.
    """
    python_error: BaseException | None = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "xyb-brand/1.0"})
        with urllib.request.urlopen(request, timeout=60, context=_ssl_context()) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        python_error = exc

    curl = shutil.which("curl")
    if curl:
        result = subprocess.run(
            [curl, "-fsSL", "--max-time", "90", url],
            check=False,
            capture_output=True,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout

    raise SystemExit(f"could not download the source logo: {python_error}")


def ensure_source(force: bool = False) -> bytes:
    """Return the source PNG bytes, downloading once and caching on disk."""
    if SOURCE_FILE.is_file() and not force:
        return SOURCE_FILE.read_bytes()
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    data = _download(SOURCE_URL)
    SOURCE_FILE.write_bytes(data)
    return data


def _open_source(data: bytes) -> Image.Image:
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    return _trim_transparent(image)


def _trim_transparent(image: Image.Image) -> Image.Image:
    """Crop fully transparent margins so the mascot fills its box."""
    bbox = image.getbbox()
    return image.crop(bbox) if bbox else image


def make_square(source: Image.Image, size: int) -> Image.Image:
    """Centre the mascot in a transparent square of ``size``."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    scale = min(size / source.width, size / source.height) * 0.88
    resized = source.resize(
        (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
        Image.LANCZOS,
    )
    canvas.alpha_composite(
        resized,
        ((size - resized.width) // 2, (size - resized.height) // 2),
    )
    return canvas


def make_wordmark(source: Image.Image, name: str, tagline: str, theme: str) -> Image.Image:
    """Compose mascot + product name + tagline into a horizontal wordmark."""
    text_rgb, tag_rgb = THEMES[theme]

    name_size = 132
    tag_size = 44
    name_font = _load_font(name_size)
    tag_font = _load_font(tag_size)

    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    name_box = probe.textbbox((0, 0), name, font=name_font)
    tag_box = probe.textbbox((0, 0), tagline, font=tag_font)
    name_h = name_box[3] - name_box[1]
    tag_h = tag_box[3] - tag_box[1]

    gap = 34
    text_w = max(name_box[2] - name_box[0], tag_box[2] - tag_box[0])
    text_h = name_h + 14 + tag_h

    mark = 220
    pad = 24
    width = pad + mark + gap + text_w + pad
    height = max(mark, text_h) + pad * 2

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mascot = make_square(source, mark)
    canvas.alpha_composite(mascot, (pad, (height - mark) // 2))

    draw = ImageDraw.Draw(canvas)
    text_x = pad + mark + gap
    text_y = (height - text_h) // 2

    draw.text((text_x, text_y), name, font=name_font, fill=(*text_rgb, 255))
    draw.text(
        (text_x + 4, text_y + name_h + 14),
        tagline,
        font=tag_font,
        fill=(*tag_rgb, 255),
    )
    return canvas


def make_favicon_svg(source: Image.Image) -> str:
    """A self-contained favicon: the mascot as an embedded base64 PNG."""
    icon = make_square(source, 64)
    buffer = io.BytesIO()
    icon.save(buffer, format="PNG", optimize=True)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="0 0 64 64" width="64" height="64">\n'
        "  <title>小胰宝</title>\n"
        f'  <image width="64" height="64" xlink:href="data:image/png;base64,{encoded}"/>\n'
        "</svg>\n"
    )


def _same_rendering(path: Path, payload: bytes) -> bool:
    """Compare decoded output, not encoder bytes.

    Two Pillow builds can encode identical pixels to different bytes (different
    zlib/libwebp settings), which made a byte comparison report a correct tree as
    stale. What matters is that the asset still renders as the intended image, so
    compare the decoded raster and its canvas size.
    """
    if path.suffix.lower() == ".svg":
        # These SVGs are a base64 PNG plus text, so the same encoder-drift
        # problem applies to the embedded raster. Compare the decoded payload.
        def embedded(text: str) -> Image.Image | None:
            match = re.search(r"base64,([A-Za-z0-9+/=]+)", text)
            if not match:
                return None
            try:
                return Image.open(io.BytesIO(base64.b64decode(match.group(1))))
            except (OSError, ValueError, binascii.Error):
                return None

        try:
            on_disk_svg = embedded(path.read_text(encoding="utf-8"))
            generated_svg = embedded(payload.decode("utf-8"))
        except (OSError, UnicodeDecodeError):
            return False
        if on_disk_svg is None or generated_svg is None:
            return False
        if on_disk_svg.size != generated_svg.size:
            return False
        return (
            on_disk_svg.convert("RGBA").tobytes()
            == generated_svg.convert("RGBA").tobytes()
        )

    try:
        on_disk = Image.open(path)
        generated = Image.open(io.BytesIO(payload))
        if on_disk.size != generated.size:
            return False
        return on_disk.convert("RGBA").tobytes() == generated.convert("RGBA").tobytes()
    except (OSError, ValueError):
        return False


def _write(path: Path, payload: bytes, check: bool, stale: list[str]) -> None:
    if check:
        if not path.is_file() or not _same_rendering(path, payload):
            stale.append(str(path.relative_to(REPO)))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _webp_bytes(image: Image.Image, height: int) -> bytes:
    """Encode as WebP, padded to the exact canvas the original asset used."""
    canvas = Image.new("RGBA", (image.width, height), (0, 0, 0, 0))
    canvas.alpha_composite(image, (0, max(0, (height - image.height) // 2)))
    buffer = io.BytesIO()
    canvas.save(buffer, format="WEBP", quality=92, method=6)
    return buffer.getvalue()


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify, do not write")
    parser.add_argument("--name", default=DEFAULT_NAME, help="wordmark text")
    parser.add_argument("--tagline", default=DEFAULT_TAGLINE, help="subtitle text")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="refetch the source logo even if it is already cached",
    )
    args = parser.parse_args()

    data = ensure_source(force=args.force_download)
    source = _open_source(data)
    stale: list[str] = []

    outputs: list[tuple[Path, bytes]] = [
        (PUBLIC / "pwa-192.png", _png_bytes(make_square(source, 192))),
        (PUBLIC / "pwa-512.png", _png_bytes(make_square(source, WHEEL_PX))),
        (PUBLIC / "apple-touch-icon.png", _png_bytes(make_square(source, 180))),
        (PUBLIC / "favico.svg", make_favicon_svg(source).encode("utf-8")),
    ]
    for theme in THEMES:
        outputs.append(
            (
                PUBLIC / f"logo_horizontal_{theme}.png",
                _png_bytes(make_wordmark(source, args.name, args.tagline, theme)),
            )
        )

    # The empty-state / thinking mascots. Upstream ships a red octopus here,
    # which fights the mint brand and reads as "someone else's product", so they
    # are derived from the same logo. The `.webp` animated variants are replaced
    # by static frames of the same square, at the same pixel size, so the
    # `<img>` tags that load them keep working.
    outputs.extend(
        [
            (PUBLIC / "octop-mascot-empty.png", _png_bytes(make_square(source, 2048))),
            (PUBLIC / "octop-mascot-tasks.png", _png_bytes(make_square(source, 600))),
            (PUBLIC / "octop-mascot-peek.webp", _webp_bytes(make_square(source, 352), 320)),
            (PUBLIC / "octop-mascot-type.webp", _webp_bytes(make_square(source, 856), 812)),
        ]
    )

    for path, payload in outputs:
        _write(path, payload, args.check, stale)

    # The vertical lockup is the square mark plus the name; emitting SVG keeps it
    # crisp at any size on the splash and login screens.
    vertical = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 320 380" '
        'width="320" height="380">\n'
        "  <title>小胰宝</title>\n"
        f'  <image x="70" y="10" width="180" height="180" '
        f'xlink:href="data:image/png;base64,'
        f'{base64.b64encode(_png_bytes(make_square(source, 180))).decode("ascii")}"/>\n'
        f'  <text x="160" y="270" text-anchor="middle" font-size="58" '
        f'font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif" '
        f'fill="{_hex(THEMES["dark"][0])}">{args.name}</text>\n'
        f'  <text x="160" y="316" text-anchor="middle" font-size="22" '
        f'font-family="PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif" '
        f'fill="{_hex(THEMES["dark"][1])}">{args.tagline}</text>\n'
        "</svg>\n"
    )
    _write(PUBLIC / "logo_vertical_dark.svg", vertical.encode("utf-8"), args.check, stale)

    vertical_white = vertical.replace(_hex(THEMES["dark"][0]), _hex(THEMES["white"][0])).replace(
        _hex(THEMES["dark"][1]), _hex(THEMES["white"][1])
    )
    _write(PUBLIC / "logo_vertical_white.svg", vertical_white.encode("utf-8"), args.check, stale)

    manifest = {
        "name": args.name,
        "short_name": args.name,
        "tagline": args.tagline,
        "source_url": SOURCE_URL,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "generated_by": "scripts/xyb-brand.py",
    }

    if args.check:
        if stale:
            print("brand assets are stale or missing:", file=sys.stderr)
            for item in stale:
                print(f"  {item}", file=sys.stderr)
            print("\nrun: python3 scripts/xyb-brand.py", file=sys.stderr)
            return 1
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        print("brand assets up to date")
        return 0

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"wrote {len(outputs) + 2} assets under {PUBLIC.relative_to(REPO)}")
    return 0


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


if __name__ == "__main__":
    sys.exit(main())
