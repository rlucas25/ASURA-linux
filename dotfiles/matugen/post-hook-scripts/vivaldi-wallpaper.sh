#!/bin/sh

set -eu

SOURCE="$1"
DEST="$HOME/.config/vivaldi/Default/VivaldiThumbnails/AsuraWallpaper.jpg"

mkdir -p "$(dirname "$DEST")"

cp -- "$SOURCE" "$DEST"