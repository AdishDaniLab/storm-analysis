#!/usr/bin/env python
"""
To compare photon count distribution between movies using horizontal box plots.
Gayatri 08/20
"""

import os
import numpy
import pandas as pd
import matplotlib.pyplot as plt

# Change directory
os.chdir("/home/gayatri/storm/flow-chamber-exp-1/")

if (__name__ == "__main__"):

    background_1 = 'test-5/background_0004_647_daostorm.csv'
    background_2 = 'test-6/background_0004_647_daostorm.csv'

    df_1 = pd.read_csv(background_1)
    df_2 = pd.read_csv(background_2)

    fig, ax = plt.subplots(figsize = (8,8))
    df_1.boxplot(column=['sum'])
    # plt.xlim([0, 8000])
    # plt.ylim([0, 500])
    plt.ylabel('Photon sum')
    plt.xlabel('Laser power')
    plt.title('Photons per molecule')
    plt.savefig('photon_sum')
    plt.show()

