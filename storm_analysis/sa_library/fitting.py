#!/usr/bin/env python
"""
This contains some of what is common to all of the peak finding algorithms.

Hazen 03/17
"""
import numpy
import os
import tifffile

import storm_analysis.sa_library.daxwriter as daxwriter
import storm_analysis.sa_library.i3dtype as i3dtype
import storm_analysis.sa_library.ia_utilities_c as utilC
import storm_analysis.sa_library.matched_filter_c as matchedFilterC
import storm_analysis.sa_library.parameters as params
import storm_analysis.sa_library.readinsight3 as readinsight3

import storm_analysis.simulator.draw_gaussians_c as dg

#
# Functions.
#
def gaussianPSF(shape, sigma):
    """
    Return a normalized 2D Gaussian, usually used for creating MatchedFilter objects.
    """
    psf = dg.drawGaussiansXY(shape,
                             numpy.array([0.5*shape[0]]),
                             numpy.array([0.5*shape[1]]),
                             sigma = sigma)
    return psf/numpy.sum(psf)

def getPeakLocations(peak_filename, margin, pixel_size, sigma):
    """
    This is for if you already know where your want fitting to happen, as
    for example in a bead calibration movie and you just want to use the
    approximate locations as inputs for fitting.

    There are two choices for peak_locations file format:

    1. A text file with the peak x, y, height and background values as 
       white spaced columns (x and y positions are in pixels as determined 
       using visualizer).

       1.0 2.0 1000.0 100.0
       10.0 5.0 2000.0 200.0
       ...

    2. An Insight3 format localization file. In this case only the localizations
       in the first frame will be used.
    """
    if os.path.exists(peak_filename):
        print("Using peak starting locations specified in", peak_filename)
    elif os.path.exists(os.path.basename(peak_filename)):
        peak_filename = os.path.basename(peak_filename)
        print("Using peak starting locations specified in", peak_filename)

    # Try to read file as if it was an Insight3 binary file.
    #
    # FIXME: This won't work properly for analysis with the 'inverted' parameter
    #        set to True.
    #
    if readinsight3.checkStatus(peak_filename):
        is_text = False

        frame_number = 1
        with readinsight3.I3Reader(peak_filename) as i3r:
            i3_locs = i3r.getMoleculesInFrame(frame_number)

        peak_locations = i3dtype.convertToMultiFit(i3_locs, 1, 1, frame_number, pixel_size)

    else:
        is_text = True
            
        # Load peak x,y locations.
        peak_locs = numpy.loadtxt(peak_filename, ndmin = 2)

        # Create peak array.
        peak_locations = numpy.zeros((peak_locs.shape[0],
                                      utilC.getNPeakPar()))
        peak_locations[:,utilC.getXCenterIndex()] = peak_locs[:,1] - 1.0
        peak_locations[:,utilC.getYCenterIndex()] = peak_locs[:,0] - 1.0
        peak_locations[:,utilC.getHeightIndex()] = peak_locs[:,2]
        peak_locations[:,utilC.getBackgroundIndex()] = peak_locs[:,3]
        
        peak_locations[:,utilC.getXWidthIndex()] = numpy.ones(peak_locs.shape[0]) * sigma
        peak_locations[:,utilC.getYWidthIndex()] = numpy.ones(peak_locs.shape[0]) * sigma    

    # Adjust positions for finding/fitting margin.
    peak_locations[:,utilC.getXCenterIndex()] += margin
    peak_locations[:,utilC.getYCenterIndex()] += margin

    print("Loaded", peak_locations.shape[0], "peak locations")
    #
    # We return is_text as the caller might want to do different things if
    # the file is text, like initialize the Z value.
    #
    return [peak_locations, is_text]
    
