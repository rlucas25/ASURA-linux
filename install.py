#!/usr/bin/env python3

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

__version__ = "0.1.2"

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


def enable_fedora_copr(copr: str, fallback_chroot: str = "fedora-rawhide-x86_64"):
    """Enable a Fedora COPR repository with DNF5, DNF4, and direct repo fallback."""
    print(f"Enabling COPR: {copr}...")
    res = subprocess.run(["sudo", "dnf", "copr", "enable", "-y", copr], capture_output=True, text=True)
    if res.returncode == 0:
        return

    print(f"Retrying COPR {copr} with chroot {fallback_chroot}...")
    # DNF5 (Fedora 41+): chroot is a positional argument
    res_dnf5 = subprocess.run(["sudo", "dnf", "copr", "enable", "-y", copr, fallback_chroot], capture_output=True, text=True)
    if res_dnf5.returncode == 0:
        return

    # DNF4 (older Fedora): chroot is --chroot flag
    res_dnf4 = subprocess.run(["sudo", "dnf", "copr", "enable", "-y", "--chroot", fallback_chroot, copr], capture_output=True, text=True)
    if res_dnf4.returncode == 0:
        return

    # Direct .repo file fallback
    try:
        owner, project = copr.split("/", 1)
        repo_path = Path("/etc/yum.repos.d") / f"_copr:copr.fedorainfracloud.org:{owner}:{project}.repo"
        repo_content = f"""[copr:copr.fedorainfracloud.org:{owner}:{project}]
name=Copr repo for {project} owned by {owner}
baseurl=https://download.copr.fedorainfracloud.org/results/{owner}/{project}/{fallback_chroot}/
type=rpm-md
skip_if_unavailable=True
gpgcheck=1
gpgkey=https://download.copr.fedorainfracloud.org/results/{owner}/{project}/pubkey.gpg
repo_gpgcheck=0
enabled=1
enabled_metadata=1
"""
        print(f"Configuring COPR repository file directly at {repo_path}...")
        subprocess.run(["sudo", "tee", str(repo_path)], input=repo_content, text=True, capture_output=True, check=False)
    except Exception as e:
        print(f"Notice: Could not configure COPR repo file for {copr}: {e}")


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


