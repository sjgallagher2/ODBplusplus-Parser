# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 16:02:08 2026

@author: SG1295
"""
from pathlib import Path
import numpy as np

import cadquery as cq
import cadquery.vis as cqvis

import shapely

# For testing only
import matplotlib as mpl
import matplotlib.pyplot as plt

from random import random
from dataclasses import dataclass 
from enum import Enum,auto
import re

import odbparse as odb
from odbparse import Coordinate2,ODBLayerMatrixType

# Beaglebone Black
root_name1 = r'examples/beagleboneblack'
ark = odb.ODBArchive(root_name1,electrical_only=True)
# %% Render top layer and profile
fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ark.render_layer('profile',ax)
ark.render_layer('top',ax)

# aesthetics
ax.set_axis_off()
fig.tight_layout()

# %% Define stackup for Beaglebone (missing from archive)
# top
# core1     3.6mil, er = 4.05
# lyr2_gnd  
# core2     4.6mil, er = 4.5
# lyr3      
# core3     36mil, er = 4.5
# lyr4      
# core4     4.6mil, er = 4.5
# lyr5_pwr  
# core5     3.6mil, er = 4.05
# bottom    

# Update stackup manually
ark.layers['top'].dielectric_constant = 4.05
ark.layers['top'].dielectric_thickness = 3.6e-3

ark.layers['lyr2_gnd'].dielectric_constant = 4.5
ark.layers['lyr2_gnd'].dielectric_thickness = 4.6e-3

ark.layers['lyr3'].dielectric_constant = 4.5
ark.layers['lyr3'].dielectric_thickness = 36e-3

ark.layers['lyr4'].dielectric_constant = 4.5
ark.layers['lyr4'].dielectric_thickness = 4.6e-3

ark.layers['lyr5_pwr'].dielectric_constant = 4.5
ark.layers['lyr5_pwr'].dielectric_thickness = 3.6e-3

ark.layers['bottom'].dielectric_constant = 4.05
ark.layers['bottom'].dielectric_thickness = 0.0

# Now calculate the position of each of these layers
ark.recalculate_stackup()


# Export using stackup information
for name in ark.copper_layer_order:
    ark.export_layer_step(name,ark.layer_zoffsets[name])
ark.export_layer_step('profile',ark.layer_zoffsets['profile'])
ark.export_layer_step('drill')
