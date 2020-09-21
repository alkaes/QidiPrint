import QtQuick 2.4
import QtQuick.Controls 1.4
import QtQuick.Controls.Styles 1.1
import QtQuick.Layouts 1.1
import QtQuick.Dialogs 1.2
import QtQuick.Window 2.1

import UM 1.2 as UM
import Cura 1.0 as Cura

UM.Dialog
{
    id: dialog;

    title: catalog.i18nc("@title:window", "QIDI Printers");

    minimumWidth: screenScaleFactor * 650;
    minimumHeight: screenScaleFactor * 300;

    property string currentName: (instanceList.currentIndex != -1 ? instanceList.currentItem.name : "");
    property int defaultVerticalMargin: UM.Theme.getSize("default_margin").height;
    property int defaultHorizontalMargin: UM.Theme.getSize("default_margin").width;

    Row {
        id: buttons;

        width: childrenRect.width;
        height: childrenRect.height;

        Button {
            id: addButton;
            text: catalog.i18nc("@action:button", "Add");
            iconName: "list-add";
            onClicked: {
                instanceDialog.oldName = "";
                instanceDialog.name = "My Printer";
                instanceDialog.url = "192.168.10.205";
                instanceDialog.open();
                nameField.textChanged();
                urlField.textChanged();
            }
        }
        Button {
            id: removeButton;
            text: catalog.i18nc("@action:button", "Remove");
            iconName: "list-remove";
            enabled: (instanceList.currentIndex != -1);
            onClicked: {
                var name = dialog.currentName;
                instanceList.currentIndex = -1;
                manager.removeInstance(name);
            }
        }
        Button {
            id: editButton;
            text: catalog.i18nc("@action:button", "Edit");
            iconName: "edit-rename";
            enabled: (instanceList.currentIndex != -1);
            onClicked: {
                instanceDialog.oldName = dialog.currentName;
                instanceDialog.name = dialog.currentName;
                instanceDialog.url = manager.instanceUrl(dialog.currentName);
                instanceDialog.open();
                nameField.textChanged();
            }
        }
    }

    Item {
        UM.I18nCatalog { id: catalog; name: "cura"; }
        SystemPalette { id: palette }

        anchors {
            top: buttons.bottom;
            topMargin: parent.defaultVerticalMargin;
            left: parent.left;
            right: parent.right;
            bottom: parent.bottom;
        }

        ScrollView {
            id: instanceScroll;

            anchors {
                top: parent.top;
                topMargin: dialog.defaultVerticalMargin;
                bottom: parent.bottom;
                left: parent.left;
            }
            width: parent.width * 0.35;

            ListView {
                id: instanceList;

                anchors {
                    top: parent.top;
                    left: parent.left;
                }

                model: manager.serverList;

                delegate: Rectangle {
                    width: parent.width;
                    height: childrenRect.height;
                    color: ListView.isCurrentItem ? palette.highlight : index % 2 ? palette.base : palette.alternateBase;
                    property string name: modelData.toString();

                    Text {
                        text: name;
                    }

                    MouseArea {
                        anchors.fill: parent;
                        onClicked: {
                            if(!parent.ListView.isCurrentItem) {
                                parent.ListView.view.currentIndex = index;
                            }
                        }
                    }
                }
            }
        }

        Item {
            id: detailsPane;

            anchors {
                left: instanceScroll.right;
                leftMargin: dialog.defaultHorizontalMargin;
                top: parent.top;
                bottom: parent.bottom;
                right: parent.right;
            }

            ColumnLayout {
                anchors.margins: dialog.defaultVerticalMargin;

                Label {
                    text: dialog.currentName;
                    font: UM.Theme.getFont("large")
                    width: parent.width
                    elide: Text.ElideRight
                }

                Label { text: catalog.i18nc("@label", "Printer IP Address"); }
                Text { font.bold: true; text: manager.instanceUrl(dialog.currentName); }
            }

            visible: (instanceList.currentIndex != -1);
        }
    }

    Item {
        UM.Dialog {
            id: instanceDialog;

            property string oldName: " "; // oldName = "" for add
            property alias name: nameField.text;
            property alias url: urlField.text;

            property bool validName: true;
            property bool validUrl: true;

            minimumWidth: screenScaleFactor * 420;
            minimumHeight: screenScaleFactor * 330;

            onAccepted: {
                manager.saveInstance(oldName, nameField.text, urlField.text);
                var index = instanceList.currentIndex;
                instanceList.currentIndex = -1;
                instanceList.currentIndexChanged();
                instanceList.currentIndex = index;
                instanceList.currentIndexChanged();
            }

            title: (oldName == "") ? catalog.i18nc("@window:title", "Add Qidi Printer") : catalog.i18nc("@window:title", "Edit Qidi Printer");

            Column {
                anchors.fill: parent;

                Label {
                    id: displayNameLabel;
                    text: catalog.i18nc("@label", "Printer Name");
                }
                TextField {
                    id: nameField;
                    text: "";
                    maximumLength: 40;
                    anchors.left: parent.left;
                    anchors.right: parent.right;
                    onTextChanged: {
                        instanceDialog.validName = manager.validName(instanceDialog.oldName, nameField.text);
                    }
                }

                Item { width: parent.width; height: displayNameLabel.height; }
                Label { text: catalog.i18nc("@label", "Printer IP Address"); }
                TextField {
                    id: urlField;
                    text: "";
                    maximumLength: 1024;
                    anchors.left: parent.left;
                    anchors.right: parent.right;
                    onTextChanged: {
                        instanceDialog.validUrl = manager.validUrl(instanceDialog.oldName, urlField.text);
                    }
                }

                Item { width: parent.width; height: displayNameLabel.height; }
                Label {
                    visible: !instanceDialog.validName;
                    text: catalog.i18nc("@error", "That instance name already exists.");
                }
                Item { width: parent.width; height: displayNameLabel.height; }
                Label {
                    visible: !instanceDialog.validUrl;
                    text: catalog.i18nc("@error", "IP not valid. Example: 192.168.10.205");
                }
            }

            rightButtons: [
                Button {
                    text: catalog.i18nc("@action:button", "Cancel");
                    onClicked: instanceDialog.reject();
                },
                Button {
                    id: okButton;
                    text: catalog.i18nc("@action:button", "Ok");
                    onClicked: instanceDialog.accept();
                    enabled: instanceDialog.validName && instanceDialog.validUrl;
                    isDefault: true;
                }
            ]
        }
    }
}
