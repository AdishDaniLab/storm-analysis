#!/usr/bin/env python

import storm_analysis


def test_3ddao_2d_fixed():

    movie_name = storm_analysis.getData("test/data/test.dax")
    settings = storm_analysis.getData("test/data/test_3d_2d_fixed.xml")
    mlist = storm_analysis.getPathOutputTest("test_3d_2d_fixed.bin")
    storm_analysis.removeFile(mlist)

    from storm_analysis.daostorm_3d.mufit_analysis import analyze
    analyze(movie_name, mlist, settings)

    
def test_3ddao_2d_fixed_low_snr():

    movie_name = storm_analysis.getData("test/data/test_low_snr.dax")
    settings = storm_analysis.getData("test/data/test_3d_2d_fixed_low_snr.xml")
    mlist = storm_analysis.getPathOutputTest("test_3d_2d_fixed_low_snr.bin")
    storm_analysis.removeFile(mlist)
    
    from storm_analysis.daostorm_3d.mufit_analysis import analyze
    analyze(movie_name, mlist, settings)


def test_3ddao_2d_fixed_non_square():

    movie_name = storm_analysis.getData("test/data/test_300x200.dax")
    settings = storm_analysis.getData("test/data/test_3d_2d_fixed.xml")
    mlist = storm_analysis.getPathOutputTest("test_3d_2d_300x200.bin")
    storm_analysis.removeFile(mlist)

    from storm_analysis.daostorm_3d.mufit_analysis import analyze
    analyze(movie_name, mlist, settings)

    
def test_3ddao_2d():

    movie_name = storm_analysis.getData("test/data/test.dax")
    settings = storm_analysis.getData("test/data/test_3d_2d.xml")
    mlist = storm_analysis.getPathOutputTest("test_3d_2d.bin")
    storm_analysis.removeFile(mlist)

    from storm_analysis.daostorm_3d.mufit_analysis import analyze
    analyze(movie_name, mlist, settings)


def test_3ddao_3d():

    movie_name = storm_analysis.getData("test/data/test.dax")
    settings = storm_analysis.getData("test/data/test_3d_3d.xml")
    mlist = storm_analysis.getPathOutputTest("test_3d_3d.bin")
    storm_analysis.removeFile(mlist)

    from storm_analysis.daostorm_3d.mufit_analysis import analyze
    analyze(movie_name, mlist, settings)


def test_3ddao_Z():

    movie_name = storm_analysis.getData("test/data/test.dax")
    settings = storm_analysis.getData("test/data/test_3d_Z.xml")
    mlist = storm_analysis.getPathOutputTest("test_3d_Z.bin")
    storm_analysis.removeFile(mlist)

    from storm_analysis.daostorm_3d.mufit_analysis import analyze
    analyze(movie_name, mlist, settings)

    
if (__name__ == "__main__"):
    test_3ddao_2d_fixed()
    test_3ddao_2d_fixed_low_snr()
    test_3ddao_2d_fixed_non_square()
    test_3ddao_2d()
    test_3ddao_3d()
    test_3ddao_Z()
