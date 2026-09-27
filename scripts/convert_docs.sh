#!/usr/bin/env bash
# Convert legacy .doc yearbooks to .docx in .cache/doc2docx (source stays read-only).
# Usage: scripts/convert_docs.sh [parallelism]   (needs LibreOffice `soffice`)
set -euo pipefail
SRC="${SOURCE_DIR:-/Volumes/MigMig/Programming/Datasets/Statistical Yearbook/Keshvari}"
OUT="$(cd "$(dirname "$0")/.." && pwd)/.cache/doc2docx"
P="${1:-4}"
mkdir -p "$OUT"
conv() {
  f="$1"; out="$2"
  y=$(basename "$(dirname "$f")"); b=$(basename "$f"); stem="${b%.*}"
  # 1387 ships one .doc per chapter (TESTnn.doc); older years one .doc for the whole book
  dest="$out/$y"; [ "$y" = "Yearbook_1387_w" ] && dest="$out/1387"
  mkdir -p "$dest"
  [ -s "$dest/$stem.docx" ] && exit 0
  prof="/tmp/lo_profile_$$_$RANDOM"
  soffice -env:UserInstallation=file://$prof --headless --convert-to docx --outdir "$dest" "$f" >/dev/null 2>&1 || echo "FAIL $f"
  rm -rf "$prof"
}
export -f conv
find "$SRC" -maxdepth 3 -type f \( -iname '*.doc' \) ! -name '~$*' \
  \( -ipath '*/13[4-8][0-9]/13[4-8][0-9].doc' -o -ipath '*Yearbook_1387_w/TEST1[4-6].doc' \) -print0 \
  | xargs -0 -P "$P" -I{} bash -c 'conv "$@"' _ {} "$OUT"
echo done
