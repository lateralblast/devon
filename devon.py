#!/usr/bin/env python3
"""
Works with Microsoft Visio stencil and drawing files two ways:

- Online, via https://vss.draw.io: automates the browser to upload a
  classic Visio stencil (.vss) file, confirm the "no sensitive information"
  checkbox, click Convert, and save the converted draw.io library file.
  The site itself only accepts .vss, not .vssx, .vsd, .vsdx, or .vsx.
- Locally, entirely offline: parses a .vss/.vssx/.vsx stencil or
  .vsd/.vsdx drawing file directly with libvisio and extracts each
  shape/page as its own file (SVG or JPEG), with no browser or upload
  involved.

Either path can also split a converted or extracted library into
individual per-shape/page files.

Usage:
    python3 devon.py --upload Stencil.vss --download Stencil.xml
    python3 devon.py --input Stencil.vss --split --output shapes/ --to svg

Requires: selenium (pip install selenium) and a Chrome/Chromium install for
the online path. Selenium 4.6+ downloads a matching chromedriver
automatically. The local path additionally needs libvisio's vss2raw/
vss2xhtml/vsd2raw/vsd2xhtml (and optionally emf2svg-conv, rsvg-convert) on
PATH; see README.md.
"""
__version__ = "0.2.4"
__description__ = "Diagram Extractor for Visio with local and ONline capability (via draw.io)"

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
import zlib


def _ensure_selenium():
    """Import selenium, installing it via pip on the fly if it's missing."""
    try:
        import selenium  # noqa: F401
    except ImportError:
        print("selenium not found; installing it with pip...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "selenium>=4.6"])
        import selenium  # noqa: F401


def _ensure_pillow():
    """Import Pillow, installing it via pip on the fly if it's missing."""
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow not found; installing it with pip...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow>=10"])
        import PIL  # noqa: F401


_ensure_selenium()

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SITE_URL = "https://vss.draw.io"

VERBOSE = False


def vlog(message: str) -> None:
    """Print a stage-progress message to stderr, only when --verbose is set."""
    if VERBOSE:
        print(f"[verbose] {message}", file=sys.stderr)


def build_driver(download_dir: str, headless: bool) -> webdriver.Chrome:
    vlog(f"Launching Chrome{' (headless)' if headless else ''}...")
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1200,900")
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        },
    )
    return webdriver.Chrome(options=options)


def wait_for_result(driver, download_dir: str, timeout: int) -> str:
    """Poll the page status banner and the download directory until the
    conversion finishes (success/error) or times out. Returns the path to
    the downloaded file on success; raises RuntimeError/TimeoutError otherwise."""
    deadline = time.time() + timeout
    seen_before = set(os.listdir(download_dir))
    while time.time() < deadline:
        status = driver.find_element(By.ID, "status")
        classes = (status.get_attribute("class") or "").split()
        if "error" in classes:
            raise RuntimeError(f"Conversion failed: {status.text.strip()}")

        entries = [f for f in os.listdir(download_dir) if f not in seen_before]
        finished = [f for f in entries if not f.endswith(".crdownload")]
        in_progress = [f for f in entries if f.endswith(".crdownload")]
        if finished and not in_progress:
            vlog(f"Downloaded {finished[0]}")
            return os.path.join(download_dir, finished[0])

        time.sleep(0.5)
    raise TimeoutError(f"Timed out after {timeout}s waiting for the conversion/download")


def convert_one_vss(driver, download_dir: str, upload_path: str, timeout: int) -> str:
    """Drive vss.draw.io through one full upload -> confirm -> convert cycle
    (a fresh page load each time keeps the site's state clean between
    conversions) and return the path of the resulting download."""
    wait = WebDriverWait(driver, timeout)
    vlog(f"Loading {SITE_URL}...")
    driver.get(SITE_URL)

    vlog(f"Uploading {upload_path}...")
    file_input = wait.until(EC.presence_of_element_located((By.ID, "fileInput")))
    file_input.send_keys(upload_path)

    vlog("Confirming the no-sensitive-information checkbox...")
    checkbox = wait.until(EC.element_to_be_clickable((By.ID, "confirmCheckbox")))
    if not checkbox.is_selected():
        checkbox.click()

    vlog("Clicking Convert...")
    convert_btn = wait.until(EC.element_to_be_clickable((By.ID, "convertBtn")))
    convert_btn.click()

    vlog("Waiting for the conversion to finish...")
    return wait_for_result(driver, download_dir, timeout)


def parse_library(content: str) -> list:
    """Parse a draw.io <mxlibrary> file (as produced by vss.draw.io) into its
    list of shape dicts (each with "xml", "w", "h", "title")."""
    content = content.strip()
    if not (content.startswith("<mxlibrary>") and content.endswith("</mxlibrary>")):
        raise ValueError("Not an <mxlibrary>...</mxlibrary> file")
    inner = content[len("<mxlibrary>"):-len("</mxlibrary>")]
    # vss.draw.io HTML-escapes quotes inside shape titles without re-escaping
    # them for JSON, so the raw JSON is invalid until entities are decoded.
    return json.loads(html.unescape(inner))


def no_spaces(name: str) -> str:
    """Replace each space in name with a single underscore, so a filename
    derived from it (e.g. from an uploaded file's own name) never carries
    spaces through into a generated filename."""
    return name.replace(" ", "_")


