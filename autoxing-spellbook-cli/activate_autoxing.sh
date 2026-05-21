#!/usr/bin/env bash
# Usage: source activate_autoxing.sh   (NOT ./activate_autoxing.sh — won't affect current shell)

deactivate_autoxing() {
    if [ -n "${_OLD_AUTOXING_PATH:-}" ]; then
        PATH="${_OLD_AUTOXING_PATH:-}"
        export PATH
        unset _OLD_AUTOXING_PATH
    fi
    if [ -n "${_OLD_AUTOXING_VIRTUAL_ENV+x}" ]; then
        if [ -n "${_OLD_AUTOXING_VIRTUAL_ENV}" ]; then
            export VIRTUAL_ENV="${_OLD_AUTOXING_VIRTUAL_ENV}"
        else
            unset VIRTUAL_ENV
        fi
        unset _OLD_AUTOXING_VIRTUAL_ENV
    fi
    if [ -n "${AUTOXING_SPELLBOOK_DIR:-}" ]; then
        unset AUTOXING_SPELLBOOK_DIR
    fi
    unset -f deactivate_autoxing
    echo "✅ Autoxing Spellbook deactivated!"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_DIR="${SCRIPT_DIR}/autoxing"
ROBOT_BIN="${SCRIPT_DIR}/bin"
VENV_BIN="${SCRIPT_DIR}/.venv/bin"

if [[ ":$PATH:" == *":$ROBOT_BIN:"* ]]; then
    echo "⚠️  Autoxing Spellbook already activated in this session"
else
    _OLD_AUTOXING_PATH="$PATH"
    _OLD_AUTOXING_VIRTUAL_ENV="${VIRTUAL_ENV-}"

    NEW_PATH="$ROBOT_BIN"
    if [ -d "$VENV_BIN" ]; then
        NEW_PATH="${NEW_PATH}:${VENV_BIN}"
        export VIRTUAL_ENV="${SCRIPT_DIR}/.venv"
    else
        echo "⚠️  No .venv found — run 'uv sync' in ${SCRIPT_DIR} first"
    fi
    export PATH="${NEW_PATH}:${PATH}"
    export AUTOXING_SPELLBOOK_DIR="$ROBOT_DIR"
    echo "✅ Autoxing Spellbook activated!"
    echo "Run 'autoxing_help' for quick reference"
    echo "Run 'deactivate_autoxing' to deactivate"
fi
