# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 16:58:52 2020

@author: meduser
"""


import subprocess
import re
from datetime import datetime, timedelta
import time
import os.path
import pathlib
from glob import glob

LOG_PATTERNS = [ '*.ecg', '*.puls', '*.resp' ]


MOCK = False
try:
    import __main__
    MOCK = __main__.MOCK
except:
    pass

class RaidError(Exception):
    pass

print("RaidTool - Mock?", MOCK)

LIST_COMMAND_TIMEOUT = 10
TRANSFER_COMMAND_TIMEOUT = 300

dateTimePattern = r'\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}'
parserRE = re.compile(r'\s*(?P<FileID>\d+)\s+(?P<MeasID>\d+)\s+(?P<Prot>.+?)(?P<Pat>.{32})\s+cld\s+(?P<Size>\d+)\s+(?P<SizeDisk>\d+)\s+(?P<CreateTime>' + dateTimePattern + ')\s+(?P<CloseTime>' + dateTimePattern + ').*')

def runCommand(cmd, timeout):
    out = subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
    return out

def parseRaidOutput(raidOutput):
    headerFound = False

    data = []

    def parseDateTime(string):
        return datetime.strptime(string, '%d.%m.%Y %H:%M:%S')

    for line in raidOutput.splitlines():
        if type(line) == bytes:
            l = line.decode('utf-8')
        else:
            l = line
        l = line.decode('utf-8')

        if 'FileID' in l:
            headerFound = True
        elif not headerFound or not l:
            continue
        m = parserRE.match(l)
        if not m: continue
        dataItem = m.groupdict()
        # keep these values as strings as they are more general
        #dataItem['FileID'] = int(dataItem['FileID'])
        #dataItem['MeasID'] = int(dataItem['MeasID'])
        dataItem['Pat'] = dataItem['Pat'].strip()
        dataItem['CreateTime'] = parseDateTime(dataItem['CreateTime'])
        dataItem['CloseTime'] = parseDateTime(dataItem['CloseTime'])
        dataItem['Dependencies'] = []
        data.append(dataItem)

    return data

# reads the LogStartMDHTime and LogEndMDHTime from the file. Returns None, None if not found
def findLogFileTimes(logFileName):

    startLogRE = re.compile(r'LogStartMDHTime:\s*(\d+)')
    endLogRE = re.compile(r'LogStopMDHTime:\s*(\d+)')

    startMs = None
    endMs = None

    with open(logFileName, 'r') as f:
        for line in f:
            m = startLogRE.match(line)
            if m:
                startMs = int(m.group(1))
                continue
            m = endLogRE.match(line)
            if m:
                endMs = int(m.group(1))

    return startMs, endMs



class RaidTool:

    def __init__(self, IP = '192.168.2.2', port = '8010', TmpDir = 'C:\\Temp\\Agora', LogDir = 'C:\\MedCom\\Log'):
        self.ip = IP
        self.port = port
        self.tmpDir = TmpDir
        self.logDir = LogDir
        self.logFileDict = {}

    def raidCommand(self, cmd):
        return f'RaidTool -a {self.ip} -p {self.port} -k ' + cmd

    def loadLogList(self):
        # create globs for extensions
        newFileDict = {}
        for glb in LOG_PATTERNS:
            for f in glob(os.path.join( os.path.abspath(self.logDir), glb))
                if f in self.logFileDict: # avoid parsing files without need, but also purge nonexisting files
                    newFileDict[f] = self.logFileDict[f]
                    continue
                createDateTime = datetime.fromtimestamp( os.path.getctime(f) )
                createDay = datetime(createDateTime.year, createDateTime.month, createDateTime.day)
                startMs, endMs = findLogFileTimes(f)
                if startMs is None or endMs is None: continue # invalid file
                startDateTime = createDay + timedelta(milliseconds = startMs)
                endDateTime = createDay + timedelta(milliseconds = endMs)
                newFileDict[f] = (startDateTime, endDateTime)
                print("File", f, "Start", startDateTime, "End", endDateTime)
        self.logFileDict = newFileDict
        return newFileDict


    def loadList(self):
        print(self.raidCommand(f'-t {LIST_COMMAND_TIMEOUT} -d'))
        if MOCK:
            with open('raidout_noanon.txt', 'rb') as raidOutFile:
                out = raidOutFile.read()
        else:
            procOutput = runCommand(self.raidCommand(f'-t {LIST_COMMAND_TIMEOUT} -d'), LIST_COMMAND_TIMEOUT+2)
            #print("Return code", procOutput.returncode)
            if procOutput.returncode != 0: raise RaidError
            out = procOutput.stdout

        raidList = parseRaidOutput(out)
        # find Log List
        logList = self.loadLogList()

        # find matches between raid files and logs
        for raidData in raidList:
            for logPath, logTimes in logList.items():
                if logTimes[0] < raidData['CloseTime'] and logTimes[1] > raidData['CreateTime']: # start of log must be before end of acquisition and vice versa
                    print(dataItem['FileID'], '->', logPath)
                    raidData['Dependencies'].append(logPath)

        return raidList

    def retrieve(self, fileID) -> bool:
        cmd = self.raidCommand(f'-m {fileID} -o "{self.getLocalFile(fileID)}" -D -T {TRANSFER_COMMAND_TIMEOUT}')
        print(cmd)
        if MOCK:
            time.sleep(1)
            return True

        targetPath = pathlib.Path(self.getLocalFile(fileID))

        targetPath.parent.mkdir(parents = True, exist_ok = True)

        procOutput = runCommand(cmd, TRANSFER_COMMAND_TIMEOUT + 2)
        if procOutput.returncode != 0: return False
        # finally, check if file was correctly created
        return targetPath.is_file()

    # returns the location/name of the local retrieved file, given the ID
    def getLocalFile(self, fileID):
        return os.path.join(self.tmpDir, f'{fileID}.dat')

