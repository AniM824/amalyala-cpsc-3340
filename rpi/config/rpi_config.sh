#!/usr/bin/env bash
set -e

REPO_DIR="$HOME/amalyala-cpsc-3340/rpi/config"

mkdir -p "$REPO_DIR/boot" "$REPO_DIR/system"

echo "# Raspberry Pi IP Address" > "$REPO_DIR/IP_ADDRESS.md"
echo "$(hostname -I)" >> "$REPO_DIR/IP_ADDRESS.md"

cp -r /boot/. "$REPO_DIR/boot/"

cp /etc/hostname "$REPO_DIR/system/"
cp /etc/hosts "$REPO_DIR/system/"
cp /etc/fstab "$REPO_DIR/system/"

cd "$HOME/amalyala-cpsc-3340"
git add -A
git commit -m "Update RPi config snapshot"
git push
