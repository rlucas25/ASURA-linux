import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import qs.Asura
import qs.Modules.Bar.Widgets

Item {
    id: root

    property color textColor: Colors.cfg.text
    property real iconHeight: Math.round(22 * ((typeof Config !== "undefined" && Config.barIconScale !== undefined) ? Config.barIconScale : 1))
    property real iconWidth: Math.round(iconHeight * (710 / 790))
    readonly property string logoPath: {
        if (typeof Quickshell !== "undefined" && typeof Quickshell.shellPath === "function") {
            var p = Quickshell.shellPath("Assets/ASURA-LOGO.svg");
            if (p)
                return p.toString();

        }
        return Qt.resolvedUrl("../../../Assets/ASURA-LOGO.svg").toString();
    }

    implicitWidth: iconWidth
    implicitHeight: iconHeight
    Layout.preferredWidth: implicitWidth
    Layout.preferredHeight: implicitHeight
    Layout.alignment: Qt.AlignVCenter

    Image {
        id: logoImg

        anchors.fill: parent
        source: root.logoPath
        sourceSize.width: 256
        sourceSize.height: 256
        fillMode: Image.PreserveAspectFit
        smooth: true
        mipmap: true
        asynchronous: false
        visible: logoImg.status === Image.Ready
        layer.enabled: visible
        layer.textureSize: Qt.size(256, 256)
        layer.smooth: true
        layer.mipmap: true

        layer.effect: MultiEffect {
            colorization: 1
            colorizationColor: root.textColor
        }

    }

    Text {
        anchors.centerIn: parent
        text: "󰀻"
        color: root.textColor
        visible: logoImg.status !== Image.Ready

        font {
            pixelSize: root.iconHeight
            family: "GeistMono Nerd Font Propo"
        }

    }

}
