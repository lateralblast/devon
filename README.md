![Devon Rex Cat](/devon.jpg)

# devon.py

Diagram Extractor for Visio with local and ONline capability (via draw.io)

Version: 0.2.5 (see [CHANGELOG.md](CHANGELOG.md))

Works with Microsoft Visio stencil and drawing files two ways:

- **Online**, via [vss.draw.io](https://vss.draw.io): automates the browser
  to convert a **classic `.vss`** stencil into a draw.io/diagrams.net
  library, without you having to drive it by hand. It scripts the same
  steps you'd do yourself: open the site, upload the `.vss` file, check
  "I confirm this file contains no sensitive or personal information,"
  click **Convert**, and save the resulting library file locally. (The
  site itself only accepts `.vss`, not `.vssx`, `.vsd`, `.vsdx`, `.vsx`, or
  `.vstx`, so this path is `.vss`-only.)
- **Locally**, entirely offline: parses a **classic `.vss` binary, modern
  `.vssx`, or legacy XML `.vsx` stencil, or a classic `.vsd`, modern
  `.vsdx`, or modern `.vstx` drawing/template** file directly with
  `libvisio` and extracts each individual shape or page as its own file
  (SVG or JPEG), with no browser or upload involved. See
  [Splitting a raw stencil or drawing file directly](#splitting-a-raw-stencil-or-drawing-file-directly-offline-no-browser)
  below.

Either path can also split a converted or extracted library into
individual per-shape files; see `--split` below.

## Supported file types

| Extension | File type | Description |
|-----------|-----------|--------------|
| `.vss` | Classic stencil | Legacy (OLE2 binary) Visio stencil: a library of master shapes. The only format `--upload` (online, via vss.draw.io) accepts; also supported by `--input` (offline, via libvisio). |
| `.vssx` | Modern stencil | Modern (OOXML/zip) Visio stencil. `--input` only: vss.draw.io's online path accepts classic `.vss` alone. |
| `.vsx` | Legacy XML stencil | Older, plain-XML Visio stencil format (from Visio's "Save As XML" option), predating both `.vss` and `.vssx`. `--input` only. |
| `.vsd` | Classic drawing | Legacy (OLE2 binary) Visio drawing: one or more drawn pages, as opposed to a shape library. `--input` only; splits into one file per page. |
| `.vsdx` | Modern drawing | Modern (OOXML/zip) Visio drawing. `--input` only; splits into one file per page. |
| `.vstx` | Modern template | Modern (OOXML/zip) Visio template: page-based like a drawing (it's what you open to start a new one), rather than master-based like a stencil. `--input` only; splits into one file per page. |
| `.xml` (`<mxlibrary>`) | Converted/exported library | A draw.io/diagrams.net shape library, as produced by `--upload` or downloaded from vss.draw.io directly. `--input` only; splits into one file per shape. |
| `.zip` | Bundle | An archive bundling one or more of the file types above. Accepted by both `--upload` and `--input`; each file found inside is extracted and processed independently. |

`.vss`/`.vsd` share the same OLE2 container and are told apart only by
extension; `.vssx`/`.vsdx`/`.vstx` share the same OOXML/zip container and
are told apart the same way, by extension, since either part a stencil or
drawing carries internally (its own masters, or a helper/preview page)
can appear in either format. See
[Splitting a raw stencil or drawing file directly](#splitting-a-raw-stencil-or-drawing-file-directly-offline-no-browser)
for the offline formats, and [Checking your setup](#checking-your-setup)
for which external tools each one needs.

## Requirements

- Python 3
- [Selenium](https://pypi.org/project/selenium/) 4.6+ (auto-downloads a matching chromedriver)
- Google Chrome or Chromium installed
- Optional, for splitting a raw `.vss`/`.vssx`/`.vsd`/`.vsdx`/`.vsx`/`.vstx`
  file directly (see below): [libvisio](https://wiki.documentfoundation.org/DLP/Libraries/libvisio)'s
  `vss2raw`/`vss2xhtml` and `vsd2raw`/`vsd2xhtml` command-line tools on
  `PATH` (`brew install libvisio` on macOS)
- Optional, to recover shapes whose artwork is an embedded Windows EMF/WMF
  metafile when splitting a raw file: `emf2svg-conv` from
  [libemf2svg](https://github.com/kakwa/libemf2svg) on `PATH`
  (`brew install libemf2svg` on macOS)
- Optional, for `--to jpg`/`--to png`: `rsvg-convert` (from
  [librsvg](https://wiki.gnome.org/Projects/LibRsvg)) on `PATH`
  (`brew install librsvg` on macOS); for `--to jpg` specifically,
  [Pillow](https://pypi.org/project/Pillow/) handles the PNG -> JPEG step
  and is installed automatically if missing

```
pip install -r requirements.txt
```

## Usage

```
python3 devon.py --upload Stencil.vss --download Stencil.xml
```

### Options

| Flag         | Default                              | Description                                              |
|--------------|---------------------------------------|------------------------------------------------------------|
| `--upload`   | *(required unless `--input` is used)* | Path to the `.vss` file to upload, or a `.zip` containing one or more |
| `--download` | `<upload basename>.xml` in the cwd    | Where to save the converted library file (a directory instead, if `--upload` is a `.zip` with multiple `.vss` files) |
| `--input`    | none                                   | Path to an existing `<mxlibrary>` file, a raw `.vss`/`.vssx`/`.vsx` stencil or `.vsd`/`.vsdx`/`.vstx` drawing/template file, or a `.zip` containing one or more, to split instead of converting one (use with `--split`); or a directory, to split every supported file directly under it |
| `--split`    | off                                    | Split the library/stencil file into individual per-shape files |
| `--recursive` | off                                    | With `--input` as a directory, also descend into its subdirectories (by default, only the files directly under it are split) |
| `--output`   | basename of `--input`/`--upload`, minus its extension | Directory to write per-shape files into (used with `--split`) |
| `--to`       | `xml`                                  | Output format for `--split`: `xml` (single-shape library files), `svg` (each shape's embedded artwork), `jpg` (rasterized JPEG), or `png` (rasterized PNG) |
| `--headless` | off                                    | Run Chrome without a visible window                        |
| `--timeout`  | `90`                                   | Seconds to wait for conversion/download                    |
| `--checkconfig` | off                                 | Check that required and optional dependencies are installed, then exit |
| `--install`  | off                                    | With `--checkconfig`, also attempt to install missing dependencies (Python packages via pip, external tools via the system package manager) |
| `--verbose`  | off                                    | Print a running commentary of what's happening at each stage, to stderr |

`--upload` and `--input` are mutually exclusive; exactly one is required.
`--split` is required when using `--input`. `--output` defaults to the
basename of `--input`/`--upload` minus its extension (e.g. `--input
Stencil.vsdx` defaults to a `Stencil/` directory) when not given.
`--to` only applies alongside `--split`.
`--install` requires `--checkconfig`.

### Checking your setup

`--checkconfig` checks every Python-package and command-line dependency
this script can use: `selenium`, Chrome/Chromium, `Pillow`, `rsvg-convert`,
and libvisio's `vss2raw`/`vss2xhtml`/`vsd2raw`/`vsd2xhtml` and
`emf2svg-conv`. It prints a report of what's installed and what's
missing, along with an install hint for anything missing:

```
python3 devon.py --checkconfig
```

It exits non-zero only if `selenium` or a Chrome/Chromium install is
missing (both unconditionally required); the rest are only needed for
specific flags (`--to jpg`, or `--input` on a raw `.vss`/`.vssx`/`.vsd`/`.vsdx`/`.vsx`/`.vstx`
file) and are reported without affecting the exit code.

This same check also runs automatically, silently, before any other flag
(`--upload`/`--input`/etc.) does anything. If `selenium` or Chrome/Chromium
turns out to be missing, the same report is printed and the script exits
before touching the requested file.

Add `--install` to also attempt installing whichever dependencies are
missing:

- Python packages (`selenium`, `Pillow`) via `pip install`.
- The external (non-Python) tools: `rsvg-convert` (librsvg), libvisio's
  `vss2raw`/`vss2xhtml`/`vsd2raw`/`vsd2xhtml`, and `emf2svg-conv`
  (libemf2svg), via whichever supported package manager (`brew`,
  `apt-get`, `dnf`, or `pacman`) is found on `PATH`.

```
python3 devon.py --checkconfig --install
```

This runs real installs against your system (via `pip`, and via `sudo` on
Linux for the package-manager installs). It doesn't touch Chrome/Chromium,
which has to be installed manually. If no supported package manager is
found, or a tool has no known package for your package manager, it's
reported so you can install it manually (see Requirements above).

### Verbose output

Add `--verbose` to any run to get a running commentary on stderr of what's
happening at each stage: which file is being read, whether it's a zip or a
raw `.vss`/`.vssx`/`.vsd`/`.vsdx`/`.vsx`/`.vstx`/`<mxlibrary>` file, each shape or page as it's
written, skipped, or rasterized, and, for the online path, each step of
driving vss.draw.io (loading the page, uploading, confirming the
checkbox, clicking Convert, waiting for the download). Normal stdout
output (the final summary lines) is unchanged; verbose lines are prefixed
`[verbose]` and go to stderr, so piping stdout elsewhere still gets just
the summary.

```
python3 devon.py --input Stencil.vssx --split --output shapes/ --to svg --verbose
```

### Example

```
python3 devon.py --upload Stencil.vss --download Stencil.xml --headless
```

On success, prints:

```
Converted library saved to: /path/to/Stencil.xml
```

If the site rejects the file (e.g. unsupported format), the script reads the
page's own error banner and raises `RuntimeError: Conversion failed: <message>`.
If nothing finishes within `--timeout` seconds, it raises a `TimeoutError`.

### Converting multiple stencils from a zip

`--upload` also accepts a `.zip` archive containing one or more `.vss`
files. A zip with a single stencil behaves just like passing that file
directly. A zip with multiple stencils converts each one in turn (through
its own fresh page load, so state never leaks between conversions) and
treats `--download` as a directory, writing one converted file per stencil
named after it:

```
python3 devon.py --upload Vendors.zip --download converted/ --headless
```

```
Converted library saved to: converted/VendorA.xml
Converted library saved to: converted/VendorB.xml
```

`--split --output shapes/` works the same way here as with `--input` (see
below): with multiple stencils, each one's shapes land in their own
subdirectory under `shapes/`.

### Splitting a library into individual shape files

A converted library file (like `Stencil.xml`) is a draw.io `<mxlibrary>` file
containing one entry per shape. `--split` breaks it apart into one
single-shape library file per shape, named after the shape's title, so each
can be imported or shared individually.

Split right after converting:

```
python3 devon.py --upload Stencil.vss --download Stencil.xml --split --output shapes/
```

Or split an already-downloaded library file, with no browser/upload involved:

```
python3 devon.py --input Stencil.xml --split --output shapes/
```

`--input` also accepts a `.zip` archive: every
`.vss`/`.vssx`/`.vsd`/`.vsdx`/`.vsx`/`.vstx` file found inside is
extracted and split (or, if it has none, every `.xml` file instead). A
`.vssx`/`.vsdx`/`.vstx` file is itself a zip package, but is detected and
treated as a single stencil/drawing/template rather than being opened as
a bundle.

A zip with a single stencil behaves just like passing that file directly:

```
python3 devon.py --input Stencil.zip --split --output shapes/
```

A zip with multiple stencils splits each one into its own subdirectory
under `--output`, named after the source file, so shapes from different
stencils never collide:

```
python3 devon.py --input Vendors.zip --split --output shapes/
```

```
Split 61 shape(s) from 'VendorA.vss' into: shapes/VendorA
Split 61 shape(s) from 'VendorB.vss' into: shapes/VendorB
Split 122 shape(s) total from 2 files into: shapes/
```

A single-stencil zip (or a plain `.vss`/`.xml` file) prints:

```
Split 61 shape(s) into: /path/to/shapes
```

### Extracting shapes as SVG

Pass `--to svg` to extract each shape's embedded artwork as a standalone
`.svg` file instead:

```
python3 devon.py --input Stencil.xml --split --output shapes/ --to svg
```

Some Visio masters convert with no visible artwork at all (an empty
placeholder). Those are skipped, and the count is reported:

```
Skipped 16 shape(s) with no visible artwork
Split 45 shape(s) into: /path/to/shapes
```

Pass `--to jpg` instead to get a rasterized, white-background JPEG per shape
(via `rsvg-convert` + Pillow) rather than the raw SVG:

```
python3 devon.py --input Stencil.xml --split --output shapes/ --to jpg
```

Pass `--to png` for a rasterized PNG per shape instead (via `rsvg-convert`
alone, no Pillow needed): transparency is preserved rather than flattened
onto a white background, unlike `--to jpg`:

```
python3 devon.py --input Stencil.xml --split --output shapes/ --to png
```

### Splitting a raw stencil or drawing file directly (offline, no browser)

`--input` also accepts a raw `.vss`/`.vssx`/`.vsx` stencil or
`.vsd`/`.vsdx`/`.vstx` drawing/template file. This uses
[libvisio](https://wiki.documentfoundation.org/DLP/Libraries/libvisio) to
parse the file natively and render each item's real artwork, entirely
offline: no browser, no vss.draw.io upload:

```
python3 devon.py --input Stencil.vss --split --output shapes/ --to svg
python3 devon.py --input Stencil.vssx --split --output shapes/ --to svg
python3 devon.py --input Stencil.vsx --split --output shapes/ --to svg
python3 devon.py --input Drawing.vsd --split --output pages/ --to svg
python3 devon.py --input Drawing.vsdx --split --output pages/ --to svg
python3 devon.py --input Template.vstx --split --output pages/ --to svg
```

A `.vss`/`.vssx`/`.vsx` stencil splits into one file per **master shape**
(via `vss2raw`/`vss2xhtml`, which handle all three formats transparently);
a `.vsd`/`.vsdx` drawing or `.vstx` template splits into one file per
**page** instead (via `vsd2raw`/`vsd2xhtml`, which likewise handle all
three formats transparently). A `.vsd`/`.vsdx`/`.vstx` file is a document
with drawn pages, not a shape library, so "shapes" there means whole
pages of the drawing/template. `.vsx` is the legacy Visio XML stencil
format (plain XML, from Visio's old "Save As XML" option), distinct from
both the binary `.vss` and the OOXML `.vssx`. `.vstx` is a template
rather than a drawing (it's what you open to start a new document), but
splits the same page-based way since that's what it actually contains.

(`--to xml` isn't supported for any of these inputs: there's no per-shape
library format to reuse. Use `--to svg`, `--to jpg`, or `--to png` instead.)

`.vssx`/`.vsd`/`.vsdx`/`.vsx`/`.vstx` are only supported by this local path, not
`--upload`: vss.draw.io's own upload check rejects anything whose filename
doesn't end in `.vss`.

Some masters/pages store their artwork as a Windows EMF/WMF metafile, which
libvisio can't rasterize and browsers can't display. If `emf2svg-conv` (from
libemf2svg) is on `PATH`, those are rendered to real SVG and recovered
automatically; otherwise they're skipped (reported the same way as above)
rather than writing a broken image. With `emf2svg-conv` installed this path
can recover every item, entirely offline.

### Splitting a whole directory

`--input` also accepts a directory: every
`.vss`/`.vssx`/`.vsd`/`.vsdx`/`.vsx`/`.vstx`/`.xml`/`.zip` file found
directly under it (not its subdirectories) is split the same way passing it
directly to `--input` would be:

```
python3 devon.py --input stencils/ --split --output shapes/ --to svg
```

Add `--recursive` to also descend into subdirectories:

```
python3 devon.py --input stencils/ --recursive --split --output shapes/ --to svg
```

Each file's output goes into a subdirectory mirroring its path relative
to the scanned directory (e.g. `stencils/vendorA/Widget.vssx` lands in
`shapes/vendorA/Widget/`), so files with the same name in different
subdirectories never collide. A `.zip` found during the scan is expanded
in place, the same way a top-level `--input` zip already is.

Unlike a single-file `--input` run, a file that fails here (for example,
an unrelated `.xml` file that isn't a real `<mxlibrary>`) is reported and
skipped rather than aborting the whole scan, since scanning a directory
is far more likely than a deliberately-built zip to sweep up something
that only coincidentally matches a known extension. The final summary
reports how many files failed, if any:

```
Skipping vendorA/notes.xml: Not an <mxlibrary>...</mxlibrary> file
Split 340 shape(s) total from 12 file(s) under: stencils/
Failed to split 1 file(s); see messages above
```

## Notes

- The converted file can be imported into draw.io/diagrams.net via
  **File > Open Library**, as can each individual file produced by `--split`.
- The confirmation checkbox reflects a real statement made to the vss.draw.io
  service; only run this against files you're comfortable uploading there.
- Large stencil files (tens of MB) can take a minute or more to convert;
  increase `--timeout` if needed.

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0/) (CC BY-NC-SA 4.0).
