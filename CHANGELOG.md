# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.8] - 2026-09-27

### Fixed

- The default `--download` filename for `--upload` (derived from the
  uploaded file's own name, e.g. `My Stencil.vss` to `My Stencil.xml`)
  could carry spaces straight through, unlike shape/page filenames, which
  were already space-free via `safe_shape_filename`. Added `no_spaces()`
  and applied it there: each space becomes its own underscore.

## [0.1.7] - 2026-09-27

### Added

- `--verbose` flag: prints a `[verbose]`-prefixed running commentary to
  stderr of what's happening at each stage (file detection, zip
  extraction, per-shape/page writes and skips, rasterization, and each
  step of the online vss.draw.io conversion). Normal stdout output is
  unchanged.

## [0.1.6] - 2026-09-27

### Added

- `--checkconfig` flag: checks whether all Python-package and PATH
  dependencies (`selenium`, Chrome/Chromium, `Pillow`, `rsvg-convert`,
  `vss2raw`/`vss2xhtml`/`vsd2raw`/`vsd2xhtml`, `emf2svg-conv`) are
  installed and prints a report, without requiring `--upload`/`--input`.
  Exits non-zero only if an unconditionally required dependency
  (`selenium`, Chrome/Chromium) is missing; the rest are feature-specific
  and reported but don't affect the exit code.
- `--install` flag (requires `--checkconfig`): attempts to install
  whichever dependencies `--checkconfig` finds missing, then re-checks and
  reports:
  - Python packages (`selenium`, `Pillow`) via `pip install`.
  - External (non-Python) tools: `rsvg-convert`/librsvg, libvisio's
    `vss2raw`/`vss2xhtml`/`vsd2raw`/`vsd2xhtml`, and `emf2svg-conv`/
    libemf2svg, via the first supported package manager found on `PATH`
    (`brew`, `apt-get`, `dnf`, or `pacman`).

  Does not touch Chrome/Chromium, which has to be installed manually.

### Changed

- Any invocation other than `-h`/`--version`/`--checkconfig` now silently
  verifies required dependencies (`selenium`, Chrome/Chromium) before doing
  anything else, exiting with the same report `--checkconfig` prints if
  one is missing. Nothing is printed when they're present.

### Fixed

