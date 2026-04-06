# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 16:02:08 2026

@author: SG1295
"""
# For testing only
from pathlib import Path
import numpy as np
import cadquery as cq
import cadquery.vis as cqvis
import matplotlib as mpl
import matplotlib.pyplot as plt

# main module import
import odbparse as odb
# from odbparse import Coordinate2,ODBLayerMatrixType

# Beaglebone Black
root_name1 = r'examples/beagleboneblack'
ark = odb.ODBArchive(root_name1,electrical_only=True)

# %%

layer = ark.layers['comp_+_top']
# pkg=ark.edadata.packages['POLYSW200-5638-310']
# pkg=ark.edadata.packages['SOP8_DCT']
# pkg=ark.edadata.packages['USB5MINI_4SHIELDED_SMD-5']
# pkg=ark.edadata.packages['BGA153_P14_P5_11P5X13']
pkg=ark.edadata.packages['RD205SMD_250D']

def get_pkg_outlines(pkg,pkg_xf):
    pkg_outline = odb._pcb_geom.parse_eda_outline(pkg.outline_record)
    pkg_outline.apply_transform(pkg_xf)
    pkg_outlines = [pkg_outline]
    for pin in pkg.pins:
        po = odb._pcb_geom.parse_eda_outline(pin.outline)
        po.apply_transform(pkg_xf)
        pkg_outlines.append(po)
    return pkg_outlines


fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')

for refdes,comp in layer.compfile.components.items():
    comp_xf = odb._pcb_geom.GeomSymbolTransform(translate_x=comp.loc.x,translate_y=comp.loc.y,rot_deg=comp.rot_deg,mirror_x=comp.mirror)
    comp_pkg_name = ark.edadata.package_number_name_lookup[comp.pkg_ref]
    comp_pkg = ark.edadata.packages[comp_pkg_name]
    comp_outlines = get_pkg_outlines(comp_pkg,comp_xf)
    
    for po in comp_outlines:
        ax.add_patch(po.to_mpl(fill=False,ec='k',lw=2))
ax.autoscale()


# %% Render top layer and profile
fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ark.render_layer('profile',ax)
ark.render_layer('top',ax)
ark.render_layer('comp_+_top',ax)

# aesthetics
ax.set_axis_off()
fig.tight_layout()
plt.show()
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
if False:  # to export, set to True
    for name in ark.copper_layer_order:
        ark.export_layer_step(name,ark.layer_zoffsets[name])
    ark.export_layer_step('profile',ark.layer_zoffsets['profile'])
    ark.export_layer_step('drill')