def setup_system_services(distro="Linux"):
    """Enable and start default system daemons (Battery, Bluetooth, Network, Energy)."""
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

    print(f"Configuring default {distro} system services (Battery, Bluetooth, Network, Power)...")
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
            "hyprland", "hyprpm", "hypridle", "quickshell", "kitty", "fastfetch", "flameshot", "micro", "starship", "btop", "fish",
            "nautilus", "pavucontrol", "vivaldi", "code", "cava", "nwg-look", "awww",
            # Fish Shell Tools
            "bat", "zoxide", "eza", "fzf", "fd",
            # Hyprland session helpers & build tools for hyprpm
            "cliphist", "gammastep", "trash-cli", "gnome-keyring", "polkit-gnome", "cmake", "cpio", "gcc", "pkgconf", "meson", "hyprwayland-scanner",
            # System, Media & Qt6
            "qt6-declarative", "qt6-5compat", "qt6-wayland",
            "xdg-desktop-portal", "xdg-desktop-portal-hyprland", "xdg-desktop-portal-gtk",
            "wireplumber", "libpulse", "sound-theme-freedesktop",
            "networkmanager", "bluez-utils", "brightnessctl", "power-profiles-daemon",
            "wl-clipboard", "wtype", "zenity", "xdg-utils", "jq", "ffmpeg",
            "python-pillow", "python-numpy",
            # Screen recording, screenshots & notifications
            "wf-recorder", "grim", "slurp", "libnotify",
            # Font & archive tools
            "fontconfig", "git", "tar", "xz",
            # GTK widget theme & core utilities
            "adw-gtk-theme", "which"
        ]
        # Proprietary VS Code build and Bibata Cursor from AUR (optional)
        arch_aur = ["visual-studio-code-bin", "bibata-cursor-theme-bin"]

        # Install official packages
        subprocess.run(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + arch_official, check=True)

        # Install AUR packages if helper is available
        aur_helper = shutil.which("paru") or shutil.which("yay")
        if aur_helper:
            print(f"Installing AUR packages using {aur_helper}...")
            subprocess.run([aur_helper, "-S", "--needed", "--noconfirm"] + arch_aur, check=False)
        else:
            print("Notice: 'paru' or 'yay' not found. Optional AUR packages skipped:")
            print("       " + " ".join(arch_aur))

        # Enable standard system daemons (Bluetooth, NetworkManager, Power)
        setup_system_services("Arch")

    elif distro == "Fedora":
        print("Configuring and installing dependencies for Fedora...")
        coprs = [
            "sdegler/hyprland",
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
            "hyprland", "hypridle", "hyprpolkitagent", "quickshell", "awww", "swww", "starship",
            "nautilus", "pavucontrol", "vivaldi-stable", "code",
            # Fish Shell Tools
            "bat", "zoxide", "eza", "fzf", "fd-find",
            # Hyprland session helpers & build tools for hyprpm
            "cliphist", "gammastep", "trash-cli", "gnome-keyring", "cmake", "cpio", "gcc", "gcc-c++", "hyprland-devel", "pkgconf-pkg-config", "meson", "hyprwayland-scanner",
            # System, Media & Qt6
            "qt6-qtdeclarative", "qt6-qt5compat", "qt6-qtwayland",
            "xdg-desktop-portal", "xdg-desktop-portal-hyprland", "xdg-desktop-portal-gtk",
            "wireplumber", "pulseaudio-utils", "sound-theme-freedesktop",
            "NetworkManager", "bluez", "brightnessctl",
            "wl-clipboard", "wtype", "zenity", "nwg-look", "xdg-utils", "jq", "ffmpeg",
            "cava", "kitty", "fastfetch", "flameshot", "micro", "btop", "fish",
            "python3-pillow", "python3-numpy",
            # Screen recording, screenshots & notifications
            "wf-recorder", "grim", "slurp", "libnotify",
            # Font & archive tools
            "fontconfig", "git", "tar", "xz",
            # GTK widget theme & core utilities
            "adw-gtk3-theme", "which"
        ]

        # In Fedora 41+, tuned-ppd provides powerprofilesctl and conflicts with power-profiles-daemon
        if not shutil.which("powerprofilesctl"):
            fedora_packages.append("power-profiles-daemon")

        # Install packages with flags to gracefully handle optional builds and conflicts
        subprocess.run(["sudo", "dnf", "install", "-y", "--skip-unavailable", "--skip-broken"] + fedora_packages, check=True)

        # Verify Hyprland installation
        if not shutil.which("hyprland"):
            print("\n[!] Hyprland binary was not detected after general package installation.")
            print("    Attempting direct installation of hyprland and hypridle...")
            res_hypr = subprocess.run(["sudo", "dnf", "install", "-y", "hyprland", "hypridle"], check=False)
            if res_hypr.returncode != 0:
                print("WARNING: Hyprland package installation failed on Fedora! Check active COPR repositories.", file=sys.stderr)
            else:
                print("✓ Hyprland installed successfully.")

        # Enable standard Fedora daemons (UPower, BlueZ, NetworkManager, TuneD/PPD)
        setup_system_services("Fedora")

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


def setup_gtk_theme():
    """Ensure adw-gtk3 widget style/theme is installed and configured."""
    print("Configuring GTK widget style (adw-gtk3)...")
    themes_dir = home / ".local/share/themes"
    themes_dir.mkdir(parents=True, exist_ok=True)

    adw_dark_usr = Path("/usr/share/themes/adw-gtk3-dark")
    adw_dark_local = themes_dir / "adw-gtk3-dark"

    if adw_dark_usr.exists() or adw_dark_local.exists():
        print("  ✓ adw-gtk3 widget theme verified.")
    else:
        print("  -> Downloading adw-gtk3 widget theme from GitHub releases...")
        adw_url = "https://github.com/lassekongo83/adw-gtk3/releases/download/v6.5/adw-gtk3v6.5.tar.xz"
        try:
            with tempfile.NamedTemporaryFile(suffix=".tar.xz", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                urllib.request.urlretrieve(adw_url, tmp_path)
                with tarfile.open(tmp_path, "r:xz") as tar:
                    try:
                        tar.extractall(path=themes_dir, filter="data")
                    except TypeError:
                        tar.extractall(path=themes_dir)
                tmp_path.unlink()
            print("  ✓ adw-gtk3 widget theme installed to ~/.local/share/themes.")
        except Exception as e:
            print(f"  Notice: Could not download adw-gtk3 widget theme: {e}")

    # Configure GTK theme and dark mode via gsettings
    if shutil.which("gsettings"):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "gtk-theme", "adw-gtk3-dark"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme", "prefer-dark"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "Conflux"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "cursor-theme", "Bibata-Modern-Ice"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "cursor-size", "24"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.interface", "font-name", "Roboto Flex 11"], check=False)
        print("  ✓ GTK interface preferences configured via gsettings.")


