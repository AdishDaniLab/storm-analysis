#!/usr/bin/env python
import numpy
import os
import shutil

import storm_analysis
import storm_analysis.sa_library.drift_utilities as driftUtils
import storm_analysis.sa_library.imagecorrelation as imagecorrelation
import storm_analysis.sa_library.parameters as params
import storm_analysis.sa_library.sa_h5py as saH5Py
import storm_analysis.sa_utilities.xyz_drift_correction as xyzDriftCorrection

import storm_analysis.test.verifications as veri

def test_drift_correction_1():
    """
    This tests the whole process.
    """
    # Calculate drift correction.
    param_name = storm_analysis.getData("test/data/test_drift.xml")    
    parameters = params.ParametersCommon().initFromFile(param_name)

    data_name = storm_analysis.getData("test/data/test_drift.hdf5")
    h5_name = storm_analysis.getPathOutputTest("test_dc_hdf5.hdf5")
    
    # Make a copy of the original as it will get modified and then
    # git will pick this up.
    shutil.copyfile(data_name, h5_name)
    
    drift_output = storm_analysis.getPathOutputTest("test_drift_drift.txt")

    [min_z, max_z] = parameters.getZRange()
    xyzDriftCorrection.xyzDriftCorrection(h5_name,
                                          drift_output,
                                          parameters.getAttr("frame_step"),
                                          parameters.getAttr("d_scale"),
                                          min_z,
                                          max_z,
                                          True)

    # Verify results.
    diffs = veri.verifyDriftCorrection(storm_analysis.getData("test/data/test_drift.txt"),
                                       drift_output)
    
    if (diffs[0] > 0.1):
        raise Exception("Frame numbers do not match.")

    # These thresholds are somewhat arbitrary, 0.1 pixel maximum error in X/Y, 30nm in Z.
    if (diffs[1] > 0.1) or (diffs[2] > 0.1):
        raise Exception("XY drift correction error.")

    if (diffs[3] > 0.03):
        raise Exception("Z drift correction error.")

def test_drift_correction_2():
    """
    Test interpolation.
    """
    x_vals = numpy.array([3,6,9,12])
    y_vals = numpy.array([1,2,2,1])
    int_y = driftUtils.interpolateData(x_vals, y_vals, 16)

    exp_y = numpy.array([0.0, 1.0/3.0, 2.0/3.0, 1.0, 4.0/3.0, 5.0/3.0, 2.0, 2.0,
                         2.0, 2.0, 5.0/3.0, 4.0/3.0, 1.0, 2.0/3.0, 1.0/3.0, 0.0])

    assert(numpy.allclose(int_y, exp_y))

    if False:
        import matplotlib
        import matplotlib.pyplot as pyplot

        int_x = numpy.arange(16)
        pyplot.plot(int_x, int_y)
        pyplot.show()

def test_drift_correction_3():
    """
    Test handling of files with no localizations.
    """
    filename = "test_dc_hdf5.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)
    
    with saH5Py.SAH5Py(h5_name, is_existing = False, overwrite = True) as h5:
        h5.setMovieInformation(128, 128, 10000, "XYZZY")

    drift_output = storm_analysis.getPathOutputTest("test_drift_drift.txt")
    
    xyzDriftCorrection.xyzDriftCorrection(h5_name,
                                          drift_output,
                                          500,
                                          2,
                                          -0.5,
                                          0.5,
                                          False)

    drift_data = numpy.loadtxt(drift_output)
    assert(numpy.allclose(drift_data[:,1], numpy.zeros(drift_data.shape[0])))

def test_drift_correction_4():
    """
    Test handling of very short files.
    """
    peaks = {"x" : numpy.zeros(10),
             "y" : numpy.ones(10)}

    filename = "test_dc_hdf5.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)
    
    with saH5Py.SAH5Py(h5_name, is_existing = False, overwrite = True) as h5:
        h5.setMovieInformation(128, 128, 100, "XYZZY")
        h5.addLocalizations(peaks, 0)
        h5.addLocalizations(peaks, 2)

    drift_output = storm_analysis.getPathOutputTest("test_drift_drift.txt")
    
    xyzDriftCorrection.xyzDriftCorrection(h5_name,
                                          drift_output,
                                          500,
                                          2,
                                          -0.5,
                                          0.5,
                                          False)

    drift_data = numpy.loadtxt(drift_output)
    assert(numpy.allclose(drift_data[:,1], numpy.zeros(drift_data.shape[0])))

