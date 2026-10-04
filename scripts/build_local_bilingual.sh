#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -z "${DEEPL_API_KEY:-}" ]]; then
  echo "DEEPL_API_KEY is not set. See i18n/DEEPL_SETUP.md." >&2
  exit 1
fi

python3 -m pip install --disable-pip-version-check -r requirements-i18n.txt

rm -rf build
mkdir -p build
rsync -a --delete \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.i18n-cache' \
  --exclude 'build' \
  ./ build/
touch build/.nojekyll

python3 scripts/prepare_korean_site.py
python3 scripts/build_english_site.py \
  --source . \
  --output build/en \
  --cache .i18n-cache/en.json
python3 scripts/build_additional_english_pages.py \
  --source . \
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
