#!/usr/bin/env python
"""
Generate histograms/bar plots to look at the distribution of heights, widths, track lengths, sum, etc columns of a molecule list.
Note : the molecule list is assumed to be in csv format, converted from bin -> txt by Insight3 and txt -> csv using pandas.

Gayatri 06/20
"""
import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import numpy

# Change directory
os.chdir("D:/new-storm-data/06-13-20_analysis/1_3_brain_movies")

if (__name__ == "__main__"):

    mlists = sorted(glob.glob('new_1_*.txt')) # Enter movie name format

    for mlist in mlists:
        df = pd.read_csv(mlist,sep='\t')
        file_name = mlist.rsplit('.txt',1)[0][:]
        # Save as .csv file for future reference 
        df.to_csv(file_name+'.csv',index=False)

        # Save mean values to a txt file
        print(df.mean(),file=open('stats_'+file_name+'.txt', "a"))

        # Plot the distribution of track lengths
        track_lengths = df['Length'].value_counts()
        print('Track lengths : ')
        print(track_lengths)
        plt.figure(figsize = (8,8))
        df['Length'].value_counts().sort_index().head().plot(kind="bar", grid=True, rot=0, color='thistle')
        # plt.ylim([0, 250000])
        plt.title('Track lengths for '+ file_name)
        plt.ylabel('No. of molecules')
        plt.xlabel('Track length in frames')
        plt.savefig('track_lengths_'+ file_name)
        # plt.show()

        # Plot the ditribution of peak heights

        h_max = df['Height'].max()
        bins = numpy.arange(0, h_max+1000, 50)
        plt.figure(figsize = (8,8))
        d1 = plt.hist(df['Height'], bins=bins, alpha=0.5, density= False, edgecolor='grey', linewidth=0.8, color='teal')
        plt.xlim([0, 4000])
        # plt.ylim([0, 100000])
        plt.title('Histogram of Heights for '+file_name)
        plt.ylabel('No. of molecules')
        plt.xlabel('Heights')
        plt.savefig('heights_'+file_name)
        # plt.show()

        # Plot the ditribution of background values

        bg_max = df['BG'].max()
        bins_bg = numpy.arange(0, bg_max+1000, 20)
        plt.figure(figsize = (8,8))
        d2 = plt.hist(df['BG'], bins=bins_bg, alpha=0.5, density= False, edgecolor='grey', linewidth=0.8, color='goldenrod')
        plt.xlim([0, 1500])
        # plt.ylim([0, 35000])
        plt.title('Histogram of Background values for '+ file_name)
        plt.ylabel('No. of molecules')
        plt.xlabel('Background')
        plt.savefig('background_'+file_name)
        # plt.show()

        # Plot the histogram of widths

        w_max = df['Width'].max()
        bins_w = numpy.arange(0, w_max+100, 10)
        plt.figure(figsize = (8,8))
        d3 = plt.hist(df['Width'], bins=bins_w, alpha=0.5, density= False, edgecolor='grey', linewidth=0.8, color='crimson')
        # plt.ylim([0, 16000])
        plt.title('Histogram of Widths for '+ file_name)
        plt.ylabel('No. of molecules')
        plt.xlabel('Width in nm')
        plt.savefig('widths_'+file_name)
        # plt.show()

        # Plot the histogram of areas

        area_max = df['Area'].max()
        bins_area = numpy.arange(0, area_max+1000, 200)
        plt.figure(figsize = (8,8))
        d4 = plt.hist(df['Area'], bins=bins_area, alpha=0.5, density= False, edgecolor='grey', linewidth=0.8, color='dimgrey')
        plt.xlim([0, 35000])
        # plt.ylim([0, 40000])
        plt.title('Histogram of Areas for '+ file_name)
        plt.ylabel('No. of molecules')
        plt.xlabel('Area in nm2')
        plt.savefig('areas_'+file_name)
        # plt.show()

        # Plot the histogram of photon counts

        i_max = df['I'].max()
        bins_i = numpy.arange(0, i_max+1000, 500)
        plt.figure(figsize = (8,8))
        d5 = plt.hist(df['I'], bins=bins_i, alpha=0.5, density= False, edgecolor='grey', linewidth=0.8, color='forestgreen')
        plt.xlim([0, 50000])
        # plt.ylim([0, 40000])
        plt.title('Distribution of Intensity for '+ file_name)
        plt.ylabel('No. of molecules')
        plt.xlabel('Intensity')
        plt.savefig('Intensity_'+file_name)
        # plt.show()

        # Plot height vs width scatter plot

        plt.figure(figsize = (8,8))
        d6 = plt.scatter(df['Width'], df['Height'], s=10, alpha=0.5, c='teal')
        plt.xlim([0, 800])
        plt.ylim([0, 9000])
        plt.title('Heights vs Widths')
        plt.ylabel('Heights')
        plt.xlabel('Widths in nm')
        plt.savefig('heights_vs_widths_'+file_name)
        # plt.show()