def padArray(ori_array, pad_size):
    """
    Pads out an array to a large size.

    ori_array - A 2D numpy array.
    pad_size - The number of elements to add to each of the "sides" of the array.
    
    The padded 2D numpy array.
    """
    if (pad_size > 0):
        [x_size, y_size] = ori_array.shape
        lg_array = numpy.ones((x_size+2*pad_size,y_size+2*pad_size))
        lg_array[pad_size:(x_size+pad_size),pad_size:(y_size+pad_size)] = ori_array.astype(numpy.float64)
        lg_array[0:pad_size,:] = numpy.flipud(lg_array[pad_size:2*pad_size,:])
        lg_array[(x_size+pad_size):(x_size+2*pad_size),:] = numpy.flipud(lg_array[x_size:(x_size+pad_size),:])
        lg_array[:,0:pad_size] = numpy.fliplr(lg_array[:,pad_size:2*pad_size])
        lg_array[:,(y_size+pad_size):(y_size+2*pad_size)] = numpy.fliplr(lg_array[:,y_size:(y_size+pad_size)])
        return lg_array
    
    else:
        return ori_array


#
# Classes.
#
def FittingException(Exception):

    def __init__(self, msg):
        Exception.__init__(self, msg)


class PeakFinder(object):
    """
    Base class for peak finding. This handles identification of peaks in an image.

    If you want to modify this with a custom peak finder or an alternative
    way to estimate the background, the recommended approach is to sub-class this
    class and then modify backgroundEstimator(), newImage() and peakFinder().
    """
    # Hard-wired defaults.
    unconverged_dist = 5.0  # Distance between peaks for marking as unconverged (this is multiplied by parameters.sigma)
    new_peak_dist = 1.0     # Minimum allowed distance between new peaks and current peaks.
    
    def __init__(self, parameters = None, **kwds):
        """
        This is called once at the start of analysis to initialize the
        parameters that will be used for peak fitting.
 
        parameters - A parameters object.
        """
        super(PeakFinder, self).__init__(**kwds)
        
        # Initialized from parameters.
        self.find_max_radius = parameters.getAttr("find_max_radius")     # Radius (in pixels) over which the maxima is maximal.
        self.iterations = parameters.getAttr("iterations")               # Maximum number of cycles of peak finding, fitting and subtraction to perform.
        self.sigma = parameters.getAttr("sigma")                         # Peak sigma (in pixels).
        self.threshold = parameters.getAttr("threshold")                 # Peak minimum threshold in units of sigma (as in "3 sigma effect").
        
        # Other member variables.
        self.background = None                                           # Current estimate of the image background.
        self.bg_filter = None                                            # Background MatchedFilter object.
        self.camera_variance = None                                      # Camera variance, only relevant for a sCMOS camera.
        self.check_mode = False                                          # Run in diagnostic mode. Only useful for debugging.
        self.image = None                                                # The original image.
        self.margin = PeakFinderFitter.margin                            # Size of the unanalyzed "edge" around the image.
        self.neighborhood = PeakFinder.unconverged_dist * self.sigma     # Radius for marking neighbors as unconverged.
        self.new_peak_radius = PeakFinder.new_peak_dist                  # Minimum allowed distance between new peaks and current peaks.
        self.parameters = parameters                                     # Keep access to the parameters object.
        self.peak_locations = None                                       # Initial peak locations, as explained below.
        self.peak_mask = None                                            # Mask for limiting peak identification to a particular AOI.
        
        # Print warning about check mode
        if self.check_mode:
            print("Warning! Running in check mode!")
            
        # Only do one cycle of peak finding as we'll always return the same locations.
        if parameters.hasAttr("peak_locations"):
            if (self.iterations != 1):
                print("WARNING: setting number of iterations to 1!")
                self.iterations = 1
        
    def backgroundEstimator(self, image):
        """
        This method does the actual background estimation. It is just a simple
        low pass filter.

        Override this if you want to change how the background is estimated.

        FIXME: Convolution should be weighted by the camera variance if it is 
               not uniform?
        """
        return self.bg_filter.convolve(image)

    def cleanUp(self):
        pass

    def findPeaks(self, fit_peaks_image, peaks):
        """
        Finds the peaks in an image & adds to the current list of peaks.
   
        fit_peaks_image - The current fit image.
        peaks - The current list of peaks.
    
        return - [True/False if new peaks were added to the current list, the new peaks]
        """

        # Use pre-specified peak locations if available, e.g. bead calibration.
        if self.peak_locations is not None:
            new_peaks = self.peak_locations
            
        # Otherwise, identify local maxima in the image and initialize fitting parameters.
        else:
            new_peaks = self.peakFinder(fit_peaks_image)

        # Update new peak identification threshold (if necessary).
        # Also, while threshold is greater than min_threshold we
        # are automatically not done.
        found_new_peaks = False
        if (self.cur_threshold > self.threshold):
            self.cur_threshold -= 1.0
            found_new_peaks = True

        # If we did not find any new peaks then we may be done.
        if (new_peaks.shape[0] == 0):
            return [found_new_peaks, peaks]

        # Add new peaks to the current list of peaks if it exists,
        # otherwise these peaks become the current list.
        if isinstance(peaks, numpy.ndarray):
            merged_peaks = self.mergeNewPeaks(peaks, new_peaks)
        
            # If none of the new peaks are valid then we may be done.
            if (merged_peaks.shape[0] == peaks.shape[0]):
                return [found_new_peaks, merged_peaks]
            else:
                return [True, merged_peaks]
        else:
            return [True, new_peaks]

    def mergeNewPeaks(self, peaks, new_peaks):
        """
        Merge new peaks into the current list of peaks.
        """
        return utilC.mergeNewPeaks(peaks,
                                   new_peaks,
                                   self.new_peak_radius,
                                   self.neighborhood)

    def newImage(self, new_image):
        """
        This is called once at the start of the analysis of a new image.
        
        new_image - A 2D numpy array.
        """
        # Make a copy of the starting image.
        self.image = numpy.copy(new_image)

        # Initialize new peak minimum threshold. If we are doing more
        # than one iteration we start a bit higher and come down to
        # the specified threshold.
        if(self.iterations>4):
            self.cur_threshold = self.threshold + 4.0
        else:
            self.cur_threshold = self.threshold + float(self.iterations)

        # Create mask to limit peak finding to a user defined sub-region of the image.
        if self.peak_mask is None:
            self.peak_mask = numpy.ones(new_image.shape)
            if self.parameters.hasAttr("x_start"):
                self.peak_mask[0:self.parameters.getAttr("x_start")+self.margin,:] = 0.0
            if self.parameters.hasAttr("x_stop"):
                self.peak_mask[self.parameters.getAttr("x_stop")+self.margin:-1,:] = 0.0
            if self.parameters.hasAttr("y_start"):
                self.peak_mask[:,0:self.parameters.getAttr("y_start")+self.margin] = 0.0
            if self.parameters.hasAttr("y_stop"):
                self.peak_mask[:,self.parameters.getAttr("y_stop")+self.margin:-1] = 0.0

        # Create filter objects if necessary.
        if self.bg_filter is None:

            # Create matched filter for background.
            bg_psf = gaussianPSF(new_image.shape, self.parameters.getAttr("background_sigma"))
            self.bg_filter = matchedFilterC.MatchedFilter(bg_psf)

            #
            # Create matched filter for foreground as well as a matched filter
            # for calculating the expected variance of the background if it was
            # smoothed on the same scale as the foeground.
            #
            if self.parameters.hasAttr("foreground_sigma"):
                if (self.parameters.getAttr("foreground_sigma") > 0.0):
                    fg_psf = gaussianPSF(new_image.shape, self.parameters.getAttr("foreground_sigma"))
                    self.fg_mfilter = matchedFilterC.MatchedFilter(fg_psf)
                    self.fg_vfilter = matchedFilterC.MatchedFilter(fg_psf * fg_psf)    

    def setVariance(self, camera_variance):
        """
        Set the camera variance, usually used in sCMOS analysis.
        """
        self.camera_variance = padArray(camera_variance, self.margin)
        return self.camera_variance
        
    def subtractBackground(self, image, bg_estimate):
        """
        Estimate the background for the image.

        Note: image is the residual image after the found / fit
              localizations have been subtracted out.
        
        image - The image to estimate the background of.
        bg_estimate - An estimate of the background.
        """

        # If we are provided with an estimate of the background
        # then just use it.
        if bg_estimate is not None:
            self.background = bg_estimate

        # Otherwise make our own estimate.
        else:
            self.background = self.backgroundEstimator(image)

        if self.check_mode:
            with tifffile.TiffWriter("bg_estimate.tif") as tf:
                tf.save(numpy.transpose(self.background.astype(numpy.float32)))
    
    