def setup_default_apps():
    """Configure default applications (Terminal, Text Editor, Browser, File Manager)."""
    print("Configuring default applications...")

    app_dirs = [
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        home / ".local/share/applications",
        Path("/var/lib/flatpak/exports/share/applications"),
    ]

    def find_desktop_file(candidates):
        for candidate in candidates:
            for d in app_dirs:
                if (d / candidate).exists():
                    return candidate
            for d in app_dirs:
                if d.exists():
                    for f in d.glob(candidate):
                        return f.name
        return None

    editor_desktop = find_desktop_file([
        "code.desktop",
        "com.microsoft.VSCode.desktop",
        "visual-studio-code.desktop",
        "code-oss.desktop",
        "micro.desktop"
    ])
    terminal_desktop = find_desktop_file(["kitty.desktop", "kitty-open.desktop"]) or "kitty.desktop"
    file_manager_desktop = find_desktop_file(["org.gnome.Nautilus.desktop", "nautilus.desktop"])
    browser_desktop = find_desktop_file(["vivaldi-stable.desktop", "vivaldi.desktop"])

    if shutil.which("xdg-mime"):
        if editor_desktop:
            text_mimes = [
                "text/plain", "text/markdown", "text/x-python", "text/x-c", "text/x-c++",
                "text/x-csrc", "text/x-chdr", "text/x-lua", "text/x-shellscript",
                "application/x-shellscript", "application/json", "application/xml",
                "text/html", "text/css", "text/javascript", "application/javascript"
            ]
            for m in text_mimes:
                subprocess.run(["xdg-mime", "default", editor_desktop, m], check=False)
            print(f"  ✓ Default text editor set: {editor_desktop}")

        if file_manager_desktop:
            subprocess.run(["xdg-mime", "default", file_manager_desktop, "inode/directory"], check=False)
            subprocess.run(["xdg-mime", "default", file_manager_desktop, "x-scheme-handler/trash"], check=False)
            print(f"  ✓ Default file manager set: {file_manager_desktop}")

        if browser_desktop:
            browser_mimes = [
                "x-scheme-handler/http", "x-scheme-handler/https", "text/html", "application/xhtml+xml"
            ]
            for m in browser_mimes:
                subprocess.run(["xdg-mime", "default", browser_desktop, m], check=False)
            print(f"  ✓ Default web browser set: {browser_desktop}")

    if browser_desktop and shutil.which("xdg-settings"):
        subprocess.run(["xdg-settings", "set", "default-web-browser", browser_desktop], check=False)
        subprocess.run(["xdg-settings", "set", "default-url-scheme-handler", "http", browser_desktop], check=False)
        subprocess.run(["xdg-settings", "set", "default-url-scheme-handler", "https", browser_desktop], check=False)

    if shutil.which("gsettings"):
        subprocess.run(["gsettings", "set", "org.gnome.desktop.default-applications.terminal", "exec", "kitty"], check=False)
        subprocess.run(["gsettings", "set", "org.gnome.desktop.default-applications.terminal", "exec-arg", "-e"], check=False)
        print("  ✓ Default terminal set: kitty")

    # Set user environment variables for default apps
    env_d = dot_dir / "environment.d"
    env_d.mkdir(parents=True, exist_ok=True)
    asura_env = env_d / "10-asura.conf"
    asura_env_content = "TERMINAL=kitty\nEDITOR=micro\nVISUAL=code\n"
    asura_env.write_text(asura_env_content)
    print(f"  ✓ User session variables written to {asura_env}")

    if shutil.which("fish"):
        try:
            subprocess.run(["fish", "-c", "set -Ux TERMINAL kitty; set -Ux EDITOR micro; set -Ux VISUAL code"], capture_output=True, check=False)
            print("  ✓ Configured fish shell universal default variables.")
        except Exception:
            pass

    # Synchronize with Asura default_apps_manager if installed
    default_apps_script = asura_dir / "Shell/quickshell/Services/default_apps_manager.py"
    if default_apps_script.exists():
        try:
            payload = json.dumps({
                "fileExplorer": "nautilus",
                "terminal": "kitty",
                "browser": "vivaldi",
                "editor": "code",
                "audioSettings": "pavucontrol"
            })
            subprocess.run(["python3", str(default_apps_script), "apply", payload], capture_output=True, timeout=5, check=False)
            print("  ✓ Asura shell default apps synchronized.")
        except Exception:
            pass


