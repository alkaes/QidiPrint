import QtQuick 2.2
import QtQuick.Controls 2.1
import QtQuick.Window 2.1
import QtQuick.Dialogs // For filedialog

import UM 1.5 as UM
import Cura 1.0 as Cura

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

        TextField {
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

        Label {
            visible: !base.validName;
            text: base.validationError;
        }

        CheckBox {
            objectName: "autoPrint"
            id: autoPrint
            checked: true
            text: "Auto Print"
        }           
    }

    rightButtons: [
        Cura.SecondaryButton
            {
            text: catalog.i18nc("@action:button", "Cancel");
            onClicked: base.reject();
        },
        Cura.SecondaryButton
            {
            text: catalog.i18nc("@action:button", "OK");
            onClicked: base.accept();
            enabled: base.validName;
        }
    ]
}
