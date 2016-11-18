#!/usr/bin/env python
#
# Python interface to the C apply_drift_correction library.
#
# Hazen 10/16
#

import ctypes
import os

from storm_analysis import asciiString
import storm_analysis.sa_library.loadclib as loadclib

adc = loadclib.loadCLibrary("storm_analysis.sa_utilities", "apply-drift-correction")

adc.applyDriftCorrection.argtypes = [ctypes.c_int,
                                     ctypes.c_void_p]

def applyDriftCorrection(mlist_filename, drift_filename):
    argc = 3
    argv = (ctypes.c_char_p * argc)()
    argv[:] = [asciiString(elt) for elt in ["apply-drift-correction",
                                            mlist_filename,
                                            drift_filename]]
    adc.applyDriftCorrection(argc, argv)

if (__name__ == "__main__"):
    import sys
    
    applyDriftCorrection(*sys.argv[1:])