class PeakFinderGaussian(PeakFinder):
    """
    This is the peak finder for 3D-DAOSTORM and sCMOS, it handles Gaussian shaped 
    peaks.
    """
    def __init__(self, parameters = None, **kwds):
        """
        This is called once at the start of analysis to initialize the
        parameters that will be used for peak fitting.
 
        parameters - A parameters object.
        """
        kwds["parameters"] = parameters
        super(PeakFinderGaussian, self).__init__(**kwds)

        # Initialized from parameters.
        self.z_value = self.parameters.getAttr("z_value", 0.0)           # The starting z value to use for peak fitting.
        
        # Other member variables.
        self.fg_mfilter = None                                           # Foreground MatchedFilter object (may be None).
        self.fg_vfilter = None                                           # Foreground variance MatchedFilter object, will be none if self.fg_mfilter is None.
        self.taken = None                                                # Spots in the image where a peak has already been added.

        # Load peak locations if specified.
        #
        # FIXME: The starting z value is always 0.0. Not sure why we don't use
        #        self.z_value for this. Though I guess it would only really be
        #        relevant for the 'Z' fitting model.
        #
        if parameters.hasAttr("peak_locations"):
            [self.peak_locations, is_text] = getPeakLocations(parameters.getAttr("peak_locations"),
                                                              self.margin,
                                                              parameters.getAttr("pixel_size"),
                                                              self.sigma)

    def newImage(self, new_image):
        """
        This is called once at the start of the analysis of a new image.
        
        new_image - A 2D numpy array.
        """
        super(PeakFinderGaussian, self).newImage(new_image)
        
        # Reset taken mask.
        self.taken = numpy.zeros(new_image.shape, dtype=numpy.int32) 

    def peakFinder(self, fit_peaks_image):
        """
        This method does the actual peak finding.
        
        Override this if you want to change the peak finding behaviour.
        """
        # Calculate background variance.
        #
        # Note the assumption here that we are working in units of photo-electrons
        # so Poisson statistics applies, variance = mean.
        #
        bg_var = self.background + fit_peaks_image

        # Add camera variance if set.
        if self.camera_variance is not None:
            bg_var += self.camera_variance

        # Calculate weighted variance if the image is being smoothed.
        if self.fg_vfilter is not None:
            bg_var = self.fg_vfilter.convolve(bg_var)

        if self.check_mode:
            with tifffile.TiffWriter("variances.tif") as tf:
                tf.save(numpy.transpose(bg_var.astype(numpy.float32)))
            
        # Check for problematic values.
        #
        # Note: numpy will also complain when we try to take the sqrt of a negative number.
        #
        if self.check_mode:            
            mask = (bg_var <= 0.0)
            if (numpy.sum(mask) > 0):
                print("Warning! zero and/or negative values detected in background variance!")
                
        # Convert to standard deviation.
        bg_std = numpy.sqrt(bg_var)

        # Calculate foreground.
        foreground = self.image - self.background - fit_peaks_image
        
        # Calculate smoothed image if we have a foreground filter.
        if self.fg_mfilter is not None:
            foreground = self.fg_mfilter.convolve(foreground)

        if self.check_mode:
            with tifffile.TiffWriter("foreground.tif") as tf:
                tf.save(numpy.transpose(foreground.astype(numpy.float32)))
            
        # Calculate foreground in units of signal to noise.
        foreground = foreground/bg_std
        
        if self.check_mode:
            with tifffile.TiffWriter("fg_bg_ratio.tif") as tf:
                tf.save(numpy.transpose(foreground.astype(numpy.float32)))
        
        # Mask the image so that peaks are only found in the AOI.
        masked_image = foreground * self.peak_mask

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


