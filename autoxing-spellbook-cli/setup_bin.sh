#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROBOT_DIR="${SCRIPT_DIR}/autoxing"
BIN_DIR="${SCRIPT_DIR}/bin"

echo "==========================================="
echo "Autoxing Spellbook — Setup bin directory"
echo "==========================================="

mkdir -p "$BIN_DIR"
rm -f "$BIN_DIR"/*

cd "$ROBOT_DIR"
count=0
for script in *.py; do
  [ "$script" = "ws_helper.py" ] && continue
  [ "$script" = "ws_cli.py" ] && continue
  [ "$script" = "cli_tables.py" ] && continue
  [ "$script" = "api_client.py" ] && continue
  case "$script" in _*) continue ;; esac
  chmod +x "$script"
  bin_name="${script%.py}"
  ln -s "$ROBOT_DIR/$script" "$BIN_DIR/$bin_name"
  echo "   ✓ $bin_name -> autoxing/$script"
  count=$((count + 1))
done

echo ""
echo "✅ Setup complete! Created $count symlinks"
echo ""
echo "To activate:"
echo "  source activate_autoxing.sh"
echo ""
echo "You'll be able to run: autoxing_help, navigate, get_maps, ..."
echo ""
echo "To deactivate:"
echo "  deactivate_autoxing"
echo ""