def safe_shape_filename(title: str, index: int, seen: dict, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", title or "").strip("_") or f"shape_{index}"
    count = seen.get(base, 0)
    seen[base] = count + 1
    return f"{base}.{ext}" if count == 0 else f"{base}_{count + 1}.{ext}"


SVG_IMAGE_RE = re.compile(r"image=data:image/svg\+xml,([A-Za-z0-9+/=]+)")


def decode_shape_xml(xml_field: str) -> str:
    """Decompress a shape's "xml" field into its plain mxGraphModel XML.
    vss.draw.io stores it as base64(deflateRaw(encodeURIComponent(xml)))."""
    raw = base64.b64decode(xml_field)
    inflated = zlib.decompress(raw, -15)
    return urllib.parse.unquote(inflated.decode("utf-8"))


def extract_svg(xml_field: str) -> bytes | None:
    """Return a shape's embedded SVG artwork as raw bytes, or None if the
    shape has no embedded image (some Visio masters convert to an empty
    placeholder with no visible content)."""
    plain_xml = decode_shape_xml(xml_field)
    match = SVG_IMAGE_RE.search(plain_xml)
    if not match:
        return None
    return base64.b64decode(match.group(1))


def rasterize_svg_to_jpg(svg_content, output_path: str, tmp_dir: str, index: int, max_size: int = 2000) -> None:
    """Rasterize SVG content (str or bytes) to a white-background JPEG, via
    rsvg-convert (SVG -> PNG, capped to max_size on the longest side, since
    some embedded artwork has a native resolution above librsvg's internal
    32767px limit) and Pillow (PNG -> JPEG)."""
    if shutil.which("rsvg-convert") is None:
        raise RuntimeError(
            "'rsvg-convert' not found on PATH. Install librsvg "
            "(e.g. `brew install librsvg`) to use --to jpg."
        )
    _ensure_pillow()
    from PIL import Image

    svg_path = os.path.join(tmp_dir, f"raster_{index}.svg")
    png_path = os.path.join(tmp_dir, f"raster_{index}.png")
    with open(svg_path, "wb" if isinstance(svg_content, bytes) else "w") as f:
        f.write(svg_content)
    subprocess.run(
        [
            "rsvg-convert", "-w", str(max_size), "-h", str(max_size), "-a",
            "-b", "white", "-o", png_path, svg_path,
        ],
        capture_output=True, check=True,
    )
    # rsvg-convert's -b white already flattens the image onto an opaque
    # background, so dropping any alpha channel here is safe.
    with Image.open(png_path) as im:
        im.convert("RGB").save(output_path, "JPEG", quality=90)


def rasterize_svg_to_png(svg_content, output_path: str, tmp_dir: str, index: int, max_size: int = 2000) -> None:
    """Rasterize SVG content (str or bytes) to a PNG, via rsvg-convert
    (capped to max_size on the longest side, since some embedded artwork
    has a native resolution above librsvg's internal 32767px limit).
    Unlike --to jpg, transparency is preserved rather than flattened onto
    a white background."""
    if shutil.which("rsvg-convert") is None:
        raise RuntimeError(
            "'rsvg-convert' not found on PATH. Install librsvg "
            "(e.g. `brew install librsvg`) to use --to png."
        )
    svg_path = os.path.join(tmp_dir, f"raster_{index}.svg")
    with open(svg_path, "wb" if isinstance(svg_content, bytes) else "w") as f:
        f.write(svg_content)
    subprocess.run(
        [
            "rsvg-convert", "-w", str(max_size), "-h", str(max_size), "-a",
            "-o", output_path, svg_path,
        ],
        capture_output=True, check=True,
    )


def split_library(content: str, out_dir: str, fmt: str = "xml") -> tuple[int, int]:
    """Split an <mxlibrary> file's shapes into individual files in out_dir,
    one per shape, named after each shape's title. fmt "xml" writes
    single-shape library files (default); fmt "svg"/"jpg"/"png" extract
    each shape's embedded artwork instead (rasterized for "jpg"/"png"),
    skipping shapes that have none. Returns (written, skipped)."""
    shapes = parse_library(content)
    vlog(f"Parsed {len(shapes)} shape(s) from the library")
    os.makedirs(out_dir, exist_ok=True)
    seen = {}
    written = 0
    skipped = 0
    tmp_dir = tempfile.mkdtemp(prefix="devon_raster_") if fmt in ("jpg", "png") else None
    try:
        for i, shape in enumerate(shapes):
            title = shape.get("title") or f"shape_{i}"
            if fmt in ("svg", "jpg", "png"):
                svg_bytes = extract_svg(shape["xml"])
                if svg_bytes is None:
                    vlog(f"Skipping '{title}': no visible artwork")
                    skipped += 1
                    continue
                if fmt == "svg":
                    filename = safe_shape_filename(shape.get("title"), i, seen, "svg")
                    vlog(f"Writing '{title}' to {filename}")
                    with open(os.path.join(out_dir, filename), "wb") as f:
                        f.write(svg_bytes)
                elif fmt == "jpg":
                    filename = safe_shape_filename(shape.get("title"), i, seen, "jpg")
                    vlog(f"Rasterizing '{title}' to {filename}")
                    rasterize_svg_to_jpg(svg_bytes, os.path.join(out_dir, filename), tmp_dir, i)
                else:
                    filename = safe_shape_filename(shape.get("title"), i, seen, "png")
                    vlog(f"Rasterizing '{title}' to {filename}")
                    rasterize_svg_to_png(svg_bytes, os.path.join(out_dir, filename), tmp_dir, i)
            else:
                filename = safe_shape_filename(shape.get("title"), i, seen, "xml")
                vlog(f"Writing '{title}' to {filename}")
                shape_content = f"<mxlibrary>{json.dumps([shape], ensure_ascii=False)}</mxlibrary>"
                with open(os.path.join(out_dir, filename), "w") as f:
                    f.write(shape_content)
            written += 1
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return written, skipped


OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

VSS_STARTPAGE_RE = re.compile(
    r"startPage\(draw:name: (.*?), svg:height: [\d.]+in, svg:width: [\d.]+in\)"
)
VSS_SVG_BLOCK_RE = re.compile(r"<svg:svg\b.*?</svg:svg>", re.DOTALL)
IMAGE_MIME_RE = re.compile(r'xlink:href="data:image/([a-zA-Z0-9+.-]+);base64')
UNRENDERABLE_IMAGE_MIMES = {"emf", "x-emf", "wmf", "x-wmf"}
SVG_IMAGE_TAG_RE = re.compile(r"<svg:image\b[^>]*?/>")
XML_ATTR_RE = re.compile(r'([\w:-]+)="([^"]*)"')
DATA_URI_RE = re.compile(r"data:image/([a-zA-Z0-9+.-]+);base64,(.+)", re.DOTALL)


def is_vss_file(path: str) -> bool:
    """True if path looks like a legacy (OLE2 compound file) Visio document
    - either a .vss stencil or a .vsd drawing, which share the same
    container format - as opposed to an <mxlibrary> XML file."""
    with open(path, "rb") as f:
        return f.read(len(OLE2_MAGIC)) == OLE2_MAGIC


def is_vsd_file(path: str) -> bool:
    """True if path is a legacy Visio DRAWING (.vsd/.vsdm), as opposed to a
    stencil (.vss/.vssm): both share the same OLE2 container and can't be
    told apart by content alone, so this also checks the extension."""
    return is_vss_file(path) and path.lower().endswith((".vsd", ".vsdm"))


def is_visio_ooxml_package(path: str) -> bool:
    """True if path looks like a modern (OOXML/zip package) Visio file,
    stencil or drawing (.vssx/.vssm/.vsdx/.vsdm), as opposed to a plain zip
    bundling loose files. Both share a "visio/document.xml" part, so this
    is checked ahead of generic zip handling."""
    if not zipfile.is_zipfile(path):
        return False
    with zipfile.ZipFile(path) as zf:
        return "visio/document.xml" in zf.namelist()


def is_vssx_file(path: str) -> bool:
    """True if path is a modern Visio STENCIL (.vssx/.vssm): an OOXML
    Visio package whose extension marks it as a stencil. Content alone
    can't reliably tell a stencil from a drawing (.vsdx/.vsdm) here, the
    same way it can't for the legacy .vss/.vsd pair: a stencil can carry
    a "visio/pages/pages.xml" part for its own helper preview page, and a
    drawing can carry a "visio/masters/masters.xml" part for local copies
    of the master shapes used on its pages, so either part can appear in
    either format."""
    return is_visio_ooxml_package(path) and path.lower().endswith((".vssx", ".vssm"))


def is_vsdx_file(path: str) -> bool:
    """True if path is a modern Visio DRAWING (.vsdx/.vsdm): an OOXML
    Visio package whose extension marks it as a drawing. See is_vssx_file
    for why content alone can't reliably tell the two apart."""
    return is_visio_ooxml_package(path) and path.lower().endswith((".vsdx", ".vsdm"))


def is_visio_xml_document(path: str) -> bool:
    """True if path looks like a legacy Visio XML-format file (.vsx
    stencil or .vdx drawing): plain XML with a <VisioDocument> root, as
    opposed to the OLE2 binary (.vss/.vsd) or OOXML zip (.vssx/.vsdx)
    containers. Checked on the raw bytes of a small head chunk rather than
    parsing the file, since it's only ever used to tell this format apart
    from the others, not to read its content."""
    with open(path, "rb") as f:
        head = f.read(4096)
    return b"<VisioDocument" in head


def is_vsx_file(path: str) -> bool:
    """True if path is a legacy Visio XML STENCIL (.vsx): a
    <VisioDocument> XML file whose extension marks it as a stencil. Like
    the OLE2 .vss/.vsd pair, content alone doesn't reliably distinguish a
    stencil from a drawing here, since even a stencil carries a helper
    Page for master previews."""
    return is_visio_xml_document(path) and path.lower().endswith(".vsx")


def is_drawing_file(path: str) -> bool:
    """True if path is a Visio DRAWING (legacy .vsd/.vsdm, or modern
    .vsdx/.vsdm), which splits into one file per page, as opposed to a
    STENCIL, which splits into one file per master shape."""
    return is_vsd_file(path) or is_vsdx_file(path)


def is_visio_document_file(path: str) -> bool:
    """True if path is a Visio file libvisio/vss.draw.io can work with
    directly (legacy .vss stencil or .vsd drawing, modern .vssx/.vsdx, or
    legacy XML .vsx stencil), as opposed to a <mxlibrary> XML file or a
    zip bundling one or more of either."""
    return is_vss_file(path) or is_vssx_file(path) or is_vsdx_file(path) or is_vsx_file(path)


def extract_files_from_zip(zip_path: str, tmp_dir: str, ext_groups) -> list:
    """Extract every file matching the first group of extensions (tried in
    order, case-insensitive) that has any matches in the zip archive, into
    tmp_dir. ext_groups is a list of extension tuples, e.g. [(".vss",)] or
    [(".vss",), (".xml",)] to fall back to .xml if there's no .vss. Returns
    the extracted paths. Raises ValueError if nothing matches."""
    vlog(f"Reading zip archive {zip_path}...")
    with zipfile.ZipFile(zip_path) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        for exts in ext_groups:
            candidates = sorted(n for n in names if n.lower().endswith(exts))
            if candidates:
                for name in candidates:
                    zf.extract(name, tmp_dir)
                vlog(f"Extracted {len(candidates)} file(s): {', '.join(candidates)}")
                return [os.path.join(tmp_dir, name) for name in candidates]
        wanted = " or ".join(exts[0] for exts in ext_groups)
        raise ValueError(f"No {wanted} file found inside {zip_path}")


def extract_inputs_from_zip(zip_path: str, tmp_dir: str) -> list:
    """Extract every .vss/.vssx/.vsd/.vsdx/.vsx file found in a zip archive
    into tmp_dir (or, failing that, every .xml file), and return their
    paths. Raises ValueError if neither is found."""
    return extract_files_from_zip(zip_path, tmp_dir, [(".vss", ".vssx", ".vsd", ".vsdx", ".vsx"), (".xml",)])


DRAWING_TAGS = ("path", "text", "rect", "circle", "ellipse", "polygon", "polyline", "line", "image")


def block_has_renderable_content(block: str) -> bool:
    """True if a vss2xhtml <svg:svg> block is fully displayable in a browser.
    Visio masters whose artwork (or any part of it) is a Windows EMF/WMF
    metafile come through as an unrenderable data URI. Even one such
    reference leaves a visible broken-image icon, so any shape containing
    one is excluded rather than shipped partially broken. Content recovered
    by emf2svg-conv uses unprefixed tags (e.g. <path>, not <svg:path>), so
    both forms are checked."""
    mimes = IMAGE_MIME_RE.findall(block)
    if any(mime.lower() in UNRENDERABLE_IMAGE_MIMES for mime in mimes):
        return False
    return any(f"<{tag}" in block or f"<svg:{tag}" in block for tag in DRAWING_TAGS)


def convert_emf_to_svg_group(emf_bytes: bytes, x: str, y: str, width: str, height: str, tmp_dir: str, index: int) -> str:
    """Render an embedded EMF/WMF blob to SVG with emf2svg-conv and wrap it as
    a positioned, correctly-scaled nested <svg:svg>, standing in for the
    original <svg:image> tag. Raises on failure (caller decides fallback)."""
    in_path = os.path.join(tmp_dir, f"emf_{index}.emf")
    out_path = os.path.join(tmp_dir, f"emf_{index}.svg")
    with open(in_path, "wb") as f:
        f.write(emf_bytes)
    subprocess.run(
        ["emf2svg-conv", "-i", in_path, "-o", out_path, "-p"],
        capture_output=True, check=True,
    )
    with open(out_path, "r") as f:
        converted = f.read()
    # emf2svg-conv emits its own leading XML declaration, which is only
    # valid at the very start of a document; strip it before nesting.
    converted = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", converted)

    root_match = re.search(r"<svg\b([^>]*)>", converted)
    if not root_match:
        raise ValueError("emf2svg-conv produced no <svg> root element")
    root_attrs = dict(XML_ATTR_RE.findall(root_match.group(1)))
    native_w, native_h = root_attrs.get("width"), root_attrs.get("height")
    if not native_w or not native_h:
        raise ValueError("emf2svg-conv output has no width/height")

    new_root = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {native_w} {native_h}" preserveAspectRatio="none">'
    )
    converted = re.sub(r"<svg\b[^>]*>", new_root, converted, count=1)
    return f'<svg:g transform="translate({x},{y})">{converted}</svg:g>'