class PeakFinderArbitraryPSF(PeakFinder):
    """
    This is the base class for Spliner and Pupilfn, it handles arbitrary
    PSF shapes possibly with multiple z values.
    """
    def __init__(self, parameters = None, psf_object = None, **kwds):
        kwds["parameters"] = parameters
        super(PeakFinderArbitraryPSF, self).__init__(**kwds)

        self.height_rescale = []
        self.fg_mfilter = []
        self.fg_mfilter_zval = []
        self.fg_vfilter = []
        self.psf_object = psf_object
        self.taken = []
        self.z_values = []

        #
        # Note: self.z_values is the Z position in 'internal' units, i.e. the units
        #       that the PSF generation library uses. For splines for example this
        #       is the spline size in Z.
        #
        #       self.fg_mfilter_zval is the Z position in microns.
        #
        self.margin = psf_object.getMargin()

        self.fg_mfilter_zval = parameters.getAttr("z_value", [0.0])
        for zval in self.fg_mfilter_zval:
            self.z_values.append(self.psf_object.getScaledZ(zval))

        if parameters.hasAttr("peak_locations"):
            [self.peak_locations, is_text] = fitting.getPeakLocations(parameters.getAttr("peak_locations"),
                                                                      self.margin,
                                                                      parameters.getAttr("pixel_size"),
                                                                      self.sigma)

            zc_index = utilC.getZCenterIndex()
            # Set initial z value (for text files).
            if is_text:
                self.peak_locations[:,zc_index] = self.z_value[0]

            # Convert z value to PSF FFT units (Insight3 localization files).
            else:
                for i in range(self.peak_locations.shape[0]):
                    self.peak_locations[i,zc_index] = self.psf_object.getScaledZ(self.peak_locations[i,zc_index])

    def newImage(self, new_image):
        """
        This is called once at the start of the analysis of a new image.
        
        new_image - A 2D numpy array.
        """
        super(PeakFinderArbitraryPSF, self).newImage(new_image)
    
        #
        # If does not already exist, create filter objects from
        # the PSF at different z values.
        #
        # As not all PSFs will be maximal in the center we can't just
        # use the image intensity at the center as the starting
        # height value. Instead we will use the intensity at the
        # peak center of the convolved image, then adjust this
        # value by the height_rescale parameter.
        #
        if (len(self.fg_mfilter) == 0):
            for zval in self.fg_mfilter_zval:
                psf = self.psf_object.getPSF(zval,
                                             shape = new_image.shape,
                                             normalize = False)
                psf_norm = psf/numpy.sum(psf)
                self.fg_mfilter.append(matchedFilterC.MatchedFilter(psf_norm))
                self.fg_vfilter.append(matchedFilterC.MatchedFilter(psf_norm * psf_norm))

                #
                # This is used to convert the height measured in the
                # convolved image to the correct height in the original
                # image, as this is the height unit that is used in
                # fitting.
                #
                # If you convolved a localization with itself the final
                # height would be sum(loc * loc). Here we are convolving
                # the localizations with a unit sum PSF, so the following
                # should give us the correct initial height under the
                # assumption that the shape of the localization is
                # pretty close to the shape of the PSF.
                #                
                self.height_rescale.append(1.0/numpy.sum(psf * psf_norm))

                # Save a picture of the PSF for debugging purposes.
                if self.check_mode:
                    print("psf max", numpy.max(psf))
                    filename = "psf_{0:.3f}.tif".format(zval)
                    tifffile.imsave(filename, psf.astype(numpy.float32))

        self.taken = []
        for i in range(len(self.fg_mfilter)):
            self.taken.append(numpy.zeros(new_image.shape, dtype=numpy.int32))
                        
    def peakFinder(self, fit_peaks_image):
        """
        This method does the actual peak finding.
        """
        all_new_peaks = None

        if self.check_mode:
            tifffile.imsave("fit_peaks.tif", numpy.transpose(fit_peaks_image.astype(numpy.float32)))

        # Calculate background variance.
        #
        # Notes:
        #
        # 1. The assumption here is that we are working in units of photo-electrons
        #    so Poisson statistics applies, variance = mean.
        #
        # 2. We use the absolute value of fit_peaks_image as some fitters (such as
        #    Spliner) will sometimes return this array with negative values. This is
        #    still probably not the correct way to handle this.
        #
        bg_var = self.background + numpy.abs(fit_peaks_image)

        # Add camera variance if set.
        if self.camera_variance is not None:
            bg_var += self.camera_variance
            
        #
        # Find peaks in image convolved with the PSF at different z values.
        #
        if self.check_mode:
            bg_tif = tifffile.TiffWriter("background.tif")
            fg_tif = tifffile.TiffWriter("foreground.tif")
            fg_bg_ratio_tif = tifffile.TiffWriter("fg_bg_ratio.tif")
            
        for i in range(len(self.fg_mfilter)):

            # Estimate background variance at this particular z value.
            background = self.fg_vfilter[i].convolve(bg_var)
                
            # Check for problematic values.
            #
            # Note: numpy will also complain when we try to take the sqrt of a negative number.
            #
            if self.check_mode:            
                mask = (background <= 0.0)
                if (numpy.sum(mask) > 0):
                    print("Warning! zero and/or negative values detected in background variance!")
                    
            # Convert to standard deviation.
            bg_std = numpy.sqrt(background)

            # Calculate foreground.
            foreground = self.image - self.background - fit_peaks_image
            foreground = self.fg_mfilter[i].convolve(foreground)
                    
            # Calculate foreground in units of signal to noise.
            fg_bg_ratio = foreground/bg_std
        
            if self.check_mode:
                bg_tif.save(numpy.transpose(background.astype(numpy.float32)))
                fg_tif.save(numpy.transpose(foreground.astype(numpy.float32)))
                fg_bg_ratio_tif.save(numpy.transpose(fg_bg_ratio.astype(numpy.float32)))        

            # Mask the image so that peaks are only found in the AOI.
            masked_image = fg_bg_ratio * self.peak_mask
        
            # Identify local maxima in the masked ratio image.
            [new_peaks, taken] = utilC.findLocalMaxima(masked_image,
                                                       self.taken[i],
                                                       self.cur_threshold,
                                                       self.find_max_radius,
                                                       self.margin)

            # Fill in initial values for peak height, background and sigma.
            new_peaks = utilC.initializePeaks(new_peaks,                    # The new peaks.
                                              foreground + self.background, # Convolved image + background.
                                              self.background,              # The current estimate of the background.
                                              self.sigma,                   # The starting sigma value.
                                              self.z_values[i])             # The starting z value.

            # Correct initial peak heights, self.height_rescale is an estimate
            # of the effect of PSF convolution on the height of the original
            # localization.
            h_index = utilC.getHeightIndex()
            new_peaks[:,h_index] = new_peaks[:,h_index] * self.height_rescale[i]
            
            if all_new_peaks is None:
                all_new_peaks = new_peaks
            else:
                all_new_peaks = numpy.append(all_new_peaks, new_peaks, axis = 0)

        if self.check_mode:
            fg_tif.close()
            fg_bg_ratio_tif.close()
                
        #
        # Remove the dimmer of two peaks with similar x,y values but different z values.
        #
        if (len(self.fg_mfilter) > 1):

            if self.check_mode:
                print("Before peak removal", all_new_peaks.shape)
                if False:
                    for i in range(all_new_peaks.shape[0]):
                        print(all_new_peaks[i,:])
                print("")
            
            all_new_peaks = utilC.removeClosePeaks(all_new_peaks,                                               
                                                   self.find_max_radius,
                                                   self.find_max_radius)

            if self.check_mode:
                print("After peak removal", all_new_peaks.shape)
                if False:
                    for i in range(all_new_peaks.shape[0]):
                        print(all_new_peaks[i,:])
                print("")

        return all_new_peaks


