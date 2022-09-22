// Copyright (c) 2018 Ultimaker B.V.
// Cura is released under the terms of the LGPLv3 or higher.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import UM as UM
import Cura as Cura

import "."

Component
{
    Item
    {
        UM.I18nCatalog { id: catalog; name: "cura"}
        property var connectedDevice: Cura.MachineManager.printerOutputDevices.length >= 1 ? Cura.MachineManager.printerOutputDevices[0] : null
        property var activePrinter: connectedDevice != null ? connectedDevice.activePrinter : null        

        Rectangle
        {

            color: UM.Theme.getColor("main_background")

            anchors.right: parent.right
            width: parent.width * 0.3
            anchors.top: parent.top
            anchors.bottom: parent.bottom

            UM.Label
            {
                font: UM.Theme.getFont("large_bold")
                color: UM.Theme.getColor("text")
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: UM.Theme.getSize("default_margin").width
                text: catalog.i18nc("@info:status", "The printer is not connected.")
                visible:
                {
                     if(activePrinter != null)
                    {
                        return activePrinter.state == "offline"
                    }
                    return true
                }                
            }

            PrintMonitor
            {
                visible:
                {
                    if(activePrinter != null)
                    {
                        return activePrinter.state != "offline"
                    }
                    return false                
                    
                }                
                anchors.fill: parent
            }

            Rectangle
            {
                id: footerSeparator
                width: parent.width
                height: UM.Theme.getSize("wide_lining").height
                color: UM.Theme.getColor("wide_lining")
                anchors.bottom: monitorButton.top
                anchors.bottomMargin: UM.Theme.getSize("thick_margin").height
            }

            // MonitorButton is actually the bottom footer panel.
            Cura.MonitorButton
            {
                id: monitorButton
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
            }
        }
    }
}