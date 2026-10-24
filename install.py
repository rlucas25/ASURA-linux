#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

__version__ = "0.1.0"

# Base directories (XDG standard)
home = Path.home()
dot_dir = home / ".config"
asura_dir = home / ".local/share/asura"
config_dir = home / ".config/asura"
bin_dir = home / ".local/bin"
hypr_dot = dot_dir / "hypr"
icons_dir = home / ".local/share/icons"
fonts_dir = home / ".local/share/fonts/Asura"

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


def setup_fedora_external_repos():
    """Configure official repositories for VS Code and Vivaldi on Fedora."""
    # Official Microsoft VS Code repository
    vscode_repo = Path("/etc/yum.repos.d/vscode.repo")
    if not vscode_repo.exists():
        print("Configuring official Microsoft VS Code repository...")
        vscode_content = """[code]
name=Visual Studio Code
baseurl=https://packages.microsoft.com/yumrepos/vscode
enabled=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
"""
        subprocess.run(["sudo", "rpm", "--import", "https://packages.microsoft.com/keys/microsoft.asc"], check=False)
        subprocess.run(["sudo", "tee", str(vscode_repo)], input=vscode_content, text=True, capture_output=True, check=False)

    # Official Vivaldi repository
    vivaldi_repo = Path("/etc/yum.repos.d/vivaldi.repo")
    if not vivaldi_repo.exists():
        print("Configuring official Vivaldi repository...")
        vivaldi_content = """[vivaldi]
name=vivaldi
baseurl=https://repo.vivaldi.com/archive/rpm/x86_64
enabled=1
gpgcheck=1
gpgkey=https://repo.vivaldi.com/archive/linux_signing_key.pub
"""
        subprocess.run(["sudo", "rpm", "--import", "https://repo.vivaldi.com/archive/linux_signing_key.pub"], check=False)
        subprocess.run(["sudo", "tee", str(vivaldi_repo)], input=vivaldi_content, text=True, capture_output=True, check=False)


