#!/usr/bin/python
#
# Finds "all" the peaks in an image.
#
# Hazen 03/13
#

import numpy
import scipy
import scipy.ndimage

import sa_library.daxwriter as daxwriter
import multi_c
import util_c


# Class for storing fit data.
class FitData:
    def __init__(self, image, parameters, background = -1, margin = 10, neighborhood = 5.0, new_peak_radius = 1.0):

        # Pad out the image so that we can analyze peaks near the
        # edge without having to add a mess of if statements to
        # the C peak fitting code.
        pad_size = 10
        [x_size, y_size] = image.shape
        lg_image = numpy.ones((x_size+2*pad_size,y_size+2*pad_size))
        lg_image[pad_size:(x_size+pad_size),pad_size:(y_size+pad_size)] = image.astype(numpy.float64)
        lg_image[0:pad_size,:] = numpy.flipud(lg_image[pad_size:2*pad_size,:])
        lg_image[(x_size+pad_size):(x_size+2*pad_size),:] = numpy.flipud(lg_image[x_size:(x_size+pad_size),:])
        lg_image[:,0:pad_size] = numpy.fliplr(lg_image[:,pad_size:2*pad_size])
        lg_image[:,(y_size+pad_size):(y_size+2*pad_size)] = numpy.fliplr(lg_image[:,y_size:(y_size+pad_size)])

        # Create mask to limit peak finding to a user defined sub-region of the image.
        self.peak_mask = numpy.ones((x_size+2*pad_size,y_size+2*pad_size))
        if hasattr(parameters, "x_start"):
            self.peak_mask[0:parameters.x_start,:] = 0.0
        if hasattr(parameters, "x_stop"):
            self.peak_mask[parameters.x_stop:-1,:] = 0.0
        if hasattr(parameters, "y_start"):
            self.peak_mask[:,0:parameters.y_start] = 0.0
        if hasattr(parameters, "y_stop"):
            self.peak_mask[:,parameters.y_stop:-1] = 0.0

        if hasattr(parameters, "background"):
            if (parameters.background<0):
                self.background = numpy.mean(image)
            else:
                self.background = parameters.background
        else:
            self.background = numpy.mean(image)

        # Current new peak minimum threshold.
        if(parameters.iterations>4):
            self.cur_threshold = 4.0*parameters.threshold              
        else:
            self.cur_threshold = float(parameters.iterations)*parameters.threshold

        self.cutoff = self.background + self.cur_threshold             # Threshold for peak identification.
        self.find_max_radius = 5                                       # Radius (in pixels) over which the maxima is maximal.
        self.image = lg_image                                          # The padded image.
        self.margin = margin                                           # Size of the unanalyzed "edge" around the image.
        self.neighborhood = parameters.sigma*neighborhood              # Radius for marking neighbors as unconverged.
        self.new_peak_radius = new_peak_radius                         # Minimum allowed distance between new peaks and current peaks.
        self.pad_size = float(pad_size)                                # Keep track of the size of the pad around the image.
        self.peaks = False                                             # The current list of peaks.
        self.proximity = 5.0                                           # Minimum distance between two newly added peaks.
        self.residual = self.image                                     # Image residual after subtracting current peaks.
        self.sigma = parameters.sigma                                  # Peak sigma (in pixels).
        self.taken = numpy.zeros((self.image.shape),dtype=numpy.int32) # Spots in the image where a peak has already been added.
        self.threshold = parameters.threshold                          # Peak minimum threshold (height, in camera units).
        #print lg_image.shape, self.image.shape, self.residual.shape


# Does the fitting given initial estimates for the image
# background, a peak finding threshold and the psf sigma.
def doFit(fit_function, fit_data, max_iterations):

    save_residual = False
    if save_residual:
        resid_dax = daxwriter.DaxWriter("./testing/residual.dax",
                                        fit_data.image.shape[0],
                                        fit_data.image.shape[1])

    for i in range(max_iterations):
        if save_residual:
            resid_dax.addFrame(fit_data.residual)
        done = findPeaks(fit_data)
        fit_function(fit_data)
        updateBackgroundCutoff(fit_data)

        if not(done):
            break
        
        #cutoff = background + threshold * std

    if save_residual:
        resid_dax.close()

    if (type(fit_data.peaks) == type(numpy.array([]))):
        fit_data.peaks[:,util_c.getXCenterIndex()] -= fit_data.pad_size
        fit_data.peaks[:,util_c.getYCenterIndex()] -= fit_data.pad_size

    # TODO: a final phase of refitting after removal of bad peaks?
    return [fit_data.peaks, fit_data.residual]

# Does fixed sigma peak fitting.
def doFit2DFixed(fit_data, iterations):
    results = doFit(iterateFit2DFixed, fit_data, iterations)
    return results

