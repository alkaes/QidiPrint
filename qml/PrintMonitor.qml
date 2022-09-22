import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import UM as UM
import Cura as Cura

import "PrinterOutput"


Item
{
    id: base
    UM.I18nCatalog { id: catalog; name: "cura"}

    function showTooltip(item, position, text)
    {
        tooltip.text = text;
        position = item.mapToItem(base, position.x - UM.Theme.getSize("default_arrow").width, position.y);
        tooltip.show(position);
    }

    function hideTooltip()
    {
        tooltip.hide();
    }

    function strPadLeft(string, pad, length) {
        return (new Array(length + 1).join(pad) + string).slice(-length);
    }

    function getPrettyTime(time)
    {
        var hours = Math.floor(time / 3600)
        time -= hours * 3600
        var minutes = Math.floor(time / 60);
        time -= minutes * 60
        var seconds = Math.floor(time);

        var finalTime = strPadLeft(hours, "0", 2) + ":" + strPadLeft(minutes, "0", 2) + ":" + strPadLeft(seconds, "0", 2);
        return finalTime;
    }

    property var connectedDevice: Cura.MachineManager.printerOutputDevices.length >= 1 ? Cura.MachineManager.printerOutputDevices[0] : null
    property var activePrinter: connectedDevice != null ? connectedDevice.activePrinter : null
    property var activePrintJob: activePrinter != null ? activePrinter.activePrintJob: null

    Column
    {
        id: printMonitor

        anchors.fill: parent

        property var extrudersModel: CuraApplication.getExtrudersModel()

        OutputDeviceHeader
        {
            outputDevice: connectedDevice
        }

        HeatedBedBox
        {
            visible:
            {
                if(activePrinter != null && activePrinter.bedTemperature != -1)
                {
                    return true
                }
                return false
            }
            printerModel: activePrinter
        }

        Rectangle
        {
            color: UM.Theme.getColor("wide_lining")
            width: parent.width
            height: UM.Theme.getSize("thick_lining").width
        }

        Rectangle
        {
            color: UM.Theme.getColor("wide_lining")
            width: parent.width
            height: childrenRect.height

            Flow
            {
                id: extrudersGrid
                spacing: UM.Theme.getSize("thick_lining").width
                width: parent.width

                Repeater
                {
                    id: extrudersRepeater
                    model: activePrinter != null ? activePrinter.extruders : null

                    ExtruderBox
                    {
                        color: UM.Theme.getColor("main_background")
                        width: index == machineExtruderCount.properties.value - 1 && index % 2 == 0 ? extrudersGrid.width : Math.round(extrudersGrid.width / 2 - UM.Theme.getSize("thick_lining").width / 2)
                        extruderModel: modelData
                    }
                }
            }
        }

        UM.SettingPropertyProvider
        {
            id: bedTemperature
            containerStack: Cura.MachineManager.activeMachine
            key: "material_bed_temperature"
            watchedProperties: ["value", "minimum_value", "maximum_value", "resolve"]
            storeIndex: 0

            property var resolve: Cura.MachineManager.activeStack != Cura.MachineManager.activeMachine ? properties.resolve : "None"
        }

        UM.SettingPropertyProvider
        {
            id: machineExtruderCount
            containerStack: Cura.MachineManager.activeMachine
            key: "machine_extruder_count"
            watchedProperties: ["value"]
        }

        ManualPrinterControl
        {
            printerModel: activePrinter
            visible: activePrinter != null ? activePrinter.canControlManually : false
        }


        MonitorSection
        {
            label: catalog.i18nc("@label", "Active print")
            width: base.width
            visible: activePrintJob != null
        }


        MonitorItem
        {
            label: catalog.i18nc("@label", "Job Name")
            value: activePrintJob != null ? activePrintJob.name : ""
            width: base.width
            visible: activePrintJob != null
        }

        MonitorItem
        {
            label: catalog.i18nc("@label", "Elapsed Time")
            value: activePrintJob != null ? getPrettyTime(activePrintJob.timeElapsed) : ""
            width: base.width
            visible: activePrintJob != null
        }

        MonitorItem
        {
            label: catalog.i18nc("@label", "Estimated time left")
            value: activePrintJob != null ? getPrettyTime(activePrintJob.timeTotal - activePrintJob.timeElapsed) : ""
            visible:
            {
                return false;
                if(activePrintJob == null)
                {
                    return false
                }

                return (activePrintJob.state == "printing" ||
                        activePrintJob.state == "resuming" ||
                        activePrintJob.state == "pausing" ||
                        activePrintJob.state == "paused")
            }
            width: base.width
        }
    }

    Cura.PrintSetupTooltip
    {
        id: tooltip
    }
}