def setup_fedora_services():
    """Enable and start default system daemons on Fedora (Battery, Bluetooth, Network, Energy)."""
    if not shutil.which("systemctl"):
        return

    services = [
        "upower.service",
        "bluetooth.service",
        "NetworkManager.service",
    ]

    # Power profile daemon (tuned-ppd on Fedora 41+ or power-profiles-daemon)
    if shutil.which("tuned-adm"):
        services.append("tuned.service")
    elif shutil.which("powerprofilesctl"):
        services.append("power-profiles-daemon.service")

    print("Configuring default Fedora system services (Battery, Bluetooth, Network)...")
    for service in services:
        print(f"  -> Enabling {service}...")
        try:
            res = subprocess.run(
                ["sudo", "systemctl", "enable", "--now", service],
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                print(f"     ✓ {service} enabled successfully.")
            else:
                err_msg = res.stderr.strip().splitlines()[0] if res.stderr.strip() else "service unavailable"
                print(f"     Notice: Could not enable {service} ({err_msg})")
        except Exception as e:
            print(f"     Notice: Could not run systemctl for {service}: {e}")


def install_dependencies():
    distro = detect_distro()

    if distro == "Arch":
        print("Installing dependencies for Arch / CachyOS Linux...")
        arch_official = [
            # Base Hyprland & Shell
            "hyprland", "hypridle", "kitty", "fastfetch", "flameshot", "micro", "starship", "btop", "fish",
            "nautilus", "pavucontrol", "vivaldi",
            # Fish Shell Tools
            "bat", "zoxide", "eza", "fzf", "fd",
            # Hyprland session helpers & build tools for hyprpm
            "cliphist", "gammastep", "trash-cli", "gnome-keyring", "polkit-gnome", "cmake", "cpio",
            # System, Media & Qt6
            "qt6-declarative", "qt6-5compat",
            "wireplumber", "libpulse", "sound-theme-freedesktop",
            "networkmanager", "bluez-utils", "brightnessctl", "power-profiles-daemon",
            "wl-clipboard", "wtype", "zenity", "xdg-utils", "jq", "ffmpeg",
            "python-pillow", "python-numpy",
            # Font & archive tools
            "fontconfig", "git", "tar", "xz"
        ]
        # Official VS Code (proprietary Microsoft build), Quickshell, and Bibata Cursor from AUR
        arch_aur = ["quickshell", "awww", "cava", "nwg-look", "visual-studio-code-bin", "bibata-cursor-theme-bin"]

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

        # Setup official third-party repos for VS Code & Vivaldi
        setup_fedora_external_repos()

        fedora_packages = [
            # Base Hyprland & Shell
            "hyprland", "hypridle", "quickshell", "awww", "starship",
            "nautilus", "pavucontrol", "vivaldi-stable", "code",
            # Fish Shell Tools
            "bat", "zoxide", "eza", "fzf", "fd-find",
            # Hyprland session helpers & build tools for hyprpm
            "cliphist", "gammastep", "trash-cli", "gnome-keyring", "cmake", "cpio",
            # System, Media & Qt6
            "qt6-qtdeclarative", "qt6-qt5compat",
            "wireplumber", "pulseaudio-utils", "sound-theme-freedesktop",
            "NetworkManager", "bluez", "brightnessctl",
            "wl-clipboard", "wtype", "zenity", "nwg-look", "xdg-utils", "jq", "ffmpeg",
            "cava", "kitty", "fastfetch", "flameshot", "micro", "btop", "fish",
            "python3-pillow", "python3-numpy",
            # Font & archive tools
            "fontconfig", "git", "tar", "xz"
        ]

        # In Fedora 41+, tuned-ppd provides powerprofilesctl and conflicts with power-profiles-daemon
        if not shutil.which("powerprofilesctl"):
            fedora_packages.append("power-profiles-daemon")

        # Install packages with flags to gracefully handle optional builds and conflicts
        subprocess.run(["sudo", "dnf", "install", "-y", "--skip-unavailable", "--skip-broken"] + fedora_packages, check=True)

        # Enable standard Fedora daemons (UPower, BlueZ, NetworkManager, TuneD/PPD)
        setup_fedora_services()

    else:
        print(f"Warning: Distribution '{distro}' not recognized automatically. Please install dependencies manually.")


def setup_fonts():
    """Install custom fonts shipped with Asura-shell into ~/.local/share/fonts/Asura."""
    print("\nInstalling Asura shell fonts...")
    font_source = script_dir / "Asura-shell" / "Shell" / "quickshell" / "Asura" / "fonts"
    if not font_source.exists():
        font_source = asura_dir / "Shell" / "quickshell" / "Asura" / "fonts"

    if not font_source.exists():
        print(f"  Notice: Font source directory not found at {font_source}")
        return

    fonts_dir.mkdir(parents=True, exist_ok=True)

    installed_count = 0
    for font_file in font_source.iterdir():
        if font_file.is_file() and font_file.suffix.lower() in [".ttf", ".otf", ".woff", ".woff2"]:
            dst = fonts_dir / font_file.name
            shutil.copy2(font_file, dst)
            installed_count += 1
            print(f"  ✓ Installed font: {font_file.name}")

    if shutil.which("fc-cache"):
        print("  -> Updating font cache...")
        subprocess.run(["fc-cache", "-f", str(fonts_dir)], check=False)
        subprocess.run(["fc-cache", "-f"], check=False)
        print(f"  ✓ {installed_count} font(s) registered in font cache.")
    else:
        print(f"  ✓ {installed_count} font(s) copied to {fonts_dir}.")
        print("  Notice: 'fc-cache' not found. Please install fontconfig to register fonts system-wide.")


def setup_cursor_and_icons():
    """Install and configure Bibata Modern Ice cursor and Conflux icon theme."""
    print("\nConfiguring cursor and icon themes...")
    icons_dir.mkdir(parents=True, exist_ok=True)

    # 1. Bibata Modern Ice (Cursor theme)
    bibata_dir = icons_dir / "Bibata-Modern-Ice"
    system_bibata = Path("/usr/share/icons/Bibata-Modern-Ice")

    if bibata_dir.exists() or system_bibata.exists():
        print("  ✓ Bibata-Modern-Ice cursor theme is present.")
    else:
        print("  -> Downloading and installing Bibata-Modern-Ice cursor theme...")
        bibata_url = "https://github.com/ful1e5/Bibata_Cursor/releases/latest/download/Bibata-Modern-Ice.tar.xz"
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                archive_path = Path(tmp_dir) / "Bibata-Modern-Ice.tar.xz"
                req = urllib.request.Request(
                    bibata_url,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req) as resp, open(archive_path, "wb") as out_file:
                    shutil.copyfileobj(resp, out_file)

                with tarfile.open(archive_path, "r:*") as tar:
                    if hasattr(tarfile, "data_filter"):
                        tar.extractall(path=icons_dir, filter="data")
                    else:
                        tar.extractall(path=icons_dir)
            print("  ✓ Bibata-Modern-Ice cursor theme installed successfully.")
        except Exception as e:
            print(f"  Notice: Could not download Bibata-Modern-Ice automatically: {e}")

    # Compatibility symlink: Bibata-Modern_Ice -> Bibata-Modern-Ice
    compat_bibata = icons_dir / "Bibata-Modern_Ice"
    if bibata_dir.exists() and not compat_bibata.exists():
        try:
            compat_bibata.symlink_to(bibata_dir.name)
            print("  ✓ Created compatibility symlink: Bibata-Modern_Ice -> Bibata-Modern-Ice")
        except Exception:
            pass

    # Configure default X11/XDG cursor theme
    default_icon_dirs = [
        home / ".icons/default",
        icons_dir / "default"
    ]
    default_theme_content = """[Icon Theme]
Name=Default
Comment=Default Cursor Theme
Inherits=Bibata-Modern-Ice
"""
    for d_dir in default_icon_dirs:
        d_dir.mkdir(parents=True, exist_ok=True)
        theme_file = d_dir / "index.theme"
        if not theme_file.exists():
            theme_file.write_text(default_theme_content)

    if shutil.which("gsettings"):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", "Bibata-Modern-Ice"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "cursor-size", "24"], check=False)

    # 2. Conflux (Icon theme)
    conflux_dir = icons_dir / "Conflux"
    if conflux_dir.exists() and (conflux_dir / "index.theme").exists():
        print("  ✓ Conflux icon theme is already installed.")
        if (conflux_dir / ".git").exists() and shutil.which("git"):
            try:
                subprocess.run(["git", "-C", str(conflux_dir), "pull", "--ff-only"], capture_output=True, timeout=10, check=False)
            except Exception:
                pass
    else:
        print("  -> Cloning Conflux icon theme repository...")
        conflux_repo = "https://github.com/MoshiurRahmanAdib/Conflux-Icon-Theme.git"
        if shutil.which("git"):
            try:
                res = subprocess.run(["git", "clone", "--depth=1", conflux_repo, str(conflux_dir)], check=False)
                if res.returncode == 0:
                    print("  ✓ Conflux icon theme installed successfully.")
                else:
                    print(f"  Notice: git clone returned exit code {res.returncode} for Conflux.")
            except Exception as e:
                print(f"  Notice: Could not clone Conflux icon theme: {e}")
        else:
            print("  Notice: 'git' is not available to clone Conflux icon theme.")

    # Update icon cache if tool is present
    if conflux_dir.exists() and shutil.which("gtk-update-icon-cache"):
        print("  -> Updating icon cache for Conflux...")
        subprocess.run(["gtk-update-icon-cache", "-q", "-f", "-t", str(conflux_dir)], check=False)
        print("  ✓ Conflux icon cache updated.")

    if shutil.which("gsettings"):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "Conflux"], check=False)


