#!/usr/bin/env python
"""
Tests some aspect of ia_utilities.
"""
import numpy
import tifffile

import storm_analysis.sa_library.dao_fit_c as daoFitC
import storm_analysis.sa_library.ia_utilities_c as iaUtilsC
import storm_analysis.simulator.draw_gaussians_c as dg


def imagesCopy(images):
    images_copy = []
    for image in images:
        images_copy.append(numpy.copy(image))
    return images_copy

        
def test_ia_util_1():
    """
    Test finding peaks in an empty image.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [0.1]

    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(images)
    assert(x.size == 0)

def test_ia_util_2():
    """
    Test finding peaks in an image.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [0.1]

    # Above threshold, unequal height.
    images[0][10,11] = 1.1
    images[0][10,12] = 1.5

    # Above threshold, unequal height.
    images[0][15,8] = 1.5
    images[0][15,9] = 1.5

    # Below threshold.
    images[0][20,11] = 0.5
    
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(images)

    assert (x.size == 2)
    for i in range(z.size):
        assert (abs(z[i] - z_values[0]) < 1.0e-6)

def test_ia_util_3():
    """
    Test agreement with fitting regarding orientation.
    """
    height = 20.0
    sigma = 1.5
    x_size = 100
    y_size = 120
    background = numpy.zeros((x_size, y_size)) + 10.0
    image = dg.drawGaussians((x_size, y_size),
                             numpy.array([[20.0, 40.0, height, sigma, sigma]]))
    image += background

    # Configure fitter.
    mfit = daoFitC.MultiFitter2D()
    mfit.initializeC(image)
    mfit.newImage(image)
    mfit.newBackground(background)

    # Configure finder.
    z_values = [0.0]
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2 * sigma,
                                threshold = background[0,0] + 0.5*height,
                                z_values = z_values)
    
    # Find peaks.
    [x, y, z] = mxf.findMaxima([image])

    sigma = numpy.ones(x.size) * sigma
    peaks = numpy.stack([x, y, z, sigma], axis = 1)

    # Pass peaks to fitter.
    mfit.newPeaks(peaks, "finder")

    # Check height.
    h = mfit.getPeakProperty("height")
    for i in range(h.size):
        assert (abs(h[i] - height)/height < 0.1)

    # Check background.
    bg = mfit.getPeakProperty("background")
    for i in range(bg.size):
        assert (abs(bg[i] - 10.0) < 1.0e-6)

    mfit.cleanup(verbose = False)

def test_ia_util_4():
    """
    Multiple z planes test.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64),
              numpy.zeros((x_size,y_size), dtype = numpy.float64),
              numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [1.0,2.0,3.0]

    images[0][20,10] = 1.3
    images[1][20,10] = 1.2
    images[2][20,10] = 1.5

    # Default z range (the entire stack).
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert(x.size == 1)
    assert(abs(z[0] - z_values[2]) < 1.0e-6)

    # z range is limited to adjacent slices.
    #
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_range = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert(x.size == 2)
    assert(abs(z[0] - z_values[0]) < 1.0e-6)
    assert(abs(z[1] - z_values[2]) < 1.0e-6)

    # z range is limited to current slice.
    #
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_range = 0,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert(x.size == 3)
    for i in range(z.size):
        assert(abs(z[i] - z_values[i]) < 1.0e-6)
    
def test_ia_util_5():
    """
    Test that limits on the number of peak duplicates are working.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [0.1]

    # Single peak.
    images[0][10,21] = 1.1
    images[0][10,20] = 1.2
    
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_values = z_values)

    # Find the peak.
    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 1)

    # This should not find anything, since the peak was
    # already found above.
    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 0)

    # Reset and now we should find it again.
    mxf.resetTaken()
    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 1)
    
def test_ia_util_6():
    """
    Test radius.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [0.1]

    images[0][10,23] = 1.2
    images[0][10,22] = 1.1
    images[0][10,21] = 1.1
    images[0][10,20] = 1.2

    # Should only find 1 peak.    
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 3,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 1)

    # Should find two peaks.
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                radius = 2,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 2)

def test_ia_util_7():
    """
    Test margin.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [0.1]

    images[0][10,5] = 1.2
    images[0][10,6] = 1.1
    images[0][10,7] = 1.1
    images[0][20,10] = 1.1
    images[0][20,11] = 1.2

    # Should only find 1 peak.
    mxf = iaUtilsC.MaximaFinder(margin = 6,
                                radius = 3,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 1)

    # Should find two peaks.
    mxf = iaUtilsC.MaximaFinder(margin = 4,
                                radius = 3,
                                threshold = 1,
                                z_values = z_values)

    [x, y, z] = mxf.findMaxima(imagesCopy(images))
    assert (x.size == 2)

def test_ia_util_8():
    """
    Test allowing multiple duplicates.
    """
    x_size = 100
    y_size = 80
    images = [numpy.zeros((x_size,y_size), dtype = numpy.float64)]
    z_values = [0.1]

    # Single peak.
    images[0][10,21] = 1.1
    images[0][10,20] = 1.2
    
    mxf = iaUtilsC.MaximaFinder(margin = 1,
                                n_duplicates = 2,
                                radius = 2,
                                threshold = 1,
                                z_values = z_values)

    # Find the peak.
    np = [1, 1, 0]
    for elt in np:
        [x, y, z] = mxf.findMaxima(imagesCopy(images))
        assert (x.size == elt)

    # Reset.
    mxf.resetTaken()
    
    # Test again.
    np = [1, 1, 0]
    for elt in np:
        [x, y, z] = mxf.findMaxima(imagesCopy(images))
        assert (x.size == elt)


if (__name__ == "__main__"):
#    test_ia_util_1()
#    test_ia_util_2()
#    test_ia_util_3()
#    test_ia_util_4()
#    test_ia_util_5()
#    test_ia_util_6()
#    test_ia_util_7()
    test_ia_util_8()
