from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QUdpSocket, QHostAddress

from typing import Union, Optional, List, cast, TYPE_CHECKING
from time import time, sleep
from enum import Enum
from timeit import default_timer as Timer
from socket import *

from UM.Logger import Logger
from UM.Platform import Platform
from UM.Job import Job

import subprocess
import re
import threading
import platform
import struct
import traceback
import sys
import base64
import json
import urllib
import os.path

from threading import Thread, Lock


class QidiResult(Enum):
    SUCCES = 0
    TIMEOUT = 1
    DISCONNECTED = 2
    WRITE_ERROR = 3
    ABORTED = 4
    FILE_EMPTY = 5
    FILE_NOT_OPEN = 6
    FAIL = 7


class QidiConnectionManager(QObject):
    progressChanged = pyqtSignal(int)
    conectionStateChanged = pyqtSignal(bool)
    updateDone = pyqtSignal()

    def __init__(self, ip_addr, temp_gcode_file, log_enabled=False):
        super().__init__()
        self._ip = QHostAddress(ip_addr)
        self._localTempGcode = temp_gcode_file
        self._port = 3000
        self.BUFSIZE = 1280
        self._file_encode = 'utf-8'
        self._abort = False
        self._filename = None
        self._log_enabled = log_enabled
        self._connected = False
        self._socket = QUdpSocket(self)
        self._last_reply = None
        self._isPrinting = False
        self._isIdle = False
        self._print_now = 0
        self._print_total = 0
        self._busy = False
        self._printing_filename = ""
        self._firmware_ver = ""
        self._printing_time = 0
        self._update_fail_cnt = 0
        self._last_times = []
        self._status = {}
        self._mutex = Lock()
        self._config = {'e_mm_per_step': '0.0',
                        's_machine_type': '0',
                        's_x_max': '0.0',
                        's_y_max': '0.0',
                        's_z_max': '0.0',
                        'x_mm_per_step': '0.0',
                        'y_mm_per_step': '0.0',
                        'z_mm_per_step': '0.0'}
        self.__log("d", "LocalPort: {}", self._socket.localPort())

    def __log(self, log_type: str, message: str, *args, **kwargs):
        if self._log_enabled:
            Logger.log(log_type, message, *args, **kwargs)

    def __send(self, cmd):
        new_command = cast(str, cmd).encode(self._file_encode, 'ignore') if type(cmd) is str else cast(bytes, cmd)  # type: bytes
        self._socket.writeDatagram(new_command, self._ip, self._port)

    def __recieve(self, timeout_ms=100):
        if timeout_ms > 0:
            start = Timer() + timeout_ms / 1000.0
            while Timer() < start and not self._socket.hasPendingDatagrams():
                pass
        msg = ''
        res = QidiResult.TIMEOUT
        while self._socket.hasPendingDatagrams():
            datagram, host, port = self._socket.readDatagram(self._socket.pendingDatagramSize())
            if datagram:
                msg += datagram.decode(self._file_encode, 'ignore')
                res = QidiResult.SUCCES

        if 'Error:Wifi reboot' in msg or 'Error:IP is connected' in msg:
            res = QidiResult.DISCONNECTED
            self._connected = False
            self.conectionStateChanged.emit(self._connected)
        return msg, res

    def sendCommand(self, cmd):
        result = self._mutex.acquire(blocking=True, timeout=1)
        if result:
            self.__send(cmd)
            self._mutex.release()
        else:
            self.__log("d", 'timeout: lock not available')

    def request(self, cmd, timeout_ms=100, retries=1):
        tryCnt = 0
        msg = ''
        res = QidiResult.TIMEOUT
        self.__recieve(0)  # discard pending datagrams
        while tryCnt < retries:
            tryCnt += 1
            if type(cmd) is str:
                self.__log("d", '[{}]sending cmd to {}: {}', tryCnt, self._ip.toString(), cmd)
            if self.abort is True:
                return '', QidiResult.ABORTED
            if not self._connected:
                return '', QidiResult.DISCONNECTED
            self.__send(cmd)
            msg, res = self.__recieve(timeout_ms)
            if res == QidiResult.SUCCES:
                if type(cmd) is str:  # Log reply message only for str commands
                    self.__log("d", 'got reply from {}: {}', self._ip.toString(), str(msg).rstrip())
                break
        return msg, res

    def abort(self):
        self.abort = True

    def connect(self, retries=1):
        with self._mutex:
            return self.__connect(retries)

    def __connect(self, retries=1):
        tryCnt = 0
        while tryCnt < retries and self._connected == False:
            tryCnt += 1
            self.__send("M4001")
            msg, res = self.__recieve()
            if res is not QidiResult.SUCCES:
                self.__log("w", '{} Connection timeout ', self._ip.toString())
                continue
            self.__log("d", 'Connected')
            msg = msg.rstrip()
            self.__log("d", msg)
            msgs = msg.split(' ')
            for item in msgs:
                _ = item.split(':')
                if len(_) == 2:
                    id = _[0]
                    value = _[1]
                    if id == 'X':
                        self._config["x_mm_per_step"] = value
                    elif id == 'Y':
                        self._config["y_mm_per_step"] = value
                    elif id == 'Z':
                        self._config["z_mm_per_step"] = value
                    elif id == 'E':
                        self._config["e_mm_per_step"] = value
                    elif id == 'T':
                        _ = value.split('/')
                        if len(_) == 5:
                            self._config["s_machine_type"] = _[0]
                            self._config["s_x_max"] = _[1]
                            self._config["s_y_max"] = _[2]
                            self._config["s_z_max"] = _[3]
                    elif id == 'U':
                        self._file_encode = value.replace("'", '')
            self._connected = True
            msg, res = self.request('M4002 ', 2000, 2)
            if res == QidiResult.SUCCES:
                if 'ok ' in msg:
                    msg = msg.rstrip()
                    msg = msg.split('ok ')
                    self._firmware_ver = msg[1]
            self.conectionStateChanged.emit(self._connected)
            return True
        return False

    def __compress_gcode(self):
        exePath = None
        if Platform.isWindows():
            exePath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VC_compress_gcode.exe')
        elif Platform.isOSX():
            exePath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'VC_compress_gcode_MAC')
        else:
            self.__log("w", "Could not find gcode compression tool")

        if exePath is not None and os.path.exists(exePath):
            cmd = '"' + exePath + '"' + ' "' + self._localTempGcode + '" ' + self._config["x_mm_per_step"] + ' ' + self._config["y_mm_per_step"] + ' ' + self._config["z_mm_per_step"] + ' ' + \
                self._config["e_mm_per_step"] + ' "' + os.path.dirname(self._localTempGcode) + '" ' \
                + self._config["s_x_max"] + ' ' + self._config["s_y_max"] + ' ' + self._config["s_z_max"] + ' ' + self._config["s_machine_type"]
            self.__log("d", cmd)

            ret = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
            self.__log("d", ret.stdout.read().decode('utf-8', 'ignore').rstrip())

            if os.path.exists(self._localTempGcode + '.tz'):  # check whether the compression succedded
                return True
            else:
                return False

    def __send_start_write(self, filename):
        self.__log("i", 'Creating file {}', filename)
        msg, res = self.request('M28 ' + filename, 2000, 3)
        if res == QidiResult.SUCCES:
            if 'Error' in msg:
                self.__log("e", 'cmd:' + msg)
                return QidiResult.WRITE_ERROR
            else:
                return QidiResult.SUCCES
        return res

    def __send_end_write(self, filename):
        self.__log("i", 'Closing file')
        msg, res = self.request('M29 ' + filename, 2000, 3)
        if res == QidiResult.SUCCES:
            if 'Error' in msg:
                self.__log("e", 'cmd:' + msg)
                return QidiResult.WRITE_ERROR
            else:
                return QidiResult.SUCCES
        return res

    def __send_file_block(self, buff, seek):
        check_sum = 0
        buff += b"000000"
        dataArray = bytearray(buff)
        seekArray = struct.pack('>I', seek)
        datSize = len(dataArray) - 6
        dataArray[datSize] = seekArray[3]
        dataArray[datSize + 1] = seekArray[2]
        dataArray[datSize + 2] = seekArray[1]
        dataArray[datSize + 3] = seekArray[0]
        for i in range(0, datSize + 4, 1):
            check_sum ^= dataArray[i]
        dataArray[datSize + 4] = check_sum
        dataArray[datSize + 5] = 131
        datSize = len(dataArray) - 6
        if datSize <= 0:
            raise Exception('error computing checksum!')
            return
        return self.request(dataArray, 2000, 3)

    def __send_file(self, fp):
        self.__log("i", 'begin sending file')
        lastProgress = seek = 0

        while True:
            try:
                if self._abort:
                    return QidiResult.ABORTED

                seek = fp.tell()
                data = fp.read(self.BUFSIZE)
                if int(100 * seek / self.__sendFileSize) > int(100 * lastProgress):
                    lastProgress = seek / self.__sendFileSize
                    progress = int(100 * lastProgress)
                    self.progressChanged.emit(progress)
                    sys.stdout.write('*')
                    sys.stdout.flush()
                if not data:
                    sys.stdout.write('\r\n')
                    self.__log("d", 'reach file end')
                    return QidiResult.SUCCES

                #self.__log("d","sending file block: {}", seek)
                msg, res = self.__send_file_block(data, seek)

                if res == QidiResult.SUCCES:
                    if 'ok' in msg:
                        continue
                    else:
                        self.__log("w", "got reply: " + msg)
                        if 'resend' in msg:
                            value = re.findall('resend \\d+', msg)
                            if value:
                                resend_offset = int(value[0].replace('resend ', ''))
                                fp.seek(resend_offset, 0)

                            else:
                                self.__log("d", 'bad offset:' + msg)
                                return QidiResult.WRITE_ERROR
                        elif 'Error' in msg:
                            return QidiResult.WRITE_ERROR
                        else:
                            return QidiResult.WRITE_ERROR
                else:
                    self.__log("e", 'send file block timeout')
                    continue
            except Exception as e:
                self.__log("w", str(e))
                return QidiResult.WRITE_ERROR

    def sendfile(self, filename):
        with self._mutex:
            ret = self.__sendfile(filename)
            return ret

    def __sendfile(self, filename):
        self._abort = False
        self._filename = None
        if not self._connected:
            if not self.__connect():
                return QidiResult.DISCONNECTED

        if os.path.exists(self._localTempGcode + '.tz'):
            os.remove(self._localTempGcode + '.tz')

        if self.__compress_gcode():
            filename += '.gcode.tz'
            send_file_path = self._localTempGcode + '.tz'
        else:
            filename += '.gcode'
            send_file_path = self._localTempGcode

        self.__log("d", 'file path: ' + send_file_path)

        try:
            self.__sendFileSize = os.path.getsize(send_file_path)
            self.__log("d", 'file size: {}', self.__sendFileSize)
            if self.__sendFileSize == 0:
                self.__log("e", 'file empty')
                return QidiResult.FILE_EMPTY

            with open(send_file_path, 'rb', buffering=1) as fp:
                if not self.__send_start_write(filename):
                    return QidiResult.WRITE_ERROR

                res = self.__send_file(fp)
                if res is not QidiResult.SUCCES:
                    return res

                if not self.__send_end_write(filename):
                    return QidiResult.WRITE_ERROR

        except Exception as e:
            self.__log("w", str(e))
            return QidiResult.WRITE_ERROR

        self._filename = filename
        return QidiResult.SUCCES

    def print(self):
        msg, res = self.request('M6030 ":' + self._filename + '" I1', 2000, 3)
        if res == QidiResult.SUCCES and 'Error' in msg:
            return QidiResult.FAIL
        return res

    def update(self):
        result = self._mutex.acquire(blocking=True, timeout=0.5)
        if result:
            ret = self.__update()
            if ret == QidiResult.SUCCES:
                self._update_fail_cnt = 0
                self.updateDone.emit()
            else:
                self._update_fail_cnt += 1
                if self._update_fail_cnt > 2:
                    self._connected = False
                    self.conectionStateChanged.emit(self._connected)
            self._mutex.release()
            return ret
        else:
            self.__log("d", 'timeout: lock not available')
            return QidiResult.TIMEOUT

    def __update(self):
        msg, res = self.request("M4000", 100, 3)
        if res == QidiResult.SUCCES:
            prev_printing_time = self._printing_time
            msg = msg.rstrip()
            msgs = msg.split(' ')
            for item in msgs:
                _ = item.split(':')
                try:
                    if len(_) == 2:
                        id = _[0]
                        value = _[1]
                        if id == 'B':
                            _ = value.split('/')
                            if len(_) == 2:
                                self._status["bed_nowtemp"] = _[0]
                                self._status["bed_targettemp"] = _[1]
                        elif id == 'E1':
                            _ = value.split('/')
                            if len(_) == 2:
                                self._status["e1_nowtemp"] = _[0]
                                self._status["e1_targettemp"] = _[1]
                        elif id == 'E2':
                            _ = value.split('/')
                            if len(_) == 2:
                                self._status["e2_nowtemp"] = _[0]
                                self._status["e2_targettemp"] = _[1]
                        elif id == 'D':
                            _ = value.split('/')
                            if len(_) == 3:
                                self._print_now = int(_[0])
                                self._print_total = int(_[1])
                                self._isIdle = _[2] is '1'
                        elif id == 'F':
                            _ = value.split('/')
                            if len(_) == 2:
                                self._status["fan"] = _[0]
                        elif id == 'X':
                            self._status["x_pos"] = value
                        elif id == 'Y':
                            self._status["y_pos"] = value
                        elif id == 'Z':
                            self._status["z_pos"] = value
                        elif id == 'T':
                            self._printing_time = int(value)
                except:
                    self.__log("e", "Could not parse M4000 reply: {}", msg)

            if self._isPrinting == False and self._printing_time > 0:
                self._last_times = []
                self._isPrinting = True
                msg, res = self.request("M4006", 100, 3)
                if res == QidiResult.SUCCES:
                    _ = msg.split("'")
                    if len(_) > 2:
                        self._printing_filename = _[1]
            elif self._printing_time == 0:
                self._isPrinting = False

        return res


