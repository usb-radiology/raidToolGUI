# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 16:58:52 2020

@author: meduser
"""


import subprocess
import re
from datetime import datetime, timedelta
import time
import os
import pathlib
from glob import glob

LOG_PATTERNS = [ '*.ecg', '*.puls', '*.resp', '*.ext', '*.ext2' ]


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
DELETE_OLD_LOGS = True

dateTimePattern = r'\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}'
parserRE = re.compile(r'\s*(?P<FileID>\d+)\s+(?P<MeasID>\d+)\s+(?P<Prot>.+?)(?P<Pat>.{32})\s+cld\s+(?P<Size>\d+)\s+(?P<SizeDisk>\d+)\s+(?P<CreateTime>' + dateTimePattern + ')\s+(?P<CloseTime>' + dateTimePattern + ').*')
nameDateRE = re.compile(r'(.*),(.*)')

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
        #l = line.decode('utf-8')
        #print(line)

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
        patNameDate = dataItem['Pat'].strip()
        nameDateMatch = nameDateRE.match(patNameDate)
        dataItem['Pat'] = nameDateMatch.group(1)
        dataItem['BirthDate'] = nameDateMatch.group(2)
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

    logFileDict = {} # make this static so it doesn't get overwritten by new initialization

    def __init__(self, IP = '192.168.2.2', port = '8010', TmpDir = 'C:\\Temp\\Agora', LogDir = 'C:\\MedCom\\Log'):
        self.ip = IP
        self.port = port
        self.tmpDir = TmpDir
        self.logDir = LogDir

    def raidCommand(self, cmd, anonymize = False):
        c = f'RaidTool -a {self.ip} -p {self.port} '

        if not anonymize:
            c += '-k '

        c += cmd
        print(c)
        return c

    def loadLogList(self):
        # create globs for extensions
        newFileDict = {}
        print(list(self.logFileDict.keys()))
        for glb in LOG_PATTERNS:
            for f in glob(os.path.join( os.path.abspath(self.logDir), glb)):
                if f in RaidTool.logFileDict: # avoid parsing files without need, but also purge nonexisting files
                    newFileDict[f] = RaidTool.logFileDict[f]
                    print("File exists in dict. Skipping")
                    continue
                createDateTime = datetime.fromtimestamp( os.path.getctime(f) )
                createDay = datetime(createDateTime.year, createDateTime.month, createDateTime.day)
                age = datetime.now() - createDateTime
                if age > timedelta(days=365):
                    #print("Old file!", f)
                    if DELETE_OLD_LOGS:
                        os.remove(f)
                        continue
                startMs, endMs = findLogFileTimes(f)
                if startMs is None or endMs is None: continue # invalid file
                startDateTime = createDay + timedelta(milliseconds = startMs)
                endDateTime = createDay + timedelta(milliseconds = endMs)
                newFileDict[f] = (startDateTime, endDateTime)
                print("File", f, "Start", startDateTime, "End", endDateTime)
        RaidTool.logFileDict = newFileDict
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
                    print(raidData['FileID'], '->', logPath)
                    raidData['Dependencies'].append(logPath)

        return raidList

    def retrieve(self, fileID, targetPathString = None, anonymize = False) -> bool:
        if targetPathString:
            targetPath = pathlib.Path(targetPathString)
        else:
            targetPath = pathlib.Path(self.getLocalFile(fileID))

        cmd = self.raidCommand(f'-m {fileID} -o "{str(targetPath)}" -D -T {TRANSFER_COMMAND_TIMEOUT}', anonymize=anonymize)
        print(cmd)
        if MOCK:
            time.sleep(1)
            return True

        targetPath.parent.mkdir(parents = True, exist_ok = True)

        procOutput = runCommand(cmd, TRANSFER_COMMAND_TIMEOUT + 2)
        if procOutput.returncode != 0: return False
        # finally, check if file was correctly created
        return targetPath.is_file()

    def fileRetrieved(self, fileID):
        return os.path.isfile(self.getLocalFile(fileID))

    # returns the location/name of the local retrieved file, given the ID
    def getLocalFile(self, fileID):
        return os.path.join(self.tmpDir, f'{fileID}.dat')