- `--install`'s `apt-get` package mapping for `libemf2svg` is `emf2svg`
  (the package's actual name on Ubuntu/Debian), not `None`/unpackaged.

## [0.1.5] - 2026-09-27

### Added

- `--input` now also accepts a legacy Visio *drawing* (`.vss`, `.vssx`, and
  now `.vsd` share the same OLE2 container as `.vss`, so `.vsd` is detected
  by extension) file, split into one file per **page** rather than per
  master shape (`.vsd` is a document with drawn pages, not a shape
  library). Uses `vsd2raw`/`vsd2xhtml` instead of `vss2raw`/`vss2xhtml`,
  sharing the same splitting/EMF-recovery logic (refactored into a new
  `split_visio_document` shared by both `split_vss` and the new
  `split_vsd`). Verified against a real file (`Floor-Layout.vst.vsd`): both
  pages extracted with real names ("Page-1", "<Background Template>") and
  correctly rendered artwork.
- `.vsd` files are also recognized inside zip bundles passed to
  `--input`/`--upload`, alongside `.vss`/`.vssx`.
- `--upload` now fails immediately with a clear message when given a `.vsd`
  file (or a zip containing only `.vsd`/`.vssx` files), matching the
  existing `.vssx` handling. vss.draw.io only accepts `.vss`.

## [0.1.4] - 2026-09-27

### Added

- `--input` now also accepts a modern `.vssx` (OOXML) Visio stencil, split
  the same offline way as `.vss`: `vss2raw`/`vss2xhtml` handle both
  formats transparently. Verified against a real 54-shape `.vssx` file
  (HPE-Edgeline.vssx): all 54 shapes extracted with real names and correct
  artwork, no `emf2svg-conv` fallback even needed.
- `.vssx` files are also recognized inside zip bundles passed to
  `--input`/`--upload` (a `.vssx` is itself a zip package, detected via its
  `visio/document.xml` part and treated as a single stencil rather than
  opened as a bundle).

### Fixed

- `--upload` now fails immediately with a clear message when given a
  `.vssx` file (or a zip containing only `.vssx` files), instead of hanging
  until `--timeout`. Verified vss.draw.io's own client-side JS rejects any
  filename not ending in `.vss`, so the Convert button never becomes
  clickable and the previous code just timed out.

## [0.1.3] - 2026-09-27

### Added

- `--upload` now also accepts a `.zip` archive containing one or more `.vss`
  files, matching the `--input` behavior added in 0.1.1/0.1.2. Each `.vss`
  found is converted through vss.draw.io in its own fresh page load. With a
  single stencil, behavior is unchanged. With multiple, `--download` is
  treated as a directory (one converted file per stencil, named after it),
  and `--split --output` puts each stencil's shapes in their own
  subdirectory, exactly like the `--input` zip handling.

## [0.1.2] - 2026-09-27

### Changed

- `--input` given a `.zip` with more than one `.vss` (or `.xml`) file now
  extracts and splits *all* of them, one output subdirectory per source
  file (named after it), instead of picking just the first one
  alphabetically and warning about the rest. A zip with a single stencil
  behaves exactly as before. Prints a per-file line plus a total summary
  when there's more than one.

## [0.1.1] - 2026-09-27

### Added

- `--input` now also accepts a `.zip` archive (detected by its contents, not
  its extension) containing an `.vss` or `<mxlibrary>` `.xml` file. The
  first matching file found is extracted to a temporary directory and used;
  if several are found, the first alphabetically is used and the rest are
  noted on stderr.

## [0.1.0] - 2026-09-27

### Changed

- Versioning scheme: each version component now rolls over into the next
  once it would exceed 9 (e.g. 0.0.9 -> 0.1.0), instead of growing past a
  single digit (e.g. 0.0.10).
- `--to jpg`'s PNG -> JPEG step now uses Pillow instead of shelling out to
  ImageMagick's `magick`, dropping that external tool dependency. Pillow is
  auto-installed via pip if missing, the same way selenium is. `rsvg-convert`
  (SVG -> PNG) is unchanged and still required.
- Added `Pillow>=10` to `requirements.txt`.

## [0.0.9] - 2026-09-27

### Added

- `--to jpg`: rasterizes each shape's artwork to a white-background JPEG
  (via `rsvg-convert` for SVG -> PNG, then ImageMagick's `magick` for
  PNG -> flattened JPEG), for both the `<mxlibrary>` path and the native
  `.vss` path. Requires `rsvg-convert` and `magick` on `PATH`
  (`brew install librsvg imagemagick`).
- Rasterization caps the output to 2000px on the longest side, since some
  embedded artwork has a native resolution above librsvg's internal
  32767px limit and would otherwise fail to convert.

## [0.0.8] - 2026-09-27

### Changed

- `--split` is now a boolean flag (no value) instead of taking the output
  directory. The output directory moved to a new `--output DIR` flag.
  `--split` requires `--output`, and vice versa. Old invocations like
  `--split shapes/` must become `--split --output shapes/`.

## [0.0.7] - 2026-09-27

### Added

- Shapes in a `.vss` file whose only artwork is an embedded Windows EMF/WMF
  metafile are now recovered automatically when `emf2svg-conv` (from
  [libemf2svg](https://github.com/kakwa/libemf2svg)) is on `PATH`: the
  metafile is rendered to real SVG and nested in place of the broken image
  reference. On `Purestorage.vss` this raised offline `.vss` splitting
  coverage from 3 of 61 shapes to all 61.

### Fixed

- Recovered content is now checked for renderable tags regardless of SVG
  namespace prefix (`<path>` as well as `<svg:path>`), so successfully
  recovered shapes are no longer misreported as having no visible artwork.
- The nested SVG built from a recovered EMF/WMF image now carries its own
  `xmlns` declaration and has its source's leading XML declaration stripped,
  so it renders (previously it was inert due to a missing namespace) and the
  output file is well-formed XML (previously a stray embedded `<?xml ...?>`
  made it invalid).

## [0.0.6] - 2026-09-27

### Added

- `--input` now also accepts a raw `.vss` stencil file (detected via its
  OLE2 compound-file signature), splitting it directly into per-shape SVG
  files entirely offline via libvisio's `vss2raw` (for each shape's real
  name) and `vss2xhtml` (for rendered artwork). No browser or vss.draw.io
  upload involved. Requires `vss2raw`/`vss2xhtml` on `PATH`
  (`brew install libvisio`). `--to xml` is not supported for this input
  type; only `--to svg`.
- Shapes whose only artwork is an embedded Windows EMF/WMF metafile (which
  neither libvisio nor a browser can render) are detected and skipped
  rather than written as broken image files.

## [0.0.5] - 2026-09-27

### Added

- `--to {xml,svg}` flag for `--split` (default: `xml`). `--to svg` extracts
  each shape's embedded artwork as a standalone `.svg` file instead of
  writing a single-shape library file; shapes with no embedded image are
  skipped and reported. `--to` requires `--split`.

## [0.0.4] - 2026-09-27

### Added

- `--split DIR` flag: splits an `<mxlibrary>` file into individual
  single-shape library files in `DIR`, named after each shape's title.
- `--input FILE` flag: splits an existing library file directly, without
  running the browser/upload/convert flow. `--upload` and `--input` are
  mutually exclusive; exactly one is required.
- `--split` can also be combined with `--upload`/`--download` to split the
  freshly converted file right after it downloads.

## [0.0.3] - 2026-09-27

### Changed

- Renamed the script from `vss_convert.py` to `devon.py`.
- `--upload` is now a required argument (previously defaulted to
  `Stencil.vss`); the script exits with an error if it's omitted.
- `--version` now prints the script name, description
  ("Draw.io Exporter for Visio ONline"), and version number.
- Replaced vendor-specific example/default filenames with generic `Stencil`
  ones throughout the script and README.

### Added

- CC BY-NC-SA 4.0 license statement in the README.

## [0.0.2] - 2026-09-26

### Added

- `requirements.txt` pinning `selenium>=4.6`.
- Automatic self-install: the script now tries to import `selenium` and, if
  missing, installs it with `pip install selenium>=4.6` before retrying,
  instead of failing outright.

## [0.0.1] - 2026-09-26

### Added

- Initial version of `vss_convert.py`: automates vss.draw.io to upload a
  `.vss` file, check the "no sensitive or personal information"
  confirmation, click Convert, and save the resulting library file.
- `--upload`, `--download`, `--headless`, and `--timeout` CLI options.
- `--version` flag.
- README documenting requirements and usage.
