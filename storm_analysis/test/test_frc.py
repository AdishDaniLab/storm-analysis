#!/usr/bin/env python

import storm_analysis


def test_frc():
    mlist_name = storm_analysis.get_data("test/data/test_drift_mlist.bin")
    results_name = storm_analysis.get_path_output_test("test_drift_frc.txt")
    
    from storm_analysis.frc.frc_calc2d import frcCalc2d
    frcCalc2d(mlist_name, results_name, False)

    
if (__name__ == "__main__"):
    test_frc()

    
