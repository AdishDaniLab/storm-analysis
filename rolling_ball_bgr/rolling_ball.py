#!/usr/bin/env python
#
# Rolling ball background estimation.
#
# Hazen 02/16
#

import numpy
import scipy
import scipy.ndimage

import rolling_ball_lib_c as rollingBallLibC

#
# Rolling ball smoothing class.
#
class RollingBall(rollingBallLibC.CRollingBall):
    pass

if (__name__ == "__main__"):

    import sys
    
    import sa_library.datareader as datareader
    import sa_library.daxwriter as daxwriter
        
    if (len(sys.argv) != 4):
        print "usage <movie> <ball radius> <smoothing sigma>"
        exit()

    input_movie = datareader.inferReader(sys.argv[1])
    output_dax = daxwriter.DaxWriter("subtracted.dax", 0, 0)    

    rb = RollingBall(float(sys.argv[2]), float(sys.argv[3]))
        
    for i in range(input_movie.filmSize()[2]):

        if((i%10) == 0):
            print "Processing frame", i

        image = input_movie.loadAFrame(i) - 100

        if 0:
            image = image.astype(numpy.float)
            lowpass = scipy.ndimage.filters.gaussian_filter(image, float(sys.argv[2]))
            sub = image - lowpass
            
        else:
            sub = rb.removeBG(image)
            
        output_dax.addFrame(sub + 100)

    output_dax.close()