class QidiNetDevice:

    def __init__(self):
        self.ipaddr = ''
        self.name = 'undefined'

    def __str__(self):
        return self.name + "[" + self.ipaddr + "]"


class QidiFinderJob(QObject, Job):

    IPListChanged = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._scan_in_progress = False
        self._udpSocket = QUdpSocket(self)
        # self._udpSocket.bind(64942)
        self.devices = []

    def _generate_broad_addr(self, targetIP, maskstr):
        iptokens = list(map(int, targetIP.split('.')))
        masktokens = list(map(int, maskstr.split('.')))
        broadlist = []
        for i in range(len(iptokens)):
            ip = iptokens[i]
            mask = masktokens[i]
            broad = ip & mask | ~mask & 255
            broadlist.append(broad)
        return '.'.join(map(str, broadlist))

    def _getAllBroadcast(self):
        ipconfig_process = subprocess.Popen('ifconfig' if Platform.isLinux() or Platform.isOSX() else 'ipconfig', stdout=subprocess.PIPE, shell=True)
        output = ipconfig_process.stdout.read().decode('utf-8', 'ignore')
        allIPlist = re.findall('\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}', output)
        allIP = ''
        for j in allIPlist:
            if j.count('255.255') < 1:
                allIP += j + '   '

        ipList = gethostbyname_ex(gethostname())
        if len(ipList) == 3:
            ipList = ipList[2]
        broadcast = []
        for i in range(len(allIPlist)):
            ipaddr = allIPlist[i]
            if ipaddr in ipList and ipaddr != '127.0.0.1' and i + 1 <= len(allIPlist):
                if Platform.isLinux() or Platform.isOSX():
                    broadcast.append(allIPlist[(i + 1)])
                else:
                    broadcast.append(self._generate_broad_addr(ipaddr, allIPlist[(i + 1)]))

        if not broadcast:
            Logger.log("w", "Cann't find valid boradcast,use all IP")
            broadcast = allIPlist
        return broadcast

    def _isDuplicateIP(self, ip):
        for device in self.devices:
            if ip == device.ipaddr:
                return True
        return False

    def _readPendingDatagrams(self):
        while self._udpSocket.hasPendingDatagrams():
            datagram, host, port = self._udpSocket.readDatagram(self._udpSocket.pendingDatagramSize())
            message = datagram.decode('utf-8', 'ignore')
            message = message.rstrip()
            if message.find('ok MAC:') != -1:
                device = QidiNetDevice()
                device.ipaddr = QHostAddress(host.toIPv4Address()[0]).toString()
                if not self._isDuplicateIP(device.ipaddr):
                    if 'NAME:' in message:
                        device.name = message[message.find('NAME:') + len('NAME:'):].split(' ')[0]
                    Logger.log("d", 'Got reply from: {}', device)
                    self.devices.append(device)
                    self.IPListChanged.emit()
                else:
                    Logger.log("d", 'Got reply from known device')

    def run(self) -> None:
        self.devices = []
        self.IPListChanged.emit()
        self._scan_in_progress = True

        broadcasts = self._getAllBroadcast()
        Logger.log("i", "Brodcast networks: {}", broadcasts)
        end_time = Timer() + 5
        while Timer() < end_time:
            Logger.log("d", 'Broadcasting discovery packet')
            for broadcast in broadcasts:
                self._udpSocket.writeDatagram('M99999'.encode('utf-8'), QHostAddress(broadcast), 3000)
            sleep(1)
            self._readPendingDatagrams()

        self.IPListChanged.emit()
        self._scan_in_progress = False
        Logger.log('i', 'device scan done')
