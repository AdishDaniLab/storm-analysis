#!/usr/bin/env python
"""
Pupil function peak fitting.

Hazen 10/17
"""

import pickle
import numpy

import tifffile

import storm_analysis.sa_library.fitting as fitting
import storm_analysis.sa_library.ia_utilities_c as utilC
import storm_analysis.sa_library.matched_filter_c as matchedFilterC

import storm_analysis.pupilfn.pupil_fit_c as pupilFitC
import storm_analysis.pupilfn.pupil_fn as pupilFn


def initFitter(finder, parameters, pupil_fn):
    """
    Initialize and return a pupilFitC.CPupilFit object.
    """
    # Load variance, scale by gain.
    #
    # Variance is in units of ADU*ADU.
    # Gain is ADU/photo-electron.
    #
    variance = None
    if parameters.hasAttr("camera_calibration"):
        [offset, variance, gain] = numpy.load(parameters.getAttr("camera_calibration"))
        variance = variance/(gain*gain)

        # Set variance in the peak finder, this method also pads the
        # variance to the correct size.
        variance = finder.setVariance(variance)

    # Get fitting Z range.
    [min_z, max_z] = parameters.getZRange()

    # Create C fitter object.
    return pupilFitC.CPupilFit(pupil_fn = pupil_fn, scmos_cal = variance)


def initFindAndFit(parameters):
    """
    Initialize and return a fitting.PeakFinderFitter object.
    """
    # Create pupil function object.
    [min_z, max_z] = parameters.getZRange()
    pupil_fn = pupilFn.PupilFunction(pf_filename = parameters.getAttr("pupil_function"),
                                     zmin = min_z * 1000.0,
                                     zmax = max_z * 1000.0)

    # PSF debugging.
    if False:
        tifffile.imsave("pupil_fn_psf.tif", pupil_fn.getPSF(0.1).astype(numpy.float32))

    # Check that the PF and camera pixel sizes agree.
    diff = abs(parameters.getAttr("pixel_size") - pupil_fn.getPixelSize()*1.0e3)
    assert (diff < 1.0e-6), "Incorrect pupil function?"
    
    # Create peak finder.
    finder = fitting.PeakFinderArbitraryPSF(parameters = parameters,
                                            psf_object = pupil_fn)

    # Create cubicFitC.CSplineFit object.
    mfitter = initFitter(finder, parameters, pupil_fn)
    
    # Create peak fitter.
    fitter = fitting.PeakFitterArbitraryPSF(mfitter = mfitter,
                                            parameters = parameters)
    
    # Specify which properties we want from the analysis.
    properties = ["background", "error", "height", "sum", "x", "y", "z"]

    return fitting.PeakFinderFitter(peak_finder = finder,
                                    peak_fitter = fitter,
                                    properties = properties)
