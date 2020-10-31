#!/usr/bin/env python
"""
Automation of storm-analysis using daostorm. It extracts the em gain, preamp gain and the imaging sequence information directly from a movie_name.xml file to create analysis_settings_movie_name.xml. 
Gayatri 06/20
"""

import os
import numpy
import glob
from xml.etree import ElementTree
import time

import storm_analysis.daostorm_3d.mufit_analysis as mFit
# import storm_analysis.sa_utilities.hdf5_to_bin as hdf5ToBin
import storm_analysis.sa_library.parameters as parameters
import storm_analysis.sa_utilities.hdf5_to_txt as hdf5ToTxt

# Change directory
os.chdir("/home/gayatri/storm/cochlea/exp-6-p15-9-Oct/F4-20-10-13-ribA-homer")

# Create analysis settings file if required.
def makeSettingsFile(movie_name,des):
    
    img_params_file = movie_name + '.xml'
    root = ElementTree.parse(img_params_file).getroot()
    
    for gain in root.iter('emccd_gain'):
        em_gain = float(gain.text)
    
    for preamp in root.iter('preampgain'):
        preamp_gain = preamp.text
    
    for shutter_seq in root.iter('shutters'):
        sh_seq = shutter_seq.text
    
    e_per_cnt = {'1.0':16.2, '2.0':8.14, '3.0':4.74}
    camera_gain = (em_gain/e_per_cnt[preamp_gain])*0.9
    print('Camera gain = ', camera_gain)
    # For 2 channel
    seq = sh_seq.rsplit("\\",1)[1][:].rsplit('.xml',1)[0][:].split('_')

    # descriptor = "0"*int(seq[0]) + "2" + "1"*(int(seq[1])-1) + "0"*int(seq[2]) + "3" + "1"*(int(seq[3])-1)     # Two-channel
    descriptor = "0"*int(seq[0]) + "2" + "1"*(int(seq[1])-1) + "0"*int(seq[0]) + "3" + "1"*(int(seq[1])-1) 
    # descriptor = "0"*int(seq[0]) + "2" + "1"*(int(seq[1])-1)      # Single-channel with shuttering
    # descriptor = "2"*int(seq[0]) + "1"*(int(seq[1]))          
    # descriptor = '0221103311'                                            # Single-channel
    # descriptor = '0021100311' # 2+3, 647 continuous, keeping second activation frame as first channel frame.
    # Create a 3D-DAOSTORM parameters object.
    print('Descriptor : ', descriptor)
    params = parameters.ParametersDAO()

    params.changeAttr("start_frame", -1)
    params.changeAttr("max_frame", -1)
    # Model for fitting and peak finding
    params.changeAttr("model", "3d")
    params.changeAttr("fit_error_model", "MLE")
    # Camera parameters
    params.changeAttr("camera_gain", camera_gain)
    params.changeAttr("camera_offset", 500.0)
    params.changeAttr("pixel_size", 160.0)
    # Fitting parameters
    params.changeAttr("background_sigma", 8.0)
    params.changeAttr("foreground_sigma", 1.0)
    params.changeAttr("sigma", 1.0)
    params.changeAttr("sigma_range", [0.8, 1.5])
    params.changeAttr("threshold", 20.0)
    params.changeAttr("roi_size", 12)
    params.changeAttr("find_max_radius", 5, node_type = "int")

    # For labelling frames as channel 1,2 or non-specific (0) 
    params.changeAttr("descriptor", descriptor)
    
    params.changeAttr("iterations", 40)
      
    params.changeAttr("verbosity", 50)
    
    # For tracking
    params.changeAttr("radius", "0.5")
    params.changeAttr("max_gap", "0")

    # z fitting parameters

    params.changeAttr("do_zfit", "1")
    params.changeAttr("cutoff", "2.0")

    params.changeAttr("max_z", "0.4")
    params.changeAttr("min_z", "-0.4")

    params.changeAttr("wxA", "0.034282347863598454")
    params.changeAttr("wxB", "0.10926698657109035")
    params.changeAttr("wxC", "0.0")
    params.changeAttr("wxD", "0.0")
    params.changeAttr("wx_c", "-139.183936547655")
    params.changeAttr("wx_d", "350.87800232410655")
    params.changeAttr("wx_wo", "326.92741964737354")
    params.changeAttr("wyA", "-0.13417028672413644")
    params.changeAttr("wyB", "0.035465457674593366")
    params.changeAttr("wyC", "0.0")
    params.changeAttr("wyD", "0.0")
    params.changeAttr("wy_c", "145.22731351696117")
    params.changeAttr("wy_d", "315.5323056186388")
    params.changeAttr("wy_wo", "312.5879140555045")

    params.changeAttr("z_correction", "1")
    params.changeAttr("z_step", "0.001")
    params.changeAttr("z_value", "0.0")

    params.changeAttr("drift_correction", 1)
    params.changeAttr("frame_step", 500)
    params.changeAttr("d_scale", 2)

    params.changeAttr("convert_to", '.bin')

    params.toXMLFile("analysis_settings_" + movie_name + des + ".xml", pretty = True)


if (__name__ == "__main__"):

    start_time = time.time()
    movies = sorted(glob.glob('movie_*.dax'))
    des = '_dao_tr' # A description about the analysis
    for movie in movies :
        movie_name = movie.rsplit('.dax',1)[0][:]
        print('Analyzing ', movie_name, 'now')
        h5 = movie_name + des + '.hdf5'
        if os.path.exists(h5):
            os.remove(h5)
        # if os.path.exists("analysis_settings_"+movie_name+".xml"):
            # mFit.analyze(movie, h5, "analysis_settings_"+movie_name+".xml")
        # else:
        makeSettingsFile(movie_name,des)
        print('Made settings file.')
        mFit.analyze(movie, h5, "analysis_settings_" + movie_name + des + ".xml")
        hdf5ToTxt.hdf5ToTxt(h5, movie_name + des + '.csv')
        
        
    print("--- %s seconds ---" % (time.time() - start_time))