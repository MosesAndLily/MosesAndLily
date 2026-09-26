#!/bin/sh
# Downloads the open-licensed (SIL OFL) fonts that make_assets.py converts to outlines.
set -e
cd "$(dirname "$0")" && mkdir -p fonts && cd fonts
base=https://raw.githubusercontent.com/google/fonts/main/ofl
curl -sSL -o Newsreader-VF.ttf  "$base/newsreader/Newsreader%5Bopsz%2Cwght%5D.ttf"
curl -sSL -o SourceSans3-VF.ttf "$base/sourcesans3/SourceSans3%5Bwght%5D.ttf"
curl -sSL -o NotoSerifKR-VF.ttf "$base/notoserifkr/NotoSerifKR%5Bwght%5D.ttf"
ls -la
