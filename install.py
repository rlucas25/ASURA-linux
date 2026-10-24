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

    if "arch" in distro_id or "arch" in distro_like or "cachyos" in distro_id:
        return "Arch"
    elif "fedora" in distro_id:
        return "Fedora"
    return "unknown"


def enable_fedora_copr(copr: str):
    """Enable a Fedora COPR repository with rawhide chroot fallback."""
    print(f"Enabling COPR: {copr}...")
    res = subprocess.run(["sudo", "dnf", "copr", "enable", "-y", copr], capture_output=True, text=True)
    if res.returncode != 0 and ("fedora-rawhide-x86_64" in res.stdout or "fedora-rawhide-x86_64" in res.stderr or "Chroot not found" in res.stdout or "Chroot not found" in res.stderr):
        print(f"Retrying COPR {copr} with rawhide chroot...")
        subprocess.run(["sudo", "dnf", "copr", "enable", "-y", "--chroot", "fedora-rawhide-x86_64", copr], check=False)


def copy_tree(src: Path, dst: Path):
    """Recursively copies src to dst, safely overwriting existing files and symlinks."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir() and not item.is_symlink():
            copy_tree(item, target)
        else:
            if target.is_symlink() or target.is_file():
                target.unlink()
            elif target.is_dir():
                shutil.rmtree(target)

            if item.is_symlink():
                link_target = os.readlink(item)
                os.symlink(link_target, target)
            else:
                shutil.copy2(item, target)


def install_dependencies():
    distro = detect_distro()

    if distro == "Arch":
        print("Installing dependencies for Arch / CachyOS Linux...")
        arch_official = [
            "hyprland", "hypridle", "kitty", "fastfetch", "flameshot", "micro", "starship", "btop", "fish",
            "qt6-declarative", "qt6-5compat",
            "wireplumber", "libpulse", "sound-theme-freedesktop",
            "networkmanager", "bluez-utils", "brightnessctl", "power-profiles-daemon",
            "wl-clipboard", "wtype", "zenity", "xdg-utils", "jq", "ffmpeg",
            "python-pillow", "python-numpy"
        ]
        arch_aur = ["quickshell", "awww", "cava", "nwg-look"]

        # Install official packages
        subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + arch_official, check=True)

        # Install AUR packages if helper is available
        aur_helper = shutil.which("paru") or shutil.which("yay")
        if aur_helper:
            print(f"Installing AUR packages using {aur_helper}...")
            subprocess.run([aur_helper, "-S", "--needed", "--noconfirm"] + arch_aur, check=False)
        else:
            print("Notice: 'paru' or 'yay' not found. Please install AUR packages manually:")
            print("       " + " ".join(arch_aur))

    elif distro == "Fedora":
        print("Configuring and installing dependencies for Fedora...")
        coprs = [
            "solopasha/hyprland",
            "avengemedia/danklinux",
            "atim/starship",
            "tofik/nwg-shell"
        ]

        # Enable COPR repositories with fallback
        for copr in coprs:
            enable_fedora_copr(copr)

        fedora_packages = [
            "hyprland", "hypridle", "quickshell", "awww", "starship",
            "qt6-qtdeclarative", "qt6-qt5compat",
            "wireplumber", "pulseaudio-utils", "sound-theme-freedesktop",
            "NetworkManager", "bluez", "brightnessctl", "power-profiles-daemon",
            "wl-clipboard", "wtype", "zenity", "nwg-look", "xdg-utils", "jq", "ffmpeg",
            "cava", "kitty", "fastfetch", "flameshot", "micro", "btop", "fish",
            "python3-pillow", "python3-numpy"
        ]

        # Install packages with --skip-unavailable to gracefully handle optional builds
        subprocess.run(["sudo", "dnf", "install", "-y", "--skip-unavailable"] + fedora_packages, check=True)

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
            if item.is_dir() and not item.is_symlink():
                copy_tree(item, destination)
            else:
                if destination.is_symlink() or destination.is_file():
                    destination.unlink()
                elif destination.is_dir():
                    shutil.rmtree(destination)

                if item.is_symlink():
                    os.symlink(os.readlink(item), destination)
                else:
                    shutil.copy2(item, destination)
            print(f"Installed configuration: {destination}")

    # Copy Asura-shell to ~/.local/share/asura
    asura_shell_src = script_dir / "Asura-shell"
    if not asura_shell_src.exists():
        asura_shell_src = script_dir / "Asura-Shell"

    if asura_shell_src.exists():
        asura_dir.parent.mkdir(parents=True, exist_ok=True)
        copy_tree(asura_shell_src, asura_dir)
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