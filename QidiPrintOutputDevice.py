from enum import Enum
import os.path
from time import time, sleep

import subprocess, re, threading, platform, struct, traceback, sys, base64, json, urllib
from typing import cast, Any, Callable, Dict, List, Optional
from socket import *

from PyQt5.QtCore import QFile, QUrl, QObject, QCoreApplication, QByteArray, QTimer, pyqtProperty, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtQml import QQmlComponent, QQmlContext

from cura.CuraApplication import CuraApplication
from UM.Resources import Resources
import UM.Qt.ListModel

from UM.Application import Application
from UM.Logger import Logger
from UM.Message import Message
from UM.Mesh.MeshWriter import MeshWriter
from UM.PluginRegistry import PluginRegistry
from UM.OutputDevice.OutputDevice import OutputDevice
from UM.OutputDevice import OutputDeviceError

from UM.i18n import i18nCatalog
from .ChituCodeWriter import ChituCodeWriter

catalog = i18nCatalog("cura")


class OutputStage(Enum):
    ready = 0
    writing = 1


class SendResult(Enum):
    SEND_DONE = 0
    CONNECT_TIMEOUT = 1
    WRITE_ERROR = 2
    FILE_EMPTY = 3
    FILE_NOT_OPEN = 4
    SEND_RUNNING = 5
    FILE_NOT_SAVE = 6
    CANNOT_START_PRINT = 7


