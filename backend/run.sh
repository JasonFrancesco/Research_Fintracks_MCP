#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

PYTHON_BIN=""
if [ -f "$DIR/../venv/bin/python" ]; then
    PYTHON_BIN="$DIR/../venv/bin/python"
elif [ -f "$DIR/venv/bin/python" ]; then
    PYTHON_BIN="$DIR/venv/bin/python"
elif command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
else
    PYTHON_BIN="python3"
fi

echo "Menjalankan Backend FastAPI..."
"$PYTHON_BIN" run.py