# Does variable sigma peak fitting.
def doFit2D(fit_data, iterations):
    results = doFit(iterateFit2D, fit_data, iterations)
    return results

# Does variable sigma (in x and y) peak fitting.
def doFit3D(fit_data, iterations):
    results = doFit(iterateFit3D, fit_data, iterations)
    return results

# Does z peak fitting.
def doFitZ(fit_data, iterations):
    results = doFit(iterateFitZ, fit_data, iterations)
    return results

# Estimates the background.
def estimateBackground(image, size = 8):
    background = scipy.ndimage.filters.gaussian_filter(image, (size, size))
    return background

# Finds the peaks in an image & adds to the current list of peaks.
def findPeaks(fit_data):

    # Identify local maxima in the (residual) of the current image.
    masked_residual = fit_data.residual * fit_data.peak_mask
    [new_peaks, fit_data.taken] = util_c.findLocalMaxima(masked_residual,
                                                         fit_data.taken,
                                                         fit_data.cutoff,
                                                         fit_data.find_max_radius,
                                                         fit_data.background,
                                                         fit_data.sigma,
                                                         fit_data.margin)


    # Remove maxima that are too close to other newly identified (brighter) maxima.
    #new_peaks = util_c.removeClosePeaks(new_peaks, fit_data.proximity, 0.0)

    # Update new peak identification threshold (if necessary).
    # Also, while threshold is greater than min_threshold we
    # are automatically not done.
    not_done = False
    if (fit_data.cur_threshold > fit_data.threshold):
        fit_data.cur_threshold -= fit_data.threshold
        not_done = True

    # If we did not find any new peaks then we may be done.
    if (new_peaks.shape[0] == 0):
        return not_done

    # Add new peaks to the current list of peaks if it exists,
    # otherwise these peaks become the current list.
    if (type(fit_data.peaks) == type(numpy.array([]))):
        peaks = util_c.mergeNewPeaks(fit_data.peaks,
                                     new_peaks,
                                     fit_data.new_peak_radius, # should use sigma instead?
                                     fit_data.neighborhood)
        
        # If none of the new peaks are valid then we may be done.
        if (peaks.shape[0] == fit_data.peaks.shape[0]):
            return not_done
        else:
            fit_data.peaks = peaks
    else:
        fit_data.peaks = new_peaks

    return True

# Initialize parameters for Z fitting.
def initZParams(wx_params, wy_params, min_z, max_z):
    multi_c.initZParams(wx_params, wy_params, min_z, max_z)

# Performs a single iteration of peak fitting.
def iterateFit(fit_func, fit_data):

    if (type(fit_data.peaks) == type(numpy.array([]))):

        # Fit to update peak locations.
        result = fit_func(fit_data.image, fit_data.peaks)
        fit_peaks = multi_c.getGoodPeaks(result[0],
                                         0.9*fit_data.threshold,
                                         0.5*fit_data.sigma)
        
        # Remove peaks that are too close to each other & refit.
        fit_peaks = util_c.removeClosePeaks(fit_peaks, fit_data.sigma, fit_data.neighborhood)
        result = fit_func(fit_data.image, fit_peaks)
        fit_peaks = multi_c.getGoodPeaks(result[0],
                                         0.9*fit_data.threshold,
                                         0.5*fit_data.sigma)

        fit_data.peaks = fit_peaks
        fit_data.residual = result[1]

# Fixed sigma fitting.
def iterateFit2DFixed(fit_data):
    iterateFit(multi_c.fitMultiGaussian2DFixed, fit_data)

# Variable sigma fitting.
def iterateFit2D(fit_data):
    iterateFit(multi_c.fitMultiGaussian2D, fit_data)

# Variable sigma in x and y fitting.
def iterateFit3D(fit_data):
    iterateFit(multi_c.fitMultiGaussian3D, fit_data)

# Z fitting.
def iterateFitZ(fit_data):
    iterateFit(multi_c.fitMultiGaussianZ, fit_data)

# Remove unconverged peaks.
def getConvergedPeaks(peaks):
    return multi_c.getConvergedPeaks(peaks, 0.0, 0.0)

# Update background & cutoff
def updateBackgroundCutoff(fit_data):
    residual_bg = estimateBackground(fit_data.residual)
    mean_residual_bg = numpy.mean(residual_bg)
    fit_data.residual -= residual_bg
    fit_data.residual += mean_residual_bg
    fit_data.background = numpy.mean(fit_data.residual)
    fit_data.cutoff = fit_data.background + fit_data.cur_threshold
    #fit_data.cutoff = fit_data.background + fit_data.threshold * numpy.std(fit_data.residual)
    #print fit_data.cutoff


#
# The MIT License
#
# Copyright (c) 2013 Zhuang Lab, Harvard University
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