def setup_hyprland_plugins():
    """Setup and enable required Hyprland plugins via hyprpm."""
    if not shutil.which("hyprpm"):
        print("  Notice: 'hyprpm' not found. Skipping Hyprland plugin configuration.")
        return

    print("Configuring Hyprland plugins via hyprpm...")

    # Refresh sudo credentials upfront so hyprpm has superuser access
    try:
        subprocess.run(["sudo", "-v"], check=True)
    except Exception as e:
        print(f"  Notice: Could not refresh sudo credentials: {e}")

    # hyprpm executes 'sudo -k' upon exit of every subcommand (dropSudo).
    # This wipes sudo timestamps between commands, causing password prompts to repeatedly
    # pop up or fail in automated environments. A temporary shim prevents 'sudo -k' from dropping
    # the timestamp during plugin setup.
    temp_bin = tempfile.mkdtemp(prefix="asura_sudo_shim_")
    shim_sudo = Path(temp_bin) / "sudo"
    real_sudo = shutil.which("sudo") or "/usr/bin/sudo"
    shim_content = f"""#!/bin/sh
if [ "$1" = "-k" ]; then
    exit 0
fi
exec "{real_sudo}" "$@"
"""
    shim_sudo.write_text(shim_content)
    shim_sudo.chmod(0o755)

    old_path = os.environ.get("PATH", "")
    env = os.environ.copy()
    env["PATH"] = f"{temp_bin}:{old_path}"

    headless_proc = None
    temp_cfg = None
    try:
        sig = env.get("HYPRLAND_INSTANCE_SIGNATURE")
        uid = os.getuid()
        hypr_run_dir = Path(f"/run/user/{uid}/hypr")

        # Detect active running Hyprland socket if not set in environment
        if not sig and hypr_run_dir.exists():
            for entry in hypr_run_dir.iterdir():
                if entry.is_dir() and (entry / ".socket.sock").exists():
                    sig = entry.name
                    env["HYPRLAND_INSTANCE_SIGNATURE"] = sig
                    break

        # hyprpm requires an active Hyprland instance to query the running version and ABI hash.
        # If Hyprland is not running, spawn a temporary minimal headless session.
        if not sig and shutil.which("Hyprland"):
            print("  -> Initializing temporary headless Hyprland session for plugin build...")
            temp_cfg = tempfile.NamedTemporaryFile("w", delete=False, suffix=".conf")
            temp_cfg.write("debug:disable_logs = false\n")
            temp_cfg.close()

            before_dirs = set(p.name for p in hypr_run_dir.iterdir() if p.is_dir()) if hypr_run_dir.exists() else set()
            headless_env = env.copy()
            headless_env["AQ_PLATFORM"] = "headless"
            headless_env["WLR_BACKENDS"] = "headless"

            headless_proc = subprocess.Popen(
                ["Hyprland", "-c", temp_cfg.name],
                env=headless_env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            # Wait for socket to become available (up to 4 seconds)
            for _ in range(40):
                time.sleep(0.1)
                if hypr_run_dir.exists():
                    now_dirs = set(p.name for p in hypr_run_dir.iterdir() if p.is_dir())
                    diff = now_dirs - before_dirs
                    for d in diff:
                        if (hypr_run_dir / d / ".socket.sock").exists():
                            sig = d
                            break
                if sig:
                    break

            if sig:
                env["HYPRLAND_INSTANCE_SIGNATURE"] = sig
                print(f"  ✓ Headless Hyprland active (instance: {sig[:16]}...)")
            else:
                print("  Notice: Could not start headless Hyprland session. Proceeding with best effort.")

        # Update hyprpm headers
        print("  -> Updating hyprpm headers (this may take a moment)...")
        subprocess.run(["hyprpm", "update", "-f"], env=env, check=False)

        res = subprocess.run(["hyprpm", "list"], env=env, capture_output=True, text=True, timeout=15)
        if "hyprland-scroll-overview" not in res.stdout:
            print("  -> Adding hyprland-scroll-overview plugin...")
            subprocess.run(["hyprpm", "add", "https://github.com/yayuuu/hyprland-scroll-overview"], input="y\n", env=env, text=True, check=False)
            subprocess.run(["hyprpm", "enable", "scrolloverview"], env=env, check=False)
            print("  ✓ hyprland-scroll-overview added and enabled.")
        else:
            print("  ✓ hyprland-scroll-overview is already registered.")
            subprocess.run(["hyprpm", "enable", "scrolloverview"], env=env, check=False)

        # Verify compiled plugin binary in cache
        user_name = Path.home().name
        so_path = Path(f"/var/cache/hyprpm/{user_name}/hyprland-scroll-overview/scrolloverview.so")
        if so_path.exists():
            print(f"  ✓ scrolloverview binary verified at {so_path}")
        else:
            print("  Notice: scrolloverview.so was not found in cache. A build might be triggered on first Hyprland launch.")

        # Reload plugins if an actual graphical Hyprland instance was already running
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            subprocess.run(["hyprpm", "reload"], env=env, check=False)

    except Exception as e:
        print(f"Notice: Could not configure hyprpm plugins: {e}")
    finally:
        if headless_proc:
            headless_proc.terminate()
            try:
                headless_proc.wait(timeout=2)
            except Exception:
                headless_proc.kill()
        if temp_cfg and Path(temp_cfg.name).exists():
            try:
                Path(temp_cfg.name).unlink()
            except Exception:
                pass
        try:
            shutil.rmtree(temp_bin, ignore_errors=True)
        except Exception:
            pass


def setup_micro_plugins():
    """Ensure micro editor plugins (like filemanager) are active and verified."""
    micro_plug_dir = dot_dir / "micro" / "plug" / "filemanager"
    if micro_plug_dir.exists():
        print(f"  ✓ Micro plugin 'filemanager' verified at {micro_plug_dir}")
    elif shutil.which("micro"):
        print("  -> Installing micro 'filemanager' plugin...")
        subprocess.run(["micro", "-plugin", "install", "filemanager"], check=False)


def setup_fish_environment():
    """Ensure fish shell commands, ~/.local/bin in PATH, and tool symlinks (like fd, awww/swww on Fedora) are compatible."""
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Ensure ~/.local/bin is in fish universal PATH
    if shutil.which("fish"):
        try:
            subprocess.run(["fish", "-c", "fish_add_path -U $HOME/.local/bin"], capture_output=True, check=False)
            print("  ✓ Added ~/.local/bin to fish universal path.")
        except Exception:
            pass

    # fd -> fd-find compatibility
    if not shutil.which("fd") and shutil.which("fd-find"):
        fd_symlink = bin_dir / "fd"
        if not fd_symlink.exists():
            fd_target = Path(shutil.which("fd-find"))
            fd_symlink.symlink_to(fd_target)
            print(f"  ✓ Created compatibility symlink: {fd_symlink} -> {fd_target}")

    # awww -> swww compatibility on Fedora
    if not shutil.which("awww") and shutil.which("swww"):
        awww_symlink = bin_dir / "awww"
        if not awww_symlink.exists():
            awww_symlink.symlink_to(Path(shutil.which("swww")))
            print(f"  ✓ Created compatibility symlink: {awww_symlink} -> swww")
        swww_bin = shutil.which("swww")
        if swww_bin:
            subprocess.run(["sudo", "ln", "-sf", swww_bin, "/usr/local/bin/awww"], capture_output=True, check=False)

    if not shutil.which("awww-daemon") and shutil.which("swww-daemon"):
        daemon_symlink = bin_dir / "awww-daemon"
        if not daemon_symlink.exists():
            daemon_symlink.symlink_to(Path(shutil.which("swww-daemon")))
            print(f"  ✓ Created compatibility symlink: {daemon_symlink} -> swww-daemon")
        daemon_bin = shutil.which("swww-daemon")
        if daemon_bin:
            subprocess.run(["sudo", "ln", "-sf", daemon_bin, "/usr/local/bin/awww-daemon"], capture_output=True, check=False)


def setup_xdg_portals():
    """Configure systemd graphical-session target binding and xdg-desktop-portal for Hyprland (required for Flameshot on Fedora)."""
    systemd_user_dir = dot_dir / "systemd/user"
    systemd_user_dir.mkdir(parents=True, exist_ok=True)

    # On Fedora, xdg-desktop-portal.service has Requisite=graphical-session.target,
    # and graphical-session.target has RefuseManualStart=yes.
    # Creating hyprland-session.target with BindsTo=graphical-session.target allows
    # standard Hyprland sessions to cleanly activate graphical-session.target.
    hypr_target = systemd_user_dir / "hyprland-session.target"
    hypr_target_content = """[Unit]
Description=Hyprland compositor session
Documentation=man:systemd.special(7)
BindsTo=graphical-session.target
Wants=graphical-session-pre.target
After=graphical-session-pre.target
"""
    hypr_target.write_text(hypr_target_content)
    print(f"  ✓ Configured systemd user target: {hypr_target}")

    portal_conf_dir = dot_dir / "xdg-desktop-portal"
    portal_conf_dir.mkdir(parents=True, exist_ok=True)
    hypr_portal_conf = portal_conf_dir / "hyprland-portals.conf"
    portal_conf_content = """[preferred]
default=hyprland;gtk
org.freedesktop.impl.portal.Screenshot=hyprland
org.freedesktop.impl.portal.ScreenCast=hyprland
"""
    hypr_portal_conf.write_text(portal_conf_content)
    print(f"  ✓ Configured XDG desktop portal preferences: {hypr_portal_conf}")

    if shutil.which("systemctl"):
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, check=False)
        if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            if shutil.which("dbus-update-activation-environment"):
                subprocess.run([
                    "dbus-update-activation-environment", "--systemd",
                    "WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "XDG_SESSION_DESKTOP"
                ], capture_output=True, check=False)
            subprocess.run(["systemctl", "--user", "start", "hyprland-session.target"], capture_output=True, check=False)
            subprocess.run([
                "systemctl", "--user", "restart",
                "xdg-desktop-portal-hyprland", "xdg-desktop-portal-gtk", "xdg-desktop-portal"
            ], capture_output=True, check=False)
            print("  ✓ Activated graphical-session.target and restarted xdg-desktop-portal services.")


