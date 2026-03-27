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

import odbparse as odb
from odbparse import Coordinate2

color_cycle = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
ncolors = len(color_cycle)
def plot_graph(g,ax=None,color=None,linestyle='-',randomize=False):#,marker='none'):
    if ax is None:
        fig,ax = plt.subplots(1,1,figsize=(7,7))
        ax.set_aspect('equal')
        ax.set_box_aspect(1)
    
    for u,v,data in g.edges(data=True):
        #data['feature'].draw(ax,None,odbconf,color=color)#,marker=marker)
        if randomize:
            scale = 0.001
            plt.plot([u.x+random()*scale-scale/2,v.x+random()*scale-scale/2],[u.y+random()*scale-scale/2,v.y+random()*scale-scale/2],color=color,ls=linestyle)
        else:
            plt.plot([u.x,v.x],[u.y,v.y],color=color,ls=linestyle)
    
    ax.autoscale()

            

root_name1 = r'examples/beagleboneblack'

ark = odb.ODBArchive(root_name1,electrical_only=True)
# ark.load_layer('rout')
# %%
# ark.export_layer_step('top')
# ark.export_layer_step('lyr2_gnd')
# ark.export_layer_step('lyr3')
# ark.export_layer_step('lyr4')
# ark.export_layer_step('lyr5_pwr')
# ark.export_layer_step('bottom')
# ark.export_layer_step('profile')
# ark.export_layer_step('drill')

# %% Define stackup
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

# Update manually
ark.layers['top'].dielectric_constant = 4.05
ark.layers['top'].layer_dielectric = 3.6e-3

ark.layers['lyr2_gnd'].dielectric_constant = 4.5
ark.layers['lyr2_gnd'].layer_dielectric = 4.6e-3

ark.layers['lyr3'].dielectric_constant = 4.5
ark.layers['lyr3'].layer_dielectric = 36e-3

ark.layers['lyr4'].dielectric_constant = 4.5
ark.layers['lyr4'].layer_dielectric = 4.6e-3

ark.layers['lyr5_pwr'].dielectric_constant = 4.5
ark.layers['lyr5_pwr'].layer_dielectric = 3.6e-3

ark.layers['bottom'].dielectric_constant = 4.05
ark.layers['bottom'].layer_dielectric = 0.0

# Now calculate the position of each of these layers
zpos = ark.odbconf.board_thickness  # start at the top
layer_zpos = {}
for i in range(len(ark.odbconf.matrix.matrix_layers)):
    ml = ark.odbconf.matrix.get_layer_by_row(i)
    if ml is None:
        continue
    name = ml.name.lower()
    if name in ark.layernames:
        if ark.layers[name].layertype != odb.ODBLayerMatrixType.DRILL:
            layer_zpos[name] = zpos - ark.layers[name].thickness 
            zpos -= (ark.layers[name].thickness + ark.layers[name].layer_dielectric)

for name,pos in layer_zpos.items():
    print(f"{name}\t\t {pos:.4f}")

# Now adjust board thickness for profile
# Simply subtracting copper thickness for top and bottom
# Then moving it up
profile_zpos = layer_zpos['bottom']+ark.layers['bottom'].thickness
ark.layers['profile'].thickness = layer_zpos['top']-profile_zpos

# Finally, export with z-position
# for name,zpos in layer_zpos.items():
#     ark.export_layer_step(name,z_offset=zpos)
ark.export_layer_step('profile',z_offset=profile_zpos)
# %% Convert to EMerge
# Make something for EMerge

# g1 is the networkx subgraph with only the nodes of interest, in some order
# path1 is the path of coordinates using nodes from g1
# path2 is the path of coordinates using nodes from g2

# def get_turn(p1,p2,p3,deg=True,cw=True):
#     """
#     Given three points in a path, find the clockwise (default) turn angle going from p1 to p2 to p3
#     """
#     dir1 = np.around((p2-p1).angle(deg))
#     dir2 = np.around((p3-p2).angle(deg))
#     turn = dir2-dir1
#     if turn > 180:
#         turn -= 360
#     elif turn < -180:
#         turn += 360
#     if cw:
#         turn *= -1  # make into clockwise angle
#     return turn

