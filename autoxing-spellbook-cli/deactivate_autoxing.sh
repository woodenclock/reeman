#!/usr/bin/env bash
# Usage: source deactivate_autoxing.sh

if [ -n "$BASH_SOURCE" ] && [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo "❌ Error: Must be sourced, not executed directly"
    echo "  source deactivate_autoxing.sh"
    exit 1
fi

if [ -n "${AUTOXING_SPELLBOOK_DIR:-}" ]; then
    SCRIPT_DIR="$(dirname "$AUTOXING_SPELLBOOK_DIR")"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

ROBOT_BIN="${SCRIPT_DIR}/bin"

if [[ ":$PATH:" == *":$ROBOT_BIN:"* ]]; then
    PATH=$(echo "$PATH" | sed -e "s|:${ROBOT_BIN}||g" -e "s|${ROBOT_BIN}:||g" -e "s|${ROBOT_BIN}||g")
    export PATH
    unset AUTOXING_SPELLBOOK_DIR
    echo "✅ Autoxing Spellbook deactivated!"
else
    echo "⚠️  Autoxing Spellbook is not currently activated"
fi
