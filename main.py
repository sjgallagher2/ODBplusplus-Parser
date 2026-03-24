# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 16:02:08 2026

@author: SG1295
"""
from pathlib import Path
import numpy as np
import networkx as nx  # graph library for mapping nets to lines

import shapely
from shapely import LineString  # library for performing boolean operations and buffering/offsetting traces
# see also: https://github.com/proto3/cavaliercontours-python

# For testing only
import matplotlib as mpl
import matplotlib.pyplot as plt
from coordinate2 import Coordinate2
import pcb_geom as geom

from random import random

import odbparse as odb

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

def plot_shapely(polygon,ax=None):
    if ax is None:
        fig,ax = plt.subplots(1,1,figsize=(7,7))
        ax.set_aspect('equal')
        ax.set_box_aspect(1)
    if polygon.geom_type == 'Polygon':
        xx,yy = polygon.exterior.coords.xy
        x = xx.tolist()
        y = yy.tolist()
        ax.plot(x,y,'k')
        for polyint in polygon.interiors:
            xx,yy = polyint.coords.xy
            x = xx.tolist()
            y = yy.tolist()
            ax.plot(x,y,'k')
    elif polygon.geom_type == 'LineString':
        xx,yy = polygon.coords.xy
        x = xx.tolist()
        y = yy.tolist()
        ax.plot(x,y,'k')

def plot_shapely_as_patch(polygon,ax=None,**patchkwargs):
    if ax is None:
        fig,ax = plt.subplots(1,1,figsize=(7,7))
        ax.set_aspect('equal')
        ax.set_box_aspect(1)
    if polygon.geom_type == 'Polygon':
        vtxs = []
        cmds = []
        xx,yy = polygon.exterior.coords.xy
        x = xx.tolist()
        y = yy.tolist()
        shell_vtxs = list(zip(x,y))
        shell_cmds = [mpl.path.Path.MOVETO]+[mpl.path.Path.LINETO]*(len(shell_vtxs)-1)
        shell_vtxs += [(0,0)]
        shell_cmds += [mpl.path.Path.CLOSEPOLY]
        vtxs = shell_vtxs
        cmds = shell_cmds
        
        for polyint in polygon.interiors:
            xx,yy = polyint.coords.xy
            x = xx.tolist()
            y = yy.tolist()
            hole_vtxs = list(zip(x,y))
            hole_cmds = [mpl.path.Path.MOVETO]+[mpl.path.Path.LINETO]*(len(hole_vtxs)-1)
            hole_vtxs += [(0,0)]
            hole_cmds += [mpl.path.Path.CLOSEPOLY]
            
            vtxs += hole_vtxs 
            cmds += hole_cmds
        path = mpl.path.Path(vtxs,cmds)
        patch = mpl.patches.PathPatch(path,**patchkwargs)
        ax.add_patch(patch)
        ax.autoscale()

root_name = 'examples/beagleboneblack'
root_p = Path(root_name)
odbconf = odb.load_ODB(root_p)
user_sym_dict = odb.load_user_symbols(odbconf)  # Needs to be done manually
# Load EDA data
edadata = odb.ODB_EDA_Data(odbconf)
# Load specific layers
toplayer = odb.ODBLayer(odbconf,'top',user_sym_dict)
bottomlayer = odb.ODBLayer(odbconf,'bottom',user_sym_dict)
lyr4layer = odb.ODBLayer(odbconf,'lyr4',user_sym_dict)
profile = odb.ODBLayer(odbconf,'profile',user_sym_dict,is_toplevel=True)

# Get simulatable layer types
layernames = []
for layer in odbconf.matrix.matrix_layers:
    if layer.layertype in odb.SIMULATION_LAYER_TYPES:
        layernames.append(layer.name.lower())  # lower() because matrix tends to change capitalization

# %%
layer = toplayer  # choose default layer
# break layer graph up on a per-symbol basis
layer_symbol_subgraphs = layer.get_partitioned_graph(user_sym_dict,edadata.feature_netnames)
# layer_symbol_subgraphs is a dict from symbol number -> list of subgraphs for that symbol

# make subtraces
subtraces = {}

for symnum, sgs in layer_symbol_subgraphs.items():
    for sg in sgs:
        netname = sg.graph['netname']
        if netname not in subtraces.keys():
            subtraces[netname] = []
        # make subtraces the easier way
        subtraces[netname].append(geom.GeomSubtrace.from_graph(sg))
        # plot_graph(sg,ax=ax)
        # you can also make subtraces the hard way
#         segs = []
#         sym = sg.graph['symbol']
#         netname = sg.graph['netname']
#         for u,v,data in sg.edges(data=True):
#             segs.append(data['feature'])
#         subtraces.append(GeomSubtrace.from_segments_and_symbol(segs, sym, netname))

# Union and plot subtraces with Shapely
all_net_polygons = []
for netnmame,netsubs in subtraces.items():
    for subtrace in netsubs:
        polygon = subtrace.to_shapely()
        all_net_polygons.append(polygon)

# Parse pads and surfaces
symbol_polygons = []
surface_polygons = []
for feat in layer.featfile.features_list:
    if isinstance(feat,odb.ODBFeaturePad):
        symbol = layer.featfile.symbol_dict[feat.sym_num]
        symbol_geom = geom.parse_symbol(feat,symbol)
        symbol_polygons.append(symbol_geom.to_shapely())
    elif isinstance(feat,odb.ODBFeatureSurface):
        shell_poly = None
        hole_polys = []
        for poly in feat.polygons:
            if poly.poly_type == odb.ODBPolygonType.ISLAND:
                if shell_poly is not None:
                    print("WARNING: More than one island for surface!")
                shell_poly = geom.GeomSimplePolygon.from_odb_polygon(poly)
                # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
            else:
                hole_polys.append(geom.GeomSimplePolygon.from_odb_polygon(poly))
                # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
                
        surface_polygons.append(geom.GeomPolygon(shell_poly,hole_polys).to_shapely())

# Now we have:
#   all_net_polygons
#   surface_polygons
#   symbol_polygons
# Let's plot
fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ax.set_box_aspect(1)
big_union = shapely.disjoint_subset_union_all(all_net_polygons+surface_polygons+symbol_polygons)
for buf in big_union.geoms:
    plot_shapely_as_patch(buf,ax)

# %%
fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ax.set_box_aspect(1)

for feat in layer.featfile.features_list:
    if feat.fnum == 3838:
        break

shell_poly = None
hole_polys = []
hole_shapelys = []
for poly in feat.polygons:
    if poly.poly_type == odb.ODBPolygonType.ISLAND:
        if shell_poly is not None:
            print("WARNING: More than one island for surface!")
        shell_poly = geom.GeomSimplePolygon.from_odb_polygon(poly)
        # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
    else:
        hole_polys.append(geom.GeomSimplePolygon.from_odb_polygon(poly))
        hole_shapelys.append(hole_polys[-1].to_shapely())
        # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())

# ax.add_patch(shell_poly.to_mpl())
# for hole in hole_polys:
    # ax.add_patch(hole.to_mpl(facecolor='r'))



bigpoly = shapely.Polygon(shell_poly.to_shapely(),hole_shapelys)

plot_shapely_as_patch(bigpoly,ax)
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


