#!/usr/bin/env python
"""
Tests of our HDF5 reader, or perhaps more accurately test of our 
understanding of how to use the h5py module.
"""
import numpy

import storm_analysis
import storm_analysis.sa_library.sa_h5py as saH5Py

import storm_analysis.dbscan.clusters_sa_h5py as clSAH5Py


def test_cl_sa_h5py_1():
    """
    Test basic cluster file mechanics (using localizations).
    """
    locs = {"x" : numpy.arange(10, dtype = numpy.float),
            "y" : numpy.arange(10, dtype = numpy.float)}

    filename = "test_clusters_sa_h5py.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)

    # Write localization data.
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieInformation(1,1,2,"")
        h5.addLocalizations(locs, 1)

    # Write clustering data for localizations.
    cluster_id = numpy.remainder(numpy.arange(10), 3)
    cluster_data = {"frame" : numpy.ones(10, dtype = numpy.int),
                    "loc_id" : numpy.arange(10)}

    cl_size = [4, 3, 3]
    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        cl_h5.addClusters(cluster_id, cluster_data)

        assert(cl_h5.getNClusters() == (len(cl_size) - 1))
        for index, cluster in cl_h5.clustersIterator():
            for field in cluster:
                assert(cluster[field].size == cl_size[index])

        for index, cluster in cl_h5.clustersIterator(skip_unclustered = False):
            for field in cluster:
                assert(cluster[field].size == cl_size[index])                


def test_cl_sa_h5py_2():
    """
    Test basic cluster file mechanics (using tracks).
    """
    tracks = {"x" : numpy.arange(11, dtype = numpy.float),
              "y" : numpy.arange(11, dtype = numpy.float)}

    filename = "test_clusters_sa_h5py.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)

    # Write localization data.
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieInformation(1,1,2,"")
        h5.addTracks(tracks)

    # Write clustering data for tracks.
    cluster_id = numpy.remainder(numpy.arange(11), 3)
    cluster_data = {"track_id" : numpy.zeros(11, dtype = numpy.int),
                    "loc_id" : numpy.arange(11)}

    cl_size = [4, 4, 3]
    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        cl_h5.addClusters(cluster_id, cluster_data)

        assert(cl_h5.getNClusters() == (len(cl_size) - 1))
        for index, cluster in cl_h5.clustersIterator(skip_unclustered = False):
            for field in cluster:
                assert(cluster[field].size == cl_size[index])
                

def test_cl_sa_h5py_3():
    """
    Test that iterator behaves properly if there are no clusters.
    """
    tracks = {"x" : numpy.arange(11, dtype = numpy.float),
              "y" : numpy.arange(11, dtype = numpy.float)}

    filename = "test_clusters_sa_h5py.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)

    # Write localization data.
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieInformation(1,1,2,"")
        h5.addTracks(tracks)

    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        for index, cluster in cl_h5.clustersIterator(skip_unclustered = False):
            assert False


def test_cl_sa_h5py_4():
    """
    Test cluster info string round trip.
    """
    locs = {"x" : numpy.arange(10, dtype = numpy.float),
            "y" : numpy.arange(10, dtype = numpy.float)}

    filename = "test_clusters_sa_h5py.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)

    # Write localization data.
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieInformation(1,1,2,"")
        h5.addLocalizations(locs, 1)

    # Write clustering data for localizations.
    cluster_id = numpy.remainder(numpy.arange(10), 3)
    cluster_data = {"frame" : numpy.ones(10, dtype = numpy.int),
                    "loc_id" : numpy.arange(10)}

    info_string = "dbscan,eps,10.0,mc,5"
    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        cl_h5.addClusters(cluster_id, cluster_data)

        cl_h5.setClusteringInfo(info_string)
        assert (cl_h5.getClusteringInfo() == info_string)


def test_cl_sa_h5py_5():
    """
    Test getting all of the localizations for clustering.
    """
    locs = {"x" : numpy.arange(4, dtype = numpy.float),
            "y" : numpy.arange(4, dtype = numpy.float)}

    filename = "test_clusters_sa_h5py.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)

    # Write localization data.
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieInformation(1,1,5,"")
        h5.setPixelSize(1.0)
        h5.addLocalizations(locs, 1)
        h5.addLocalizations(locs, 3)

    # Test getting all the localization data.
    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        [x, y, z, cl_dict] = cl_h5.getDataForClustering()
        assert(numpy.allclose(x, cl_dict['loc_id']))
        assert(numpy.allclose(y, cl_dict['loc_id']))
        assert(numpy.allclose(z, numpy.zeros(x.size)))
        assert(numpy.allclose(cl_dict['frame'], numpy.array([1,1,1,1,3,3,3,3])))


def test_cl_sa_h5py_6():
    """
    Test getting all of the tracks for clustering.
    """
    tracks = {"x" : numpy.arange(4, dtype = numpy.float),
              "y" : numpy.arange(4, dtype = numpy.float),
              "z" : numpy.arange(4, dtype = numpy.float)}

    filename = "test_clusters_sa_h5py.hdf5"
    h5_name = storm_analysis.getPathOutputTest(filename)
    storm_analysis.removeFile(h5_name)

    # Write localization data.
    with saH5Py.SAH5Py(h5_name, is_existing = False) as h5:
        h5.setMovieInformation(1,1,2,"")
        h5.setPixelSize(1.0)
        h5.addTracks(tracks)
        h5.addTracks(tracks)

    # Test getting all the tracking data (ignoring z).
    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        [x, y, z, cl_dict] = cl_h5.getDataForClustering()
        assert(numpy.allclose(x, cl_dict['loc_id']))
        assert(numpy.allclose(y, cl_dict['loc_id']))
        assert(numpy.allclose(z, numpy.zeros(x.size)))
        assert(numpy.allclose(cl_dict['track_id'], numpy.array([0,0,0,0,1,1,1,1])))

    # Test getting all the tracking data (not ignoring z).
    with clSAH5Py.SAH5Clusters(h5_name) as cl_h5:
        [x, y, z, cl_dict] = cl_h5.getDataForClustering(ignore_z = False)
        assert(numpy.allclose(x, cl_dict['loc_id']))
        assert(numpy.allclose(y, cl_dict['loc_id']))
        assert(numpy.allclose(z, 1000.0*cl_dict['loc_id']))
        assert(numpy.allclose(cl_dict['track_id'], numpy.array([0,0,0,0,1,1,1,1])))
        
        
if (__name__ == "__main__"):
    test_cl_sa_h5py_1()
    test_cl_sa_h5py_2()
    test_cl_sa_h5py_3()
    test_cl_sa_h5py_4()
    test_cl_sa_h5py_5()
    test_cl_sa_h5py_6()


    
