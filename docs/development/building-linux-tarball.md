# Building the Linux `logforge-*.tar.gz` bundle

Releases are built on **Linux x86_64** (e.g. GitHub Actions `ubuntu-latest`) by [`.github/workflows/release.yml`](../../.github/workflows/release.yml) after `python -m build`.

Contributors working from a clone should start with [setup.md](setup.md) (editable install and tests).

## What you get

- **`app/bin/logforge`** — Shell script (not an ELF). It sets `PYTHONPATH` to the bundled `app/lib/python3.11/site-packages` and runs `python/bin/python3.11 -m logforge`. The ELF is the **embedded CPython interpreter** under `python/bin/`.
- **`python/`** — Pinned [python-build-standalone](https://github.com/astral-sh/python-build-standalone) `install_only` tarball (see `PBS_*` variables in [`scripts/build_linux_tgz.sh`](../../scripts/build_linux_tgz.sh)).
- **`app/lib/python3.11/site-packages/`** — From `pip install --prefix app` of the LogForge wheel and dependencies (no relocatable venv; avoids broken shebangs after moving the tree).
- **`LICENSE`**, **`NOTICE`** (from the repo root when present), **`PYTHON_PSF_LICENSE.txt`**, **`THIRD_PARTY_NOTICES.txt`** — See [linux-tarball.md](../deployment/linux-tarball.md).

## Backend

LogForge remains a normal **Python** application (FastAPI, Typer, etc.). The bundle does not change runtime behavior—only how the interpreter and packages are laid out on disk.

## Local reproduction (Linux x86_64 only)

```bash
python -m pip install build
VERSION=$(python -c "import re; print(re.search(r'__version__\s*=\s*\"([^\"]+)\"', open('src/logforge/__init__.py', encoding='utf-8').read()).group(1))")
python -m build   # produces dist/logforge-${VERSION}-py3-none-any.whl
bash scripts/build_linux_tgz.sh "$VERSION"
```

**Dependencies of the script:** `bash`, `curl`, `tar`, `gzip`, `sha256sum`, `find`. Embedded Python is downloaded; host Python is only used for `python -m build` before the script runs.

## Updating the embedded Python

Edit **`PBS_RELEASE`**, **`PBS_NAME`**, and the launcher path **`python3.11`** in:

- [`scripts/build_linux_tgz.sh`](../../scripts/build_linux_tgz.sh) (`PY=`, `SITE=` in the wrapper heredoc).

Re-download the matching `.sha256` from the same release and commit any changes to the script.

## Third-party notices

The build installs [`pip-licenses`](https://pypi.org/project/pip-licenses/) in a **disposable venv** and writes `THIRD_PARTY_NOTICES.txt` in the bundle. `pip-licenses` is listed under `[project.optional-dependencies] dev` in [`pyproject.toml`](../../pyproject.toml).

## CI

On tag push, the workflow builds the wheel, runs `scripts/build_linux_tgz.sh`, smoke-tests `logforge --version` and `logforge init`, then uploads wheels, sdists, the Linux tarball, `.sha256` files, and `checksums.txt`.
