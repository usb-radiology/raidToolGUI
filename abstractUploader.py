#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class AbstractUploader:

    def uploadData(self, dataPath, deleteOriginal = False, dataStructure = None):
        pass

    def close(self):
        pass
