#!/usr/bin/env python
"""
Tests of fitz_c fitting of Z values. This is used by 
3D-DAOSTORM / sCMOS when using the '3d' model.
"""
import numpy

import storm_analysis

import storm_analysis.sa_library.parameters as params
import storm_analysis.sa_library.sa_h5py as saH5Py

import storm_analysis.sa_utilities.fitz_c as fitzC


def test_fitz_c_1():
    """
    Test setting z values for raw localizations.
    """
    # Load 3D parameters.
    settings = storm_analysis.getData("test/data/test_3d_3d.xml")
    parameters = params.ParametersDAO().initFromFile(settings)

    [wx_params, wy_params] = parameters.getWidthParams()
    [min_z, max_z] = parameters.getZRange()
    pixel_size = parameters.getAttr("pixel_size")

    # Calculate widths.
    z_vals = numpy.arange(-250.0, 251.0, 50)
    [sx, sy] = fitzC.calcSxSy(wx_params, wy_params, z_vals)

    # Create HDF5 file with these widths.
    peaks = {"x" : numpy.zeros(sx.size),
             "xsigma" : sx/pixel_size,
             "ysigma" : sy/pixel_size}

    h5_name = storm_analysis.getPathOutputTest("test_sa_hdf5.hdf5")
    storm_analysis.removeFile(h5_name)
    
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieProperties(256, 256, 10, "XYZZY")
        h5.setPixelSize(pixel_size)
        h5.addLocalizations(peaks, 1)

    # Calculate Z values.
    fitzC.fitzRaw(h5_name, 1.5, wx_params, wy_params, min_z, max_z, 1.0e-3)

    # Check Z values.
    with saH5Py.SAH5Py(h5_name) as h5:
        locs = h5.getLocalizationsInFrame(1)
        assert(numpy.allclose(locs["z"], z_vals*1.0e-3))


def test_fitz_c_2():
    """
    Test that localizations with wx, wy values that are not near
    the calibration curve are assigned z values less than z minimum.
    """
    # Load 3D parameters.
    settings = storm_analysis.getData("test/data/test_3d_3d.xml")
    parameters = params.ParametersDAO().initFromFile(settings)

    [wx_params, wy_params] = parameters.getWidthParams()
    [min_z, max_z] = parameters.getZRange()
    pixel_size = parameters.getAttr("pixel_size")

    # Calculate widths.
    z_vals = numpy.arange(-250.0, 251.0, 100)
    [sx, sy] = fitzC.calcSxSy(wx_params, wy_params, z_vals)

    # Create HDF5 file with these widths.
    peaks = {"x" : numpy.zeros(sx.size),
             "xsigma" : sx/pixel_size + numpy.ones(sx.size),
             "ysigma" : sy/pixel_size + numpy.ones(sx.size)}

    h5_name = storm_analysis.getPathOutputTest("test_sa_hdf5.hdf5")
    storm_analysis.removeFile(h5_name)
    
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieProperties(256, 256, 10, "XYZZY")
        h5.setPixelSize(pixel_size)
        h5.addLocalizations(peaks, 1)

    # Calculate Z values.
    fitzC.fitzRaw(h5_name, 1.5, wx_params, wy_params, min_z, max_z, 1.0e-3)

    # Check Z values.
    with saH5Py.SAH5Py(h5_name) as h5:
        locs = h5.getLocalizationsInFrame(1)
        assert(numpy.allclose(locs["z"], min_z*numpy.ones(sx.size)-1.0e-3))
    
    
if (__name__ == "__main__"):
    test_fitz_c_1()
    test_fitz_c_2()
    
