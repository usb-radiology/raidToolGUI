#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 15:50:48 2020

@author: francesco
"""

import os
import os.path
import subprocess
import re

driveByNameAvailable = True
try:
    from win32api import GetLogicalDriveStrings, GetVolumeInformation
except:
    # findDriveByName is not working if win32api doesn't exist
    print("win32api not found. Can't locate drive by name")
    driveByNameAvailable = False

if driveByNameAvailable:
    def findDriveByName(driveRegex):
        drives = GetLogicalDriveStrings().split('\x00')
        for drivePath in drives:
            if not drivePath: continue
            driveName = GetVolumeInformation(drivePath)[0]
            m = re.match('^' + driveRegex + '$', driveName)
            if m: return drivePath
        return None

else:
    def findDriveByName(driveRegex):
        return None

from pathlib import Path
import shutil
import time

from abstractUploader import AbstractUploader

MOCK = False
try:
    import __main__
    MOCK = __main__.MOCK
except:
    pass

print("Agora - Mock?", MOCK)

def runCommand(cmd):
    if MOCK:
        print(cmd)
        return
    else:
        out = subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return (out.returncode == 0)

def translatePattern(pattern, dataStructure):
    replaceDict = {
            '%FileID%': dataStructure['FileID'],
            '%MeasID%': dataStructure['MeasID'],
            '%PatName%': dataStructure['Pat'],
            '%ProtName%': dataStructure['Prot'],
            '%CreateTime%': dataStructure['CreateTime'].strftime('%Y%m%d%H%M%S')
        }
    for key, rep in replaceDict.items():
        pattern = pattern.replace(key, rep)

    return pattern


class DriveUploader(AbstractUploader):

    def __init__(self, drivePath = None, folderPath = None, connectCommand = None, disconnectCommand = None, driveRegex = None, filePattern = None, skipTemp = False):
        assert drivePath or driveRegex # there must either be a fixed path or a drive name
        self.drivePath = drivePath
        if folderPath is None:
            self.folderPath = ''
        else:
            self.folderPath = folderPath
        self.connectCommand = connectCommand
        self.disconnectCommand = disconnectCommand
        self.driveRegex = driveRegex
        self.filePattern = filePattern
        self.skipTemp = skipTemp

    def skipTemp(self):
        return self.skipTemp

    def uploadData(self, raidObj, fileID, deleteOriginal = False, dataStructure = None):
        if MOCK:
            time.sleep(1)
            print("Uploading", fileID)
            return True

        if self.drivePath: # This is either a fixed drive or a samba share
            drivePath = self.drivePath
            if not os.path.exists(drivePath):
                if not self.connectCommand:
                    print("Drive doesn't exist and can't be mounted")
                    return False
                if not runCommand(self.connectCommand):
                    print("Error mounting remote drive!")
                    return False
        else:
            # this must be a removeable drive: search by name
            drivePath = findDriveByName(self.driveRegex)
            if not drivePath:
                print('Drive not connected')
                return False

        remotePath = Path(drivePath, self.folderPath)

        if dataStructure and self.filePattern:
            remoteFileName = translatePattern(self.filePattern, dataStructure)
        else:
            remoteFileName = f'{fileID}.dat'

        remotePath /= remoteFileName

        # make sure that file is retrieved, unless we are skipping the temporary file creation
        if not self.skipTemp and not raidObj.fileRetrieved(fileID):
            raidObj.retrieve(fileID)

        if not raidObj.fileRetrieved(fileID):
            raidObj.retrieve(fileID, str(remotePath)) # retrieve file now, directly to target
        else:
            dataPath = raidObj.getLocalFile(fileID)
            data = Path(dataPath)

            # remotepath is a file. Create its parent if needed
            try:
                remotePath.parent.mkdir(parents = True, exist_ok = True)
            except:
                return False


            print(f'Copying {str(data)} to {str(remotePath)}')

            try:
                shutil.copy(data, remotePath)
            except:
                return False

            # delete original file upon completion
            if deleteOriginal: data.unlink()

        # copy dependencies
        try:
            deps = dataStructure['Dependencies']
        except:
            deps = []
        if deps:
            depDir = remotePath.with_name( remotePath.name + '.deps' )
            try:
                depDir.mkdir(parents = True, exist_ok = True)
            except:
                return False
            for dep in deps:
                shutil.copy(dep, depDir)

        return True

    def close(self):
        if MOCK: return
        if self.disconnectCommand and os.path.exists(self.drivePath): runCommand(self.disconnectCommand)