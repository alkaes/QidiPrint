import UM as UM
import Cura as Cura

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Cura.MachineAction
{
    id: base
    anchors.fill: parent;
    property var selectedPrinter: null

    property var connectedDevice: Cura.MachineManager.printerOutputDevices.length >= 1 ? Cura.MachineManager.printerOutputDevices[0] : null
    property var printerModel: connectedDevice != null ? connectedDevice.activePrinter : null

    property var currentLanguage: UM.Preferences.getValue("general/language")

    Connections
    {
        target: dialog ? dialog : null
        ignoreUnknownSignals: true
        onNextClicked:
        {
            // Connect to the printer if the MachineAction is currently shown
            if(base.parent.wizard == dialog)
            {
                printerConnect();
            }
        }
    }

    function printerConnect()
    {
        if(base.selectedPrinter)
        {
            var printerKey = base.selectedPrinter.name
            if(manager.getStoredKey() != printerKey)
            {
                manager.setKey(printerKey);
                completed();
            }
             manager.changestage();
        }
    }

    function printerDisconnect()
    {
        if(base.selectedPrinter)
        {
            var printerKey = base.selectedPrinter.name
            if(manager.getStoredKey() == printerKey)
            {
                manager.disconnect(printerKey);
                completed();
            }
        }
    }

    Column
    {
        anchors.fill: parent;
        id: discoverUM3Action
        spacing: UM.Theme.getSize("default_margin").height

        SystemPalette { id: palette }
        UM.I18nCatalog { id: catalog; name:"cura" }
        UM.Label
        {
            id: pageTitle
            width: parent.width
            text: catalog.i18nc("@title:window", "Connect to Networked Printer")
            wrapMode: Text.WordWrap
            font.pointSize: 18
        }

        UM.Label
        {
            id: pageDescription
            width: parent.width
            wrapMode: Text.WordWrap
            text: catalog.i18nc("@label", "To print directly to your printer over the network, please make sure your printer is connected to the network using a network cable or by connecting your printer to your WIFI network.\n\nSelect your printer from the list below:")
        }

        Row
        {
            spacing: UM.Theme.getSize("default_lining").width

            Cura.SecondaryButton
            {
                id: addButton
                text: catalog.i18nc("@action:button", "Add");
                onClicked:
                {
                    manualPrinterDialog.showDialog("", "");
                }
            }

            Cura.SecondaryButton
            {
                id: editButton
                text: catalog.i18nc("@action:button", "Edit")
                onClicked:
                {
                    manualPrinterDialog.showDialog(base.selectedPrinter.name, base.selectedPrinter.address);
                }
                enabled : (base.selectedPrinter != null && base.selectedPrinter && base.selectedPrinter.status == "Closed")
            }

            Cura.SecondaryButton
            {
                id: removeButton
                text: catalog.i18nc("@action:button", "Remove")
                onClicked: 
                {
                    manager.removePrinter(base.selectedPrinter.name);
                    base.selectedPrinter = null;
                }
                enabled : (base.selectedPrinter != null && base.selectedPrinter && base.selectedPrinter.status == "Closed")
            }

            Cura.SecondaryButton
            {
                id: rediscoverButton
                text: catalog.i18nc("@action:button", "Refresh")
                onClicked: manager.runDiscovery()
            }
        }

        Row
        {
            id: contentRow
            width: parent.width
            spacing: UM.Theme.getSize("default_margin").width

            Column
            {
                width: Math.round(parent.width * 0.5)
                spacing: UM.Theme.getSize("default_margin").height
                ListView
                {
                    id: listview

                    width: parent.width
                    height: base.height - contentRow.y - discoveryTip.height

                    ScrollBar.vertical: UM.ScrollBar {}
                    clip: true

                    model: manager.foundDevices
                    onModelChanged:
                    {
                        var selectedKey = manager.getStoredKey();
                        for(var i = 0; i < model.length; i++) {
                            if(model[i].name == selectedKey)
                            {
                                currentIndex = i;
                                return
                            }
                        }
                        currentIndex = -1;
                    }
                    currentIndex: -1
                    onCurrentIndexChanged:
                    {
                        base.selectedPrinter = listview.model[currentIndex];
                    }
                    Component.onCompleted:
                    {
                        manager.runDiscovery()
                    }
                    delegate: Rectangle
                    {
                        height: childrenRect.height
                        color: ListView.isCurrentItem ? palette.highlight : index % 2 ? palette.base : palette.alternateBase
                        width: parent.width
                        Label
                        {
                            anchors.left: parent.left
                            anchors.leftMargin: UM.Theme.getSize("default_margin").width
                            anchors.right: parent.right
                            text: listview.model[index].name
                            color: parent.ListView.isCurrentItem ? palette.highlightedText : palette.text
                            elide: Text.ElideRight
                        }

                        MouseArea
                        {
                            anchors.fill: parent;
                            onClicked:
                            {
                                if(!parent.ListView.isCurrentItem)
                                {
                                    parent.ListView.view.currentIndex = index;
                                }
                            }
                        }
                    }
                }
                UM.Label
                {
                    id: discoveryTip
                    anchors.left: parent.left
                    anchors.right: parent.right
                    wrapMode: Text.WordWrap
                    text: catalog.i18nc("@label", "");
                    onLinkActivated: Qt.openUrlExternally(link)
                }                
            }
            Column
            {
                width: Math.round(parent.width * 0.5)
                visible: base.selectedPrinter ? true : false
                // spacing: UM.Theme.getSize("default_margin").height
                UM.Label
                {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: base.selectedPrinter ? base.selectedPrinter.name : ""
                    font: UM.Theme.getFont("large")
                    elide: Text.ElideRight
                }
                Grid
                {
                    visible: base.selectedPrinter != null
                    width: parent.width
                    columns: 2
                    UM.Label
                    {
                        width: Math.round(parent.width * 0.5)
                        wrapMode: Text.WordWrap
                        text: catalog.i18nc("@label", "Firmware version")
                    }
                    UM.Label
                    {
                        width: Math.round(parent.width * 0.5)
                        wrapMode: Text.WordWrap
                        text: base.selectedPrinter ? base.selectedPrinter.firmwareVersion : ""
                    }
                    UM.Label
                    {
                        width: Math.round(parent.width * 0.5)
                        wrapMode: Text.WordWrap
                        text: catalog.i18nc("@label", "Address")
                    }
                    UM.Label
                    {
                        width: Math.round(parent.width * 0.5)
                        wrapMode: Text.WordWrap
                        text: base.selectedPrinter ? base.selectedPrinter.address : ""
                    }
                    UM.Label
                    {
                        width: Math.round(parent.width * 0.5)
                        wrapMode: Text.WordWrap
                        text: catalog.i18nc("@label", "Status")
                    }
                    UM.Label
                    {
                        width: Math.round(parent.width * 0.5)
                        wrapMode: Text.WordWrap
                        text: base.selectedPrinter ? base.selectedPrinter.status : ""
                    }                    
                }
                Row{
                    spacing: 10
                    Cura.PrimaryButton
                    {
                        id: connectbtn
                        text: catalog.i18nc("@action:button", "Connect")
                        enabled: {
                            if (base.selectedPrinter) {
                                if (base.connectedDevice != null) {
                                    if (base.connectedDevice.address  != base.selectedPrinter.address) {
                                        return true
                                    }else{
                                        return false
                                    }
                                }                                
                            }
                            if (base.selectedPrinter && (base.selectedPrinter.status == "Connected" || base.selectedPrinter.status == "Connecting"))
                            {
                                return false
                            }                             
                            return true                    
                        }
                        onClicked: printerConnect()
                    }
                    Cura.SecondaryButton
                    {
                        id: unconnectbtn
                        text: catalog.i18nc("@action:button", "Disconnect")
                        enabled: {
                            if (base.selectedPrinter) {
                                if (base.selectedPrinter.status != "Closed")
                                {
                                    return true
                                }                                  
                                if (base.connectedDevice != null) {                                 
                                    if (base.connectedDevice.address == base.selectedPrinter.address) {
                                        return true
                                    }
                                }                                
                            }
                            return false
                        }
                        onClicked: printerDisconnect()
                    }
                }

            }
        }
    }

    UM.Dialog
    {
        id: manualPrinterDialog
        property alias addressText: addressField.text
        property alias nameFieldText: nameField.text
        property string oldName: ""
        property bool validName: true;

        title: catalog.i18nc("@title:window", "Add Qidi Printer")

        minimumWidth: 420 * screenScaleFactor
        minimumHeight: 230 * screenScaleFactor
        width: minimumWidth
        height: minimumHeight

        signal showDialog(string name, string address)
        onShowDialog:
        {
            nameFieldText = name
            oldName = name
            addressText = address;
            addressField.selectAll();
            addressField.focus = true;
            manualPrinterDialog.show();
            nameField.textChanged();
            addressField.textChanged();
        }

        onAccepted:
        {
            manager.setManualPrinter(oldName, nameFieldText, addressText)
        }

        Column {
            anchors.fill: parent
            spacing: UM.Theme.getSize("default_margin").height

            UM.Label {
                id: displayNameLabel;
                text: catalog.i18nc("@label", "Printer Name");
            }
            Cura.TextField {
                id: nameField;
                text: "";
                maximumLength: 40;
                anchors.left: parent.left;
                anchors.right: parent.right;
                onTextChanged: {
                    manualPrinterDialog.validName = manager.validName(base.selectedPrinter.name, nameField.text);
                }                
            }

            UM.Label
            {
                text: catalog.i18nc("@alabel","Enter the IP address of your printer on the network.")
                width: parent.width
                wrapMode: Text.WordWrap
            }

            Cura.TextField
            {
                id: addressField
                width: parent.width
                maximumLength: 40
                validator: RegularExpressionValidator
                {
                    regularExpression: /^((?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])\.){0,3}(?:[0-1]?[0-9]?[0-9]|2[0-4][0-9]|25[0-5])$/
                }
                onAccepted: btnOk.clicked()
            }
        }

        rightButtons: [
            Cura.PrimaryButton {
                id: btnOk
                text: catalog.i18nc("@action:button", "OK")
                onClicked:
                {
                    manualPrinterDialog.accept()
                    manualPrinterDialog.hide()
                }
                enabled: manualPrinterDialog.addressText.trim() != "" && manualPrinterDialog.validName
            },
            Cura.SecondaryButton {
                text: catalog.i18nc("@action:button","Cancel")
                onClicked:
                {
                    manualPrinterDialog.reject()
                    manualPrinterDialog.hide()
                }
            }            
        ]
    }
}
