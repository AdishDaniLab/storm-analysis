#!/usr/bin/env python

import storm_analysis
    
def test_l1h():

    # Test setupAMatrix.
    a_matrix_file = storm_analysis.getData("test/data/test_l1h")
    storm_analysis.removeFile(a_matrix_file)

    from storm_analysis.L1H.setup_A_matrix import setupAMatrix
    setupAMatrix("theoritical", a_matrix_file, 1.0, False)

    # Test L1H.
    movie_name = storm_analysis.getData("test/data/test_l1h.dax")
    settings = storm_analysis.getData("test/data/test_l1h.xml")
    hres = storm_analysis.getPathOutputTest("test_l1h_list.hres")
    mlist = storm_analysis.getPathOutputTest("test_l1h_list.bin")
    storm_analysis.removeFile(hres)
    storm_analysis.removeFile(mlist)

    from storm_analysis.L1H.cs_analysis import analyze
    analyze(movie_name, settings, hres, mlist)
    

if (__name__ == "__main__"):
    test_l1h()

