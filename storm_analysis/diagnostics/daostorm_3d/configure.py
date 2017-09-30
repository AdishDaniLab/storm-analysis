#!/usr/bin/env python
"""
Configure folder for 3D-DAOSTORM testing.

Hazen 09/17
"""
import inspect
import numpy
import os
import subprocess

import storm_analysis
import storm_analysis.sa_library.parameters as parameters


def testingParameters(gain, offset, model):
    """
    Create a 3D-DAOSTORM parameters object.
    """
    params = parameters.ParametersDAO()

    params.setAttr("max_frame", "int", -1)    
    params.setAttr("start_frame", "int", -1)    
    params.setAttr("append_metadata", "int", 0)
    
    params.setAttr("background_sigma", "float", 8.0)
    params.setAttr("camera_gain", "float", gain)
    params.setAttr("camera_offset", "float", offset)
    params.setAttr("find_max_radius", "int", 5)
    params.setAttr("foreground_sigma", "float", 1.0)
    params.setAttr("iterations", "int", 20)
    params.setAttr("model", "string", model)
    params.setAttr("orientation", "string", "normal")
    params.setAttr("pixel_size", "float", 100.0)
    params.setAttr("sigma", "float", 1.5)
    params.setAttr("threshold", "float", 6.0)

    # Don't do tracking.
    params.setAttr("descriptor", "string", "1")
    params.setAttr("radius", "float", "0.0")

    # Don't do drift-correction.
    params.setAttr("d_scale", "int", 2)
    params.setAttr("drift_correction", "int", 0)
    params.setAttr("frame_step", "int", 500)
    params.setAttr("z_correction", "int", 0)

    # Z fitting.
    #
    # These are nonsense values. We test either '2D' of '3D' mode
    # and check how will we do at fitting the localization widths.
    #
    params.setAttr("do_zfit", "int", 0)

    params.setAttr("cutoff", "float", 0.0)    
    params.setAttr("max_z", "float", 0.5)
    params.setAttr("min_z", "float", -0.5)
    params.setAttr("z_value", "float", 0.0)
    params.setAttr("z_step", "float", 1.0)

    params.setAttr("wx_wo", "float", 1.0)
    params.setAttr("wx_c", "float", 1.0)
    params.setAttr("wx_d", "float", 1.0)
    params.setAttr("wxA", "float", 0.0)
    params.setAttr("wxB", "float", 0.0)
    params.setAttr("wxC", "float", 0.0)
    params.setAttr("wxD", "float", 0.0)

    params.setAttr("wy_wo", "float", 1.0)
    params.setAttr("wy_c", "float", 1.0)
    params.setAttr("wy_d", "float", 1.0)
    params.setAttr("wyA", "float", 0.0)
    params.setAttr("wyB", "float", 0.0)
    params.setAttr("wyC", "float", 0.0)
    params.setAttr("wyD", "float", 0.0)

    return params
    

# Create parameters file for analysis.
#
print("Creating XML file.")
params = testingParameters(1.0, 100.0, "2d")
params.toXMLFile("dao.xml")

# Create localization on a grid file.
#
print("Creating gridded localization.")
sim_path = os.path.dirname(inspect.getfile(storm_analysis)) + "/simulator/"
subprocess.call(["python", sim_path + "emitters_on_grid.py",
                 "--bin", "grid_list.bin",
                 "--nx", "14",
                 "--ny", "9",
                 "--spacing", "20"])

# Create randomly located localizations file.
#
print("Creating random localization.")
subprocess.call(["python", sim_path + "emitters_uniform_random.py",
                 "--bin", "random_list.bin",
                 "--density", "1.0",
                 "--sx", "300",
                 "--sy", "200"])
