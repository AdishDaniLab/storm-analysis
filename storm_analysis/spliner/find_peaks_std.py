#!/usr/bin/env python
"""
Cubic spline peak finder.

Hazen 03/16
"""

import pickle
import numpy

import tifffile

import storm_analysis.sa_library.fitting as fitting
import storm_analysis.sa_library.ia_utilities_c as utilC
import storm_analysis.sa_library.matched_filter_c as matchedFilterC

import storm_analysis.spliner.cubic_fit_c as cubicFitC
import storm_analysis.spliner.spline_to_psf as splineToPSF


class SplinerPeakFinder(fitting.PeakFinderArbitraryPSF):
    """
    Spliner peak finding.
    """
    def __init__(self, parameters = None, **kwds):
        kwds["parameters"] = parameters
        super(SplinerPeakFinder, self).__init__(**kwds)
        
        # Load the spline.
        self.psf_object = splineToPSF.loadSpline(parameters.getAttr("spline"))

        # Update margin based on the spline size.
        old_margin = self.margin
        self.margin = int((self.psf_object.getSize() + 1)/4 + 2)

        self.fg_mfilter_zval = parameters.getAttr("z_value", [0.0])
        for zval in self.fg_mfilter_zval:
            self.z_values.append(self.psf_object.getScaledZ(zval))

        if parameters.hasAttr("peak_locations"):

            # Correct for any difference in the margins.
            self.peak_locations[:,utilC.getXCenterIndex()] += self.margin - old_margin
            self.peak_locations[:,utilC.getYCenterIndex()] += self.margin - old_margin

            # Provide the "correct" starting z value.
            self.peak_locations[:,utilC.getZCenterIndex()] = self.z_value[0]


class SplinerPeakFitter(fitting.PeakFitter):
    """
    Spliner peak fitting.
    """
    def __init__(self, **kwds):
        super(SplinerPeakFitter, self).__init__(**kwds)

        # Update refitting neighborhood parameter.
        self.neighborhood = int(0.25 * self.mfitter.getSize()) + 1
        
    # Convert from spline z units to real z units.
    def rescaleZ(self, peaks):
        return self.mfitter.rescaleZ(peaks)
        

class SplinerFinderFitter(fitting.PeakFinderFitter):
    """
    Class for spline based peak finding and fitting.
    """
    def getConvergedPeaks(self, peaks):
        converged_peaks = super(SplinerFinderFitter, self).getConvergedPeaks(peaks)
        return self.peak_fitter.rescaleZ(converged_peaks)


def initFitter(finder, parameters):
    """
    Initialize and return a cubicFitC.CSplineFit object.
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

    # Load spline and create the appropriate type of spline fitter.
    with open(parameters.getAttr("spline"), 'rb') as fp:
        psf_data = pickle.load(fp)

    # If this is a 3D spline, get the range it covers in microns.
    if(psf_data["type"] == "3D"):
        min_z = psf_data["zmin"]/1000.0
        max_z = psf_data["zmax"]/1000.0
            
    spline = psf_data["spline"]
    coeff = psf_data["coeff"]

    # Create C fitter object.
    if (len(spline.shape) == 2):
        return cubicFitC.CSpline2DFit(scmos_cal = variance,
                                      spline_vals = spline,
                                      coeff_vals = coeff)
    else:
        return cubicFitC.CSpline3DFit(scmos_cal = variance,
                                      spline_vals = spline,
                                      coeff_vals = coeff,
                                      min_z = min_z,
                                      max_z = max_z)
    
def initFindAndFit(parameters):
    """
    Initialize and return a SplinerFinderFitter object.
    """
    # Create peak finder.
    finder = SplinerPeakFinder(parameters = parameters)

    # Create cubicFitC.CSplineFit object.
    mfitter = initFitter(finder, parameters)
    
    # Create peak fitter.
    fitter = SplinerPeakFitter(mfitter = mfitter,
                               parameters = parameters)

    return SplinerFinderFitter(peak_finder = finder,
                               peak_fitter = fitter)    
