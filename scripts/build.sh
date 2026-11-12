#!/usr/bin/env bash
# Build the installable extension zip into dist/ (only popup_pro/ goes in it).
# Uses Blender (5.0+) if it is on PATH; otherwise a Python that has bpy
# (pip install bpy), python3 by default:  PYTHON=/path/to/python scripts/build.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
if command -v blender >/dev/null 2>&1; then
    blender --command extension build --source-dir popup_pro --output-dir dist
else
    py="${PYTHON:-python3}"
    # bpy carries Blender's own extension builder
    ext="$("$py" -c 'import bpy, os
print(os.path.join(bpy.utils.system_resource("SCRIPTS"), "addons_core", "bl_pkg", "cli",
                   "blender_ext.py"))' | tail -n 1)" && [ -f "$ext" ] || {
        echo "No blender on PATH, and $py has no bpy (pip install bpy, or set PYTHON)" >&2
        exit 1
    }
    "$py" "$ext" build --source-dir popup_pro --output-dir dist
fi
