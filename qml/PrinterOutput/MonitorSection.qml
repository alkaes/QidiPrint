// Copyright (c) 2017 Ultimaker B.V.
// Cura is released under the terms of the LGPLv3 or higher.

import QtQuick

import UM as UM
import Cura as Cura

Item
{
    id: base
    property string label
    height: childrenRect.height

    Rectangle
    {
        color: UM.Theme.getColor("setting_category")
        width: base.width
        height: UM.Theme.getSize("section").height

        UM.Label
        {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: UM.Theme.getSize("default_margin").width
            text: label
            font: UM.Theme.getFont("default")
            color: UM.Theme.getColor("setting_category_text")
        }
    }
}