def setup_hyprland_plugins():
    """Setup and enable required Hyprland plugins via hyprpm."""
    if not shutil.which("hyprpm"):
        return

    print("Configuring Hyprland plugins via hyprpm...")
    try:
        res = subprocess.run(["hyprpm", "list"], capture_output=True, text=True, timeout=10)
        if "hyprland-scroll-overview" not in res.stdout:
            print("  -> Adding hyprland-scroll-overview plugin...")
            subprocess.run(["hyprpm", "add", "https://github.com/yayuuu/hyprland-scroll-overview"], check=False)
            subprocess.run(["hyprpm", "enable", "scrolloverview"], check=False)
            subprocess.run(["hyprpm", "reload"], check=False)
        else:
            print("  ✓ hyprland-scroll-overview is already registered.")
            subprocess.run(["hyprpm", "enable", "scrolloverview"], check=False)
    except Exception as e:
        print(f"Notice: Could not configure hyprpm plugins: {e}")


def setup_micro_plugins():
    """Ensure micro editor plugins (like filemanager) are active and verified."""
    micro_plug_dir = dot_dir / "micro" / "plug" / "filemanager"
    if micro_plug_dir.exists():
        print(f"  ✓ Micro plugin 'filemanager' verified at {micro_plug_dir}")
    elif shutil.which("micro"):
        print("  -> Installing micro 'filemanager' plugin...")
        subprocess.run(["micro", "-plugin", "install", "filemanager"], check=False)


