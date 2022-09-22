import QtQuick

import UM as UM
import Cura as Cura

Item
{
    property string label: ""
    property string value: ""
    height: childrenRect.height

    property var connectedPrinter: Cura.MachineManager.printerOutputDevices.length >= 1 ? Cura.MachineManager.printerOutputDevices[0] : null

    Row
    {
        height: UM.Theme.getSize("setting_control").height
        width: Math.floor(base.width - 2 * UM.Theme.getSize("default_margin").width)
        anchors.left: parent.left
        anchors.leftMargin: UM.Theme.getSize("default_margin").width

        UM.Label
        {
            width: Math.floor(parent.width * 0.4)
            anchors.verticalCenter: parent.verticalCenter
            text: label
            color: connectedPrinter != null && connectedPrinter.acceptsCommands ? UM.Theme.getColor("setting_control_text") : UM.Theme.getColor("setting_control_disabled_text")
            elide: Text.ElideRight
        }
        UM.Label
        {
            width: Math.floor(parent.width * 0.6)
            anchors.verticalCenter: parent.verticalCenter
            text: value
            color: connectedPrinter != null && connectedPrinter.acceptsCommands ? UM.Theme.getColor("setting_control_text") : UM.Theme.getColor("setting_control_disabled_text")
            elide: Text.ElideRight
        }
    }
}