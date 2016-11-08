#!/usr/bin/env python
#
# Removes current category zero molecules.
#
# Records the cluster size associated with 
# a localization in its fit area field.
#
# Hazen 11/11
#

import storm_analysis.dbscan.dbscan_c as dbscanC
import storm_analysis.sa_library.i3dtype as i3dtype
import storm_analysis.sa_library.readinsight3 as readinsight3
import storm_analysis.sa_library.writeinsight3 as writeinsight3


def clusterSize(clist_name, clist_size_name, remove_cat0 = False):
    
    # Load the data.
    i3_data_in = readinsight3.loadI3GoodOnly(clist_name)

    # Remove category zero localizations.
    if remove_cat0:
        print("warning, removing category zero localizations!")
        i3_data = i3dtype.maskData(i3_data_in, (i3_data_in['c'] != 0))
    else:
        i3_data =  i3_data_in
        
    # Record cluster localization numbers in the fit area field.
    i3_data['a'] = dbscanC.localizationClusterSize(i3_data['lk'])+1

    # Copy cluster id into the frame field.
    i3_data['fr'] = i3_data['lk']

    # Save the data.
    i3_data_out = writeinsight3.I3Writer(clist_size_name)
    i3_data_out.addMolecules(i3_data)
    i3_data_out.close()
