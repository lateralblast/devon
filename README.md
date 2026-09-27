![Devon Rex Cat](/devon.jpg)

# devon.py

Diagram Extractor for Visio with local and ONline capability (via draw.io)

Version: 0.2.0 (see [CHANGELOG.md](CHANGELOG.md))

Works with Microsoft Visio stencil and drawing files two ways:

- **Online**, via [vss.draw.io](https://vss.draw.io): automates the browser
  to convert a **classic `.vss`** stencil into a draw.io/diagrams.net
  library, without you having to drive it by hand. It scripts the same
  steps you'd do yourself: open the site, upload the `.vss` file, check
  "I confirm this file contains no sensitive or personal information,"
  click **Convert**, and save the resulting library file locally. (The
  site itself only accepts `.vss`, not `.vssx`, `.vsd`, or `.vsdx`, so this
  path is `.vss`-only.)
- **Locally**, entirely offline: parses a **classic `.vss` or modern
  `.vssx` stencil, or a classic `.vsd` or modern `.vsdx` drawing** file
  directly with `libvisio` and extracts each individual shape or page as
  its own file (SVG or JPEG), with no browser or upload involved. See
  [Splitting a raw stencil or drawing file directly](#splitting-a-raw-stencil-or-drawing-file-directly-offline-no-browser)
  below.

Either path can also split a converted or extracted library into
individual per-shape files; see `--split` below.

## Requirements

- Python 3
- [Selenium](https://pypi.org/project/selenium/) 4.6+ (auto-downloads a matching chromedriver)
- Google Chrome or Chromium installed
- Optional, for splitting a raw `.vss`/`.vssx`/`.vsd`/`.vsdx` file directly
  (see below): [libvisio](https://wiki.documentfoundation.org/DLP/Libraries/libvisio)'s
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
| `--input`    | none                                   | Path to an existing `<mxlibrary>` file, a raw `.vss`/`.vssx` stencil or `.vsd`/`.vsdx` drawing file, or a `.zip` containing one or more, to split instead of converting one (use with `--split`) |
| `--split`    | off                                    | Split the library/stencil file into individual per-shape files (requires `--output`) |
| `--output`   | none                                   | Directory to write per-shape files into (used with `--split`) |
| `--to`       | `xml`                                  | Output format for `--split`: `xml` (single-shape library files), `svg` (each shape's embedded artwork), `jpg` (rasterized JPEG), or `png` (rasterized PNG) |
| `--headless` | off                                    | Run Chrome without a visible window                        |
| `--timeout`  | `90`                                   | Seconds to wait for conversion/download                    |
| `--checkconfig` | off                                 | Check that required and optional dependencies are installed, then exit |
| `--install`  | off                                    | With `--checkconfig`, also attempt to install missing dependencies (Python packages via pip, external tools via the system package manager) |
| `--verbose`  | off                                    | Print a running commentary of what's happening at each stage, to stderr |

`--upload` and `--input` are mutually exclusive; exactly one is required.
`--split` is required when using `--input`, and requires `--output` in turn.
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
specific flags (`--to jpg`, or `--input` on a raw `.vss`/`.vssx`/`.vsd`/`.vsdx`
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
raw `.vss`/`.vssx`/`.vsd`/`.vsdx`/`<mxlibrary>` file, each shape or page as it's
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

`--input` also accepts a `.zip` archive: every `.vss`/`.vssx`/`.vsd`/`.vsdx`
file found inside is extracted and split (or, if it has none, every `.xml`
file instead). A `.vssx`/`.vsdx` file is itself a zip package, but is
detected and treated as a single stencil or drawing rather than being
opened as a bundle.

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

`--input` also accepts a raw `.vss`/`.vssx` stencil or `.vsd`/`.vsdx`
drawing file. This uses [libvisio](https://wiki.documentfoundation.org/DLP/Libraries/libvisio)
to parse the file natively and render each item's real artwork, entirely
offline: no browser, no vss.draw.io upload:

```
python3 devon.py --input Stencil.vss --split --output shapes/ --to svg
python3 devon.py --input Stencil.vssx --split --output shapes/ --to svg
python3 devon.py --input Drawing.vsd --split --output pages/ --to svg
python3 devon.py --input Drawing.vsdx --split --output pages/ --to svg
```

A `.vss`/`.vssx` stencil splits into one file per **master shape** (via
`vss2raw`/`vss2xhtml`, which handle both formats transparently); a
`.vsd`/`.vsdx` drawing splits into one file per **page** instead (via
`vsd2raw`/`vsd2xhtml`, which likewise handle both formats transparently).
A `.vsd`/`.vsdx` file is a document with drawn pages, not a shape library,
so "shapes" there means whole pages of the drawing.

(`--to xml` isn't supported for any of these inputs: there's no per-shape
library format to reuse. Use `--to svg`, `--to jpg`, or `--to png` instead.)

`.vssx`/`.vsd`/`.vsdx` are only supported by this local path, not
`--upload`: vss.draw.io's own upload check rejects anything whose filename
doesn't end in `.vss`.

Some masters/pages store their artwork as a Windows EMF/WMF metafile, which
libvisio can't rasterize and browsers can't display. If `emf2svg-conv` (from
libemf2svg) is on `PATH`, those are rendered to real SVG and recovered
automatically; otherwise they're skipped (reported the same way as above)
rather than writing a broken image. With `emf2svg-conv` installed this path
can recover every item, entirely offline.

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
