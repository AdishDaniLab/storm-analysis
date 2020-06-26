#!/usr/bin/env python
"""
Automation of storm-analysis using daostorm. By'automation' I mean it will extract the em gain, preamp gain and the imaging sequence information directly from a movie_name.xml file to create analysis_settings_movie_name.xml. 
Gayatri 06/20
"""

import os
import numpy
import glob
from xml.etree import ElementTree
import time

import storm_analysis.daostorm_3d.mufit_analysis as mFit
import storm_analysis.sa_utilities.hdf5_to_bin as hdf5ToBin
import storm_analysis.sa_library.parameters as parameters

# Change directory
os.chdir("/home/gayatri/storm-data/daostorm-analysis-folder")

# Create analysis settings file if required.
def makeSettingsFile(movie_name):
    
    img_params_file = movie_name + '.xml'
    root = ElementTree.parse(img_params_file).getroot()
    
    for gain in root.iter('emccd_gain'):
        em_gain = float(gain.text)
    
    for preamp in root.iter('preampgain'):
        preamp_gain = preamp.text
    
    for shutter_seq in root.iter('shutters'):
        sh_seq = shutter_seq.text
    
    e_per_cnt = {'1.0':20.4, '2.0':10.3, '3.0':4.74}
    camera_gain = (em_gain/e_per_cnt[preamp_gain])*2.0
    print('Camera gain = ', camera_gain)
    seq = sh_seq.rsplit("\\",1)[1][:].rsplit('.xml',1)[0][:].split('_')
    
    descriptor = "0"*int(seq[0]) + "2" + "1"*(int(seq[1])-1) + "0"*int(seq[0]) + "3" + "1"*(int(seq[1])-1)

    # Make calibration analysis XML file.
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
    params.changeAttr("threshold", 18.0)
    params.changeAttr("roi_size", 17)
    params.changeAttr("find_max_radius", 10, node_type = "int")

    # For labelling frames as channel 1,2 or non-specific (0) 
    params.changeAttr("descriptor", descriptor)
    
    params.changeAttr("iterations", 1)
      
    params.changeAttr("verbosity", 50)
      
    # For tracking
    params.changeAttr("radius", "0.5")
    params.changeAttr("max_gap", "0.0")

    # z fitting parameters

    params.changeAttr("do_zfit", "0")
    params.changeAttr("cutoff", "2.0")

    params.changeAttr("max_z", "0.6")
    params.changeAttr("min_z", "-0.6")

    params.changeAttr("wxA", "0.050119582755921564")
    params.changeAttr("wxB", "-0.038482334539429654")
    params.changeAttr("wxC", "0.0")
    params.changeAttr("wxD", "0.0")
    params.changeAttr("wx_c", "-144.081886319453")
    params.changeAttr("wx_d", "377.13320076926516")
    params.changeAttr("wx_wo", "336.48962165491014")
    params.changeAttr("wyA", "-0.32957504814432875")
    params.changeAttr("wyB", "-0.08975268030962602")
    params.changeAttr("wyC", "0.0")
    params.changeAttr("wyD", "0.0")
    params.changeAttr("wy_c", "146.22755402271096")
    params.changeAttr("wy_d", "377.1703414484828")
    params.changeAttr("wy_wo", "318.16521710703404")

    params.changeAttr("z_correction", "0")
    params.changeAttr("z_step", "0.001")
    params.changeAttr("z_value", "0.0")

    params.changeAttr("drift_correction", 1)
    params.changeAttr("frame_step", 500)
    params.changeAttr("d_scale", 2)

    params.changeAttr("convert_to", '.bin')

    params.toXMLFile("analysis_settings_"+movie_name+".xml", pretty = True)


if (__name__ == "__main__"):

    start_time = time.time()
    movies = sorted(glob.glob('storm_*.dax'))
    for movie in movies :
        movie_name = movie.rsplit('.dax',1)[0][:]
        print('Analyzing ', movie_name, 'now')
        h5 = movie_name+'_daostorm.hdf5'
        if os.path.exists(h5):
            os.remove(h5)
        if os.path.exists("analysis_settings_"+movie_name+".xml"):
            mFit.analyze(movie, h5, "analysis_settings_"+movie_name+".xml")
        else:
            makeSettingsFile(movie_name)
            print('Made settings file, now let starting analysis')
            mFit.analyze(movie, h5, "analysis_settings_"+movie_name+".xml")
        
        
    print("--- %s seconds ---" % (time.time() - start_time))