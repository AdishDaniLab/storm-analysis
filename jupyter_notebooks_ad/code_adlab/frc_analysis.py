#!/usr/bin/env python
"""
Generate FRC curve to measure resolution of image.
Gayatri 07/20
"""

import os
import pandas as pd 
import matplotlib.pyplot as plt
import numpy
import glob
import scipy.signal
from scipy.interpolate import interp1d
from matplotlib.offsetbox import AnchoredText

# Change directory
os.chdir("/home/gayatri/storm-data/frc_resolution")

if (__name__ == "__main__"):
    
    # Load the frc results file obtained using storm_analysis/frc/frc_calc2d.py

    # frc_result = 'frc_result_corti.txt'
    frc_results = sorted(glob.glob('frc_result_*.txt'))
    for frc_result in frc_results:

        file_name = frc_result.rsplit('.txt',1)[0][:]
        df = pd.read_csv(frc_result, sep=' ', header=None)
        df.columns = ['xvals', 'frc']

        # The x axis will contain spatial frequencies and y axis correlation

        # Convert columns to numpy arrays
        xdata = df['xvals'].to_numpy()
        ydata =  df['frc'].to_numpy()

        # Do interpolation
        f = interp1d(xdata, ydata, kind='cubic')

        # Define a new x axis with double the number of samples, for better resolution
        xnew = numpy.linspace(numpy.amin(xdata), numpy.amax(xdata), num=2000, endpoint=True)

        # Apply a filter to get the approximate curve
        yhat = scipy.signal.savgol_filter(f(xnew), 101, 1) # window size 51, polynomial order 3

        # Define the threshold correlation at which the inverse of spatial frequency gives resolution.
        a = 0.143
        index = (numpy.abs(yhat-a)).argmin()
        print(numpy.round(1/xnew[index], 1))
        res = str(numpy.round(1/xnew[index], 1))
    
        # Generate a graph showing the frc curve, fit, and calculated resolution.
        fig, ax = plt.subplots(figsize = (8,8))
    
        d2 = plt.plot(xdata, f(xdata), color='orange')
        d3 = plt.axhline(y=0.143, xmin=0, xmax=1,  linestyle='--',  color='burlywood')
        d4 = plt.plot(xnew, yhat, color='red')
        plt.grid(color='b', ls = '-.', lw = 0.25)
        plt.xlim([0.0, numpy.amax(xdata)])
        plt.title('FRC plot for ' + frc_result)
        plt.ylabel('Correlation')
        plt.xlabel('Spatial Frequency (nm-1)')
        at = AnchoredText("Resolution = " + res + ' nm',
                        loc='upper right', prop=dict(size=12), frameon=True,
                        )
        at.patch.set_boxstyle("round,pad=0.2,rounding_size=0.2")
        ax.add_artist(at)

        # Save image
        plt.savefig(file_name, bbox_inches = 'tight', pad_inches = 0.4)