class PeakFitter(object):
    """
    Base class for peak fitting. This handles refinement of the
    parameters of the peaks that were identified with PeakFinder.

    The actual fitting is done by an the self.mfitter object, this
    is primarily just a wrapper for the self.mfitter object.
    """

    def __init__(self, mfitter = None, parameters = None, **kwds):
        """
        parameters - A (fitting) parameters object.
        """
        super(PeakFitter, self).__init__(**kwds)
        
        self.image = None      # The image for peak fitting.
        self.mfitter = mfitter # An instance of a sub-class of the MultiFitter class.

        self.sigma = parameters.getAttr("sigma")                   # Peak sigma (in pixels).
        self.neighborhood = self.sigma*PeakFinder.unconverged_dist # Radius for marking neighbors as unconverged.

    def cleanUp(self):
        self.mfitter.cleanup()

    def fitPeaks(self, peaks):
        """
        Performs a single iteration of peak fitting.
        
        peaks - A numpy array of peaks to fit.
    
        return - [updated peaks, fit peaks image]
        """
        # Fit to update peak locations.
        [fit_peaks, fit_peaks_image] = self.peakFitter(peaks)
        fit_peaks = self.mfitter.getGoodPeaks(fit_peaks,
                                              0.5*self.sigma)
        
        # Remove peaks that are too close to each other & refit.
        fit_peaks = utilC.removeClosePeaks(fit_peaks, self.sigma, self.neighborhood)
        [fit_peaks, fit_peaks_image] = self.peakFitter(fit_peaks)

        fit_peaks = self.mfitter.getGoodPeaks(fit_peaks,
                                              0.5 * self.sigma)
        
        return [fit_peaks, fit_peaks_image]

    def newImage(self, new_image):
        """
        new_image - A new image (2D numpy array).
        """
        self.mfitter.newImage(new_image)

    def peakFitter(self, peaks):
        """
        This method does the actual peak fitting.
        """
        fit_peaks = self.mfitter.doFit(peaks)
        fit_peaks_image = self.mfitter.getFitImage()
        return [fit_peaks, fit_peaks_image]


