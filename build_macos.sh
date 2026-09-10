#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_root"
exec .venv/bin/pyinstaller --noconfirm --clean Jarvis.spec
