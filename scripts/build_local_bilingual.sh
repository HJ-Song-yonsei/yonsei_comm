#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${DEEPL_API_KEY:-}" ]]; then
  echo "DEEPL_API_KEY is not set. See i18n/DEEPL_SETUP.md." >&2
  exit 1
fi

python3 -m pip install --disable-pip-version-check -r requirements-i18n.txt

# Assemble the local build tree with Python rather than macOS's bundled rsync.
# The system rsync can fail with "Illegal byte sequence" on decomposed Korean
# Unicode filenames (notably HWP attachments under data/files/).
python3 - <<'PY'
from pathlib import Path
import shutil

root = Path.cwd()
build = root / "build"
excluded = {".git", ".github", ".i18n-cache", ".i18n-source", "build"}

if build.exists():
    shutil.rmtree(build)
build.mkdir(parents=True)

for item in root.iterdir():
    if item.name in excluded:
        continue
    target = build / item.name
    if item.is_symlink():
        target.symlink_to(item.readlink(), target_is_directory=item.is_dir())
    elif item.is_dir():
        shutil.copytree(item, target, symlinks=True)
    else:
        shutil.copyfile(item, target)

(build / ".nojekyll").touch()
print("Local static site assembled in build/")
PY

python3 scripts/prepare_korean_site.py
python3 scripts/prepare_translation_source.py
python3 scripts/build_english_site.py \
  --source .i18n-source \
  --output build/en \
  --cache .i18n-cache/en.json
python3 scripts/build_additional_english_pages.py \
  --source .i18n-source \
  --output build/en \
  --cache .i18n-cache/en.json
python3 scripts/postprocess_english_site.py
python3 scripts/refine_english_site.py
python3 scripts/verify_i18n_build.py

echo
echo "Build complete. Preview with:"
echo "  python3 -m http.server 8000 --directory build"
echo "  http://localhost:8000/"
echo "  http://localhost:8000/en/"
