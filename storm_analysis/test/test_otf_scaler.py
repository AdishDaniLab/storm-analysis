#!/usr/bin/env python
import numpy

import storm_analysis

import storm_analysis.simulator.pupil_math as pupilMath
import storm_analysis.pupilfn.otf_scaling_c as otfSC
import storm_analysis.pupilfn.pupil_function_c as pfFnC

import tifffile


def test_otf_scaler_1():
    """
    Test that the C and the Python libraries agree on the calculation
    of an OTF scaled PSF.
    """
    otf_sigma = 1.8
    
    geo = pupilMath.Geometry(128, 0.1, 0.6, 1.5, 1.4)
    pf = geo.createFromZernike(1.0, [[1.3, 2, 2]])

    pf_c = pfFnC.PupilFunction(geometry = geo)
    pf_c.setPF(pf)

    otf_sc = otfSC.OTFScaler(geometry = geo, sigma = otf_sigma)

    gsf = geo.gaussianScalingFactor(otf_sigma)
    psf_py = geo.pfToPSF(pf, [0.0], scaling_factor = gsf)

    psf_c = pf_c.getPSFIntensity()
    psf_c = otf_sc.scale(psf_c)
    
    if False:
        with tifffile.TiffWriter(storm_analysis.getPathOutputTest("test_otf_scaler_1.tif")) as tf:
            tf.save(psf_c.astype(numpy.float32))
            tf.save(psf_py.astype(numpy.float32))
            
    assert numpy.allclose(psf_c, psf_py)
    
    pf_c.cleanup()
    otf_sc.cleanup()

            
if (__name__ == "__main__"):
    test_otf_scaler_1()

    
    