def recover_unrenderable_images(block: str, tmp_dir: str) -> str:
    """Replace each unrenderable (EMF/WMF) <svg:image> in block with a real
    rendered SVG via emf2svg-conv, when that tool is available. Images that
    fail to convert, or aren't EMF/WMF, are left untouched."""
    if shutil.which("emf2svg-conv") is None:
        return block

    counter = [0]

    def repl(match):
        tag = match.group(0)
        attrs = dict(XML_ATTR_RE.findall(tag))
        href = attrs.get("xlink:href", "")
        data_match = DATA_URI_RE.match(href)
        if not data_match or data_match.group(1).lower() not in UNRENDERABLE_IMAGE_MIMES:
            return tag
        try:
            emf_bytes = base64.b64decode(data_match.group(2))
            counter[0] += 1
            vlog(f"Recovering embedded EMF/WMF image #{counter[0]} via emf2svg-conv...")
            return convert_emf_to_svg_group(
                emf_bytes, attrs.get("x", "0"), attrs.get("y", "0"),
                attrs.get("width", "0"), attrs.get("height", "0"),
                tmp_dir, counter[0],
            )
        except Exception:
            return tag

    return SVG_IMAGE_TAG_RE.sub(repl, block)


def split_visio_document(doc_path: str, out_dir: str, fmt: str, raw_tool: str, xhtml_tool: str) -> tuple[int, int]:
    """Split a Visio document (a .vss/.vssx/.vsx stencil's masters, or a
    .vsd/.vsdx drawing's pages) into individual files, entirely offline,
    using libvisio: raw_tool supplies each item's real name (via its "draw:name"
    property) and xhtml_tool supplies the rendered artwork. Both walk the
    file's items in the same order, which this pairs up positionally
    (validated by matching dimensions). Items whose artwork is an embedded
    Windows EMF/WMF metafile (which libvisio can't rasterize and browsers
    can't display) are recovered with emf2svg-conv when it's installed,
    otherwise skipped. fmt "svg" (default) writes the rendered SVG
    directly; fmt "jpg"/"png" rasterizes it. Returns (written, skipped)."""
    for tool in (raw_tool, xhtml_tool):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"'{tool}' not found on PATH. Install libvisio "
                "(e.g. `brew install libvisio`) to split this file directly."
            )

    vlog(f"Running {raw_tool} on {doc_path} to get item names...")
    raw_out = subprocess.run(
        [raw_tool, doc_path], capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    names = VSS_STARTPAGE_RE.findall(raw_out)

    vlog(f"Running {xhtml_tool} on {doc_path} to render artwork...")
    svg_out = subprocess.run(
        [xhtml_tool, doc_path], capture_output=True, check=True,
    ).stdout.decode("utf-8", errors="replace")
    blocks = VSS_SVG_BLOCK_RE.findall(svg_out)

    if len(names) != len(blocks) or not names:
        raise RuntimeError(
            f"libvisio produced {len(names)} name(s) but {len(blocks)} rendered "
            "item(s); can't reliably pair them up."
        )
    vlog(f"Paired {len(names)} name(s) with their rendered artwork")

    os.makedirs(out_dir, exist_ok=True)
    seen = {}
    written = 0
    skipped = 0
    tmp_dir = tempfile.mkdtemp(prefix="devon_emf_")
    try:
        for i, (name, block) in enumerate(zip(names, blocks)):
            block = recover_unrenderable_images(block, tmp_dir)
            if not block_has_renderable_content(block):
                vlog(f"Skipping '{name}': no renderable content")
                skipped += 1
                continue
            svg_doc = '<?xml version="1.0" encoding="UTF-8"?>\n' + block + "\n"
            if fmt == "jpg":
                filename = safe_shape_filename(name, i, seen, "jpg")
                vlog(f"Rasterizing '{name}' to {filename}")
                rasterize_svg_to_jpg(svg_doc, os.path.join(out_dir, filename), tmp_dir, i)
            elif fmt == "png":
                filename = safe_shape_filename(name, i, seen, "png")
                vlog(f"Rasterizing '{name}' to {filename}")
                rasterize_svg_to_png(svg_doc, os.path.join(out_dir, filename), tmp_dir, i)
            else:
                filename = safe_shape_filename(name, i, seen, "svg")
                vlog(f"Writing '{name}' to {filename}")
                with open(os.path.join(out_dir, filename), "w") as f:
                    f.write(svg_doc)
            written += 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    return written, skipped


def split_vss(vss_path: str, out_dir: str, fmt: str = "svg") -> tuple[int, int]:
    """Split a Visio stencil (legacy binary .vss, legacy XML .vsx, or
    modern .vssx) file's masters into individual per-shape files. See
    split_visio_document."""
    return split_visio_document(vss_path, out_dir, fmt, "vss2raw", "vss2xhtml")


def split_vsd(vsd_path: str, out_dir: str, fmt: str = "svg") -> tuple[int, int]:
    """Split a Visio drawing (legacy .vsd or modern .vsdx) file's pages
    into individual per-page files. See split_visio_document."""
    return split_visio_document(vsd_path, out_dir, fmt, "vsd2raw", "vsd2xhtml")


def split_one_input(path: str, target_dir: str, fmt: str) -> tuple[int, int]:
    """Dispatch a single resolved --input file (a raw Visio document, or
    an <mxlibrary> XML file) to the matching split_* function, based on
    is_visio_document_file/is_drawing_file, logging the detected type.
    Returns (written, skipped). Exits if fmt is "xml" and path is a raw
    document, since there's no per-shape library format for those."""
    if is_visio_document_file(path):
        if fmt == "xml":
            sys.exit(
                "--to xml is not supported when --input is a .vss/.vssx/.vsd/.vsdx/.vsx "
                "file; use --to svg, --to jpg, or --to png"
            )
        if is_drawing_file(path):
            vlog("Detected a raw .vsd/.vsdx drawing; splitting into per-page files")
            return split_vsd(path, target_dir, fmt)
        vlog("Detected a raw .vss/.vssx/.vsx stencil; splitting into per-shape files")
        return split_vss(path, target_dir, fmt)
    vlog("Detected an <mxlibrary> file; parsing and splitting")
    with open(path, "r") as f:
        content = f.read()
    return split_library(content, target_dir, fmt)


BROWSER_BINARIES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
BROWSER_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _find_browser() -> str | None:
    """Best-effort search for an installed Chrome/Chromium: PATH first, then
    the usual macOS .app install locations (not on PATH by default)."""
    for name in BROWSER_BINARIES:
        path = shutil.which(name)
        if path:
            return path
    for path in BROWSER_PATHS:
        if os.path.isfile(path):
            return path
    return None


# Which library provides each external (non-Python) command-line tool, so
# --install can group e.g. vss2raw/vss2xhtml/vsd2raw/vsd2xhtml under a
# single libvisio install rather than trying it four times.
TOOL_LIBRARY = {
    "rsvg-convert": "librsvg",
    "vss2raw": "libvisio",
    "vss2xhtml": "libvisio",
    "vsd2raw": "libvisio",
    "vsd2xhtml": "libvisio",
    "emf2svg-conv": "libemf2svg",
}

# Supported package managers, tried in this order: (binary on PATH, install
# command prefix, {library: package name}). A library mapped to None isn't
# known to be packaged for that manager.
PACKAGE_MANAGERS = [
    ("brew", ["brew", "install"], {
        "librsvg": "librsvg",
        "libvisio": "libvisio",
        "libemf2svg": "libemf2svg",
    }),
    ("apt-get", ["sudo", "apt-get", "install", "-y"], {
        "librsvg": "librsvg2-bin",
        "libvisio": "libvisio-tools",
        "libemf2svg": "emf2svg",
    }),
    ("dnf", ["sudo", "dnf", "install", "-y"], {
        "librsvg": "librsvg2-tools",
        "libvisio": "libvisio-tools",
        "libemf2svg": None,
    }),
    ("pacman", ["sudo", "pacman", "-S", "--noconfirm"], {
        "librsvg": "librsvg",
        "libvisio": "libvisio",
        "libemf2svg": None,
    }),
]


# Which pip package provides each required Python module, keyed by the
# same label used in checks (its import name differs for Pillow, hence the
# separate mapping rather than reusing the label).
PYTHON_PACKAGES = {
    "selenium": ("selenium", "selenium>=4.6"),
    "Pillow": ("PIL", "Pillow>=10"),
}


def _find_package_manager():
    for name, cmd_prefix, mapping in PACKAGE_MANAGERS:
        if shutil.which(name):
            return name, cmd_prefix, mapping
    return None, None, None


def install_python_packages(labels) -> None:
    """Best-effort pip install of the given Python package labels (e.g.
    "Pillow"). Never raises: a failed install just leaves the
    corresponding package reported as still missing afterwards."""
    for label in sorted(labels):
        _, pip_spec = PYTHON_PACKAGES[label]
        print(f"  installing {label} via pip ({pip_spec})...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_spec])
        except subprocess.CalledProcessError as e:
            print(f"  failed to install {label}: {e}")


def install_libraries(libraries: set) -> None:
    """Best-effort install of the given library names (e.g. {"libvisio"})
    via whichever supported system package manager is on PATH. Never
    raises: a failed/unknown install just leaves the corresponding tool(s)
    reported as still missing afterwards."""
    pm_name, cmd_prefix, mapping = _find_package_manager()
    if not pm_name:
        print("  no supported package manager found (tried brew, apt-get, dnf, pacman)")
        print("  install these manually, see README.md")
        return

    for library in sorted(libraries):
        package = mapping.get(library)
        if not package:
            print(f"  no known {pm_name} package for {library}; install manually, see README.md")
            continue
        print(f"  installing {library} via {pm_name} ({package})...")
        try:
            subprocess.run(cmd_prefix + [package], check=True)
        except subprocess.CalledProcessError as e:
            print(f"  failed to install {library}: {e}")


def check_config(install: bool = False, quiet: bool = False) -> int:
    """Check every Python-package and PATH dependency this script can use,
    print a report, and return an exit code (0 if all unconditionally
    required ones are present, 1 otherwise). Dependencies needed only for
    specific flags (e.g. --to jpg, --input on a raw file) are reported but
    don't affect the exit code, since not every invocation needs them. If
    install is True, attempts to install missing Python packages via pip
    and missing external (non-Python) tools via the system package
    manager, before reporting. If quiet is True, the report is suppressed
    when every required dependency is present (still shown on failure)."""
    def tool_check(name, hint):
        return (name, "PATH", shutil.which(name), False, hint)

    checks = [
        ("selenium", "Python package", _has_module("selenium"), True,
         "pip install selenium>=4.6"),
        ("Chrome or Chromium", "browser", _find_browser(), True,
         "install Google Chrome or Chromium, needed for the online --upload path"),
        ("Pillow", "Python package", _has_module("PIL"), False,
         "pip install Pillow>=10, needed for --to jpg"),
        tool_check("rsvg-convert", "install librsvg (e.g. `brew install librsvg`), needed for --to jpg/png"),
        tool_check("vss2raw", "install libvisio (e.g. `brew install libvisio`), needed to split raw .vss/.vssx/.vsx files locally"),
        tool_check("vss2xhtml", "install libvisio, needed to split raw .vss/.vssx/.vsx files locally"),
        tool_check("vsd2raw", "install libvisio, needed to split raw .vsd/.vsdx files locally"),
        tool_check("vsd2xhtml", "install libvisio, needed to split raw .vsd/.vsdx files locally"),
        tool_check("emf2svg-conv", "install libemf2svg (e.g. `brew install libemf2svg`), optional, recovers EMF/WMF artwork"),
    ]

    if install:
        missing_python_packages = [
            label for label, kind, found, _, _ in checks
            if kind == "Python package" and not found
        ]
        if missing_python_packages:
            print("Installing missing Python packages:\n")
            install_python_packages(missing_python_packages)
            print()
            checks = [
                (label, kind, _has_module(PYTHON_PACKAGES[label][0]) if kind == "Python package" else found, required, hint)
                for label, kind, found, required, hint in checks
            ]

        missing_libraries = {
            TOOL_LIBRARY[label] for label, kind, found, _, _ in checks
            if kind == "PATH" and not found
        }
        if missing_libraries:
            print("Installing missing external tools:\n")
            install_libraries(missing_libraries)
            print()
            checks = [
                (label, kind, shutil.which(label) if kind == "PATH" else found, required, hint)
                for label, kind, found, required, hint in checks
            ]

    all_required_present = all(found for _, _, found, required, _ in checks if required)
    if quiet and all_required_present:
        return 0

    print("Checking devon.py dependencies:\n")
    for label, kind, found, required, hint in checks:
        marker = "[ok]     " if found else ("[MISSING]" if required else "[missing]")
        detail = found if isinstance(found, str) else ("installed" if found else "not found")
        print(f"{marker} {label} ({kind}): {detail}")
        if not found:
            print(f"           {hint}")

    print()
    if all_required_present:
        print("All required dependencies are present.")
    else:
        print("Some required dependencies are missing.")
    return 0 if all_required_present else 1


# Extensions directory --input treats as candidate input files; everything
# else is silently skipped, same as a zip bundle only ever looks at files
# with one of these extensions.
KNOWN_INPUT_EXTENSIONS = (".vss", ".vssx", ".vsd", ".vsdx", ".vsx", ".xml", ".zip")


def find_directory_inputs(root_dir: str, recursive: bool) -> list:
    """Return every file directly under root_dir matching
    KNOWN_INPUT_EXTENSIONS (or, if recursive, under any of its
    subdirectories too), sorted for stable output."""
    found = []
    if recursive:
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.lower().endswith(KNOWN_INPUT_EXTENSIONS):
                    found.append(os.path.join(dirpath, filename))
    else:
        for filename in os.listdir(root_dir):
            full_path = os.path.join(root_dir, filename)
            if os.path.isfile(full_path) and filename.lower().endswith(KNOWN_INPUT_EXTENSIONS):
                found.append(full_path)
    found.sort()
    return found


def split_directory(root_dir: str, output_dir: str, fmt: str, recursive: bool) -> None:
    """Split every file matching KNOWN_INPUT_EXTENSIONS directly under
    root_dir (or, if recursive, under any of its subdirectories too) via
    split_one_input, writing into a subdirectory of output_dir that
    mirrors each file's path relative to root_dir (each path component
    sanitized the same way a zip bundle's per-file subdirectories already
    are), so same-named files in different subdirectories never collide.
    A file that's itself a zip bundle is expanded the same way a
    top-level --input zip is (see extract_inputs_from_zip). Unlike a
    single --input/--upload run, a per-file failure here is reported and
    skipped rather than aborting the whole scan, since a directory scan is
    far more likely than a curated zip to sweep up an unrelated file that
    only coincidentally matches a known extension."""
    found = find_directory_inputs(root_dir, recursive)
    if not found:
        sys.exit(f"No supported files found {'under' if recursive else 'in'} {root_dir}")
    vlog(f"Found {len(found)} candidate file(s) {'under' if recursive else 'in'} {root_dir}")

    total_written = 0
    total_skipped = 0
    total_failed = 0
    zip_tmp_dirs = []
    try:
        for found_path in found:
            rel_display = os.path.relpath(found_path, root_dir)
            rel_stem = os.path.splitext(rel_display)[0]
            safe_parts = [
                re.sub(r"[^A-Za-z0-9._-]+", "_", part).strip("_") or "stencil"
                for part in rel_stem.split(os.sep)
            ]
            target_dir = os.path.join(output_dir, *safe_parts)

            paths_to_process = [found_path]
            if zipfile.is_zipfile(found_path) and not is_visio_ooxml_package(found_path):
                vlog(f"{rel_display} is a zip archive")
                zip_tmp_dir = tempfile.mkdtemp(prefix="devon_zip_")
                zip_tmp_dirs.append(zip_tmp_dir)
                try:
                    paths_to_process = extract_inputs_from_zip(found_path, zip_tmp_dir)
                except ValueError as e:
                    print(f"Skipping {rel_display}: {e}", file=sys.stderr)
                    total_failed += 1
                    continue

            multiple_inner = len(paths_to_process) > 1
            for path in paths_to_process:
                vlog(f"Processing {path}")
                inner_target_dir = target_dir
                if multiple_inner:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "stencil"
                    inner_target_dir = os.path.join(target_dir, safe_stem)

                try:
                    written, skipped = split_one_input(path, inner_target_dir, fmt)
                except Exception as e:
                    print(f"Skipping {rel_display}: {e}", file=sys.stderr)
                    total_failed += 1
                    continue
                vlog(f"Wrote {written} shape(s), skipped {skipped}, from {path}")
                print(f"Split {written} shape(s) from '{rel_display}' into: {inner_target_dir}")
                total_written += written
                total_skipped += skipped
    finally:
        for zip_tmp_dir in zip_tmp_dirs:
            shutil.rmtree(zip_tmp_dir, ignore_errors=True)

    where = "under" if recursive else "in"
    print(f"Split {total_written} shape(s) total from {len(found)} file(s) {where}: {root_dir}")
    if total_skipped:
        print(f"Skipped {total_skipped} shape(s) with no visible artwork", file=sys.stderr)
    if total_failed:
        print(f"Failed to split {total_failed} file(s); see messages above", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Convert a Visio .vss stencil via vss.draw.io, or split a .vss/.vssx/.vsd/.vsdx/.vsx file locally"
    )
    parser.add_argument(
        "--version", action="version",
        version=f"%(prog)s - {__description__} - v{__version__}",
    )
    parser.add_argument(
        "--upload",
        help="Path to the .vss file to upload, or a .zip containing one or more "
             "(required unless --input is used)",
    )
    parser.add_argument(
        "--download",
        help="Path to save the converted file to (default: <upload basename>.xml in the "
             "current directory). If --upload is a .zip with multiple .vss files, this is "
             "treated as a directory instead, one converted file per stencil",
    )
    parser.add_argument(
        "--input",
        help="Path to an existing <mxlibrary> file, a raw .vss/.vssx/.vsx stencil "
             "or .vsd/.vsdx drawing file, or a .zip containing one or more, to "
             "split instead of converting one (use with --split); or a directory, "
             "to split every supported file directly under it (add --recursive "
             "to also descend into its subdirectories)",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="Split the library/stencil file into individual per-shape files",
    )
    parser.add_argument(
        "--output",
        metavar="DIR",
        help="Directory to write per-shape files into (used with --split; default: the "
             "basename of --input/--upload, minus its extension, e.g. --input Stencil.vsdx "
             "defaults to a Stencil/ directory)",
    )
    parser.add_argument(
        "--to",
        choices=["xml", "svg", "jpg", "png"],
        default="xml",
        help="Output format for --split: single-shape library files (xml, default), "
             "each shape's embedded artwork (svg), or a rasterized JPEG (jpg) or PNG (png)",
    )
    parser.add_argument("--headless", action="store_true", help="Run Chrome headless")
    parser.add_argument("--timeout", type=int, default=90, help="Seconds to wait for conversion (default: 90)")
    parser.add_argument(
        "--checkconfig",
        action="store_true",
        help="Check that required and optional dependencies are installed, then exit",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="With --checkconfig, also attempt to install missing Python "
             "packages via pip and missing external command-line tools via "
             "the system package manager",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print a running commentary of what's happening at each stage, to stderr",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="With --input as a directory, also descend into its subdirectories "
             "(by default, only the files directly under it are split)",
    )
    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    if args.install and not args.checkconfig:
        parser.error("--install requires --checkconfig")

    if args.checkconfig:
        sys.exit(check_config(install=args.install))

    # Any other flag: verify required dependencies before doing anything
    # else (quiet on success; the full report is printed only on failure).
    vlog("Checking required dependencies...")
    rc = check_config(quiet=True)
    if rc != 0:
        sys.exit(rc)
    vlog("All required dependencies are present.")

    if args.input and args.upload:
        parser.error("--input and --upload cannot be used together")
    if args.input and not args.split:
        parser.error("--split is required when using --input")
    if not args.input and not args.upload:
        parser.error("one of --upload or --input is required")
    if args.output and not args.split:
        parser.error("--output requires --split")
    if args.to != "xml" and not args.split:
        parser.error("--to requires --split")
    if args.recursive and not args.input:
        parser.error("--recursive requires --input")

    if args.input:
        input_path = os.path.abspath(args.input)
        vlog(f"Reading input: {input_path}")
        input_is_dir = os.path.isdir(input_path)
        if args.recursive and not input_is_dir:
            sys.exit(f"--recursive requires --input to be a directory: {input_path}")
        if not input_is_dir and not os.path.isfile(input_path):
            sys.exit(f"Input not found: {input_path}")

        if args.output:
            output_dir = os.path.abspath(args.output)
        else:
            output_dir = os.path.abspath(
                no_spaces(os.path.splitext(os.path.basename(input_path))[0]) or "output"
            )
            vlog(f"--output not given; defaulting to {output_dir}")

        if input_is_dir:
            split_directory(input_path, output_dir, args.to, args.recursive)
            return

        input_paths = [input_path]
        zip_tmp_dir = None
        if zipfile.is_zipfile(input_path) and not is_visio_ooxml_package(input_path):
            vlog("Input is a zip archive")
            zip_tmp_dir = tempfile.mkdtemp(prefix="devon_zip_")
            try:
                input_paths = extract_inputs_from_zip(input_path, zip_tmp_dir)
            except ValueError as e:
                shutil.rmtree(zip_tmp_dir, ignore_errors=True)
                sys.exit(str(e))

        multiple = len(input_paths) > 1
        try:
            total_written = 0
            total_skipped = 0
            for path in input_paths:
                vlog(f"Processing {path}")
                target_dir = output_dir
                if multiple:
                    stem = os.path.splitext(os.path.basename(path))[0]
                    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "stencil"
                    target_dir = os.path.join(output_dir, safe_stem)

                written, skipped = split_one_input(path, target_dir, args.to)
                vlog(f"Wrote {written} shape(s), skipped {skipped}, from {path}")

                if multiple:
                    print(f"Split {written} shape(s) from '{os.path.basename(path)}' into: {target_dir}")
                total_written += written
                total_skipped += skipped
        finally:
            if zip_tmp_dir:
                shutil.rmtree(zip_tmp_dir, ignore_errors=True)

        if multiple:
            print(f"Split {total_written} shape(s) total from {len(input_paths)} files into: {output_dir}")
        else:
            print(f"Split {total_written} shape(s) into: {output_dir}")
        if total_skipped:
            print(f"Skipped {total_skipped} shape(s) with no visible artwork", file=sys.stderr)
        return

    upload_path = os.path.abspath(args.upload)
    vlog(f"Reading upload: {upload_path}")
    if not os.path.isfile(upload_path):
        sys.exit(f"Upload file not found: {upload_path}")
    if is_vssx_file(upload_path):
        sys.exit(
            "vss.draw.io only accepts classic .vss files for online conversion, not .vssx "
            "(its own upload check rejects anything else). Use --input instead to split a "
            ".vssx file locally and offline."
        )
    if is_vsd_file(upload_path):
        sys.exit(
            "vss.draw.io only accepts classic .vss files for online conversion, not .vsd "
            "(its own upload check rejects anything else). Use --input instead to split a "
            ".vsd file locally and offline."
        )
    if is_vsdx_file(upload_path):
        sys.exit(
            "vss.draw.io only accepts classic .vss files for online conversion, not .vsdx "
            "(its own upload check rejects anything else). Use --input instead to split a "
            ".vsdx file locally and offline."
        )
    if is_vsx_file(upload_path):
        sys.exit(
            "vss.draw.io only accepts classic .vss files for online conversion, not .vsx "
            "(its own upload check rejects anything else). Use --input instead to split a "
            ".vsx file locally and offline."
        )

    upload_paths = [upload_path]
    upload_zip_tmp_dir = None
    if zipfile.is_zipfile(upload_path):
        vlog("Upload is a zip archive")
        upload_zip_tmp_dir = tempfile.mkdtemp(prefix="devon_zip_")
        try:
            upload_paths = extract_files_from_zip(upload_path, upload_zip_tmp_dir, [(".vss",)])
        except ValueError as e:
            shutil.rmtree(upload_zip_tmp_dir, ignore_errors=True)
            with zipfile.ZipFile(upload_path) as zf:
                names = [n.lower() for n in zf.namelist()]
                if any(n.endswith((".vssx", ".vsd", ".vsdx", ".vsx")) for n in names):
                    sys.exit(
                        f"{e} (it has .vssx/.vsd/.vsdx/.vsx files, but vss.draw.io only accepts classic "
                        ".vss for online conversion; use --input instead to split them locally)"
                    )
            sys.exit(str(e))

    multiple = len(upload_paths) > 1

    split_output_base = None
    if args.split:
        if args.output:
            split_output_base = os.path.abspath(args.output)
        else:
            split_output_base = os.path.abspath(
                no_spaces(os.path.splitext(os.path.basename(upload_path))[0]) or "output"
            )
            vlog(f"--output not given; defaulting to {split_output_base}")

    tmp_download_dir = tempfile.mkdtemp(prefix="vss_draw_io_")
    driver = build_driver(tmp_download_dir, args.headless)
    try:
        for path in upload_paths:
            vlog(f"Converting {path}")
            base = no_spaces(os.path.splitext(os.path.basename(path))[0])
            if multiple:
                # --download is a directory when converting multiple stencils.
                download_dir = os.path.abspath(args.download) if args.download else os.getcwd()
                download_target = os.path.join(download_dir, f"{base}.xml")
            else:
                download_target = os.path.abspath(args.download) if args.download else os.path.abspath(f"{base}.xml")

            downloaded_file = convert_one_vss(driver, tmp_download_dir, path, args.timeout)

            target_dir = os.path.dirname(download_target)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)
            shutil.move(downloaded_file, download_target)
            print(f"Converted library saved to: {download_target}")

            if args.split:
                vlog(f"Splitting {download_target}")
                split_output = split_output_base
                if multiple:
                    safe_base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_") or "stencil"
                    split_output = os.path.join(split_output, safe_base)
                with open(download_target, "r") as f:
                    content = f.read()
                written, skipped = split_library(content, split_output, args.to)
                print(f"Split {written} shape(s) into: {split_output}")
                if skipped:
                    print(f"Skipped {skipped} shape(s) with no visible artwork", file=sys.stderr)
    finally:
        vlog("Closing Chrome and cleaning up temporary files...")
        driver.quit()
        shutil.rmtree(tmp_download_dir, ignore_errors=True)
        if upload_zip_tmp_dir:
            shutil.rmtree(upload_zip_tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
