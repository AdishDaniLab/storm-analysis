#!/usr/bin/env python
"""
Generate image averages for conventional movies.

Gayatri 09/20
"""

import os
import sys
import glob
import storm_analysis.sa_library.datareader as datareader
# import storm_analysis.sa_library.arraytoimage as arraytoimage
import tifffile
import numpy

# Change directory
# os.chdir("D:/gayatri-folder/STORM_analysis/06-07-20_extract_info_old_movies/daostorm")

if (__name__ == "__main__"):

    folder = sys.argv[1]
    os.chdir(folder)
    try: 
        os.mkdir('tiffs') 
    except OSError as error: 
        print(error) 
    convs = sorted(glob.glob('conv*.dax')) # Enter movie name format

    for file in convs:
        file_name = file.rsplit('.dax',1)[0][:]
        img = datareader.DaxReader(file).averageFrames()
        with tifffile.TiffWriter('tiffs/'+file_name+'_avg.tif') as tf:
            tf.save(img.astype(numpy.float32))
            # imsave('temp.tif', data, compress=6, metadata={'axes': 'TZCYX'})
        
        
    
