#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class AbstractUploader:

    def uploadData(self, raidObj, fileID, deleteOriginal = False, dataStructure = None):
        pass

    def close(self):
        pass

    # returns whether this uploader can skip the temp storage
    def skipTemp(self):
        return False
