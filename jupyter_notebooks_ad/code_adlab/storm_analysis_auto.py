import os
import numpy
import glob
import matplotlib.pyplot as plt
import glob
import time

import storm_analysis.daostorm_3d.mufit_analysis as mFit
# import storm_analysis.sa_utilities.hdf5_to_bin as hdf5ToBin

# Change directory
os.chdir("/home/gayatri/storm-data/daostorm-analysis-folder")

# Create analysis settings file if required.



if (__name__ == "__main__"):

    start_time = time.time()
    movies = sorted(glob.glob('storm_0007.dax'))
    for movie in movies :
        movie_name = movie.rsplit('.dax',1)[0][:] #Edit this!!
        print('Analyzing ', movie_name)
        h5 = movie_name+'_daostorm.hdf5'
        if os.path.exists(h5):
            os.remove(h5)
        mFit.analyze(movie, h5, "analysis_settings_"+movie_name+".xml")
        
    print("--- %s seconds ---" % (time.time() - start_time)