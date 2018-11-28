#!/bin/bash
#
# This file is based on the following example at conda.io:
#
# http://conda.pydata.org/docs/travis.html#using-conda-with-travis-ci
#

# Download Python2 or Python3 Miniconda.
if [ $TOXENV == "2.7" ]
then
    wget https://repo.continuum.io/miniconda/Miniconda2-latest-Linux-x86_64.sh -O miniconda.sh
else
    wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh
fi
bash miniconda.sh -b -p $HOME/miniconda
export PATH="$HOME/miniconda/bin:$PATH"

# What does this do?
hash -r

# Not interactive, so always yes.
conda config --set always_yes yes --set changeps1 no

# Update conda?
conda update -q conda

# Useful for debugging any issues with conda
conda info -a
gcc --version

# Create & activate the test virtual environment.
conda create -q -n test-environment python=$TOXENV
source activate test-environment

# Install conda dependencies.
conda config --add channels conda-forge
conda install numpy scipy pytest matplotlib tifffile pillow h5py astropy shapely randomcolor pywavelets

# Compile C libraries.
scons

# Install the storm-analysis project.
python setup.py install

# Test the project.
python setup.py test
