#!/bin/bash
set -e

echo "Setting up serial port access for TESmart serial control..."

echo "[1/2] Adding $USER to the dialout group..."
sudo usermod -a -G dialout $USER

echo "[2/2] Granting StreamController Flatpak access to host devices..."
flatpak override --user --device=all com.core447.StreamController

echo ""
echo "Setup complete. Reboot for the group change to take effect."
