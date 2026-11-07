pragma Singleton

import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Bluetooth

Singleton {
    id: root

    readonly property var adapter: (Bluetooth.defaultAdapter)
        ? Bluetooth.defaultAdapter
        : (Bluetooth.adapters && Bluetooth.adapters.values && Bluetooth.adapters.values.length > 0 
            ? Bluetooth.adapters.values[0] 
            : null)

    readonly property bool bluetoothEnabled: adapter
        ? (adapter.enabled || adapter.powered || (typeof BluetoothAdapterState !== "undefined" && adapter.state === BluetoothAdapterState.Enabled))
        : false

    readonly property var allDevices: {
        var map = {};
        var list = [];
        function add(d) {
            if (d && d.address && !map[d.address]) {
                map[d.address] = true;
                list.push(d);
            }
        }
        if (adapter && adapter.devices && adapter.devices.values) {
            for (var i = 0; i < adapter.devices.values.length; i++) {
                add(adapter.devices.values[i]);
            }
        }
        if (Bluetooth.devices && Bluetooth.devices.values) {
            for (var j = 0; j < Bluetooth.devices.values.length; j++) {
                add(Bluetooth.devices.values[j]);
            }
        }
        return list;
    }

    function getDeviceDisplayName(d) {
        if (!d) return "Device";
        if (d.name && d.name.trim() !== "") return d.name.trim();
        if (d.deviceName && d.deviceName.trim() !== "") return d.deviceName.trim();
        return d.address || "Device";
    }

    readonly property var connectedDevices: allDevices.filter(d => d && (d.connected || (typeof BluetoothDeviceState !== "undefined" && d.state === BluetoothDeviceState.Connected)))
    readonly property var pairedDevices: allDevices.filter(d => d && d.paired && !d.connected && (typeof BluetoothDeviceState === "undefined" || d.state !== BluetoothDeviceState.Connected))
    readonly property var availableDevices: allDevices.filter(d => d && !d.paired && getDeviceDisplayName(d) !== "")

    readonly property bool hasConnectedDevice: connectedDevices.length > 0
    readonly property string activeDeviceName: hasConnectedDevice ? getDeviceDisplayName(connectedDevices[0]) : ""

    property bool manualScanning: false
    readonly property bool isScanning: (adapter && adapter.discovering !== undefined) ? adapter.discovering : manualScanning

    property string connectingAddress: ""
    property string statusMessage: ""

    readonly property string scriptPath: {
        var p = (typeof Quickshell.shellPath === "function")
            ? Quickshell.shellPath("Services/bluetooth_manager.py").toString()
            : (Quickshell.env("HOME") + "/.local/share/asura/Shell/quickshell/Services/bluetooth_manager.py");
        return p.replace(/^file:\/\//, "").replace(/^file:/, "");
    }

    Timer {
        id: statusResetTimer
        interval: 3500
        onTriggered: root.statusMessage = ""
    }

    Timer {
        id: autoStopScanTimer
        interval: 25000
        repeat: false
        onTriggered: {
            if (root.isScanning) {
                root.stopScan();
            }
        }
    }

    function showStatus(msg) {
        root.statusMessage = msg;
        statusResetTimer.restart();
    }

    Process {
        id: scanProc
        command: []
    }

    Process {
        id: stopScanProc
        command: ["bluetoothctl", "scan", "off"]
        running: false
    }

    Process {
        id: actionProc
        property var callback: null

        stdout: StdioCollector {
            onStreamFinished: {
                let parsed = null;
                try {
                    if (this.text && this.text.trim().length > 0) {
                        parsed = JSON.parse(this.text.trim());
                    }
                } catch (e) {
                    console.warn("BluetoothService action parse error:", e, this.text);
                }
                if (actionProc.callback) {
                    actionProc.callback(parsed);
                    actionProc.callback = null;
                }
            }
        }
    }

    function findDevice(mac) {
        if (!mac) return null;
        return allDevices.find(d => d && d.address && d.address.toLowerCase() === mac.toLowerCase()) || null;
    }

    function togglePower() {
        var newState = !bluetoothEnabled;
        if (adapter) {
            if (typeof adapter.enabled !== "undefined") {
                try { adapter.enabled = newState; } catch (e) {}
            }
            if (typeof adapter.powered !== "undefined") {
                try { adapter.powered = newState; } catch (e) {}
            }
        }
        showStatus(newState ? "Enabling Bluetooth..." : "Disabling Bluetooth...");
        actionProc.command = [
            "python3",
            root.scriptPath,
            "power",
            newState ? "on" : "off"
        ];
        actionProc.callback = function(res) {};
        actionProc.running = true;
    }

    function startScan() {
        if (!bluetoothEnabled) return;
        manualScanning = true;

        // 1. Quickshell native D-Bus discovery
        if (adapter && typeof adapter.discovering !== "undefined") {
            try {
                adapter.discovering = true;
            } catch (e) {
                console.warn("BluetoothAdapter set discovering error: " + e);
            }
        }

        // 2. Parallel CLI trigger (with timeout so process terminates cleanly)
        scanProc.running = false;
        scanProc.command = ["bluetoothctl", "--timeout", "25", "scan", "on"];
        scanProc.running = true;

        autoStopScanTimer.restart();
        showStatus("Searching for devices...");
    }

    function stopScan() {
        manualScanning = false;
        autoStopScanTimer.stop();

        // 1. Quickshell native D-Bus discovery stop
        if (adapter && typeof adapter.discovering !== "undefined") {
            try {
                adapter.discovering = false;
            } catch (e) {
                console.warn("BluetoothAdapter stop discovering error: " + e);
            }
        }

        // 2. Stop CLI scan process
        scanProc.running = false;
        stopScanProc.running = true;
        showStatus("Search completed.");
    }

    function toggleScan() {
        if (root.isScanning) {
            root.stopScan();
        } else {
            root.startScan();
        }
    }

    function connectDevice(mac) {
        if (!mac) return;
        connectingAddress = mac;
        showStatus("Connecting to " + mac + "...");

        actionProc.command = [
            "python3",
            root.scriptPath,
            "connect",
            mac
        ];
        actionProc.callback = function(res) {
            connectingAddress = "";
            if (res && res.success) {
                showStatus("Connected!");
            } else {
                showStatus("Connection failed.");
            }
        };
        actionProc.running = true;
    }

    function disconnectDevice(mac) {
        if (!mac) return;
        showStatus("Disconnecting...");

        actionProc.command = [
            "python3",
            root.scriptPath,
            "disconnect",
            mac
        ];
        actionProc.callback = function(res) {
            showStatus("Disconnected.");
        };
        actionProc.running = true;
    }

    function pairDevice(mac) {
        if (!mac) return;
        connectingAddress = mac;
        showStatus("Pairing...");

        // Temporarily pause scan in UI so RF channel stays clear for handshake
        if (root.isScanning) {
            root.stopScan();
        }

        actionProc.command = [
            "python3",
            root.scriptPath,
            "pair",
            mac
        ];
        actionProc.callback = function(res) {
            connectingAddress = "";
            if (res && res.success) {
                if (res.connected) {
                    showStatus("Paired and connected!");
                } else {
                    showStatus("Paired successfully.");
                }
            } else {
                var err = (res && res.error) ? res.error : "Pairing failed.";
                showStatus(err);
            }
        };
        actionProc.running = true;
    }

    function removeDevice(mac) {
        if (!mac) return;
        showStatus("Removing device...");

        actionProc.command = [
            "python3",
            root.scriptPath,
            "remove",
            mac
        ];
        actionProc.callback = function(res) {
            showStatus("Device removed.");
        };
        actionProc.running = true;
    }

    function getDeviceIcon(iconName, name) {
        var lowerIcon = (iconName || "").toLowerCase();
        var lowerName = (name || "").toLowerCase();

        if (lowerIcon.includes("headset") || lowerIcon.includes("headphones") || lowerIcon.includes("audio-headset") || lowerIcon.includes("audio-card") || lowerName.includes("headphone") || lowerName.includes("fone") || lowerName.includes("buds") || lowerName.includes("airpods") || lowerName.includes("earbuds"))
            return "headphones";
        if (lowerIcon.includes("gamepad") || lowerIcon.includes("gaming") || lowerIcon.includes("joystick") || lowerName.includes("controller") || lowerName.includes("xbox") || lowerName.includes("dualshock") || lowerName.includes("dualsense"))
            return "sports_esports";
        if (lowerIcon.includes("keyboard") || lowerName.includes("keyboard") || lowerName.includes("teclado"))
            return "keyboard";
        if (lowerIcon.includes("mouse") || lowerName.includes("mouse"))
            return "mouse";
        if (lowerIcon.includes("phone") || lowerName.includes("phone") || lowerName.includes("iphone") || lowerName.includes("galaxy") || lowerName.includes("celular"))
            return "smartphone";
        if (lowerIcon.includes("watch") || lowerName.includes("watch") || lowerName.includes("relogio") || lowerName.includes("band"))
            return "watch";
        if (lowerIcon.includes("tv") || lowerIcon.includes("video-display") || lowerName.includes("tv") || lowerName.includes("smart tv"))
            return "tv";
        if (lowerIcon.includes("computer") || lowerIcon.includes("laptop") || lowerName.includes("laptop") || lowerName.includes("notebook") || lowerName.includes("desktop") || lowerName.includes("pc"))
            return "laptop";
        if (lowerIcon.includes("speaker") || lowerIcon.includes("audio") || lowerName.includes("speaker") || lowerName.includes("caixa") || lowerName.includes("jbl") || lowerName.includes("som"))
            return "speaker";

        return "bluetooth";
    }
}
