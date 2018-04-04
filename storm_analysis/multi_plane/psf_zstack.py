#!/usr/bin/env python
"""
Given a movie and list of locations (the output of
multi_plane.psf_localizations), generate an average
z stack.

The average z stack results are in units of photo-electrons.

FIXME: Averaging should be done with weighting by pixel 
       variance?

FIXME: Drift correction, if specified, is not corrected for 
       the channel to channel mapping.

Hazen 05/17
"""

import numpy
import scipy
import scipy.ndimage
import tifffile

import storm_analysis.sa_library.analysis_io as analysisIO
import storm_analysis.sa_library.datareader as datareader
import storm_analysis.sa_library.sa_h5py as saH5Py
import storm_analysis.spliner.measure_psf_utils as measurePSFUtils


def psfZStack(movie_name, h5_filename, zstack_name, scmos_cal = None, aoi_size = 8, driftx = 0.0, drifty = 0.0):
    """
    driftx, drifty are in units of pixels per frame, (bead x last frame - bead x first frame)/n_frames.
    """

    # Load movie.
    movie_data = datareader.inferReader(movie_name)
    [movie_x, movie_y, movie_len] = movie_data.filmSize()
    
    # Load localizations.
    with saH5Py.SAH5Py(h5_filename) as h5:
        locs = h5.getLocalizations()
        x = locs["y"] + 1
        y = locs["x"] + 1

    # Load sCMOS calibration data.
    gain = numpy.ones((movie_y, movie_x))
    offset = numpy.zeros((movie_y, movie_x))
    if scmos_cal is not None:
        [offset, variance, gain] = analysisIO.loadCMOSCalibration(scmos_cal)
        gain = 1.0/gain
    
    z_stack = numpy.zeros((4*aoi_size, 4*aoi_size, movie_len))

    for i in range(movie_len):
        if ((i%50) == 0):
            print("Processing frame", i)

        #
        # Subtract pixel offset and convert to units of photo-electrons.
        #
        frame = (movie_data.loadAFrame(i) - offset) * gain

        #
        # Subtract estimated background. This assumes that the image is
        # mostly background and that the background is uniform.
        #
        frame = frame - numpy.median(frame)

        for j in range(x.size):
            xf = x[j] + driftx * float(i)
            yf = y[j] + drifty * float(i)

            im_slice_up = measurePSFUtils.extractAOI(frame, aoi_size, xf, yf)

            z_stack[:,:,i] += im_slice_up

    # Normalize by the number of localizations.
    z_stack = z_stack/float(x.size)
    
    print("max intensity", numpy.amax(z_stack))

    # Save z_stack.
    numpy.save(zstack_name + ".npy", z_stack)

    # Save (normalized) z_stack as tif for inspection purposes.
    z_stack = z_stack/numpy.amax(z_stack)
    z_stack = z_stack.astype(numpy.float32)
    with tifffile.TiffWriter(zstack_name + ".tif") as tf:
        for i in range(movie_len):
            tf.save(z_stack[:,:,i])

            
if (__name__ == "__main__"):

    import argparse

    parser = argparse.ArgumentParser(description = 'Average AOIs together into a z-stack for PSF measurement.')

    parser.add_argument('--movie', dest='movie', type=str, required=True,
                        help = "The name of the movie, can be .dax, .tiff or .spe format.")
    parser.add_argument('--bin', dest='mlist', type=str, required=True,
                        help = "The name of the localizations psf file.")
    parser.add_argument('--zstack', dest='zstack', type=str, required=True,
                        help = "The name of the file to save the zstack (without an extension).")
    parser.add_argument('--scmos_cal', dest='scmos_cal', type=str, required=False, default = None,
                        help = "The name of the sCMOS calibration data file.")    
    parser.add_argument('--aoi_size', dest='aoi_size', type=int, required=False, default=8,
                        help = "The size of the area of interest around the bead in pixels. The default is 8.")
    parser.add_argument('--driftx', dest='driftx', type=float, required=False, default=0.0,
                        help = "Drift in x in pixels per frame. The default is 0.0.")
    parser.add_argument('--drifty', dest='drifty', type=float, required=False, default=0.0,
                        help = "Drift in y in pixels per frame. The default is 0.0.")

    args = parser.parse_args()
    
    psfZStack(args.movie,
              args.mlist,
              args.zstack,
              scmos_cal = args.scmos_cal,
              aoi_size = args.aoi_size,
              driftx = args.driftx,
              drifty = args.drifty)
