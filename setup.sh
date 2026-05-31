#!/bin/bash
set -e

echo "Setting up serial port access for TESmart serial control..."

echo "[1/3] Creating udev rule for FT232 serial adapter..."
echo 'SUBSYSTEM=="tty", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6001", TAG+="uaccess"' \
    | sudo tee /etc/udev/rules.d/99-tesmart-serial.rules > /dev/null

echo "[2/3] Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "[3/3] Granting StreamController Flatpak access to host devices..."
flatpak override --user --device=all com.core447.StreamController

echo ""
echo "Setup complete. Unplug and replug the serial adapter, then restart StreamController."