class PeakFitterArbitraryPSF(PeakFitter):
    """
    Class for arbitrary PSF based peak fitting.
    """
    def __init__(self, **kwds):
        super(PeakFitterArbitraryPSF, self).__init__(**kwds)

        # Update refitting neighborhood parameter.
        self.neighborhood = int(0.5 * self.mfitter.getSize()) + 1

    def rescaleZ(self, peaks):
        """
        Convert from fitting z units to microns.
        """
        return self.mfitter.rescaleZ(peaks)

    
class PeakFinderFitter(object):
    """
    Base class to encapsulate peak finding and fitting. 

    To get an idea of how all the pieces are supposed to go together, please see:
      3d_daostorm/find_peaks.py
      sCMOS/find_peaks.py
    """
    
    margin = 10   # Size of the unanalyzed edge around the image. This is also
                  #  a constant in the C libraries, so if you change this you
                  #  also need to change that.

    def __init__(self, peak_finder = None, peak_fitter = None, **kwds):
        """
        peak_finder - A PeakFinder object.
        peak_fitter - A PeakFitter object.
        """
        super(PeakFinderFitter, self).__init__(**kwds)

        self.peak_finder = peak_finder
        self.peak_fitter = peak_fitter

        #
        # Update margin. Normally this is 10 as specified above for the
        # class variable, but the fitters that use splines may change this.
        #
        self.margin = self.peak_finder.margin

    def analyzeImage(self, movie_reader, save_residual = False, verbose = False):
        """
        movie_reader - analysis_io.MovieReader object.
        save_residual - (Optional) Save the residual image after peak fitting, default is False.

        return - [Found peaks, Image residual]
        """
        # Load image (in photo-electrons).
        [image, fit_peaks_image] = self.loadImage(movie_reader)

        # Load background estimate (in photo-electrons).
        bg_estimate = self.loadBackgroundEstimate(movie_reader)

        self.peak_finder.newImage(image)
        self.peak_fitter.newImage(image)

        if save_residual:
            resid_tif = tifffile.TiffWriter("residual.tif")

        peaks = False
        for i in range(self.peak_finder.iterations):
            if save_residual:
                resid_tif.save(numpy.transpose((image - fit_peaks_image).astype(numpy.float32)))

            # Update background estimate.
            self.peak_finder.subtractBackground(image - fit_peaks_image, bg_estimate)

            # Find new peaks.
            [found_new_peaks, peaks] = self.peak_finder.findPeaks(fit_peaks_image, peaks)

            # Fit new peaks.
            if isinstance(peaks, numpy.ndarray):
                [peaks, fit_peaks_image] = self.peak_fitter.fitPeaks(peaks)

            if verbose:
                if isinstance(peaks, numpy.ndarray):
                    print(" peaks:", i, found_new_peaks, peaks.shape[0])
                else:
                    print(" peaks:", i, found_new_peaks, "NA")

            if not found_new_peaks:
                break

        if save_residual:
            resid_tif.save(numpy.transpose((image - fit_peaks_image).astype(numpy.float32)))
            resid_tif.close()

        if isinstance(peaks, numpy.ndarray):
            peaks[:,utilC.getXCenterIndex()] -= float(self.margin)
            peaks[:,utilC.getYCenterIndex()] -= float(self.margin)

        return [peaks, fit_peaks_image]

    def cleanUp(self):
        self.peak_finder.cleanUp()
        self.peak_fitter.cleanUp()

    def getConvergedPeaks(self, peaks, verbose = False):
        """
        peaks - A 1D numpy array containing the peaks.
        
        return - A 1D numpy array containing only the converged peaks.
        """
        if (peaks.shape[0] > 0):
            status_index = utilC.getStatusIndex()
            mask = (peaks[:,status_index] == 1.0)  # 0.0 = running, 1.0 = converged.
            if verbose:
                print(" ", numpy.sum(mask), "converged out of", peaks.shape[0])
            return peaks[mask,:]
        else:
            return peaks

    def loadBackgroundEstimate(self, movie_reader):
        bg_estimate = movie_reader.getBackground()
        if bg_estimate is not None:
            bg_estimate = padArray(bg_estimate, self.margin)
            
        return bg_estimate
        
    def loadImage(self, movie_reader):
        image = padArray(movie_reader.getFrame(), self.margin)
        fit_peaks_image = numpy.zeros(image.shape)
        return [image, fit_peaks_image]


