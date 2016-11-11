#!/usr/bin/python
#
# sCMOS peak finder.
#
# Hazen 01/14
#

import numpy

import storm_analysis.sa_library.fitting as fitting
import storm_analysis.sa_library.ia_utilities_c as utilC
import storm_analysis.sa_library.dao_fit_c as daoFitC

import storm_analysis.sCMOS.scmos_utilities_c as scmosUtilitiesC


#
# Load sCMOS data.
#
def loadSCMOSData(calibration_filename, margin):

    # Load camera calibration data.
    [offset, variance, gain] = numpy.load(calibration_filename)

    # Pad out camera calibration data to the final image size.
    lg_offset = fitting.padArray(offset, margin)
    lg_variance = fitting.padArray(variance, margin)
    lg_gain = fitting.padArray(gain, margin)

    return [lg_offset, lg_variance, lg_gain]


#
# sCMOS peak finding.
#
class SCMOSPeakFinder(fitting.PeakFinder):

    def __init__(self, parameters):
        fitting.PeakFinder.__init__(self, parameters)
        
        # Create image smoother object.
        [lg_offset, lg_variance, lg_gain] = loadSCMOSData(parameters.camera_calibration,
                                                          fitting.PeakFinderFitter.margin)
        self.smoother = scmosUtilitiesC.Smoother(lg_offset, lg_variance, lg_gain)

    def peakFinder(self, image):

        # Calculate convolved image, this is where the background subtraction happens.
        smooth_image = self.smoother.smoothImage(image, self.sigma)

        # Mask the image so that peaks are only found in the AOI.
        masked_image = smooth_image * self.peak_mask
        
        # Identify local maxima in the masked image.
        [new_peaks, self.taken] = utilC.findLocalMaxima(masked_image,
                                                        self.taken,
                                                        self.cur_threshold,
                                                        self.find_max_radius,
                                                        self.margin)

        # Fill in initial values for peak height, background and sigma.
        new_peaks = utilC.initializePeaks(new_peaks,         # The new peaks.
                                          self.image,        # The original image.
                                          self.background,   # The current estimate of the background.
                                          self.sigma,        # The starting sigma value.
                                          self.z_value)      # The starting z value.
        
        return new_peaks

    def subtractBackground(self, image, bg_estimate):

        # Use provided background estimate.
        if bg_estimate is not None:
            self.background = bg_estimate

        # Estimate the background from the current (residual) image.
        else:
            self.background = self.backgroundEstimator(image)

        #
        # Just return the image as peakFinder() will do a background subtraction by
        # convolution and we don't want to make things complicated by also doing that here.
        #
        return image


#
# sCMOS peak fitting.
#
class SCMOSPeakFitter(fitting.PeakFitter):

    def __init__(self, parameters):
        fitting.PeakFitter.__init__(self, parameters)

        # Create image regularizer object & calibration term for peak fitting.
        [lg_offset, lg_variance, lg_gain] = loadSCMOSData(parameters.camera_calibration,
                                                          fitting.PeakFinderFitter.margin)
        self.scmos_cal = lg_variance/(lg_gain*lg_gain)
        self.regularizer = scmosUtilitiesC.Regularizer(lg_offset, lg_variance, lg_gain)

    def fitPeaks(self, peaks):
        [fit_peaks, residual] = fitting.PeakFitter.fitPeaks(self, peaks)
        residual = self.regularizer.deregularizeImage(residual)
        
        return [fit_peaks, residual]
        
    def newImage(self, new_image):
        reg_image = self.regularizer.regularizeImage(new_image)
        self.mfitter.newImage(reg_image)


class SCMOS2DFixedFitter(SCMOSPeakFitter):
    
    def __init__(self, parameters):
        SCMOSPeakFitter.__init__(self, parameters)
        self.mfitter = daoFitC.MultiFitter2DFixed(self.scmos_cal, self.wx_params, self.wy_params, self.min_z, self.max_z)


class SCMOS2DFitter(SCMOSPeakFitter):

    def __init__(self, parameters):
        SCMOSPeakFitter.__init__(self, parameters)
        self.mfitter = daoFitC.MultiFitter2D(self.scmos_cal, self.wx_params, self.wy_params, self.min_z, self.max_z)


class SCMOS3DFitter(SCMOSPeakFitter):

    def __init__(self, parameters):
        SCMOSPeakFitter.__init__(self, parameters)
        self.mfitter = daoFitC.MultiFitter3D(self.scmos_cal, self.wx_params, self.wy_params, self.min_z, self.max_z)

    
class SCMOSZFitter(SCMOSPeakFitter):

    def __init__(self, parameters):
        SCMOSPeakFitter.__init__(self, parameters)
        self.mfitter = daoFitC.MultiFitterZ(self.scmos_cal, self.wx_params, self.wy_params, self.min_z, self.max_z)


#
# Base class to encapsulate sCMOS peak finding and fitting.
#
class sCMOSFinderFitter(fitting.PeakFinderFitter):

    def __init__(self, parameters, peak_finder, peak_fitter):
        fitting.PeakFinderFitter.__init__(self, parameters)
        self.peak_finder = peak_finder
        self.peak_fitter = peak_fitter
        

#
# Return the appropriate type of finder and fitter.
#
def initFindAndFit(parameters):
    fitters = {'2dfixed' : SCMOS2DFixedFitter,
               '2d' : SCMOS2DFitter,
               '3d' : SCMOS3DFitter,
               'Z' : SCMOSZFitter}
    return sCMOSFinderFitter(parameters,
                             SCMOSPeakFinder(parameters),
                             fitters[parameters.model](parameters))


#
# The MIT License
#
# Copyright (c) 2016 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
