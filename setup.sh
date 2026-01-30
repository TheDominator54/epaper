#!/usr/bin/env bash
# Run on the Raspberry Pi to set up the e-paper app.
set -e
cd "$(dirname "$0")"

echo "Cloning Waveshare e-Paper library..."
git clone --depth 1 https://github.com/waveshareteam/e-Paper.git lib/e-Paper

echo "Installing Python dependencies..."
pip3 install -r requirements.txt

echo ""
echo "Done. To run:"
echo "  export PYTHONPATH=\"$(pwd)/lib/e-Paper/RaspberryPi_JetsonNano/python/lib\""
echo "  python3 app/main.py"
echo ""
echo "Or run:  ./run.sh"
