#!/usr/bin/env python
"""
Estimate Cramer-Rao bounds for a spline based on the formulation in
this paper (specifically equation 18):

"Three dimensional single molecule localization using a phase retrieved pupil
function", Sheng Liu, Emil B. Kromann, Wesley D. Krueger, Joerg Bewersdorf, 
and Keith A. Lidke, Optics Express 2013.

Hazen 02/17
"""

import math
import numpy
import pickle

import storm_analysis.spliner.spline_to_psf as splineToPSF


# FIXME: Also handle 2D splines.

class CramerRaoException(Exception):
    pass


class CRSplineToPSF3D(splineToPSF.SplineToPSF3D):

    def getSplineVals(self, spline_method, scaled_z):
        """
        Return the spline values of a given method such as:

        spline.f - The PSF
        spline.dx - The derivative in x
        ...

        This is basically a specialized version of the getPSF() method.
        """
        vals_size = int((self.spline_size - 1)/2)
                
        vals = numpy.zeros((vals_size, vals_size))
        if((vals_size%2) == 0):
            for x in range(vals_size):
                for y in range(vals_size):
                    vals[y,x] = spline_method(scaled_z,
                                              float(2*y),
                                              float(2*x))
        else:
            for x in range(vals_size):
                for y in range(vals_size):
                    vals[y,x] = spline_method(scaled_z,
                                              float(2*y) + 1.0,
                                              float(2*x) + 1.0)
        return vals

    def getPSFCR(self, scaled_z):
        return self.getSplineVals(self.spline.f, scaled_z)

    def getDx(self, scaled_z):
        return self.getSplineVals(self.spline.dxf, scaled_z)

    def getDy(self, scaled_z):
        return self.getSplineVals(self.spline.dyf, scaled_z)

    def getDz(self, scaled_z):
        return self.getSplineVals(self.spline.dzf, scaled_z)
    

class CRBound3D(object):
    """
    Class for calculating a 3D Cramer-Rao bounds given a spline.

    Notes: 
      (1) This returns the variance.
      (2) The results for x,y and z are nanometers.
    """
    def __init__(self, spline_file, pixel_size = 160.0, weighting = 1.0):
        self.weighting = weighting

        with open(spline_file, 'rb') as fp:
            self.s_to_psf = CRSplineToPSF3D(pickle.load(fp))

        self.delta_xy = 0.5*pixel_size # Splines are 2x up-sampled.
        self.delta_z = (self.s_to_psf.getZMax() - self.s_to_psf.getZMin())/float(self.s_to_psf.spline_size)

    def calcCRBound(self, background, photons, z_position = 0.0):
        """
        Wraps calcCRBoundScaledZ, converts z_position from 
        nanometers to spline units.
        """
        scaled_z = self.s_to_psf.getScaledZ(z_position)
        return self.calcCRBoundScaledZ(background, photons, scaled_z)
            
    def calcCRBoundScaledZ(self, background, photons, scaled_z):
        """
        Calculate Cramer-Rao bounds for a 3D spline.

        Note: This expects z to be in spline units, not nanometers.
        """
        # Calculate PSF and it's derivatives.
        psf = self.s_to_psf.getPSFCR(scaled_z)
        psf_dx = self.s_to_psf.getDx(scaled_z)
        psf_dy = self.s_to_psf.getDy(scaled_z)
        psf_dz = self.s_to_psf.getDz(scaled_z)

        # Normalize to unity & multiply by the number of photons.
        psf_norm = self.weighting/numpy.sum(psf)

        psf_di = psf * psf_norm
        
        psf_dx = -psf_dx * psf_norm * photons / self.delta_xy
        psf_dy = -psf_dy * psf_norm * photons / self.delta_xy
        psf_dz = psf_dz * psf_norm * photons / self.delta_z
        psf_dbg = numpy.ones(psf.shape)

        psf_inv = 1.0/(psf_di * photons + background)

        # Calculate Fisher information matrix.
        fmat = numpy.zeros((5,5))
        drvs = [psf_di, psf_dx, psf_dy, psf_dz, psf_dbg]
        for t1 in range(5):
            for t2 in range(5):
                fmat[t1, t2] = numpy.sum(psf_inv * drvs[t1] * drvs[t2])

        fmat_inv = numpy.linalg.inv(fmat)
        crlb = numpy.zeros(5)
        for i in range(5):
            crlb[i] = fmat_inv[i,i]

        return crlb

    def check(self):
        """
        Check that both PSF calculations agree..
        """
        psf_cr = self.s_to_psf.getPSFCR(self.s_to_psf.getScaledZ(0.0))
        psf_stp = self.s_to_psf.getPSF(0.0, normalize = False)

        print(numpy.sum(psf_cr), numpy.sum(psf_stp))

    def getSize(self):
        return self.s_to_psf.getSplineSize()

    
if (__name__ == "__main__"):

    import argparse

    parser = argparse.ArgumentParser(description = '(3D) Cramer-Rao bounds calculation, results in nanometers')

    parser.add_argument('--spline', dest='spline', type=str, required=True,
                        help = "The name of the spline file")
    parser.add_argument('--background', dest='background', type=float, required=True,
                        help = "The non-specific fluorescence background.")
    parser.add_argument('--photons', dest='photons', type=int, required=True,
                        help = "The number of photons in the PSF image.")
    parser.add_argument('--pixel_size', dest='pixel_size', type=float, required=False, default=160.0,
                        help = "The XY pixel size in nanometers.")

    args = parser.parse_args()
    
    crb = CRBound3D(args.spline, pixel_size = args.pixel_size)
    #crb.check()
    print(crb.calcCRBound(args.background, args.photons))