def setup_fish_environment():
    """Ensure fish shell commands (like fd on Fedora) are compatible."""
    if not shutil.which("fd") and shutil.which("fd-find"):
        bin_dir.mkdir(parents=True, exist_ok=True)
        fd_symlink = bin_dir / "fd"
        if not fd_symlink.exists():
            fd_target = Path(shutil.which("fd-find"))
            fd_symlink.symlink_to(fd_target)
            print(f"  ✓ Created compatibility symlink: {fd_symlink} -> {fd_target}")


def main():
    parser = argparse.ArgumentParser(
        prog="install.py",
        description=f"ASURA Installer v{__version__} - Automated dotfiles, shell, fonts and themes installation."
    )
    parser.add_argument("-v", "--version", action="version", version=f"ASURA Installer {__version__}")
    parser.add_argument("--skip-deps", action="store_true", help="Skip system package dependency installation")
    parser.add_argument("--skip-themes", action="store_true", help="Skip icon and cursor theme installation")
    parser.add_argument("--skip-fonts", action="store_true", help="Skip font installation")
    args = parser.parse_args()

    print("=" * 56)
    print(f"             ASURA Installer v{__version__}")
    print("=" * 56)

    if os.geteuid() == 0:
        print("ERROR: Do not run the installer as root! Run as a normal user.", file=sys.stderr)
        sys.exit(1)

    if not args.skip_deps:
        install_dependencies()
    else:
        print("Skipping dependency installation (--skip-deps specified).")

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

    # Install CLI command to ~/.local/bin/asura
    cli_source = asura_dir / "cli" / "main.py"
    if cli_source.exists():
        bin_dir.mkdir(parents=True, exist_ok=True)
        cli_source.chmod(0o755)
        cli_target = bin_dir / "asura"
        if cli_target.is_symlink() or cli_target.is_file():
            cli_target.unlink()
        elif cli_target.is_dir():
            shutil.rmtree(cli_target)

        cli_target.symlink_to(cli_source)
        print(f"CLI installed: {cli_target} -> {cli_source}")

    # Setup fonts shipped with Asura-shell
    if not args.skip_fonts:
        setup_fonts()
    else:
        print("Skipping font installation (--skip-fonts specified).")

    # Setup Bibata Modern Ice cursor and Conflux icon themes
    if not args.skip_themes:
        setup_cursor_and_icons()
    else:
        print("Skipping theme installation (--skip-themes specified).")

    # Setup plugins & environment integrations
    print("\nVerifying plugins and environment integrations...")
    setup_micro_plugins()
    setup_hyprland_plugins()
    setup_fish_environment()

    print("\n" + "=" * 56)
    print(f"     ASURA installation completed successfully! (v{__version__})")
    print("=" * 56)


if __name__ == "__main__":
    main()