def test_drift_correction_5():
    """
    Test XY offset determination & correction.
    """
    n_locs = 500
    peaks = {"x" : numpy.random.normal(loc = 10.0, scale = 0.2, size = n_locs),
             "y" : numpy.random.normal(loc = 10.0, scale = 0.2, size = n_locs)}

    h5_name = storm_analysis.getPathOutputTest("test_dc_hdf5.hdf5")

    # Save peaks.
    with saH5Py.SAH5Py(h5_name, is_existing = False, overwrite = True) as h5:
        h5.setMovieInformation(20, 20, 2, "")
        h5.addLocalizations(peaks, 0)
        peaks["x"] += 1.0
        h5.addLocalizations(peaks, 1)

    scale = 2
    with driftUtils.SAH5DriftCorrection(filename = h5_name, scale = scale) as h5d:
        h5d.setFrameRange(0,1)
        im1 = h5d.grid2D()
        h5d.setFrameRange(1,2)
        im2 = h5d.grid2D()

        # Check that both images have the same number localizations.
        assert(numpy.sum(im1) == numpy.sum(im2))

        # Measure offset.
        [corr, dx, dy, success] = imagecorrelation.xyOffset(im1, im2, scale)

        # Test that it succeeded.
        assert(success)

        # Test that we got the right answer.
        dx = dx/scale
        dy = dy/scale
        assert(numpy.allclose(numpy.array([dx, dy]), numpy.array([-1.0, 0.0]), atol = 1.0e-6))

        # Test that we are correcting in the right direction.
        h5d.setDriftCorrectionXY(dx, dy)
        im2 = h5d.grid2D(drift_corrected = True)
        [corr, dx, dy, success] = imagecorrelation.xyOffset(im1, im2, scale)
        dx = dx/scale
        dy = dy/scale

        assert(numpy.allclose(numpy.array([dx, dy]), numpy.array([0.0, 0.0]), atol = 1.0e-6))

def test_drift_correction_6():
    """
    Test Z offset determination & correction.
    """
    n_locs = 500
    peaks = {"x" : numpy.random.normal(loc = 10.0, scale = 0.2, size = n_locs),
             "y" : numpy.random.normal(loc = 10.0, scale = 0.2, size = n_locs),
             "z" : numpy.random.normal(scale = 0.05, size = n_locs)}

    h5_name = storm_analysis.getPathOutputTest("test_dc_hdf5.hdf5")

    # Save peaks.
    t_dz = 0.3
    with saH5Py.SAH5Py(h5_name, is_existing = False, overwrite = True) as h5:
        h5.setMovieInformation(20, 20, 2, "")
        h5.addLocalizations(peaks, 0)
        peaks["z"] += t_dz
        h5.addLocalizations(peaks, 1)

    scale = 2
    z_min = -1.0
    z_max = 1.0
    z_bins = int((z_max - z_min)/0.05)
    with driftUtils.SAH5DriftCorrection(filename = h5_name, scale = scale, z_bins = z_bins) as h5d:
        h5d.setFrameRange(0,1)
        im1 = h5d.grid3D(z_min, z_max)
        h5d.setFrameRange(1,2)
        im2 = h5d.grid3D(z_min, z_max)

        # Check that both images have the same number localizations.
        assert(numpy.sum(im1) == numpy.sum(im2))

        # Measure offset.
        [corr, fit, dz, success] = imagecorrelation.zOffset(im1, im2)

        # Test that it succeeded.
        assert(success)

        # Check result.
        dz = dz * (z_max - z_min)/float(z_bins)
        assert(abs(dz - t_dz)/t_dz < 0.1)
        
        # Test that we are correcting in the right direction.
        h5d.setDriftCorrectionZ(-dz)
        im2 = h5d.grid3D(z_min, z_max, drift_corrected = True)
        [corr, fit, dz, success] = imagecorrelation.zOffset(im1, im2)
        dz = -dz * (z_max - z_min)/float(z_bins)
        assert(abs(dz) < 0.1)
        
    
if (__name__ == "__main__"):
    test_drift_correction_1()
    test_drift_correction_2()
    test_drift_correction_3()
    test_drift_correction_4()
    test_drift_correction_5()
    test_drift_correction_6()
