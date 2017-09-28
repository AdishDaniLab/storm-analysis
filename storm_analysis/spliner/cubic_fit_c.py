#!/usr/bin/env python
"""
Simple Python interface to cubic_spline.c.

Hazen 01/14
"""

import ctypes
import numpy
from numpy.ctypeslib import ndpointer
import os
import sys

import storm_analysis.sa_library.ia_utilities_c as utilC
import storm_analysis.sa_library.loadclib as loadclib
import storm_analysis.sa_library.dao_fit_c as daoFitC

import storm_analysis.spliner.spline2D as spline2D
import storm_analysis.spliner.spline3D as spline3D


def loadCubicFitC():
    cubic_fit = loadclib.loadCLibrary("storm_analysis.spliner", "cubic_fit")

    # From sa_library/multi_fit.c
    cubic_fit.mFitGetFitImage.argtypes = [ctypes.c_void_p,
                                          ndpointer(dtype=numpy.float64)]

    cubic_fit.mFitGetResidual.argtypes = [ctypes.c_void_p,
                                          ndpointer(dtype=numpy.float64)]
    
    cubic_fit.mFitGetResults.argtypes = [ctypes.c_void_p,
                                         ndpointer(dtype=numpy.float64)]

    cubic_fit.mFitGetUnconverged.argtypes = [ctypes.c_void_p]
    cubic_fit.mFitGetUnconverged.restype = ctypes.c_int

    cubic_fit.mFitNewImage.argtypes = [ctypes.c_void_p,
                                       ndpointer(dtype=numpy.float64)]
    
    # From spliner/cubic_spline.c
    cubic_fit.getZSize.argtypes = [ctypes.c_void_p]
    cubic_fit.getZSize.restype = ctypes.c_int

    cubic_fit.initSpline2D.argtypes = [ndpointer(dtype=numpy.float64),
                                       ctypes.c_int,
                                       ctypes.c_int]
    cubic_fit.initSpline2D.restype = ctypes.c_void_p
    
    cubic_fit.initSpline3D.argtypes = [ndpointer(dtype=numpy.float64),
                                       ctypes.c_int,
                                       ctypes.c_int,
                                       ctypes.c_int]
    cubic_fit.initSpline3D.restype = ctypes.c_void_p

    # From spliner/cubic_fit.c
    cubic_fit.cfCleanup.argtypes = [ctypes.c_void_p]

    cubic_fit.cfInitialize.argtypes = [ctypes.c_void_p,
                                       ndpointer(dtype=numpy.float64),
                                       ndpointer(dtype=numpy.float64),
                                       ctypes.c_double,
                                       ctypes.c_int,
                                       ctypes.c_int]
    cubic_fit.cfInitialize.restype = ctypes.c_void_p
    
    cubic_fit.cfIterateSpline.argtypes = [ctypes.c_void_p]    
    
    cubic_fit.cfNewPeaks.argtypes = [ctypes.c_void_p,
                                     ndpointer(dtype=numpy.float64),
                                     ctypes.c_int]

    return cubic_fit
    

#
# Classes.
#

class CSplineFit(daoFitC.MultiFitterBase):

    def __init__(self, **kwds):
        super(CSplineFit, self).__init__(**kwds)

        self.c_spline = None
        self.py_spline = None

        self.clib = loadCubicFitC()
        
        # Default clamp parameters.
        #
        # These set the (initial) scale for how much these parameters
        # can change in a single fitting iteration.
        #
        self.clamp = numpy.array([1.0,  # Height (Note: This is relative to the initial guess).
                                  1.0,  # x position
                                  0.3,  # width in x (not relevant).
                                  1.0,  # y position
                                  0.3,  # width in y (not relevant).
                                  1.0,  # background (Note: This is relative to the initial guess).
                                  1.0]) # z position

    def cleanup(self):
        if self.mfit is not None:
            self.clib.cfCleanup(self.mfit)
        self.mfit = None
        self.c_spline = None

    def getGoodPeaks(self, peaks):
        if (peaks.size > 0):
            status_index = utilC.getStatusIndex()

            mask = (peaks[:,status_index] != 2.0)
            if self.verbose:
                print(" ", numpy.sum(mask), "were good out of", peaks.shape[0])
            return peaks[mask,:]
        else:
            return peaks

    def getSplineSize(self):
        return self.py_spline.getSize()
        
    def initializeC(self, image):
        """
        This initializes the C fitting library. You can call this directly, but
        the idea is that it will get called automatically the first time that you
        provide a new image for fitting.
        """
        if self.scmos_cal is None:
            self.scmos_cal = numpy.ascontiguousarray(numpy.zeros(image.shape))
        else:
            self.scmos_cal = numpy.ascontiguousarray(self.scmos_cal)

        if (image.shape[0] != self.scmos_cal.shape[0]) or (image.shape[1] != self.scmos_cal.shape[1]):
            raise daoFitC.MultiFitterException("Image shape and sCMOS calibration shape do not match.")

        self.im_shape = self.scmos_cal.shape
        self.mfit = self.clib.cfInitialize(self.c_spline,
                                           self.scmos_cal,
                                           numpy.ascontiguousarray(self.clamp),
                                           self.default_tol,
                                           self.scmos_cal.shape[1],
                                           self.scmos_cal.shape[0])
        
    def iterate(self):
        self.clib.cfIterateSpline(self.mfit)

    def newPeaks(self, peaks):
        self.clib.cfNewPeaks(self.mfit,
                             numpy.ascontiguousarray(peaks),
                             peaks.shape[0])

    def setVariance(self, variance):
        self.scmos_cal = variance


class CSpline2DFit(CSplineFit):

    def __init__(self, spline_vals = None, coeff_vals = None, **kwds):
        super(CSpline2DFit, self).__init__(**kwds)

        # Initialize spline.
        self.py_spline = spline2D.Spline2D(spline_vals, coeff = coeff_vals)
        self.c_spline = self.clib.initSpline2D(numpy.ascontiguousarray(self.py_spline.coeff, dtype = numpy.float64),
                                               self.py_spline.max_i,
                                               self.py_spline.max_i)
        

class CSpline3DFit(CSplineFit):
    
    def __init__(self, spline_vals = None, coeff_vals = None, **kwds):
        super(CSplineFit, self).__init__(**kwds)

        # Initialize spline.
        self.py_spline = spline3D.Spline3D(spline_vals, coeff = coeff_vals)
        self.c_spline = self.clib.initSpline3D(numpy.ascontiguousarray(self.py_spline.coeff, dtype = numpy.float64),
                                               self.py_spline.max_i,
                                               self.py_spline.max_i,
                                               self.py_spline.max_i)
        self.inv_zscale = 1.0/self.clib.getZSize(self.c_spline)
        
    def rescaleZ(self, peaks, zmin, zmax):
        z_index = utilC.getZCenterIndex()
        spline_range = zmax - zmin
        peaks[:,z_index] = peaks[:,z_index] * self.inv_zscale * spline_range + zmin
        return peaks
