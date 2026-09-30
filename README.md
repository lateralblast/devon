![Devon Rex Cat](/devon.jpg)

# devon.py

Diagram Extractor for Visio with local and online capability (via draw.io)

Version: 0.2.6 (see [CHANGELOG.md](CHANGELOG.md))

`devon.py` pulls shapes and pages out of Microsoft Visio stencil, drawing and
template files. It has two modes:

- **Online** ([vss.draw.io](https://vss.draw.io)): drives Chrome through the
  site's own steps (open the page, upload the file, tick the "no sensitive or
  personal information" box, click **Convert**) and saves the resulting
  draw.io/diagrams.net library. The site only takes classic `.vss`, so this
  mode is `.vss`-only.
- **Local** (offline): parses the file directly with `libvisio` and writes each
  shape or page as its own SVG, JPEG or PNG. No browser, no upload. See
  [Splitting a raw stencil or drawing file directly](#splitting-a-raw-stencil-or-drawing-file-directly-offline-no-browser).

Either mode can split the result into one file per shape with `--split`.

## Quick start

```
pip install -r requirements.txt
python3 devon.py --upload Stencil.vss --download Stencil.xml
python3 devon.py --input Stencil.vssx --split --output shapes/ --to svg
```

## Supported file types

| Extension | Type | Notes |
|-----------|------|-------|
| `.vss` | Classic stencil | OLE2 binary shape library. The only format `--upload` accepts; `--input` also reads it. |
| `.vssx` | Modern stencil | OOXML/zip shape library. `--input` only. |
| `.vsx` | Legacy XML stencil | Plain XML from Visio's old "Save As XML". `--input` only. |
| `.vsd` | Classic drawing | OLE2 binary, one or more pages. `--input` only; one file per page. |
| `.vsdx` | Modern drawing | OOXML/zip, one or more pages. `--input` only; one file per page. |
| `.vstx` | Modern template | OOXML/zip. Page-based like a drawing, not master-based like a stencil. `--input` only; one file per page. |
| `.xml` (`<mxlibrary>`) | draw.io library | Produced by `--upload` or downloaded from vss.draw.io. `--input` only; one file per shape. |
| `.zip` | Bundle | Any mix of the above. Accepted by `--upload` and `--input`; each file inside is processed on its own. |

`.vss` and `.vsd` share the OLE2 container, and `.vssx`, `.vsdx` and `.vstx`
share the OOXML/zip container, so the extension is what tells them apart. Their
contents can't: a stencil can carry a helper page, and a drawing can carry
local copies of its masters.

## Requirements

- Python 3
- [Selenium](https://pypi.org/project/selenium/) 4.6+ (downloads a matching chromedriver itself)
- Google Chrome or Chromium
- Optional, for splitting raw Visio files:
  [libvisio](https://wiki.documentfoundation.org/DLP/Libraries/libvisio)'s
  `vss2raw`/`vss2xhtml` and `vsd2raw`/`vsd2xhtml` on `PATH`
  (`brew install libvisio` on macOS)
- Optional, to recover shapes whose artwork is an embedded EMF/WMF metafile:
  `emf2svg-conv` from [libemf2svg](https://github.com/kakwa/libemf2svg) on
  `PATH` (`brew install libemf2svg`)
- Optional, for `--to jpg` and `--to png`: `rsvg-convert` from
  [librsvg](https://wiki.gnome.org/Projects/LibRsvg) on `PATH`
  (`brew install librsvg`). `--to jpg` also needs
  [Pillow](https://pypi.org/project/Pillow/), which is installed automatically
  if missing.

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--upload` | required unless `--input` is used | `.vss` file to convert online, or a `.zip` containing one or more |
| `--download` | `<upload basename>.xml` in the cwd | Where to save the converted library. A directory if `--upload` is a zip with several `.vss` files |
| `--input` | none | An `<mxlibrary>` file, a raw stencil/drawing/template file, a `.zip` of these, or a directory. A directory splits every supported file directly under it |
| `--split` | off | Split the library or document into per-shape (or per-page) files |
| `--inspect` | off | Report each `--input` file's detected type and contents; write nothing |
| `--recursive` | off | With a directory `--input`, also descend into subdirectories |
| `--output` | basename of `--input`/`--upload`, minus extension | Directory for the per-shape files. `--input Stencil.vsdx` defaults to `Stencil/` |
| `--to` | `xml` | Output for `--split`: `xml` (single-shape libraries), `svg`, `jpg` (white background) or `png` (transparent) |
| `--headless` | off | Run Chrome without a window |
| `--timeout` | `90` | Seconds to wait for conversion and download |
| `--checkconfig` | off | Report installed and missing dependencies, then exit |
| `--install` | off | With `--checkconfig`, try to install what's missing |
| `--verbose` | off | Log each stage to stderr |

Constraints:

- `--upload` and `--input` are mutually exclusive, and one is required.
- `--input` needs `--split` or `--inspect`, and the two can't be combined.
- `--to` only applies with `--split`. `--to xml` isn't available for raw
  Visio files, which have no per-shape library format; use `svg`, `jpg` or `png`.
- `--install` requires `--checkconfig`.

## Checking your setup

```
python3 devon.py --checkconfig
```

The report covers `selenium`, Chrome/Chromium, `Pillow`, `rsvg-convert`,
libvisio's four tools and `emf2svg-conv`, with an install hint for each
missing item. It exits non-zero only when `selenium` or Chrome/Chromium is
missing. The rest matter only for particular flags (`--to jpg`, or `--input` on
a raw Visio file) and don't affect the exit code.

The same check runs silently before every other invocation. If `selenium` or
Chrome/Chromium is missing, the report prints and the script exits before it
touches your file.

Add `--install` to install what's missing:

```
python3 devon.py --checkconfig --install
```

Python packages (`selenium`, `Pillow`) go in through `pip`. The external tools
(`rsvg-convert`, the libvisio tools, `emf2svg-conv`) go in through whichever of
`brew`, `apt-get`, `dnf` or `pacman` is on `PATH`, using `sudo` on Linux. This
changes your system. It never installs Chrome/Chromium; do that yourself. If no
package manager is found, or one has no package for a tool, the report says so.

## Online conversion

```
python3 devon.py --upload Stencil.vss --download Stencil.xml --headless
```

On success it prints:

```
Converted library saved to: /path/to/Stencil.xml
```

If the site rejects the file, the script reads the page's error banner and
raises `RuntimeError: Conversion failed: <message>`. If nothing finishes within
`--timeout` seconds, it raises `TimeoutError`.

### Several stencils from a zip

`--upload` accepts a `.zip` of `.vss` files. Each stencil gets its own fresh
page load, so state never leaks between conversions. With more than one,
`--download` is treated as a directory:

```
python3 devon.py --upload Vendors.zip --download converted/ --headless
```

```
Converted library saved to: converted/VendorA.xml
Converted library saved to: converted/VendorB.xml
```

`--split --output shapes/` works the same as with `--input`; each stencil's
shapes land in a subdirectory of `shapes/`.

## Splitting

### A converted library

A converted library is a draw.io `<mxlibrary>` file with one entry per shape.
`--split` writes one single-shape library per shape, named after its title, so
each can be imported or shared alone.

```
# right after converting
python3 devon.py --upload Stencil.vss --download Stencil.xml --split --output shapes/

# from a library you already have, no browser
python3 devon.py --input Stencil.xml --split --output shapes/
```

`--input` also takes a `.zip`. Every `.vss`, `.vssx`, `.vsd`, `.vsdx`, `.vsx`
and `.vstx` inside is split; if there are none, every `.xml` is. A
`.vssx`/`.vsdx`/`.vstx` is itself a zip, but it's detected and treated as one
stencil, drawing or template, not unpacked as a bundle.

A zip holding one stencil behaves like passing that file. A zip holding several
splits each into a subdirectory of `--output` named after the source file:

```
python3 devon.py --input Vendors.zip --split --output shapes/
```

```
Split 61 shape(s) from 'VendorA.vss' into: shapes/VendorA
Split 61 shape(s) from 'VendorB.vss' into: shapes/VendorB
Split 122 shape(s) total from 2 files into: shapes/
```

A single stencil, zipped or not, prints:

```
Split 61 shape(s) into: /path/to/shapes
```

### Output formats

`--to svg` writes each shape's embedded artwork as a standalone `.svg`:

```
python3 devon.py --input Stencil.xml --split --output shapes/ --to svg
```

Some masters convert to an empty placeholder with no visible artwork. These are
skipped and counted:

```
Skipped 16 shape(s) with no visible artwork
Split 45 shape(s) into: /path/to/shapes
```

`--to jpg` rasterizes each shape onto a white background (`rsvg-convert` plus
Pillow). `--to png` uses `rsvg-convert` alone and keeps transparency:

```
python3 devon.py --input Stencil.xml --split --output shapes/ --to jpg
python3 devon.py --input Stencil.xml --split --output shapes/ --to png
```

### A raw stencil or drawing file (offline, no browser)

`--input` accepts any raw Visio file. `libvisio` parses it natively and renders
each item's real artwork:

```
python3 devon.py --input Stencil.vss --split --output shapes/ --to svg
python3 devon.py --input Stencil.vssx --split --output shapes/ --to svg
python3 devon.py --input Stencil.vsx --split --output shapes/ --to svg
python3 devon.py --input Drawing.vsd --split --output pages/ --to svg
python3 devon.py --input Drawing.vsdx --split --output pages/ --to svg
python3 devon.py --input Template.vstx --split --output pages/ --to svg
```

Stencils (`.vss`, `.vssx`, `.vsx`) split into one file per **master shape**,
through `vss2raw` and `vss2xhtml`. Drawings and templates (`.vsd`, `.vsdx`,
`.vstx`) split into one file per **page**, through `vsd2raw` and `vsd2xhtml`.
Each tool pair reads all three of its formats. A template is what you open to
start a new drawing, but it holds pages, so it splits like one.

Only this local path reads `.vssx`, `.vsd`, `.vsdx`, `.vsx` and `.vstx`.
vss.draw.io rejects any upload whose filename doesn't end in `.vss`.

Some masters and pages store their artwork as a Windows EMF/WMF metafile, which
libvisio can't rasterize and browsers can't display. With `emf2svg-conv` on
`PATH` these are converted to real SVG and recovered. Without it they're skipped
and counted, as above, rather than written as broken images.

### A whole directory

`--input` also accepts a directory. Every `.vss`, `.vssx`, `.vsd`, `.vsdx`,
`.vsx`, `.vstx`, `.xml` and `.zip` directly under it is split as if you had
passed it alone:

```
python3 devon.py --input stencils/ --split --output shapes/ --to svg
```

Add `--recursive` to descend into subdirectories:

```
python3 devon.py --input stencils/ --recursive --split --output shapes/ --to svg
```

Output mirrors each file's path relative to the scanned directory, so
`stencils/vendorA/Widget.vssx` lands in `shapes/vendorA/Widget/` and two
`Widget.vssx` files in different folders don't collide. A `.zip` found during
the scan is expanded in place.

A file that fails is reported and skipped; it doesn't abort the scan. A
directory is likelier than a hand-built zip to contain something that only
matches an extension, such as an `.xml` file that isn't a real `<mxlibrary>`.
The summary counts the failures:

```
Skipping vendorA/notes.xml: Not an <mxlibrary>...</mxlibrary> file
Split 340 shape(s) total from 12 file(s) under: stencils/
Failed to split 1 file(s); see messages above
```

## Inspecting without splitting

`--inspect` reports what a file is and what it holds, and writes nothing:

```
python3 devon.py --input Stencil.vssx --inspect
```

```
Stencil.vssx: modern Visio stencil (.vssx)
  54 master shapes:
    - Server Rack
    - Switch 24-port
    ...
```

It takes the same `--input` targets as `--split`: a raw Visio file, an
`<mxlibrary>` file, a `.zip` (each file inside is inspected) or a directory
(add `--recursive` to descend). For raw files it runs only `vss2raw` or
`vsd2raw` to list names, skipping the xhtml tool, EMF recovery and
rasterization, so it's much cheaper than a split. `--output` and `--to` don't
apply. A file that fails to inspect is reported and the scan continues.

## Verbose output

`--verbose` logs each stage to stderr with a `[verbose]` prefix: the file being
read, whether it's a zip, raw file or `<mxlibrary>`, each shape or page written,
skipped or rasterized, and, online, each step of driving vss.draw.io. The
summary lines on stdout are unchanged, so piping stdout still gets only those.

```
python3 devon.py --input Stencil.vssx --split --output shapes/ --to svg --verbose
```

## Notes

- Import the converted library, or any file from `--split`, into
  draw.io/diagrams.net with **File > Open Library**.
- The confirmation checkbox is a real statement to the vss.draw.io service. Only
  upload files you're comfortable sending there.
- Stencils of tens of megabytes can take a minute or more to convert. Raise
  `--timeout` if needed.

## Help support development

Fund me here: https://ko-fi.com/richardatlateralblast

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/) (CC BY-NC-SA 4.0).
