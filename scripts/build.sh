#!/usr/bin/env bash
# Build the installable extension zip into dist/ (needs Blender 4.3+ on PATH).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
blender --command extension build --source-dir popup_pro --output-dir dist