class PeakFinderFitterArbitraryPSF(PeakFinderFitter):
    """
    Class for arbitrary PSF based peak finding and fitting.
    """
    def getConvergedPeaks(self, peaks):
        converged_peaks = super(PeakFinderFitterArbitraryPSF, self).getConvergedPeaks(peaks)
        return self.peak_fitter.rescaleZ(converged_peaks)

    
class PSFFunction(object):
    """
    This is the base class for handling the PSF for fitters that use
    arbitrary PSFs such as PSFFFT, PupilFN and Spliner. In theory it
    handles all of the details of the PSF, such as how many pixels
    it covers, how much margin to add to the image, how to convert
    Z values, etc..
    """
    def getCPointer(self):
        """
        Returns a pointer to the C library structure that is
        used to describe the PSF.

        pupilData in pupilfn/pupil_function.h for example.
        """
        assert False

    def getMargin(self):
        """
        Return the margin to add to the image for finding/fitting.
        """
        assert False
        
    def getPSF(self, z_value, shape = None, normalize = False):
        """
        Return an image of the PSF at z_value, centered in an 
        array of size shape.
        """
        assert False

    def getScaledZ(self, z_value):
        """
        This expects z_value to be in nanometers.
        """
        return z_value
        
    def getSize(self):
        """
        Return the X/Y size in pixels (all the fitters expect the 
        PSF to be square).
        """
        assert False

    def rescaleZ(self, z_value):
        """
        Convert from fitting units back to microns.
        """
        return z_value

#
# The MIT License
#
# Copyright (c) 2014 Zhuang Lab, Harvard University
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
