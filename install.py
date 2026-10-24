#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Base directories (XDG standard)
home = Path.home()
dot_dir = home / ".config"
asura_dir = home / ".local/share/asura"
config_dir = home / ".config/asura"
hypr_dot = dot_dir / "hypr"

# Installer root directory
script_dir = Path(__file__).resolve().parent


def detect_distro() -> str:
    """Detect the Linux distribution by reading /etc/os-release."""
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return "unknown"

    data = {}
    for line in os_release.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip("\"'")

    distro_id = data.get("ID", "").lower()
    distro_like = data.get("ID_LIKE", "").lower()

    if "arch" in distro_id or "arch" in distro_like:
        return "Arch"
    elif "fedora" in distro_id:
        return "Fedora"
    return "unknown"


def install_dependencies():
    arch = [
    "quickshell", "hyprland", "awww", "hypridle",
    "qt6-declarative", "qt6-5compat",
    "wireplumber", "libpulse", "cava", "wf-recorder", "sound-theme-freedesktop",
    "networkmanager", "bluez-utils", "brightnessctl", "power-profiles-daemon",
    "wl-clipboard", "wtype", "zenity", "nwg-look", "xdg-utils", "jq", "ffmpeg",
    "python-pillow", "python-numpy"
]

    fedora = ["quickshell", "hyprland", "awww", "hypridle",
    "qt6-qtdeclarative", "qt6-qt5compat", "cava", "zenity", "wl-clipboard","wtype", "nwg-look", "xdg-utils","jq", "ffmpeg",
    "python-pillow", "python-numpy", "kitty", "fastfetch", "flameshot", "micro", "starship", "btop", "fish"]

    distro = detect_distro()   
    if distro == "Arch":
        print("Installing dependencies for Arch Linux...")
        subprocess.run(["sudo", "pacman", "-S", "--needed"] + arch, check=True)
    elif distro == "Fedora":
        print("Installing dependencies for Fedora...")
        subprocess.run(["sudo", "dnf", "install", "-y"] + fedora, check=True)
    else:
        print(f"Warning: Distribution '{distro}' not recognized automatically. Please install dependencies manually.")


def main():
    if os.geteuid() == 0:
        print("ERROR: Do not run the installer as root! Run as a normal user.", file=sys.stderr)
        sys.exit(1)

    install_dependencies()

    # Copy dotfiles to ~/.config
    dotfiles_src = script_dir / "dotfiles"
    if dotfiles_src.exists():
        dot_dir.mkdir(parents=True, exist_ok=True)
        for item in dotfiles_src.iterdir():
            destination = dot_dir / item.name
            if item.is_dir():
                shutil.copytree(item, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(item, destination)
            print(f"Installed configuration: {destination}")

    # Copy Asura-shell to ~/.local/share/asura
    asura_shell_src = script_dir / "Asura-shell"
    if not asura_shell_src.exists():
        asura_shell_src = script_dir / "Asura-Shell"

    if asura_shell_src.exists():
        asura_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(asura_shell_src, asura_dir, dirs_exist_ok=True)
        print(f"Shell files copied to: {asura_dir}")

    # Symlink ~/.config/hypr -> ~/.local/share/asura/hypr
    target_hypr = asura_dir / "hypr"
    if target_hypr.exists():
        if hypr_dot.is_symlink() or hypr_dot.is_file():
            hypr_dot.unlink()
        elif hypr_dot.is_dir():
            shutil.rmtree(hypr_dot)

        hypr_dot.symlink_to(target_hypr, target_is_directory=True)
        print(f"Symlink created: {hypr_dot} -> {target_hypr}")


if __name__ == "__main__":
    main()