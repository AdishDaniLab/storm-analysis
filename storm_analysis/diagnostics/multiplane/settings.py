#!/usr/bin/env python
"""
Settings to use in Spliner simulations.

Note: Background photons are per plane, total photons are divided across all the planes.

Hazen 09/17
"""
import numpy

camera_gain = 1.0
camera_offset = 100.0
camera_variance = 1.0
independent_heights = 0

# Mapping with a small offset.
if True:
    mappings = {"0_0_x" : numpy.array([0.0, 1.0, 0.0]),
                "0_0_y" : numpy.array([0.0, 0.0, 1.0]),
                "0_1_x" : numpy.array([2.0, 1.0, 0.0]),
                "0_1_y" : numpy.array([5.0, 0.0, 1.0]),
                "1_0_x" : numpy.array([-2.0, 1.0, 0.0]),
                "1_0_y" : numpy.array([-5.0, 0.0, 1.0])}

# Mapping with x flip.
else:
    mappings = {"0_0_x" : numpy.array([0.0, 1.0, 0.0]),
                "0_0_y" : numpy.array([0.0, 0.0, 1.0]),
                "0_1_x" : numpy.array([302.0, -1.0, 0.0]),
                "0_1_y" : numpy.array([5.0, 0.0, 1.0]),
                "1_0_x" : numpy.array([302.0, -1.0, 0.0]),
                "1_0_y" : numpy.array([-5.0, 0.0, 1.0])}

n_frames = 5
photons = [[10, 500], [10, 1000]]
pixel_size = 100.0
#psf_model = "psf_fft"
psf_model = "pupilfn"
#psf_model = "spline"  # This is one of 'spline', 'pupilfn' or 'psf_fft'.
psf_size = 20
pupil_fn = []
#pupil_fn = [[1.3, 2, 2]]
test_z_range = 250.0
tolerance = 0.3
x_size = 300
y_size = 200
z_planes = [-250.0, 250.0]

# These parameters are specific to particular PSF models.
psf_z_range = 600.0
psf_z_step = 200.0

pupilfn_z_range = 750.0

spline_z_range = 750.0
