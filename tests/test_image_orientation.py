"""EXIF orientation: a path source is drawn upright on every backend, and sized
that way (puikit#174).

A phone photo held upright is stored landscape with Orientation 6. The rule is
that every backend draws it upright *and* reports the upright size — the two
have to agree, or a layout fits a portrait picture into a landscape box and
stretches it, which is what macOS did. A :class:`RasterImage` is drawn as
given; ``RasterImage.from_pillow`` is where the tag is still readable.

The reference for "upright" is Pillow's ``ImageOps.exif_transpose``, checked
once against a hand-worked case so the reference itself is pinned.
"""

from __future__ import annotations

import struct
import sys

import pytest

from puikit.image import (
    RasterImage, exif_upright, exif_upright_size, image_size, upright_size)
from puikit.backends import _terminal_graphics as tg

macos = pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
windows = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

ORIENTATIONS = range(1, 9)

#: Stored 32x16, one colour per quadrant, so every one of the eight turns puts
#: a different colour in the top-left corner. Big flat blocks, so a JPEG's
#: chroma subsampling cannot move a sampled colour.
STORED = (32, 16)
QUADRANTS = {"tl": (255, 0, 0), "tr": (0, 255, 0), "bl": (0, 0, 255), "br": (255, 255, 255)}


@pytest.fixture(autouse=True)
def clean_caches():
    tg.clear_cache()
    image_size.cache_clear()
    yield
    tg.clear_cache()
    image_size.cache_clear()