def setup_asura_config():
    """Ensure ~/.config/asura directory exists with default hypr-vars.lua, hypr-user.lua, and config.json with auto colors."""
    config_dir.mkdir(parents=True, exist_ok=True)
    hypr_vars = config_dir / "hypr-vars.lua"
    if not hypr_vars.exists():
        hypr_vars.write_text("return {}\n")
        print(f"  ✓ Created default user variables file: {hypr_vars}")

    hypr_user = config_dir / "hypr-user.lua"
    if not hypr_user.exists():
        hypr_user.write_text("-- Custom user Hyprland configurations\n")
        print(f"  ✓ Created default user config file: {hypr_user}")

    # Default wallpaper path (check both installed shell dir and repo script_dir)
    default_wallpaper_path = asura_dir / "Shell/quickshell/Assets/default_wallpaper.jpg"
    if not default_wallpaper_path.exists():
        fallback_src = script_dir / "Asura-shell/Shell/quickshell/Assets/default_wallpaper.jpg"
        if fallback_src.exists():
            default_wallpaper_path = fallback_src

    # Copy default wallpaper to ~/Pictures/Wallpapers as well for convenient selection
    wallpapers_folder = home / "Pictures/Wallpapers"
    wallpapers_folder.mkdir(parents=True, exist_ok=True)
    dest_wall = wallpapers_folder / "default_wallpaper.jpg"
    if default_wallpaper_path.exists() and not dest_wall.exists():
        try:
            shutil.copy2(default_wallpaper_path, dest_wall)
            print(f"  ✓ Copied default wallpaper to: {dest_wall}")
        except Exception:
            pass

    # Ensure default screenshots and recordings directories exist
    screenshots_dir = home / "Pictures/Screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    flameshot_ini = dot_dir / "flameshot/flameshot.ini"
    if flameshot_ini.exists():
        try:
            ini_text = flameshot_ini.read_text()
            if "/home/lucas/" in ini_text and str(home) != "/home/lucas":
                flameshot_ini.write_text(ini_text.replace("/home/lucas/", f"{home}/"))
        except Exception:
            pass

    recordings_dir = home / "Videos/Recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)

    # Ensure default config.json has colorsAutoGenerate = True, wallpaper, and recordingsFolder
    config_file = config_dir / "config.json"
    import json
    target_default_wall = str(dest_wall) if dest_wall.exists() else str(default_wallpaper_path)
    if not config_file.exists():
        initial_cfg = {
            "colorsAutoGenerate": True,
            "isDarkMode": True,
            "scheme": "tonal-spot",
            "wallpaper": target_default_wall,
            "recordingsFolder": "~/Videos/Recordings"
        }
        config_file.write_text(json.dumps(initial_cfg, indent=2) + "\n")
        print(f"  ✓ Created default Asura config with auto colors enabled: {config_file}")
    else:
        try:
            cfg_data = json.loads(config_file.read_text())
            current_wall = cfg_data.get("wallpaper", "")
            needs_repair = not current_wall
            if current_wall:
                expanded_wall = Path(os.path.expanduser(str(current_wall).replace("file://", "")))
                if not expanded_wall.exists():
                    needs_repair = True
            if needs_repair:
                cfg_data["wallpaper"] = target_default_wall
                config_file.write_text(json.dumps(cfg_data, indent=2) + "\n")
                print(f"  ✓ Configured working default wallpaper in config: {config_file}")
        except Exception:
            pass

    # Set up Python venv for dynamic color generation (materialyoucolor)
    state_venv = home / ".local/state/quickshell/.venv"
    if not (state_venv / "bin/python").exists() and not (state_venv / "bin/python3").exists():
        print("  -> Setting up Python environment for dynamic color generation...")
        try:
            state_venv.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run([sys.executable, "-m", "venv", str(state_venv)], check=False)
            venv_pip = state_venv / "bin/pip"
            subprocess.run([str(venv_pip), "install", "materialyoucolor", "pillow", "numpy"], capture_output=True, check=False)
            print("  ✓ Python environment for dynamic colors initialized.")
        except Exception as e:
            print(f"  Notice: Python venv setup: {e}")

    # Generate initial theme colors from default wallpaper
    switchwall_script = asura_dir / "Shell/quickshell/scripts/colors/switchwall.sh"
    if switchwall_script.exists() and default_wallpaper_path.exists():
        try:
            print("  -> Generating initial theme colors from default wallpaper...")
            subprocess.run([
                "bash", str(switchwall_script),
                "--path", str(default_wallpaper_path),
                "--mode", "dark",
                "--scheme", "tonal-spot"
            ], capture_output=True, check=False)
            print("  ✓ Initial theme colors generated successfully.")
        except Exception as e:
            print(f"  Notice: Initial dynamic color generation deferred: {e}")

    # If running inside an active Wayland / Hyprland session, immediately set wallpaper via awww/swww
    if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        path_with_local = f"{bin_dir}:/usr/local/bin:{os.environ.get('PATH', '')}"
        awww_bin = shutil.which("awww", path=path_with_local) or shutil.which("swww", path=path_with_local)
        daemon_bin = shutil.which("awww-daemon", path=path_with_local) or shutil.which("swww-daemon", path=path_with_local)
        if awww_bin:
            try:
                daemon_running = (
                    subprocess.run(["pgrep", "-x", "awww-daemon"], capture_output=True).returncode == 0
                    or subprocess.run(["pgrep", "-x", "swww-daemon"], capture_output=True).returncode == 0
                )
                if daemon_bin and not daemon_running:
                    subprocess.Popen([daemon_bin], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for _ in range(30):
                    if subprocess.run([awww_bin, "query"], capture_output=True).returncode == 0:
                        break
                    time.sleep(0.1)
                target_wall = wallpapers_folder / "default_wallpaper.jpg"
                if not target_wall.exists():
                    target_wall = default_wallpaper_path
                if target_wall.exists():
                    subprocess.run([awww_bin, "img", str(target_wall), "--transition-type", "wave", "--transition-duration", "1"], capture_output=True, check=False)
                    print(f"  ✓ Applied default wallpaper to active display: {target_wall}")
            except Exception as e:
                print(f"  Notice: Live wallpaper application: {e}")


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

    # Ensure Asura-shell content is actually present (e.g. freshly cloned git repo without --recurse-submodules)
    if not (asura_shell_src / "cli" / "main.py").exists():
        print("\nNotice: Asura-shell submodule is not initialized or empty. Fetching files...")
        if shutil.which("git"):
            try:
                if (script_dir / ".git").exists():
                    subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=script_dir, check=False)

                if not (asura_shell_src / "cli" / "main.py").exists():
                    if asura_shell_src.exists():
                        shutil.rmtree(asura_shell_src)
                    subprocess.run(["git", "clone", "--recurse-submodules", "https://github.com/rlucas25/Asura-shell.git", str(asura_shell_src)], check=False)
            except Exception as e:
                print(f"Warning: Could not fetch Asura-shell submodule: {e}")

    if asura_shell_src.exists() and (asura_shell_src / "cli" / "main.py").exists():
        asura_dir.parent.mkdir(parents=True, exist_ok=True)
        copy_tree(asura_shell_src, asura_dir)
        print(f"Shell files copied to: {asura_dir}")

        # Ensure ~/.local/share/asura is a valid standalone git repository
        git_target = asura_dir / ".git"
        if git_target.is_file():
            git_target.unlink()
        if not (git_target / "config").exists():
            if git_target.is_dir():
                shutil.rmtree(git_target)
            subprocess.run(["git", "-C", str(asura_dir), "init"], check=False)
            subprocess.run(["git", "-C", str(asura_dir), "remote", "add", "origin", "https://github.com/rlucas25/Asura-shell.git"], check=False)
            subprocess.run(["git", "-C", str(asura_dir), "fetch", "origin", "main"], check=False)
            subprocess.run(["git", "-C", str(asura_dir), "reset", "--hard", "origin/main"], check=False)
            subprocess.run(["git", "-C", str(asura_dir), "branch", "--set-upstream-to=origin/main", "main"], check=False)

    # Symlink ~/.config/hypr -> ~/.local/share/asura/hypr
    target_hypr = asura_dir / "hypr"
    if target_hypr.exists():
        if hypr_dot.is_symlink() or hypr_dot.is_file():
            hypr_dot.unlink()
        elif hypr_dot.is_dir():
            shutil.rmtree(hypr_dot)

        hypr_dot.symlink_to(target_hypr, target_is_directory=True)
        print(f"Symlink created: {hypr_dot} -> {target_hypr}")

    # Symlink ~/.config/quickshell -> ~/.local/share/asura/Shell/quickshell
    target_quickshell = asura_dir / "Shell" / "quickshell"
    quickshell_dot = dot_dir / "quickshell"
    if target_quickshell.exists():
        if quickshell_dot.is_symlink() or quickshell_dot.is_file():
            quickshell_dot.unlink()
        elif quickshell_dot.is_dir():
            shutil.rmtree(quickshell_dot)

        quickshell_dot.symlink_to(target_quickshell, target_is_directory=True)
        print(f"Symlink created: {quickshell_dot} -> {target_quickshell}")

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

    # Ensure helper and manager scripts are executable
    services_dir = asura_dir / "Shell/quickshell/Services"
    if services_dir.exists():
        for script_file in services_dir.glob("*.py"):
            try:
                script_file.chmod(0o755)
            except Exception:
                pass

    hypr_scripts_dir = asura_dir / "hypr/scripts"
    if hypr_scripts_dir.exists():
        for script_file in hypr_scripts_dir.glob("*.sh"):
            try:
                script_file.chmod(0o755)
            except Exception:
                pass

    # Setup fonts shipped with Asura-shell
    if not args.skip_fonts:
        setup_fonts()
    else:
        print("Skipping font installation (--skip-fonts specified).")

    # Setup Bibata Modern Ice cursor, Conflux icon themes and adw-gtk3 widget theme
    if not args.skip_themes:
        setup_cursor_and_icons()
        setup_gtk_theme()
    else:
        print("Skipping theme installation (--skip-themes specified).")

    # Setup plugins & environment integrations
    print("\nVerifying plugins and environment integrations...")
    setup_fish_environment()
    setup_xdg_portals()
    setup_asura_config()
    setup_micro_plugins()
    setup_hyprland_plugins()
    setup_default_apps()

    print("\n" + "=" * 56)
    print(f"     ASURA installation completed successfully! (v{__version__})")
    print("=" * 56)


if __name__ == "__main__":
    main()