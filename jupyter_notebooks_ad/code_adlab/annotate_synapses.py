#!/usr/bin/env python
"""
Annotate synapses in conventional image for easy cropping.

Gayatri 11/20
"""

import os
import glob
import storm_analysis.sa_library.datareader as datareader
import numpy

if (__name__ == "__main__"):

    convs = sorted(glob.glob('conv*.tif')) # Enter movie name format

    for file in convs:
        file_name = file.rsplit('.dax',1)[0][:]
        img = datareader.DaxReader(file).averageFrames()

        
        
    
