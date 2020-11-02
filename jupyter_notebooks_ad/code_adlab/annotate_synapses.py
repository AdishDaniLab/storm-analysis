#!/usr/bin/env python
"""
Annotate synapses in conventional image for easy cropping.

Gayatri 11/20
"""

import os
import glob
import numpy
import matplotlib.pyplot as plt
import pandas as pd
import tifffile

import storm_analysis.daostorm_3d.mufit_analysis as mFit
import storm_analysis.sa_utilities.hdf5_to_txt as hdf5ToTxt
import storm_analysis.sa_library.datareader as datareader

# Change directory
os.chdir("D:/new-storm-data/cochlea/exp-6-p15-9-Oct/F2-20-10-12-set1-ribA-single/tiffs")

if (__name__ == "__main__"):

    convs = sorted(glob.glob('conv*avg.png')) # Enter movie name format
    
    # Do peak finding for averaged conventional images. 
    for file in convs:
        file_name = file.rsplit('.tif',1)[0][:]
        h5 = file_name + '.hdf5'
        if os.path.exists(h5):
            os.remove(h5)
        mFit.analyze(file, h5, "analysis_settings_conv.xml")
        hdf5ToTxt.hdf5ToTxt(h5, file_name + '.csv')

    # Overlay bounding boxes on detected peaks.
    for file in convs:
        file_name = file.rsplit('.png',1)[0][:]
        im = plt.imread(file)
        
        df = pd.read_csv(file_name + '.csv', usecols=['index','sum', 'x', 'y'])
        fig, ax = plt.subplots()
        implot = plt.imshow(im, cmap='gray')
        plt.scatter(df['x'],df['y'], marker="s", s=150, facecolors='none', edgecolors='white')
        for i, txt in enumerate(df['index']):
            ax.annotate(txt+1, (df['x'][i], df['y'][i]), color='white', size=8, xytext=(2, 7), textcoords='offset points')
        plt.axis('off')
        plt.savefig(file_name+'_marked.png', bbox_inches = 'tight', pad_inches = 0)


    


