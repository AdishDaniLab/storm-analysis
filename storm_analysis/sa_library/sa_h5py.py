#!/usr/bin/env python
"""
Wraps h5py (http://www.h5py.org/).

Hazen 12/17
"""
import h5py
import numpy
import os
import time


# This is the maximum size of a dataset in a group of tracks.
track_block_size = 10000


class SAH5PyException(Exception):
    pass


def isSAHDF5(filename):
    """
    Queries if 'filename' is a storm-analysis HDF5 file.
    """

    # Make sure the file exists.
    if not os.path.exists(filename):
        raise SAH5PyException(filename + " does not exist.")

    # Try and open it and check that it has the expected attributes.
    try:
        with SAH5Py(filename) as h5:
            if ('version' in h5.hdf5.attrs) and ('sa_type' in h5.hdf5.attrs):
                return True
    except OSError:
        pass

    return False
            

class SAH5Py(object):
    """
    HDF5 file reader/writer.

    Important differences between this format and the old Insight3 format: 
    1. We don't swap the x/y axises on saving.
    2. We dropped the single pixel offset in x/y.
    3. We use 0 based frame indexing like the movie reader.

    The internal structure is one group per frame analyzed, with
    each localization property saved as a separate dataset.

    Localizations that have been tracked and averaged together are
    stored in groups with a maximum dataset size of 'track_block_size'.
   
    The metadata is stored in the 'metadata.xml' root dataset as a 
    variable length unicode string.

    The 'sa_type' attribute records what generated this file, one
    of the SMLM analysis programs for example, or another program
    that for example was used to merge one or more of these files.
    """
    def __init__(self, filename = None, sa_type = 'unknown', **kwds):
        super(SAH5Py, self).__init__(**kwds)

        self.last_write_time = time.time()
        self.n_track_groups = 0
        self.total_added = 0

        if os.path.exists(filename):
            self.hdf5 = h5py.File(filename, "r+")
            self.existing = True
        else:
            self.hdf5 = h5py.File(filename, "w")
            self.hdf5.attrs['version'] = 0.1
            self.hdf5.attrs['sa_type'] = sa_type
            self.existing = False
            
    def __enter__(self):
        return self

    def __exit__(self, etype, value, traceback):
        if self.hdf5:
            self.hdf5.close()

    def addLocalizations(self, localizations, frame_number, channel = None):
        """
        Add localization data to the HDF5 file. Each element of localizations
        is stored in it's own dataset. In the case of multi-channel data, the
        data from the other channels is stored in datasets with the prefix 
        'cX_' where X is the channel number. The channel 0 data must be added
        first to create the group.
        """
        if (channel is not None):
            assert(isinstance(channel, int))
            
        grp_name = self.getGroupName(frame_number)
        if (channel is None) or (channel == 0):
            grp = self.hdf5.create_group(grp_name)

            # Add initial values for drift correction. These only apply to
            # channel 0.
            grp.attrs['dx'] = 0.0
            grp.attrs['dy'] = 0.0
            grp.attrs['dz'] = 0.0

            # Update counter. Notes:
            #
            # 1. This assumes the existance of the "x" field.
            # 2. This is not necessarily the same as the total number of
            #    localizations in a file as there could for example have
            #    been an analysis restart.
            #
            grp.attrs['n_locs'] = localizations["x"].size
            self.total_added += localizations["x"].size
        else:
            grp = self.getGroup(frame_number)

        for key in localizations:
            d_name = key
            if (channel is not None) and (channel > 0):
                d_name = "c" + str(channel) + "_" + key
            grp.create_dataset(d_name, data = localizations[key])

        # Flush the file once a minute.
        #
        # FIXME: Not sure if this a bad idea, as for example this might
        #        already be handled in some way by HDF5.
        # 
        current_time = time.time()
        if (current_time > (self.last_write_time + 60.0)):
            self.last_write_time = current_time
            self.hdf5.flush()
            
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

    def addMovieInformation(self, movie_reader):
        """
        Store some properties of the movie as attributes.
        """
        self.hdf5.attrs['movie_hash_value'] = movie_reader.hashID()
        self.hdf5.attrs['movie_l'] = movie_reader.getMovieL()
        self.hdf5.attrs['movie_x'] = movie_reader.getMovieX()
        self.hdf5.attrs['movie_y'] = movie_reader.getMovieY()

    def addTracks(self, tracks):
        """
        Add tracks to the HDF5 file. Tracks are one or more localizations 
        that have been averaged together.

        Note that all the tracks have to added in a single instantiation. 
        If you close this object then the new object will start over and 
        overwrite any existing tracking information.
        """
        # Create tracks group, if necessary.
        if(self.n_track_groups == 0):

            # Delete old tracking information, if any.
            if("tracks" in self.hdf5):
                del self.hdf5["tracks"]
            self.hdf5.create_group("tracks")

        track_grp = self.hdf5["tracks"]
        grp = track_grp.create_group(self.getTrackGroupName(self.n_track_groups))

        # Add the tracks.
        for field in tracks:
            grp.create_dataset(field, data = tracks[field])
        grp.attrs['n_tracks'] = tracks["tx"].size

        self.n_track_groups += 1
        track_grp.attrs['n_groups'] = self.n_track_groups
        
    def close(self):
        print("Added", self.total_added)
        self.hdf5.close()
    
    def getFileType(self):
        return self.hdf5.attrs['sa_type']
    
    def getFileVersion(self):
        return self.hdf5.attrs['version']

    def getGroup(self, frame_number):
        grp_name = self.getGroupName(frame_number)
        if grp_name in self.hdf5:
            return self.hdf5[grp_name]

    def getGroupName(self, frame_number):
        assert(isinstance(frame_number, int))
        return "/fr_" + str(frame_number)

    def getLocalizations(self, drift_corrected = False, fields = None):
        return self.getLocalizationsInFrameRange(0,
                                                 self.hdf5.attrs['movie_l'],
                                                 drift_corrected = drift_corrected,
                                                 fields = fields)
    
    def getLocalizationsInFrame(self, frame_number, drift_corrected = False, fields = None):

        locs = {}
        grp = self.getGroup(frame_number)
        
        if grp is not None:

            # Return all the datasets in the group.
            if fields is None:
                for field in grp:
                    locs[field] = grp[field][()]

            # Return only the fields that the user requested.
            else:
                for field in fields:
                    locs[field] = grp[field][()]

        if drift_corrected and bool(locs):
            if "x" in locs:
                locs["x"] += grp.attrs['dx']
            if "y" in locs:
                locs["y"] += grp.attrs['dy']
            if "z" in locs:
                locs["z"] += grp.attrs['dz']

        return locs

    def getLocalizationsInFrameRange(self, start, stop, drift_corrected = False, fields = None):
        """
        Return the localizations in the range start <= frame number < stop.
        """
        assert(stop > start)
        locs = {}
        for i in range(start, stop):
            temp = self.getLocalizationsInFrame(i,
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
        """
        Return the dimensions of the movie and it's hash value ID.
        """
        return [self.hdf5.attrs['movie_x'],
                self.hdf5.attrs['movie_y'],
                self.hdf5.attrs['movie_l'],
                self.hdf5.attrs['movie_hash_value']]

    def getMovieLength(self):
        """
        Return the length of the movie.
        """
        return self.hdf5.attrs['movie_l']

    def getNLocalizations(self):
        n_locs = 0
        for i in range(self.getMovieLength()):
            grp = self.getGroup(i)
            if(grp is not None):
                n_locs += grp.attrs['n_locs']
        return n_locs

    def getNTracks(self):
        if(not "tracks" in self.hdf5):
            return 0
        track_grp = self.hdf5["tracks"]
        n_tracks = 0
        for i in range(track_grp.attrs['n_groups']):
            n_tracks += track_grp[self.getTrackGroupName(i)].attrs['n_tracks']
        return n_tracks

    def getTrackGroupName(self, index):
        return "tracks_" + str(index)
                
    def isAnalyzed(self, frame_number):
        return not self.getGroup(frame_number)
        
    def isExisting(self):
        """
        Return TRUE if the underlying HDF5 file already existed, FALSE if
        we just created it.
        """
        return self.existing

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


if (__name__ == "__main__"):

    import os
    import sys

    from xml.etree import ElementTree

    if (len(sys.argv) != 2):
        print("usage: <hdf5_file>")
        exit()

    if not os.path.exists(sys.argv[1]):
        print("File", sys.argv[1], "not found.")
        exit()
        
    with SAH5Py(sys.argv[1]) as h5:
        metadata = ElementTree.fromstring(h5.getMetadata())

        print(" meta data:")
        for node in sorted(metadata, key = lambda node: node.tag):
            print("    " + node.tag.strip() + " - " + node.text.strip())

        print()
        print("Frames:", h5.getMovieLength())
        print("Localizations:", h5.getNLocalizations())
        print("Tracks:", h5.getNTracks())
        print()
        print("Localization statistics:")
        
        locs = h5.getLocalizations()
        print(locs["x"].size)
        for field in locs:
            print("  {0:15} {1:.3f} {2:.3f} {3:.3f} {4:.3f}".format(field,
                                                                    numpy.mean(locs[field]),
                                                                    numpy.std(locs[field]),
                                                                    numpy.min(locs[field]),
                                                                    numpy.max(locs[field])))