# # NOTE: Segments changing width in turn are not supported (not clear how to define it)
# class Segment:
#     def __init__(self,p1,p2,w0=0,prev_turn=None,next_turn=None):
#         k = odb.get_unit_conversion(odb.ODBUnit.INCH, odb.ODBUnit.MM)
#         self.p1 = p1*k
#         self.p2 = p2*k
#         self.w0 = w0*k
#         self.prev_turn = prev_turn
#         self.next_turn = next_turn
#     def get_length(self,do_correct=True):
#         L = (self.p2-self.p1).magnitude()
#         if not do_correct:
#             return L
#         dx1 = 0
#         dx2 = 0
#         if self.prev_turn is not None:
#             dx1 = (self.w0/2)*np.tan(np.deg2rad(self.prev_turn/2))
#         if self.next_turn is not None:
#             dx2 = (self.w0/2)*np.tan(np.deg2rad(self.next_turn/2))
#         return L-abs(dx1)-abs(dx2)

#     def get_unit(self):
#         vec = self.p2-self.p1
#         return vec/vec.magnitude()
    
#     def __repr__(self):
#         return f'Segment ({self.p1.x},{self.p1.y}) -> ({self.p2.x},{self.p2.y}) with width {self.w0}, prev turn {self.prev_turn}, next turn {self.next_turn}'

# # Make segments
# def get_segments(path0,layer1,linefeats,g):
#     segs1 = []
#     for p1,p2 in zip(path0,path0[1:]):
#         segs1.append(Segment(p1,p2))  # will update w0 and turns later
    
#     # Update w0
#     for feat in linefeats:
#         p1 = feat.pt_s 
#         p2 = feat.pt_e 
        
#         if p1 in g:
#             w0 = layer1.symbol_dict[feat.sym_num].diameter  # mils
#             k1 = odb.get_unit_conversion(odb.ODBUnit.INCH, odb.ODBUnit.MM)
#             k2 = odb.get_unit_conversion(odb.ODBUnit.MIL, odb.ODBUnit.MM)
#             for i,seg in enumerate(segs1):
#                 if seg.p1 == (p1*k1) and seg.p2 == (p2*k1):
#                     segs1[i].w0 = w0*k2
#                 elif seg.p2 == p1 and seg.p1 == p2:
#                     segs1[i].w0 = w0*k2
    
#     # Update prev_turn and next_turn
#     for i,(p1,p2,p3) in enumerate(zip(path0,path0[1:],path0[2:])):
#         turn = get_turn(p1,p2,p3)
#         segs1[i].next_turn = turn
#         if i >= 1:
#             segs1[i+1].prev_turn = turn
    
#     return segs1

# segs1 = get_segments(path1,tlay,tlinefeats,g1)
# segs2 = get_segments(path2,tlay,tlinefeats,g2)

# print(f'# {netname1}:')
# # First start with initial coords and direction
# uvec = segs1[0].get_unit()
# print(f"pcb.new(0, 0, w0_mm, ({uvec.x},{uvec.y})).store('p1') \\")
# # commands are .straight(length) and .turn(angle_cw)
# for i in range(len(segs1)):
#     print(f'    .straight({segs1[i].get_length(False):.5f}) \\')  # go straight first, then figure out turn    
#     if segs1[i].next_turn is not None:
#         print(f'    .pturn({segs1[i].next_turn},corner_type="square") \\')
# print("    .store('p3')")

# print(f'# {netname2}:')
# # First start with initial coords and direction
# uvec = segs2[0].get_unit()
# orig = segs2[0].p1-segs1[0].p1
# print(f"pcb.new({orig.x:.5f}, {orig.y:.5f}, w0_mm, ({uvec.x},{uvec.y})).store('p2') \\")
# # commands are .straight(length) and .turn(angle_cw)
# for i in range(len(segs2)):
#     print(f'    .straight({segs2[i].get_length(False):.5f}) \\')  # go straight first, then figure out turn    
#     if segs2[i].next_turn is not None:
#         print(f'    .pturn({segs2[i].next_turn},corner_type="square") \\')
# print("    .store('p4')")


