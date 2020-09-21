import re
import os.path
import json

from PyQt5.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtQml import QQmlComponent, QQmlContext

from UM.Message import Message
from UM.Logger import Logger

from UM.Extension import Extension
from UM.PluginRegistry import PluginRegistry
from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin

from . import QidiPrintOutputDevice
from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

from cura.CuraApplication import CuraApplication


class QidiPrintPlugin(QObject, Extension, OutputDevicePlugin):
    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        Extension.__init__(self)
        OutputDevicePlugin.__init__(self)
        self.addMenuItem(catalog.i18n("QidiPrint Connections"), self.showSettingsDialog)
        self._dialogs = {}
        self._dialogView = None

        CuraApplication.getInstance().getPreferences().addPreference("QidiPrint/instances", json.dumps({}))
        self._instances = json.loads(CuraApplication.getInstance().getPreferences().getValue("QidiPrint/instances"))

    def start(self):
        manager = self.getOutputDeviceManager()
        for name, instance in self._instances.items():
            manager.addOutputDevice(QidiPrintOutputDevice.QidiPrintOutputDevice(name, instance["url"]))

    def stop(self):
        manager = self.getOutputDeviceManager()
        for name in self._instances.keys():
            manager.removeOutputDevice(name)

    def _createDialog(self, qml):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), qml)
        dialog = CuraApplication.getInstance().createQmlComponent(path, {"manager": self})
        return dialog

    def _showDialog(self, qml):
        if not qml in self._dialogs:
            self._dialogs[qml] = self._createDialog(qml)
        self._dialogs[qml].show()

    def showSettingsDialog(self):
        self._showDialog("QidiPrintPlugin.qml")

    serverListChanged = pyqtSignal()
    @pyqtProperty("QVariantList", notify=serverListChanged)
    def serverList(self):
        return list(self._instances.keys())

    @pyqtSlot(str, result=str)
    def instanceUrl(self, name):
        if name in self._instances.keys():
            return self._instances[name]["url"]
        return None

    @pyqtSlot(str, str, str)
    def saveInstance(self, oldName, name, url):
        if oldName:
            # this is a edit operation, delete the old instance before saving the new one
            self.removeInstance(oldName)

        self._instances[name] = {
            "url": url
        }
        manager = self.getOutputDeviceManager()
        manager.addOutputDevice(QidiPrintOutputDevice.QidiPrintOutputDevice(name, url))
        CuraApplication.getInstance().getPreferences().setValue("QidiPrint/instances", json.dumps(self._instances))
        self.serverListChanged.emit()
        Logger.log("d", "Instance saved: " + name)

    @pyqtSlot(str)
    def removeInstance(self, name):
        manager = self.getOutputDeviceManager()
        manager.removeOutputDevice(name)
        del self._instances[name]
        CuraApplication.getInstance().getPreferences().setValue("QidiPrint/instances", json.dumps(self._instances))
        self.serverListChanged.emit()
        Logger.log("d", "Instance removed: " + name)

    @pyqtSlot(str, str, result = bool)
    def validName(self, oldName, newName):
        if not newName:
            # empty string isn't allowed
            return False
        if oldName == newName:
            # if name hasn't changed, it is not a duplicate
            return True

        # duplicates not allowed
        return (not newName in self._instances.keys())

    @pyqtSlot(str, str, result = bool)
    def validUrl(self, oldName, newUrl):
        if not re.match('(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[1-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])\.(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])', newUrl):
            return False

        return True
