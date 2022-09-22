import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import QtQuick.Window

import UM as UM
import Cura as Cura

UM.Dialog
{
    id: base;
    property string object: "";

    property alias newName: nameField.text;
    property bool validName: true;
    property string validationError;
    property string dialogTitle: "Upload Filename";

    title: dialogTitle;

    minimumWidth: screenScaleFactor * 400
    minimumHeight: screenScaleFactor * 120

    property variant catalog: UM.I18nCatalog { name: "uranium"; }

    signal textChanged(string text);
    signal selectText()
    onSelectText: {
        nameField.selectAll();
        nameField.focus = true;
    }

    Column {
        anchors.fill: parent;

        Cura.TextField {
            objectName: "nameField";
            id: nameField;
            width: parent.width;
            text: base.object;
            maximumLength: 100;
            onTextChanged: base.textChanged(text);
            Keys.onReturnPressed: { if (base.validName) base.accept(); }
            Keys.onEnterPressed: { if (base.validName) base.accept(); }
            Keys.onEscapePressed: base.reject();
        }

        UM.Label {
            visible: !base.validName;
            text: base.validationError;
        }

        UM.CheckBox {
            objectName: "autoPrint"
            id: autoPrint
            checked: true
            text: "Auto Print"
        }           
    }

    rightButtons: [
        Cura.SecondaryButton {
            text: catalog.i18nc("@action:button", "Cancel");
            onClicked: base.reject();
        },
        Cura.PrimaryButton {
            text: catalog.i18nc("@action:button", "OK");
            onClicked: base.accept();
            enabled: base.validName;
        }
    ]
}
