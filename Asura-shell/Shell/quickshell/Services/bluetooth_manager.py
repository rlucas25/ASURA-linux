#!/usr/bin/env python3
"""Asura Bluetooth Manager - Reliable BlueZ operations with agent and pairable support."""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def run_cmd(cmd, timeout=15):
    try:
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def get_device_info(mac):
    code, stdout, _ = run_cmd(["bluetoothctl", "info", mac], timeout=5)
    if code != 0:
        return {"exists": False}

    info = {"exists": True, "mac": mac, "paired": False, "trusted": False, "connected": False}
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Paired:"):
            info["paired"] = "yes" in line.lower()
        elif line.startswith("Trusted:"):
            info["trusted"] = "yes" in line.lower()
        elif line.startswith("Connected:"):
            info["connected"] = "yes" in line.lower()
        elif line.startswith("Name:"):
            info["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Icon:"):
            info["icon"] = line.split(":", 1)[1].strip()
    return info


def pair_device(mac):
    mac = mac.strip().upper()

    # 1. Ensure controller is pairable and powered
    run_cmd(["bluetoothctl", "power", "on"], timeout=5)
    run_cmd(["bluetoothctl", "pairable", "on"], timeout=5)

    # 2. If device is not in BlueZ cache, run a brief scan to discover it
    info = get_device_info(mac)
    if not info.get("exists"):
        run_cmd(["bluetoothctl", "--timeout", "4", "scan", "on"], timeout=6)

    # 3. Temporarily pause scanning so radio doesn't drop packets during handshake
    run_cmd(["bluetoothctl", "scan", "off"], timeout=5)
    time.sleep(0.3)

    # 3. Pair with explicit agent (NoInputNoOutput handles headphones, mice, etc.)
    code, stdout, stderr = run_cmd(
        ["bluetoothctl", "--agent", "NoInputNoOutput", "pair", mac],
        timeout=25
    )

    combined = (stdout + " " + stderr).lower()
    pair_success = "successful" in combined or "already exists" in combined

    # Check device info in case bluetoothctl returned non-zero but BlueZ paired it
    info = get_device_info(mac)
    if info.get("paired"):
        pair_success = True

    if not pair_success:
        err_msg = stdout or stderr or "Pairing failed"
        for line in (stdout + "\n" + stderr).splitlines():
            if "failed" in line.lower() or "error" in line.lower():
                err_msg = line.strip()
                break
        return {"success": False, "error": err_msg, "mac": mac}

    # 4. Mark device as trusted (essential so it reconnects automatically)
    run_cmd(["bluetoothctl", "trust", mac], timeout=5)

    # 5. Connect to the device profiles
    time.sleep(0.5)
    conn_code, conn_out, conn_err = run_cmd(["bluetoothctl", "connect", mac], timeout=15)
    conn_combined = (conn_out + " " + conn_err).lower()
    conn_success = "successful" in conn_combined

    final_info = get_device_info(mac)

    return {
        "success": True,
        "paired": final_info.get("paired", True),
        "trusted": final_info.get("trusted", True),
        "connected": final_info.get("connected", conn_success),
        "mac": mac,
        "name": final_info.get("name", "")
    }


def connect_device(mac):
    mac = mac.strip().upper()
    run_cmd(["bluetoothctl", "trust", mac], timeout=5)
    code, stdout, stderr = run_cmd(["bluetoothctl", "connect", mac], timeout=15)
    combined = (stdout + " " + stderr).lower()
    success = "successful" in combined or get_device_info(mac).get("connected", False)

    return {
        "success": success,
        "connected": success,
        "mac": mac,
        "output": stdout or stderr
    }


def disconnect_device(mac):
    mac = mac.strip().upper()
    code, stdout, stderr = run_cmd(["bluetoothctl", "disconnect", mac], timeout=10)
    combined = (stdout + " " + stderr).lower()
    success = "successful" in combined or not get_device_info(mac).get("connected", True)

    return {
        "success": success,
        "disconnected": success,
        "mac": mac
    }


def remove_device(mac):
    mac = mac.strip().upper()
    # 1. Disconnect first
    run_cmd(["bluetoothctl", "disconnect", mac], timeout=5)
    # 2. Untrust
    run_cmd(["bluetoothctl", "untrust", mac], timeout=5)
    # 3. Remove
    code, stdout, stderr = run_cmd(["bluetoothctl", "remove", mac], timeout=10)
    combined = (stdout + " " + stderr).lower()
    success = "successful" in combined or not get_device_info(mac).get("exists", False)

    return {
        "success": success,
        "removed": success,
        "mac": mac
    }


def set_power(state):
    state_str = "on" if state in ("on", "1", "true", True) else "off"
    code, stdout, stderr = run_cmd(["bluetoothctl", "power", state_str], timeout=10)
    if state_str == "on":
        run_cmd(["bluetoothctl", "pairable", "on"], timeout=5)

    return {
        "success": code == 0,
        "power": state_str
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Missing command argument"}))
        sys.exit(1)

    cmd = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else ""

    if cmd == "pair":
        if not arg:
            print(json.dumps({"error": "MAC address required for pair"}))
            sys.exit(1)
        res = pair_device(arg)
        print(json.dumps(res))
    elif cmd == "connect":
        if not arg:
            print(json.dumps({"error": "MAC address required for connect"}))
            sys.exit(1)
        res = connect_device(arg)
        print(json.dumps(res))
    elif cmd == "disconnect":
        if not arg:
            print(json.dumps({"error": "MAC address required for disconnect"}))
            sys.exit(1)
        res = disconnect_device(arg)
        print(json.dumps(res))
    elif cmd == "remove" or cmd == "forget":
        if not arg:
            print(json.dumps({"error": "MAC address required for remove"}))
            sys.exit(1)
        res = remove_device(arg)
        print(json.dumps(res))
    elif cmd == "power":
        res = set_power(arg)
        print(json.dumps(res))
    elif cmd == "info":
        res = get_device_info(arg)
        print(json.dumps(res))
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
