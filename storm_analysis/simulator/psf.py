#!/usr/bin/python
#
# Classes for creating different kinds of PSFs.
#
# Hazen 11/16
#

import numpy
import random

import storm_analysis.simulator.draw_gaussians_c as dg


class PSF(object):
    """
    Draws the emitter PSFs on an image.
    """
    def __init__(self, x_size, y_size, nm_per_pixel):
        self.nm_per_pixel = nm_per_pixel
        self.x_size = x_size
        self.y_size = y_size


class GaussianPSF(PSF):
    """
    Gaussian PSF.
    """
    def __init__(self, x_size, y_size, nm_per_pixel):
        PSF.__init__(self, x_size, y_size, nm_per_pixel)

    def getPSFs(self, i3_data):
        x = i3_data['x']
        y = i3_data['y']
        h = i3_data['h']

        ax = i3_data['ax']
        w = i3_data['w']
        wx = numpy.sqrt(w*w/ax)/self.nm_per_pixel
        wy = numpy.sqrt(w*w*ax)/self.nm_per_pixel

        return dg.drawGaussian((self.x_size, self,y_size),
                               [x, y, h, wx, wy])


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