class QidiPrintOutputDevice(OutputDevice):

    def __init__(self, name, target_ip):
        description = catalog.i18nc(
            "@action:button", "Send to {0}").format(name)

        super().__init__(name)
        self.setShortDescription(description)
        self.setDescription(description)
        self.setPriority(10)
        self._name = name
        self._PluginName = 'QIDI Print'

        self.PORT = 3000
        self.BUFSIZE = 1280
        self.RECVBUF = 1280
        self.targetSendFileName = None
        self.progress = 0
        self.sendMax = 0
        self.sock = socket(AF_INET, SOCK_DGRAM)
        self.sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)

        self._localTempGcode = Resources.getStoragePath(
            Resources.Resources, 'data.gcode')
        self._send_thread = None
        self._file_encode = 'utf-8'

        self._update_timer = QTimer()
        self._update_timer.setInterval(100)
        self._update_timer.setSingleShot(False)
        self._update_timer.timeout.connect(self._update)

        self._stage = OutputStage.ready
        self._targetIP = target_ip

        Logger.log("d", self._name + " | New QidiPrintOutputDevice created")
        Logger.log("d", self._name + " | IP: " + self._targetIP)

        if hasattr(self, '_message'):
            self._message.hide()
        self._message = None

    def requestWrite(self, node, fileName=None, *args, **kwargs):
        if self._stage != OutputStage.ready:
            raise OutputDeviceError.DeviceBusyError()

        if fileName:
            fileName = os.path.splitext(fileName)[0] + '.gcode.tz'
        else:
            fileName = "%s.gcode.tz" % Application.getInstance().getPrintInformation().jobName
        self.targetSendFileName = fileName

        path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), 'UploadFilename.qml')
        self._dialog = CuraApplication.getInstance(
        ).createQmlComponent(path, {"manager": self})
        self._dialog.textChanged.connect(self.onFilenameChanged)
        self._dialog.accepted.connect(self.onFilenameAccepted)
        self._dialog.show()
        self._dialog.findChild(QObject, "nameField").setProperty(
            'text', self.targetSendFileName)
        self._dialog.findChild(QObject, "nameField").select(
            0, len(self.targetSendFileName) - 9)
        self._dialog.findChild(QObject, "nameField").setProperty('focus', True)

    def onFilenameChanged(self):
        fileName = self._dialog.findChild(
            QObject, "nameField").property('text').strip()
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

    def encodeCmd(self, cmd):
        return cmd.encode(self._file_encode, 'ignore')

    def decodeCmd(self, cmd):
        return cmd.decode(self._file_encode, 'ignore')

    def _genTempGcodeFile(self):
        fp = open(self._localTempGcode, 'w+', buffering=1)
        if not fp:
            self._result = SendResult.FILE_NOT_SAVE
        else:
            #writer = cast(MeshWriter, PluginRegistry.getInstance().getPluginObject("ChituCodeWriter"))
            writer = ChituCodeWriter()
            success = writer.write(fp, None, MeshWriter.OutputMode.TextMode)
            fp.close()
            if not success:
                self._result = SendResult.FILE_NOT_SAVE

    def sendDatThread(self):
        Logger.log('i', '==========start send file============')
        try:
            while True:
                oldseek = 0
                self.sock.settimeout(2)
                Logger.log('i', 'targetIP:' + self._targetIP)
                tryCnt = 0
                while True:
                    try:
                        if self._abort:
                            break
                        if tryCnt > 3:
                            self._result = SendResult.CONNECT_TIMEOUT
                            break
                        self.sock.sendto(self.encodeCmd(
                            'M4001\r\n'), (self._targetIP, self.PORT))
                        message, address = self.sock.recvfrom(self.RECVBUF)
                        Logger.log('d', message)
                        break
                    except timeout:
                        Logger.log('w', 'Socket M4001 timeout ')
                    except:
                        tryCnt += 1
                        traceback.print_exc()

                if self._result != SendResult.SEND_RUNNING:
                    break
                if self._abort:
                    break
                filePath = self._localTempGcode + '.tz'
                Logger.log('d', 'compressed file path: ' + filePath)
                try:
                    self.sendMax = os.path.getsize(filePath)
                    Logger.log('d', 'compressed file size: ' +
                               str(self.sendMax))
                    if self.sendMax == 0:
                        self._result = SendResult.FILE_EMPTY
                        break
                    fp = open(filePath, 'rb', buffering=1)
                    if not fp:
                        self._result = SendResult.FILE_NOT_OPEN
                        Logger.log('e', '==error open file %s', filePath)
                        break
                except Exception as e:
                    Logger.log('w', str(e))
                    self._result = SendResult.FILE_EMPTY
                    break
                else:
                    fp.seek(0, 0)
                    cmd = 'M28 ' + self.targetSendFileName
                    Logger.log('d', 'cmd:' + cmd)
                    self.sock.sendto(self.encodeCmd(
                        cmd), (self._targetIP, self.PORT))
                    message, address = self.sock.recvfrom(self.RECVBUF)
                    message = message.decode('utf-8', 'replace')
                    Logger.log('d', 'message: ' + message)
                    if 'Error' in message:
                        self._result = SendResult.WRITE_ERROR
                        self._errorMsg = message
                        break
                    self.sock.settimeout(0.1)
                    lastProgress = 0
                    lastDataArray = None
                    finishedCnt = 0
                    timeoutCnt = 0
                    finishedRcvOkCnt = 0
                    while True:
                        try:
                            if self._abort:
                                break
                            data = fp.read(self.BUFSIZE)
                            if not data:
                                Logger.log('f', 'reach file end')
                                if finishedCnt >= 50 or not lastDataArray:
                                    break
                                dataArray = lastDataArray
                                sleep(0.33)
                                finishedCnt += 1
                            else:
                                finishedRcvOkCnt = finishedCnt = 0
                                check_sum = 0
                                data += self.encodeCmd('000000')
                                dataArray = bytearray(data)
                                seek = fp.tell()
                                seekArray = struct.pack('>I', oldseek)
                                oldseek = seek
                                if int(100 * seek / self.sendMax) > int(100 * lastProgress):
                                    lastProgress = seek / self.sendMax
                                    self.progress = int(100 * lastProgress)
                                datSize = len(dataArray) - 6
                                if datSize <= 0:
                                    break
                                dataArray[datSize] = seekArray[3]
                                dataArray[datSize + 1] = seekArray[2]
                                dataArray[datSize + 2] = seekArray[1]
                                dataArray[datSize + 3] = seekArray[0]
                                for i in range(0, datSize + 4, 1):
                                    check_sum ^= dataArray[i]

                                dataArray[datSize + 4] = check_sum
                                dataArray[datSize + 5] = 131
                                lastDataArray = dataArray

                            self.sock.sendto(
                                dataArray, (self._targetIP, self.PORT))
                            message, address = self.sock.recvfrom(self.RECVBUF)
                            timeoutCnt = 0
                            message = message.decode('utf-8', 'replace')
                            if 'ok' in message:
                                if finishedRcvOkCnt > 3:
                                    break
                                elif finishedCnt:
                                    finishedRcvOkCnt += 1
                                else:
                                    continue

                            elif 'Error' in message:
                                self._result = SendResult.WRITE_ERROR
                                break
                            elif 'resend' in message:
                                value = re.findall('resend \\d+', message)
                                if value:
                                    value = value[0].replace('resend ', '')
                                    oldseek = offset = int(value)
                                    fp.seek(offset, 0)
                                    Logger.log(
                                        'd', 'resend offset:' + str(offset))
                                else:
                                    Logger.log('d', 'Error offset:' + message)
                        except timeout:
                            if finishedCnt < 4 and timeoutCnt > 150 or finishedCnt > 45:
                                Logger.log(
                                    'w', 'finishedCnt: ' + str(finishedCnt) + ' timeoutcnt: ' + str(timeoutCnt))
                                self._result = SendResult.CONNECT_TIMEOUT
                                break
                            timeoutCnt += 1
                        except:
                            traceback.print_exc()
                            self._abort = True

                    fp.close()
                    os.remove(filePath)
                break

            if not self._abort and self._result == SendResult.SEND_RUNNING:
                self.sock.settimeout(2)
                tryCnt = 0
                while True:
                    try:
                        self.sock.sendto(self.encodeCmd(
                            'M29'), (self._targetIP, self.PORT))
                        message, address = self.sock.recvfrom(self.RECVBUF)
                        message = message.decode('utf-8', 'replace')
                        Logger.log('d', 'M29 rcv:' + message)
                        if 'Error' in message:
                            self._result = SendResult.WRITE_ERROR
                            break
                        else:
                            self._result = SendResult.SEND_DONE
                            break
                    except:
                        tryCnt += 1
                        Logger.log('i', 'Try to Close file')
                        if tryCnt > 6:
                            self._result = SendResult.CONNECT_TIMEOUT
                            break

        except:
            self._result = SendResult.WRITE_ERROR
            traceback.print_exc()

    def dataCompressThread(self):
        Logger.log('i', '========start compress file=========')
        self.datamask = '[0-9]{1,12}\\.[0-9]{1,12}'
        self.maxmask = '[0-9]'
        tryCnt = 0
        while True:
            try:
                if self._abort:
                    break
                self.sock.settimeout(2)
                Logger.log('d', self._targetIP)
                self.sock.sendto(self.encodeCmd('M4001'),
                                 (self._targetIP, self.PORT))
                message, address = self.sock.recvfrom(self.BUFSIZE)
                pattern = re.compile(self.datamask)
                msg = message.decode('utf-8', 'ignore')
                if 'X' not in msg or 'Y' not in msg or 'Z' not in msg:
                    continue
                msg = msg.replace('\r', '')
                msg = msg.replace('\n', '')
                msgs = msg.split(' ')
                Logger.log('d', msg)
                e_mm_per_step = z_mm_per_step = y_mm_per_step = x_mm_per_step = '0.0'
                s_machine_type = s_x_max = s_y_max = s_z_max = '0.0'
                for item in msgs:
                    _ = item.split(':')
                    if len(_) == 2:
                        id = _[0]
                        value = _[1]
                        Logger.log('d', _)
                        if id == 'X':
                            x_mm_per_step = value
                        elif id == 'Y':
                            y_mm_per_step = value
                        elif id == 'Z':
                            z_mm_per_step = value
                        elif id == 'E':
                            e_mm_per_step = value
                        elif id == 'T':
                            _ = value.split('/')
                            if len(_) == 5:
                                s_machine_type = _[0]
                                s_x_max = _[1]
                                s_y_max = _[2]
                                s_z_max = _[3]
                        elif id == 'U':
                            self._file_encode = value.replace("'", '')
                exePath = os.path.join(os.path.dirname(
                    os.path.abspath(__file__)), 'VC_compress_gcode.exe')
                cmd = '"' + exePath + '"' + ' "' + self._localTempGcode + '" ' + x_mm_per_step + ' ' + y_mm_per_step + ' ' + z_mm_per_step + ' ' + \
                    e_mm_per_step + ' "' + \
                    os.path.dirname(self._localTempGcode) + '" ' + s_x_max + \
                    ' ' + s_y_max + ' ' + s_z_max + ' ' + s_machine_type
                Logger.log('d', cmd)
                ret = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
                Logger.log('d', ret.stdout.read().decode('utf-8', 'ignore'))
                break
            except timeout:
                tryCnt += 1
                if tryCnt > 2:
                    self._result = SendResult.CONNECT_TIMEOUT
                    break
            except:
                traceback.print_exc()
                break

    def startSendingThread(self):
        Logger.log('i', '=============QIDI SEND BEGIN============')
        self._errorMsg = ''

        self._abort = False
        self._stage = OutputStage.writing
        self.writeStarted.emit(self)

        if self._result == SendResult.SEND_RUNNING:
            self.dataCompressThread()
            if self._result == SendResult.SEND_RUNNING:                
                self.sendDatThread()

        if self._message:
            self._message.hide()
            self._message = None  # type:Optional[Message]

        self.writeFinished.emit(self)
        self._stage = OutputStage.ready

        if self._abort:
            self._stage = OutputStage.ready
            Message(catalog.i18nc('@info:status', 'Upload Canceled'),
                    title=catalog.i18nc("@info:title", "ABORTED")).show()
            return

        if self._result == SendResult.SEND_DONE:
            self._message = Message(catalog.i18nc(
                "@info:status", "Do you wish to print now?"), title=catalog.i18nc("@label", "SUCCESS"))
            self._message.addAction("YES", catalog.i18nc(
                "@action:button", "YES"), None, "")
            self._message.addAction("NO", catalog.i18nc(
                "@action:button", "NO"), None, "")
            self._message.actionTriggered.connect(self._onActionTriggered)
            self._message.show()
            self.writeSuccess.emit(self)
            self._stage = OutputStage.ready
            return

        result_msg = "Unknown Error!!!"
        if self._result == SendResult.CONNECT_TIMEOUT:
            self.writeError.emit(self)
            result_msg = 'Connection timeout'
        elif self._result == SendResult.WRITE_ERROR:
            self.writeError.emit(self)
            result_msg = self._errorMsg
            if 'create file' in self._errorMsg:
                m = Message(catalog.i18nc(
                    '@info:status', ' Write error,please check that the SD card /U disk has been inserted'), lifetime=0)
                m.show()
        elif self._result == SendResult.FILE_EMPTY:
            self.writeError.emit(self)
            result_msg = 'File empty'
        elif self._result == SendResult.FILE_NOT_OPEN:
            self.writeError.emit(self)
            result_msg = "Cannot Open File"
        elif self._result == SendResult.FILE_NOT_SAVE:
            self.writeError.emit(self)
            result_msg = "Cannot Save File"
        elif self._result == SendResult.CANNOT_START_PRINT:
            self.writeError.emit(self)
            result_msg = "Cannot start print"

        self._message = Message(catalog.i18nc(
            "@info:status", result_msg), title=catalog.i18nc("@label", "FAILURE"))
        self._message.show()
        self._stage = OutputStage.ready
        Logger.log('e', result_msg)

    def onFilenameAccepted(self):
        self.targetSendFileName = self._dialog.findChild(
            QObject, "nameField").property('text').strip()
        if not self.targetSendFileName.endswith('.gcode.tz') and '.' not in self.targetSendFileName:
            self.targetSendFileName += '.gcode.tz'
        Logger.log("d", self._name + " | Filename set to: " +
                   self.targetSendFileName)
        self._dialog.deleteLater()

        self._message = Message(
            catalog.i18nc("@info:status",
                          "Uploading to {}").format(self._name),
            title=catalog.i18nc("@label", self._PluginName),
            progress=-1, lifetime=0, dismissable=False, use_inactivity_timer=False
        )
        self._message.addAction("ABORT", catalog.i18nc(
            "@action:button", "Cancel"), None, "")
        self._message.actionTriggered.connect(self._onActionTriggered)
        self._message.show()

        self._result = SendResult.SEND_RUNNING
        self._genTempGcodeFile()

        self._send_thread = threading.Thread(target=self.startSendingThread)
        self._send_thread.daemon = True
        self._send_thread.start()
        self._update_timer.start()

    def _onActionTriggered(self, message, action):
        self._update_timer.stop()
        if self._message:
            self._message.hide()
            self._message = None  # type:Optional[Message]            
        if action == "YES":
            self.sock.settimeout(2)
            tryCnt = 0
            while True:
                try:
                    cmd = 'M6030 ":' + self.targetSendFileName + '" I1'
                    Logger.log('i', 'Start print: ' + cmd)
                    self.sock.sendto(self.encodeCmd(
                        cmd), (self._targetIP, self.PORT))
                    message, address = self.sock.recvfrom(self.RECVBUF)
                    message = message.decode('utf-8', 'replace')
                    if 'Error' in message:
                        self._result = SendResult.CANNOT_START_PRINT
                        break
                    else:
                        break
                except:
                    traceback.print_exc()
                    tryCnt += 1
                    if tryCnt > 6:
                        self._result = SendResult.CONNECT_TIMEOUT
        elif action == "ABORT":
            Logger.log("i", "Stopping upload because the user pressed cancel.")
            self._abort = True

    def _update(self):
        if self._stage == OutputStage.writing and self._message:
            self._message.setProgress(int(self.progress))
            self._message.show()
            self.writeProgress.emit(self, int(self.progress))
