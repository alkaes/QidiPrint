from enum import Enum
import os.path
from time import time, sleep

import subprocess, re, threading, platform, struct, traceback, sys, base64, json, urllib
from typing import cast, Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QFile, QUrl, QObject, QCoreApplication, QByteArray, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtQml import QQmlComponent, QQmlContext
from timeit import default_timer as Timer

from cura.CuraApplication import CuraApplication
from cura.PrinterOutput.PrinterOutputDevice import PrinterOutputDevice, ConnectionState, ConnectionType
from cura.PrinterOutput.Models.PrinterOutputModel import PrinterOutputModel
from cura.PrinterOutput.Models.PrintJobOutputModel import PrintJobOutputModel
from cura.PrinterOutput.GenericOutputController import GenericOutputController

from UM.Resources import Resources
import UM.Qt.ListModel

from UM.Application import Application
from UM.Logger import Logger
from UM.Message import Message
from UM.Mesh.MeshWriter import MeshWriter
from UM.PluginRegistry import PluginRegistry
from UM.OutputDevice.OutputDevice import OutputDevice
from UM.OutputDevice import OutputDeviceError
from UM.Platform import Platform
from UM.Signal import signalemitter
from UM.Job import Job

from UM.i18n import i18nCatalog
from .ChituCodeWriter import ChituCodeWriter

from .QidiConnectionManager import QidiConnectionManager, QidiResult

from queue import Queue
from threading import Thread, Event
from time import time
from typing import Union, Optional, List, cast, TYPE_CHECKING

catalog = i18nCatalog("cura")


class OutputStage(Enum):
    ready = 0
    writing = 1


