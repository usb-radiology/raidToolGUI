#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 10 15:50:57 2020

@author: francesco
"""

import yaml
from raidTool import RaidTool
from agora import AgoraUploader
from driveUploader import DriveUploader

CONFIG_FILE = 'config.yml'


def initFromConfig():
    with open(CONFIG_FILE, 'r') as yf:
        config = yaml.load(yf, Loader=yaml.FullLoader)

    raidConfigDict = config['Raid']
    raidTool = RaidTool(**raidConfigDict)

    ruleList = config['Rules']

    targetsDict = config['Targets']

    # solve inheritances in place
    def solveInheritances(target: dict):
        if 'Inherit' not in target: return

        base = targetsDict[target['Inherit']]

        # first make sure that the base does not have any inheritances
        solveInheritances(base)

        for key, value in base.items():
            if key not in target:
                target[key] = value # keep the base inheritance

        del target['Inherit']

    targetObjectsDict = {}

    for key,target in targetsDict.items():
        solveInheritances(target)
        if target['Type'] == 'Agora':
            targetObjectsDict[key] = AgoraUploader(agoraIP = target['IP'],
                                                   projectName = target['ProjectName'],
                                                   folderName = target['FolderName'],
                                                   apiID = target['ApiID'])
        elif target['Type'] == 'Drive':
            targetObjectsDict[key] = DriveUploader(drivePath = target.get('DrivePath'), # get returns None if no key is found
                                                   folderPath = target.get('FolderPath'),
                                                   connectCommand = target.get('ConnectCommand'),
                                                   disconnectCommand = target.get('DisconnectCommand'),
                                                   driveRegex = target.get('DriveRegex'),
                                                   filePattern = target.get('FilePattern'),
                                                   skipTemp = target.get('SkipTemp') or False,
                                                   anonymize= target.get('Anonymize') or False)
        else:
            print("Warning! Unknown target type!")

    globalConfig = config['Global']

    return raidTool, targetObjectsDict, ruleList, globalConfig