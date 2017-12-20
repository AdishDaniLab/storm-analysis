#!/usr/bin/env python
"""
Wraps h5py (http://www.h5py.org/).

Hazen 12/17
"""
import h5py
import numpy
import os


class SAH5PyException(Exception):
    pass


class SAH5Py(object):
    """
    HDF5 file reader/writer.

    An important difference between this format and the Insight3 
    format is that we dropped the single pixel offset in x/y.

    Unlike the Insight3 format I believe we can do both at the same
    time with HDF5.

    The internal structure is one group per frame analyzed, with
    each localization property saved as a separate dataset.
   
    The metadata is stored in the 'metadata.xml' root dataset as a 
    variable length unicode string.

    The 'sa_type' attribute records what generated this file, one
    of the SMLM analysis programs for example, or another program
    that for example was used to merge one or more of these files.
    """
    def __init__(self, filename = None, sa_type = 'analysis', **kwds):
        super(SAH5Py, self).__init__(**kwds)

        if os.path.exists(filename):
            self.hdf5 = h5py.File(filename, "r+")
        else:
            self.hdf5 = h5py.File(filename, "w")
            self.hdf5.attrs['version'] = 0.1
            self.hdf5.attrs['sa_type'] = sa_type
            
    def __enter__(self):
        return self

    def __exit__(self, etype, value, traceback):
        if self.hdf5:
            self.hdf5.close()

    def addLocalizations(self, localizations, frame_number, channel = None):
        """
        Add localization data to the HDF5 file. Each element of localizations
        is stored in it's own dataset. In the case of multi-channel data, the
        data from the other channels is stored in a sub-groups of the frame
        group. Both 'frame_number' and 'channel' should be integers.
        """
        grp_name = self.getGroupName(frame_number)
        if channel is None:
            grp = self.hdf5.create_group(grp_name)

            # Add initial values for drift correction. These only apply to
            # channel 0.
            grp.attrs['dx'] = 0.0
            grp.attrs['dy'] = 0.0
            grp.attrs['dz'] = 0.0
        else:
            grp = self.hdf5[grp_name].create_group(self.getChannelName(channel))

        for key in localizations:
            grp.create_dataset(key, data = localizations[key])
            
    def addMetadata(self, metadata):
        """
        Add metadata to the HDF5 file, this is the contents of the XML file
        that was used to analyze the data along with some information about
        the size of the movie.
        """
        assert(isinstance(metadata, str))

        #dt = h5py.special_dtype(vlen = unicode)
        dt = h5py.special_dtype(vlen = str)

        # The +10 was choosen arbitrarily.
        dset_size = (int(len(metadata)+10),)
        dset = self.hdf5.create_dataset("metadata.xml", dset_size, dtype = dt)
        dset[:len(metadata)] = metadata
        self.hdf5.flush()

    def addMovieInformation(self, movie_reader):
        """
        Store some properties of the movie as attributes.
        """
        self.hdf5.attrs['movie_hash_value'] = movie_reader.hashID()
        self.hdf5.attrs['movie_l'] = movie_reader.getMovieL()
        self.hdf5.attrs['movie_x'] = movie_reader.getMovieX()
        self.hdf5.attrs['movie_y'] = movie_reader.getMovieY()
        
    def close(self):
        self.hdf5.close()

    def getChannelName(self, channel):
        assert(isinstance(channel, int))
        return "ch_" + str(channel)
    
    def getFileType(self):
        return self.hdf5.attrs['sa_type']
    
    def getFileVersion(self):
        return self.hdf5.attrs['version']

    def getGroup(self, frame_number, channel = None):
        grp_name = self.getGroupName(frame_number)
        if channel is not None:
            grp_name += "/" + self.getChannelName(channel)

        if grp_name in self.hdf5:
            return self.hdf5[grp_name]

    def getGroupName(self, frame_number):
        assert(isinstance(frame_number, int))
        return "/fr_" + str(frame_number)

    def getLocalizations(self, channel = None, drift_corrected = False, fields = None):
        return self.getLocalizationsInFrameRange(0,
                                                 self.hdf5.attrs['movie_l'],
                                                 channel = channel,
                                                 drift_corrected = drift_corrected,
                                                 fields = fields)
    
    def getLocalizationsInFrame(self, frame_number, channel = None, drift_corrected = False, fields = None):
        assert(isinstance(frame_number, int))

        locs = {}
        grp = self.getGroup(frame_number, channel)
        
        if grp is not None:
            if fields is None:
                for field in grp:
                    if not (field[:3] == "ch_"):
                        locs[field] = grp[field][()]

            else:
                for field in fields:
                    locs[field] = grp[field][()]

        if drift_corrected:
            if (channel is not None) and (channel != 0):
                raise SAH5PyException("Drift correction is only valid for channel 0!")

            if bool(locs):
                if "x" in locs:
                    locs["x"] += grp.attrs['dx']
                if "y" in locs:
                    locs["y"] += grp.attrs['dy']
                if "z" in locs:
                    locs["z"] += grp.attrs['dz']

        return locs

    def getLocalizationsInFrameRange(self, start, stop, channel = None, drift_corrected = False, fields = None):
        """
        Return the localizations in the range start <= frame number < stop.
        """
        assert(stop > start)
        locs = {}
        for i in range(start, stop):
            temp = self.getLocalizationsInFrame(i,
                                                channel = channel,
                                                fields = fields,
                                                drift_corrected = drift_corrected)
            if(not bool(temp)):
                continue
            
            for field in temp:
                if field in locs:
                    locs[field] = numpy.concatenate((locs[field], temp[field]))
                else:
                    locs[field] = temp[field]

        return locs

    def getPixelSize(self):
        if 'pixel_size' in self.hdf5.attrs:
            return self.hdf5.attrs['pixel_size']
        
    def getMetadata(self):
        if "metadata.xml" in self.hdf5:
            return self.hdf5["metadata.xml"][0]
    
    def getMovieInformation(self):
        return [self.hdf5.attrs['movie_x'],
                self.hdf5.attrs['movie_y'],
                self.hdf5.attrs['movie_l'],
                self.hdf5.attrs['movie_hash_value']]

    def setDriftCorrection(self, frame_number, dx = 0.0, dy = 0.0, dz = 0.0):
        grp = self.getGroup(frame_number)
        if grp is not None:
            grp.attrs['dx'] = dx
            grp.attrs['dy'] = dy
            grp.attrs['dz'] = dz

    def setPixelSize(self, pixel_size):
        """
        Add pixel size in information (in nanometers).
        """
        self.hdf5.attrs['pixel_size'] = pixel_size