class QidiPrintOutputDevice(PrinterOutputDevice):
    printerStatusChanged = pyqtSignal()

    def __init__(self, name, address):
        super().__init__(name, connection_type=ConnectionType.NetworkConnection)
        self.setShortDescription(catalog.i18nc("@action:button Preceded by 'Ready to'.", "Send to " + name))
        self.setDescription(catalog.i18nc("@info:tooltip",  "Send to " + name))
        self.setConnectionText(catalog.i18nc("@info:status", "Connected via Network"))
        self.setName(name)
        self.setIconName("print")
        self._properties = {}
        self._address = address
        self._PluginName = 'QIDI Print'
        self.setPriority(3)

        self._application = CuraApplication.getInstance()
        self._preferences = Application.getInstance().getPreferences()
        self._preferences.addPreference("QidiPrint/autoprint", False)
        self._autoPrint = self._preferences.getValue("QidiPrint/autoprint")        

        self._update_timer.setInterval(1000)

        self._output_controller = GenericOutputController(self)
        self._output_controller.setCanUpdateFirmware(False)

        # Set when print is started in order to check running time.
        self._print_start_time = None  # type: Optional[float]
        self._print_estimated_time = None  # type: Optional[int]

        self._accepts_commands = True   # from PrinterOutputDevice

        self._monitor_view_qml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qml', 'MonitorItem.qml')
        self._localTempGcode = Resources.getStoragePath(Resources.Resources, 'data.gcode')

        self._qidi = QidiConnectionManager(self._address, self._localTempGcode, False)
        self._qidi.progressChanged.connect(self._update_progress)
        self._qidi.conectionStateChanged.connect(self._conectionStateChanged)
        self._qidi.updateDone.connect(self._update_status)

        self._stage = OutputStage.ready

        Logger.log("d", self._name + " | New QidiPrintOutputDevice created")
        Logger.log("d", self._name + " | IP: " + self._address)

        if hasattr(self, '_message'):
            self._message.hide()
        self._message = None

    def _update_progress(self, progress):
        if self._message:
            self._message.setProgress(int(progress))
        self.writeProgress.emit(self, progress)

    def _conectionStateChanged(self, new_state):
        if new_state == True:
            container_stack = CuraApplication.getInstance().getGlobalContainerStack()
            num_extruders = container_stack.getProperty("machine_extruder_count", "value")
            # Ensure that a printer is created.
            printer = PrinterOutputModel(output_controller=self._output_controller, number_of_extruders=num_extruders, firmware_version=self.firmwareVersion)
            printer.updateName(container_stack.getName())
            self._printers = [printer]
            self.setConnectionState(ConnectionState.Connected)
            self.printersChanged.emit()
        else:
            #self._printers = None
            self.setConnectionState(ConnectionState.Connecting)
            if self.printers[0]:
                self.printers[0].updateState("offline")

    def _update(self):
        if self._qidi._connected == False:
            Thread(target=self._qidi.connect, daemon=True, name="Qidi Connect").start()
            self.printerStatusChanged.emit()
            return
        if self.connectionState != ConnectionState.Connected:
            self.setConnectionState(ConnectionState.Connected)
        Thread(target=self._qidi.update, daemon=True, name="Qidi Update").start()

    def close(self):
        super().close()
        if self._message:
            self._message.hide()
        self.printerStatusChanged.emit()

    def pausePrint(self):
        self.sendCommand("M25")

    def resumePrint(self):
        self.sendCommand("M24")

    def cancelPrint(self):
        self._cancelPrint = True
        self.sendCommand("M33")        

    def _update_status(self):
        printer = self.printers[0]
        status = self._qidi._status
        if "bed_nowtemp" in status:
            printer.updateBedTemperature(int(status["bed_nowtemp"]))
        if "bed_targettemp" in status:
            printer.updateTargetBedTemperature(int(status["bed_targettemp"]))

        extruder = printer.extruders[0]
        if "e1_nowtemp" in status:
            extruder.updateHotendTemperature(int(status["e1_nowtemp"]))
        if "e1_targettemp" in status:
            extruder.updateTargetHotendTemperature(int(status["e1_targettemp"]))

        if len(printer.extruders) > 1:
            extruder = printer.extruders[1]
            if "e2_nowtemp" in status:
                extruder.updateHotendTemperature(int(status["e2_nowtemp"]))
            if "e2_targettemp" in status:
                extruder.updateTargetHotendTemperature(int(status["e2_targettemp"]))

        if self._qidi._isPrinting:
            if printer.activePrintJob is None:
                print_job = PrintJobOutputModel(output_controller=self._output_controller)
                printer.updateActivePrintJob(print_job)
            else:
                print_job = printer.activePrintJob
            elapsed = self._qidi._printing_time
            print_job.updateTimeElapsed(int(self._qidi._printing_time))
            print_job.updateName(self._qidi._printing_filename)

            if self._qidi._print_total > 0:
                progress = float(self._qidi._print_now) / float(self._qidi._print_total)
                if progress > 0:
                    print_job.updateTimeTotal(int(self._qidi._printing_time / progress))
            if self._qidi._isIdle:
                if self._cancelPrint:
                    job_state = 'aborting'
                else:
                    job_state = 'paused'
            else:
                job_state = 'printing'
            print_job.updateState(job_state)
        else:
            if printer.activePrintJob:
                printer.updateActivePrintJob(None)
            job_state = 'idle'
            self._cancelPrint = False
            print_job = None

        printer.updateState(job_state)
        self.printerStatusChanged.emit()

    def requestWrite(self, node, fileName=None, *args, **kwargs):
        if self._stage != OutputStage.ready or self._qidi._isPrinting:
            Message(catalog.i18nc('@info:status', 'Cannot Print, printer is busy'), title=catalog.i18nc("@info:title", "BUSY")).show()
            raise OutputDeviceError.DeviceBusyError()

        # Make sure post-processing plugin are run on the gcode
        self.writeStarted.emit(self)
        if fileName:
            fileName = os.path.splitext(fileName)[0]
        else:
            fileName = "%s" % Application.getInstance().getPrintInformation().jobName
        self.targetSendFileName = fileName

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qml', 'UploadFilename.qml')
        self._dialog = CuraApplication.getInstance().createQmlComponent(path, {"manager": self})
        self._dialog.textChanged.connect(self.onFilenameChanged)
        self._dialog.accepted.connect(self.onFilenameAccepted)
        self._dialog.show()
        self._dialog.findChild(QObject, "autoPrint").setProperty('checked', self._autoPrint)
        self._dialog.findChild(QObject, "nameField").setProperty('text', self.targetSendFileName)
        self._dialog.findChild(QObject, "nameField").select(0, len(self.targetSendFileName))
        self._dialog.findChild(QObject, "nameField").setProperty('focus', True)        

    def onFilenameChanged(self):
        fileName = self._dialog.findChild(QObject, "nameField").property('text').strip()
        forbidden_characters = "\"'´`<>()[]?*\,;:&%#$!"
        for forbidden_character in forbidden_characters:
            if forbidden_character in fileName:
                self._dialog.setProperty('validName', False)
                self._dialog.setProperty(
                    'validationError', 'Filename cannot contain {}'.format(forbidden_characters))
                return
        if fileName == '.' or fileName == '..':
            self._dialog.setProperty('validName', False)
            self._dialog.setProperty(
                'validationError', 'Filename cannot be "." or ".."')
            return
        self._dialog.setProperty('validName', len(fileName) > 0)
        self._dialog.setProperty('validationError', 'Filename too short')

    def startSendingThread(self):
        Logger.log('i', '=============QIDI SEND BEGIN============')
        self._errorMsg = ''

        self._qidi._abort = False
        self._stage = OutputStage.writing

        res = self._qidi.sendfile(self.targetSendFileName)
        if self._message:
            self._message.hide()
            self._message = None  # type:Optional[Message]
        self.writeFinished.emit(self)

        self._stage = OutputStage.ready

        if res == QidiResult.SUCCES:
            if self._autoPrint is False:
                self._message = Message(catalog.i18nc("@info:status", "Do you wish to print now?"), title=catalog.i18nc("@label", "SUCCESS"))
                self._message.addAction("PRINT", catalog.i18nc("@action:button", "YES"), None, "")
                self._message.addAction("NO", catalog.i18nc("@action:button", "NO"), None, "")
                self._message.actionTriggered.connect(self._onActionTriggered)
                self._message.setProgress(None)
                self._message.show()
            else:
                self._onActionTriggered(self._message, "PRINT")
            self.writeSuccess.emit(self)
            self._stage = OutputStage.ready
            return

        self.writeError.emit(self)
        if res == QidiResult.ABORTED:
            Message(catalog.i18nc('@info:status', 'Upload Canceled'),
                    title=catalog.i18nc("@info:title", "ABORTED")).show()
            return

        result_msg = "Unknown Error!!!"
        if self._result == QidiResult.TIMEOUT:
            result_msg = 'Connection timeout'
        elif self._result == QidiResult.WRITE_ERROR:
            self.writeError.emit(self)
            result_msg = self._errorMsg
            if 'create file' in self._errorMsg:
                m = Message(catalog.i18nc('@info:status', ' Write error, please check that the SD card /U disk has been inserted'), lifetime=0)
                m.show()
        elif self._result == QidiResult.FILE_EMPTY:
            self.writeError.emit(self)
            result_msg = 'File empty'
        elif self._result == QidiResult.FILE_NOT_OPEN:
            self.writeError.emit(self)
            result_msg = "Cannot Open File"

        self._message = Message(catalog.i18nc("@info:status", result_msg), title=catalog.i18nc("@label", "FAILURE"))
        self._message.show()
        Logger.log('e', result_msg)

    def updateChamberFan(self):        
        global_container_stack = self._application.getGlobalContainerStack()
        if not global_container_stack:
            return

        cooling_chamber = global_container_stack.getProperty("cooling_chamber", "value")
        if cooling_chamber == False:
            return

        cooling_chamber_at_layer = global_container_stack.getProperty("cooling_chamber_at_layer", "value")

        scene = self._application.getController().getScene()
        gcode_dict = getattr(scene, "gcode_dict", {})
        if not gcode_dict:
            return

        data = gcode_dict[0]
        for layer in data:
            lines = layer.split("\n")
            for line in lines:
                if ";LAYER:" in line:
                    index = data.index(layer)
                    current_layer = int(line.split(":")[1])
                    if current_layer == cooling_chamber_at_layer:
                        layer = "M106 T-2 ;Enable chamber loop\n" + layer
                        data[index] = layer
                        data[-1] = "M107 T-2 ;Disable chamber loop\n" + data[-1]
                        setattr(scene, "gcode_dict", gcode_dict)
                        return


    def onFilenameAccepted(self):
        self.targetSendFileName = self._dialog.findChild(QObject, "nameField").property('text').strip()
        autoprint = self._dialog.findChild(QObject, "autoPrint").property('checked')
        if autoprint != self._autoPrint:
            self._autoPrint = autoprint
            self._preferences.setValue("QidiPrint/autoprint", self._autoPrint)
        Logger.log("d", self._name + " | Filename set to: " + self.targetSendFileName)
        self._dialog.deleteLater()        
        self.updateChamberFan()
        success = False
        with open(self._localTempGcode, 'w+', buffering=1) as fp:
            if fp:
                writer = ChituCodeWriter()
                success = writer.write(fp, None, MeshWriter.OutputMode.TextMode)

        if success:
            self._message = Message(
                catalog.i18nc("@info:status", "Uploading to {}").format(self._name),
                title=catalog.i18nc("@label", "Print jobs"),
                progress=-1, lifetime=0, dismissable=False, use_inactivity_timer=False
            )
            self._message.addAction("ABORT", catalog.i18nc("@action:button", "Cancel"), None, "")
            self._message.actionTriggered.connect(self._onActionTriggered)
            self._message.show()
            Thread(target=self.startSendingThread, daemon=True, name=self._name + " File Send").start()
        else:
            self._message = Message(catalog.i18nc("@info:status", "Cannot create gcode file!"), title=catalog.i18nc("@label", "FAILURE"))
            self._message.show()

    def _onActionTriggered(self, message, action):
        if self._message:
            self._message.hide()
            self._message = None  # type:Optional[Message]
        if action == "PRINT":
            res = self._qidi.print()
            if res is not QidiResult.SUCCES:
                Message(catalog.i18nc('@info:status', 'Cannot Print'), title=catalog.i18nc("@info:title", "FAILURE")).show()
            else:
                CuraApplication.getInstance().getController().setActiveStage("MonitorStage")
        elif action == "ABORT":
            Logger.log("i", "Stopping upload because the user pressed cancel.")
            self._qidi._abort = True

    def getProperties(self):
        return self._properties

    @pyqtSlot(str, result=str)
    def getProperty(self, key):
        key = key.encode("utf-8")
        if key in self._properties:
            return self._properties.get(key, b"").decode("utf-8")
        else:
            return ""

    @pyqtSlot(str)
    def sendCommand(self, cmd):
        if isinstance(cmd, str):
            self._qidi.sendCommand(cmd)
        elif isinstance(cmd, list):
            for eachCommand in cmd:
                self._qidi.sendCommand(eachCommand)

    @pyqtProperty(str, notify=printerStatusChanged)
    def status(self):
        return str(self._connection_state).split('.')[1]

    @pyqtProperty(str, constant=True)
    def name(self):
        return self._name

    @pyqtProperty(str, notify=printerStatusChanged)
    def firmwareVersion(self):
        return self.getFirmwareName()

    def getFirmwareName(self):
        return self._qidi._firmware_ver

    @pyqtProperty(str, notify=printerStatusChanged)
    def xPosition(self) -> bool:
        if "x_pos" in self._qidi._status:
            return self._qidi._status["x_pos"][:-1]
        else:
            return ""

    @pyqtProperty(str, notify=printerStatusChanged)
    def yPosition(self) -> bool:
        if "y_pos" in self._qidi._status:
            return self._qidi._status["y_pos"][:-1]
        else:
            return ""

    @pyqtProperty(str, notify=printerStatusChanged)
    def zPosition(self) -> bool:
        if "z_pos" in self._qidi._status:
            return self._qidi._status["z_pos"][:-1]
        else:
            return ""

    @pyqtProperty(str, notify=printerStatusChanged)
    def coolingFan(self) -> bool:
        if "fan" in self._qidi._status:
            fan = float(self._qidi._status["fan"])
            return "{}".format(int(fan/2.55))
        else:
            return ""
