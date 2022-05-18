from UM.i18n import i18nCatalog
from UM.Logger import Logger
from UM.Settings.DefinitionContainer import DefinitionContainer
from UM.Application import Application

from UM.Settings.ContainerRegistry import ContainerRegistry
from cura.MachineAction import MachineAction
from UM.PluginRegistry import PluginRegistry
from cura.CuraApplication import CuraApplication

from PyQt6.QtCore import pyqtSignal, pyqtProperty, pyqtSlot, QUrl, QObject
from PyQt6.QtQml import QQmlComponent, QQmlContext
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtNetwork import QNetworkRequest, QNetworkAccessManager

import os.path
import json
import base64
import time

from PyQt6.QtCore import QTimer

catalog = i18nCatalog("cura")

class QidiMachineConfig(MachineAction):
    printersChanged = pyqtSignal()
    printersTryToConnect = pyqtSignal()

    def __init__(self):
        super().__init__("QidiMachineConfig", "QidiPrint")
        self._qml_url = "qml//QidiMachineConfig.qml"
        ContainerRegistry.getInstance().containerAdded.connect(self._onContainerAdded)

        self._application = CuraApplication.getInstance()
        self._network_plugin = None

        self.__additional_components_context = None
        self.__additional_component = None
        self.__additional_components_view = None

    @pyqtSlot()
    def runDiscovery(self):
        if not self._network_plugin:
            Logger.log("d", "Starting printer discovery.")
            self._network_plugin = self._application.getOutputDeviceManager().getOutputDevicePlugin(self._plugin_id)
            if not self._network_plugin:
                return
            self._network_plugin.printerListChanged.connect(self._onPrinterDiscoveryChanged)
            self.printersChanged.emit()
        self._network_plugin.startDiscovery()

    # Re-filters the list of printers.
    @pyqtSlot()
    def reset(self):
        Logger.log("d", "Reset the list of found printers.")
        self.printersChanged.emit()

    @pyqtSlot(str)
    def removePrinter(self, key):
        if self._network_plugin:
            self._network_plugin.removePrinter(key)

    @pyqtSlot(str, str, str)
    def setManualPrinter(self, oldName, name, address):
        if oldName != "":
            # This manual printer replaces a current manual printer
            self._network_plugin.removePrinter(oldName)
        if address != "":
            self._network_plugin.addPrinter(name, address)

    @pyqtSlot(str, str, result = bool)
    def validName(self, oldName, newName):
        if not newName:
            # empty string isn't allowed
            return False
        if oldName == newName:
            # if name hasn't changed, it is not a duplicate
            return True
        # duplicates not allowed
        return (not newName in self._network_plugin._instances.keys())

    def _onPrinterDiscoveryChanged(self, *args):
        self.printersChanged.emit()

    @pyqtProperty("QVariantList", notify=printersChanged)
    def foundDevices(self):
        if self._network_plugin:
            printers = list(self._network_plugin.getPrinters().values())
            printers.sort(key=lambda k: k.name)
            return printers
        else:
            return []

    @pyqtSlot()
    def changestage(self):
        CuraApplication.getInstance().getController().setActiveStage("MonitorStage")

    @pyqtSlot(str)
    def disconnect(self, key):
        global_container_stack = self._application.getGlobalContainerStack()
        if global_container_stack:
            meta_data = global_container_stack.getMetaData()
            if "qidi_active_printer" in meta_data:
                global_container_stack.setMetaDataEntry("qidi_active_printer", None)
        Logger.log("d", "disconnecting '{}'", key)
        if self._network_plugin:
            self._network_plugin.disconnect(key)

    @pyqtSlot(str)
    def setKey(self, key):
        Logger.log("d", "QidiPrint Plugin the network key of the active machine to %s", key)
        global_container_stack = self._application.getGlobalContainerStack()
        if global_container_stack:
            meta_data = global_container_stack.getMetaData()
            if "qidi_active_printer" in meta_data:
                global_container_stack.setMetaDataEntry("qidi_active_printer", key)
            else:
                Logger.log("d", "QidiPrint Plugin add dataEntry")
                global_container_stack.setMetaDataEntry("qidi_active_printer", key)

        if self._network_plugin:
            # Ensure that the connection states are refreshed.
            Application.getInstance().globalContainerStackChanged.emit()

    @pyqtSlot(result=str)
    def getStoredKey(self):
        global_container_stack = self._application.getGlobalContainerStack()
        if global_container_stack:
            meta_data = global_container_stack.getMetaData()
            if "qidi_active_printer" in meta_data:
                return global_container_stack.getMetaDataEntry("qidi_active_printer")
        return ""

    def _onContainerAdded(self, container):
        # Add this action as a supported action to all machine definitions
        if isinstance(container, DefinitionContainer) and container.getMetaDataEntry("type") == "machine" and container.getMetaDataEntry("manufacturer") == 'Qidi':
            self._application.getMachineActionManager().addSupportedAction(container.getId(), self.getKey())