def _photo(tmp_path, orientation: int, fmt: str = "JPEG") -> str:
    Image = pytest.importorskip("PIL.Image")
    w, h = STORED
    image = Image.new("RGB", STORED)
    for name, colour in QUADRANTS.items():
        x0 = 0 if name[1] == "l" else w // 2
        y0 = 0 if name[0] == "t" else h // 2
        image.paste(colour, (x0, y0, x0 + w // 2, y0 + h // 2))
    ext = "jpg" if fmt == "JPEG" else "tiff"
    path = tmp_path / f"o{orientation}.{ext}"
    if fmt == "JPEG":
        exif = Image.Exif()
        exif[0x0112] = orientation
        image.save(path, "JPEG", quality=95, exif=exif)
    else:
        image.save(path, "TIFF", tiffinfo={0x0112: orientation})
    return str(path)


def _corners(width: int, height: int, pixel) -> tuple:
    """The colour at the centre of each quadrant, as ``pixel(x, y)`` reads it."""
    xs, ys = (width // 4, width * 3 // 4), (height // 4, height * 3 // 4)
    return tuple(tuple(pixel(x, y)[:3]) for y in ys for x in xs)


def _close(a: tuple, b: tuple) -> bool:
    return all(abs(p - q) <= 40 for ca, cb in zip(a, b) for p, q in zip(ca, cb))


def _expected(path: str):
    """``(size, corners)`` of the picture as it should be shown."""
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        shown = ImageOps.exif_transpose(image).convert("RGB")
        return shown.size, _pillow_corners(shown)


def _pillow_corners(image) -> tuple:
    return _corners(*image.size, lambda x, y: image.getpixel((x, y)))


def _raster_corners(raster) -> tuple:
    w = raster.width

    def pixel(x, y):
        i = (y * w + x) * 4
        return tuple(raster.data[i:i + 3])

    return _corners(raster.width, raster.height, pixel)


# --------------------------------------------------------------------------- #
# The reference, pinned
# --------------------------------------------------------------------------- #

def test_the_reference_turns_orientation_6_a_quarter_clockwise(tmp_path):
    # Orientation 6: the stored top-left is shown top-right, the stored
    # bottom-left top-left.
    size, corners = _expected(_photo(tmp_path, 6))
    assert size == (16, 32)
    tl, tr, _bl, _br = corners
    assert _close((tl, tr), (QUADRANTS["bl"], QUADRANTS["tl"]))


# --------------------------------------------------------------------------- #
# The shared pieces in puikit.image
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_upright_size_swaps_only_the_quarter_turns(orientation):
    expected = (2, 3) if orientation >= 5 else (3, 2)
    assert upright_size(3, 2, orientation) == expected


@pytest.mark.parametrize("tag", [None, 0, 9, "6"])
def test_a_missing_or_bogus_tag_leaves_the_size_alone(tag):
    assert upright_size(3, 2, tag) == (3, 2)


@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_the_header_parse_reports_the_upright_size(tmp_path, orientation):
    path = _photo(tmp_path, orientation)
    assert image_size(path) == _expected(path)[0]


def _jpeg_with_app1(tmp_path, *payloads: bytes) -> str:
    """A tagless 32x16 JPEG with the given APP1 segments spliced in after SOI."""
    Image = pytest.importorskip("PIL.Image")
    plain = tmp_path / "plain.jpg"
    Image.new("RGB", STORED).save(plain, "JPEG")
    data = plain.read_bytes()
    segments = b"".join(b"\xff\xe1" + struct.pack(">H", len(p) + 2) + p for p in payloads)
    path = tmp_path / "spliced.jpg"
    path.write_bytes(data[:2] + segments + data[2:])
    return str(path)


def _exif_payload(order: str, orientation: int) -> bytes:
    mark = b"II" if order == "<" else b"MM"
    ifd = struct.pack(order + "H", 1) + struct.pack(
        order + "HHIHH", 0x0112, 3, 1, orientation, 0) + struct.pack(order + "I", 0)
    return b"Exif\x00\x00" + mark + struct.pack(order + "HI", 42, 8) + ifd


@pytest.mark.parametrize("order", ["<", ">"])
def test_both_byte_orders_are_read(tmp_path, order):
    assert image_size(_jpeg_with_app1(tmp_path, _exif_payload(order, 6))) == (16, 32)


def test_an_app1_that_is_not_exif_is_passed_over(tmp_path):
    # XMP also lives in APP1 and has no orientation tag to offer; it must not
    # end the search for the Exif segment, or reset what that segment said.
    xmp = b"http://ns.adobe.com/xap/1.0/\x00<x:xmpmeta/>"
    assert image_size(_jpeg_with_app1(tmp_path, xmp, _exif_payload("<", 8))) == (16, 32)
    image_size.cache_clear()
    assert image_size(_jpeg_with_app1(tmp_path, _exif_payload("<", 8), xmp)) == (16, 32)


def test_a_truncated_exif_block_is_a_picture_without_a_tag(tmp_path):
    assert image_size(_jpeg_with_app1(tmp_path, _exif_payload("<", 6)[:14])) == STORED


@pytest.mark.parametrize("fmt", ["JPEG", "TIFF"])
@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_an_unloaded_pillow_image_is_measured_upright(tmp_path, orientation, fmt):
    # The TIFF plugin reports the turned size before load and the JPEG plugin
    # the stored one; the answer has to be the upright size for both.
    Image = pytest.importorskip("PIL.Image")
    path = _photo(tmp_path, orientation, fmt)
    with Image.open(path) as image:
        assert exif_upright_size(image) == _expected(path)[0]


def test_an_upright_picture_is_not_copied():
    Image = pytest.importorskip("PIL.Image")
    image = Image.new("RGB", (3, 2))
    assert exif_upright(image) is image


# --------------------------------------------------------------------------- #
# RasterImage.from_pillow — the one place a raster's tag is still readable
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_from_pillow_turns_a_tagged_picture_upright(tmp_path, orientation):
    Image = pytest.importorskip("PIL.Image")
    path = _photo(tmp_path, orientation)
    with Image.open(path) as image:
        raster = RasterImage.from_pillow(image)
    size, corners = _expected(path)
    assert raster.size == size
    assert _close(_raster_corners(raster), corners)


def test_from_pillow_can_keep_the_stored_order(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    with Image.open(_photo(tmp_path, 6)) as image:
        assert RasterImage.from_pillow(image, upright=False).size == STORED


# --------------------------------------------------------------------------- #
# The terminal backends (Pillow)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("fmt", ["JPEG", "TIFF"])
@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_the_terminal_draws_and_sizes_upright(tmp_path, orientation, fmt):
    path = _photo(tmp_path, orientation, fmt)
    size, corners = _expected(path)
    assert tg.natural_size(path) == size
    decoded = tg._open(path)
    assert decoded.size == size
    assert _close(_pillow_corners(decoded), corners)


# --------------------------------------------------------------------------- #
# macOS — NSImage draws upright on its own; the size has to follow it
# --------------------------------------------------------------------------- #

@macos
@pytest.mark.parametrize("fmt", ["JPEG", "TIFF"])
@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_macos_sizes_what_nsimage_draws(tmp_path, orientation, fmt):
    AppKit = pytest.importorskip("AppKit")
    from puikit.backends.macos_backend import _imageio_pixel_size

    path = _photo(tmp_path, orientation, fmt)
    size = _expected(path)[0]
    assert _imageio_pixel_size(path) == size
    drawn = AppKit.NSImage.alloc().initWithContentsOfFile_(path).size()
    assert (int(drawn.width), int(drawn.height)) == size


# --------------------------------------------------------------------------- #
# Windows — WIC hands back the stored picture; PuiKit turns it
# --------------------------------------------------------------------------- #

@windows
@pytest.mark.parametrize("fmt", ["JPEG", "TIFF"])
@pytest.mark.parametrize("orientation", ORIENTATIONS)
def test_windows_draws_and_sizes_upright(tmp_path, orientation, fmt):
    from puikit.backends import _win32_native as native

    path = _photo(tmp_path, orientation, fmt)
    size, corners = _expected(path)
    factory = native.create_wic_factory()
    assert native.wic_image_size(factory, path) == size
    source = native.wic_load_bitmap_source(factory, path)
    assert source is not None
    try:
        w, h = native.wic_bitmap_size(source)
        raw = native.wic_copy_pixels_bgra(source, w, h)
    finally:
        source.release()
    assert (w, h) == size
    rgba = native.rgba_to_bgra(raw)  # the swizzle is its own inverse
    assert _close(_raster_corners(RasterImage(w, h, rgba)), corners)
