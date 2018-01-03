#!/usr/bin/env python
"""
Classes for simulating different dye photophysics.

Hazen 11/16
"""

import numpy
import random

import storm_analysis.sa_library.i3dtype as i3dtype

import storm_analysis.simulator.simbase as simbase


class PhotoPhysics(simbase.SimBase):
    """
    Returns location and intensity (peak height in photons) of
    the emitters that are on in the current frame.
    """
    def __init__(self, sim_fp, x_size, y_size, h5_data):
        super(PhotoPhysics, self).__init__(sim_fp, x_size, y_size, h5_data)

        
class AlwaysOn(PhotoPhysics):
    """
    All the emitters are on all the time.
    """
    def __init__(self, sim_fp, x_size, y_size, h5_data, photons = 2000):
        super(AlwaysOn, self).__init__(sim_fp, x_size, y_size, h5_data)
        self.saveJSON({"photophysics" : {"class" : "AlwaysOn",
                                         "photons" : str(photons)}})
        self.h5_data['sum'] = photons * numpy.ones(self.h5_data['x'].size)

    def getEmitters(self, frame):
        temp = {}
        for key in self.h5_data:
            temp[key] = self.h5_data[key].copy()
            
        return temp

    
class SimpleSTORM(PhotoPhysics):
    """
    Each emitter on for 1 frame out of every 1000 frames 
    on average, both are exponentially distributed.

    Args:
        on_time : Average on time in frames.
        off_time : Average off time in frames.

    """
    def __init__(self, sim_fp, x_size, y_size, h5_data, photons = 2000, on_time = 1.0, off_time = 1000.0):
        super(SimpleSTORM, self).__init__(sim_fp, x_size, y_size, h5_data)
        self.photons = photons
        self.off_time = off_time
        self.on_time = on_time

        self.n_emitters = self.i3_data['x'].size
        self.saveJSON({"photophysics" : {"class" : "SimpleSTORM",
                                         "photons" : str(self.photons),
                                         "on_time" : str(self.on_time),
                                         "off_time" : str(self.off_time)}})

        # Initially all the emitters are off.
        self.am_on = numpy.zeros(self.n_emitters, dtype = numpy.bool_)
        self.next_transistion = numpy.random.exponential(self.off_time, self.n_emitters)

    def getEmitters(self, frame):
        integrated_on = numpy.zeros(self.n_emitters)

        #
        # This is a little complicated because we are trying to include accurate
        # modeling of emitters that turned on/off more than once in a single frame.
        #
        for i in range(self.n_emitters):
                
            # The easy case, no change in state in the current frame.
            if (self.next_transistion[i] >= (frame + 1.0)):
                if self.am_on[i]:
                    integrated_on[i] = 1.0

            else:
                last_transistion = frame
                while (self.next_transistion[i] < (frame + 1.0)):
                    if self.am_on[i]:
                        integrated_on[i] += self.next_transistion[i] - last_transistion

                    self.am_on[i] = not self.am_on[i]
                    last_transistion = self.next_transistion[i]
                    if self.am_on[i]:
                        self.next_transistion[i] += numpy.random.exponential(self.on_time)
                    else:
                        self.next_transistion[i] += numpy.random.exponential(self.off_time)
                    
                # Turned on and not off again in the current frame.
                if self.am_on[i]:
                    integrated_on[i] += (frame + 1.0) - last_transistion

        # Set sum and return only those emitters that have sum > 0.
        self.h5_data['sum'] = integrated_on * self.photons
        mask = (self.h5_data['sum'] > 0.0)

        temp = {}
        for key in self.h5_data:
            temp[key] = self.h5_data[key][mask].copy()
            
        return temp

#
# The MIT License
#
# Copyright (c) 2016 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
