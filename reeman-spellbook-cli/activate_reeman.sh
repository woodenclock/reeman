#!/usr/bin/env bash
# Usage: source activate_reeman.sh   (NOT ./activate_reeman.sh — won't affect current shell)

deactivate_reeman() {
    if [ -n "${_OLD_REEMAN_PATH:-}" ]; then
        PATH="${_OLD_REEMAN_PATH:-}"
        export PATH
        unset _OLD_REEMAN_PATH
    fi
    if [ -n "${_OLD_REEMAN_VIRTUAL_ENV+x}" ]; then
        if [ -n "${_OLD_REEMAN_VIRTUAL_ENV}" ]; then
            export VIRTUAL_ENV="${_OLD_REEMAN_VIRTUAL_ENV}"
        else
            unset VIRTUAL_ENV
        fi
        unset _OLD_REEMAN_VIRTUAL_ENV
    fi
    if [ -n "${REEMAN_SPELLBOOK_DIR:-}" ]; then
        unset REEMAN_SPELLBOOK_DIR
    fi
    unset -f deactivate_reeman
    echo "✅ Reeman Spellbook deactivated!"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_DIR="${SCRIPT_DIR}/reeman"
ROBOT_BIN="${SCRIPT_DIR}/bin"
VENV_BIN="${SCRIPT_DIR}/.venv/bin"

if [[ ":$PATH:" == *":$ROBOT_BIN:"* ]]; then
    echo "⚠️  Reeman Spellbook already activated in this session"
else
    _OLD_REEMAN_PATH="$PATH"
    _OLD_REEMAN_VIRTUAL_ENV="${VIRTUAL_ENV-}"

    NEW_PATH="$ROBOT_BIN"
    if [ -d "$VENV_BIN" ]; then
        NEW_PATH="${NEW_PATH}:${VENV_BIN}"
        export VIRTUAL_ENV="${SCRIPT_DIR}/.venv"
    else
        echo "⚠️  No .venv found — run 'uv sync' in ${SCRIPT_DIR} first"
    fi
    export PATH="${NEW_PATH}:${PATH}"
    export REEMAN_SPELLBOOK_DIR="$ROBOT_DIR"
    echo "✅ Reeman Spellbook activated!"
    echo "Run 'reeman_help' for quick reference"
    echo "Run 'deactivate_reeman' to deactivate"
fi
