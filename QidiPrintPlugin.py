import re, os.path, json, threading, time
from PyQt5.QtCore import QObject, QUrl, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtQml import QQmlComponent, QQmlContext

from UM.Message import Message
from UM.Logger import Logger
from UM.Application import Application

from UM.PluginRegistry import PluginRegistry
from UM.OutputDevice.OutputDevicePlugin import OutputDevicePlugin
from UM.Signal import Signal, signalemitter
from UM.Job import Job
from . import QidiPrintOutputDevice

from threading import Thread, Event
from .QidiConnectionManager import QidiFinderJob, QidiNetDevice

from UM.i18n import i18nCatalog
catalog = i18nCatalog("cura")

from cura.CuraApplication import CuraApplication

@signalemitter
class QidiPrintPlugin(QObject, OutputDevicePlugin):
    addPrinterSignal = Signal()
    removePrinterSignal = Signal()
    printerListChanged = Signal()

    def __init__(self):
        super().__init__()
        self.addPrinterSignal.connect(self.addPrinter)
        self.removePrinterSignal.connect(self.removePrinter)
        self._preferences = Application.getInstance().getPreferences()
        self._preferences.addPreference("QidiPrint/instances", json.dumps({}))
        Application.getInstance().globalContainerStackChanged.connect(self.onglobalContainerStackChanged)

        self._printers = {}
        self._instances = json.loads(self._preferences.getValue("QidiPrint/instances"))
        self._scan_job = QidiFinderJob()
        self._scan_job.IPListChanged.connect(self._discoveredDevices)

    @classmethod
    def getInstance(cls, *args, **kwargs) -> "QidiPrintPlugin":
        return cls.__instance

    def _loadConfiguration(self):
        for name, instance in self._instances.items():
            if 'ip' in instance.keys():
                self.addPrinter(name, instance['ip'])

    def _discoveredDevices(self):
        for device in self._scan_job.devices:
            self.addPrinter(device.name, device.ipaddr)

    def start(self):
        self._loadConfiguration()
        self.onglobalContainerStackChanged()

    def startDiscovery(self):
        if self._scan_job.isRunning() is True:
            return
        self._scan_job.start()

    def stop(self):
        pass

    def getPrinters(self):
        return self._printers

    def disconnect(self, key):
        Logger.log("d", "disconnecting '{}'", key)
        if key in self._printers:
            self._printers[key].close()            

    def onglobalContainerStackChanged(self):
        active_machine = Application.getInstance().getGlobalContainerStack()
        if not active_machine or active_machine.getMetaDataEntry("manufacturer") != "Qidi":
            for key in self._printers:
                self.disconnect(key)
            return

        Logger.log("d", "GlobalContainerStack change %s" % active_machine.getMetaDataEntry("qidi_active_printer"))

        for key in self._printers:
            if key == active_machine.getMetaDataEntry("qidi_active_printer"):
                if not self._printers[key].isConnected():
                    Logger.log("d", "Connecting [%s]..." % key)
                    self._printers[key].connect()
                    self._printers[key].connectionStateChanged.connect(self._onPrinterConnectionStateChanged)
            else:
                Logger.log("d", "Closing connection [%s]..." % key)
                self._printers[key].close()
                if self._printers[key].isConnected():
                    Logger.log("d", "Closing connection [%s]..." % key)
                    self._printers[key].connectionStateChanged.disconnect(self._onPrinterConnectionStateChanged)

    def addPrinter(self, name, address):
        if name in self._printers:  # Is the printer already in the list?
            return

        # check for duplicate addresses
        for key in self._printers:
            if self._printers[key].address == address:
                return

        # add to cura config
        if name not in self._instances.keys():
            self._instances[name] = {"ip": address}
            self._preferences.setValue("QidiPrint/instances", json.dumps(self._instances))

        # Check if printer instance is already in OutputDeviceManager
        printer = self.getOutputDeviceManager().getOutputDevice(name)
        if not printer:
            printer = QidiPrintOutputDevice.QidiPrintOutputDevice(name, address)
        self._printers[name] = printer
        self.printerListChanged.emit()

    def removePrinter(self, name):
        printer = self._printers.pop(name, None)
        if printer:
            printer.close()
            self._onPrinterConnectionStateChanged(name)

        if name in self._instances.keys():
            del self._instances[name]
            self._preferences.setValue("QidiPrint/instances", json.dumps(self._instances))
        self.printerListChanged.emit()

    def _onPrinterConnectionStateChanged(self, key):
        if key not in self._printers:
            return        
        if self._printers[key].isConnected():            
            if not key in self.getOutputDeviceManager().getOutputDeviceIds():
                Logger.log("d", "adding output device: '{}'", key)
                self.getOutputDeviceManager().addOutputDevice(self._printers[key])
        else:
            global_container_stack = CuraApplication.getInstance().getGlobalContainerStack()
            if global_container_stack:
                meta_data = global_container_stack.getMetaData()
                if "qidi_active_printer" in meta_data:
                    localkey = global_container_stack.getMetaDataEntry("qidi_active_printer")
                    if localkey != key and key in self._printers:
                        Logger.log("d", "removing output device: '{}'", key)
                        self.getOutputDeviceManager().removeOutputDevice(key)
