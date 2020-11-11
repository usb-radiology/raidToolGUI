#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul  9 15:50:48 2020

@author: francesco
"""

import os
import os.path

from gtagora import Agora
from pathlib import Path
import time

from abstractUploader import AbstractUploader

MOCK = False
try:
    import __main__
    MOCK = __main__.MOCK
except:
    pass

print("Agora - Mock?", MOCK)

class AgoraUploader(AbstractUploader):

    def __init__(self, agoraIP, projectName, folderName, apiID):
        self.agoraIP = agoraIP
        self.projectName = projectName
        self.folderName = folderName
        self.apiID = apiID

        self.agora = None

        if MOCK: return

        try:
            curNoProxy = os.environ['NO_PROXY']
            #print(curNoProxy)
            if agoraIP not in curNoProxy:
                curNoProxy += ',' + agoraIP
                #print(curNoProxy)
                os.environ['NO_PROXY'] = curNoProxy
        except:
            os.environ['NO_PROXY'] = agoraIP

    def uploadData(self, dataPath, deleteOriginal = False, dataStructure = None):
        if MOCK:
            time.sleep(1)
            print("Uploading", dataPath)
            return True
        if not self.agora: self.agora = Agora.create(f'https://{self.agoraIP}/', self.apiID)

        projects = self.agora.get_projects()
        prj = None
        if not self.projectName:
            prj = self.agora.get_myagora()
        else:
            for p in projects:
                if p.name == self.projectName:
                    prj = p
                    break

        if not prj: return False

        rootFolder = prj.get_root_folder()
        print(rootFolder.name)
        targetFolder = rootFolder.get_or_create(self.folderName)
        print(targetFolder.name)
        data = Path(dataPath)
        fileList = [data]
        try:
            deps = dataStructure['Dependencies']
        except:
            deps = []
        if deps:
            relations = { str(data): deps }
            fileList.extend( [Path(dep) for dep in deps] ) # add dependencies to upload list
        else:
            relations = {}
        try:
            ip = targetFolder.upload(fileList, relations = relations)
        except:
            return False

        complete = ip.complete()

        # delete original file upon completion
        if complete and deleteOriginal: data.unlink()

        return complete

    def close(self):
        if self.agora: self.agora.close()
        self.agora = None

#print(uploadData(agora, projectName, folderName, dataPath))
#agora.close()
