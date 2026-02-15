#!/usr/bin/env bash
# Run the 13.3" e-Paper C demo (must be built first with ./build.sh).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EPD="$SCRIPT_DIR/demo/epd"
if [[ ! -x "$EPD" ]]; then
  echo "Demo not built. Run: ./build.sh"
  exit 1
fi
sudo "$EPD"
