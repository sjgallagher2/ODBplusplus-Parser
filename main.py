# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 16:02:08 2026

@author: SG1295
"""
from pathlib import Path
from enum import Enum,auto
from dataclasses import dataclass,field
import numpy as np
import networkx as nx  # graph library for mapping nets to lines

# For testing only
import matplotlib as mpl
import matplotlib.pyplot as plt
from coordinate2 import Coordinate2

import odbparse as odb


root_name = 'examples/beagleboneblack'
root_p = Path(root_name)
odbconf = odb.load_ODB(root_p)
user_sym_dict = odb.load_user_symbols(odbconf)  # Needs to be done manually

# Parse relevant layers into `layer_features` list
# NOTE - Some funny business here with the uppercase/lowercase. TODO
stepname = odbconf.matrix.matrix_steps[0].name.lower()
layer_features = {}  # List of features files for different layers
boardoutline_path = root_p/f'steps/{stepname}/profile'  # example 1
boardoutline_feat = odb.ODBFeatureFile(boardoutline_path,odbconf)
boardoutline_feat.add_user_symbols(user_sym_dict)
for layer in odbconf.matrix.matrix_layers:
    if layer.layertype in odb.SIMULATION_LAYER_TYPES:
        featpath = root_p/f'steps/{stepname}/layers/{layer.name.lower()}/features'
        featfile = odb.ODBFeatureFile(featpath,odbconf)
        featfile.add_user_symbols(user_sym_dict)
        layer_features[layer.name.lower()] = featfile

fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ax.set_box_aspect(1)
alpha = 0.3
boardoutline_feat.draw(ax,fc=(0.8,0.1,0.1,alpha+0.2))
layer_features['top'].draw(ax,fc=(0.1,0.8,0.1,alpha))
ax.autoscale()
fig.tight_layout()

# %%
# Parse netlist file
fpath = odbconf.root_path/f'steps/{stepname}/netlists/cadnet/netlist'
netlistfile = odb.ODBNetlistFile(fpath)
# Make graph of nets and break into subgraphs by name
tgraph = nx.Graph()
bgraph = nx.Graph()
# Nodes are Coordinate2 objects, nets are edges

tlay = layer_features['top']  # 'top'
blay = layer_features['bottom']  # 'bottom'
tlinefeats = [feat for feat in tlay.features_list if isinstance(feat,odb.ODBFeatureLine)]
blinefeats = [feat for feat in blay.features_list if isinstance(feat,odb.ODBFeatureLine)]

for feat in tlinefeats:
        p1 = feat.pt_s 
        p2 = feat.pt_e 
        if p1.y > 0 and p2.y > 0:
            tgraph.add_edge(p1,p2)

for feat in blinefeats:
        p1 = feat.pt_s 
        p2 = feat.pt_e 
        if p1.y > 0 and p2.y > 0:
            bgraph.add_edge(p1,p2)

net_graphs_top = {}
net_graphs_bot = {}
for netp in netlistfile.net_points:
    if netp.side in ['T','B']:
        pt = Coordinate2(netp.loc.x,netp.loc.y)
        if pt in tgraph.nodes:
            netname = netlistfile.netnames_dict[netp.net_num]
            if netname not in net_graphs_top.keys():
                # Add the graph of nodes connected to this point to the dict
                net_graphs_top[netname] = tgraph.subgraph(nx.node_connected_component(tgraph,pt))
            else:
                # Union with current, can be the same
                current_nodes = set(net_graphs_top[netname].nodes)
                total_nodes = current_nodes.union(nx.node_connected_component(tgraph,pt))
                net_graphs_top[netname] = tgraph.subgraph(total_nodes)

for netp in netlistfile.net_points:
    if netp.side in ['D','B']:
        pt = Coordinate2(netp.loc.x,netp.loc.y)
        if pt in bgraph.nodes:
            netname = netlistfile.netnames_dict[netp.net_num]
            if netname not in net_graphs_bot.keys():
                # Add the graph of nodes connected to this point to the dict
                net_graphs_bot[netname] = bgraph.subgraph(nx.node_connected_component(bgraph,pt))
            else:
                # Union with current, can be the same
                current_nodes = set(net_graphs_bot[netname].nodes)
                total_nodes = current_nodes.union(nx.node_connected_component(bgraph,pt))
                net_graphs_bot[netname] = bgraph.subgraph(total_nodes)

# Plot top layer lines and highlight a diff pair
fig,ax = plt.subplots()
ax.set_aspect('equal')
ax.set_box_aspect(1)

for feat in tlinefeats:
    p1 = feat.pt_s 
    p2 = feat.pt_e 
    if p1.y > 0 and p2.y > 0:
        if p1 in net_graphs_top['HDMI_TXC+']:
            feat.draw(ax,tlay.symbol_dict,odbconf,'r')
        elif p1 in net_graphs_top['HDMI_TXC-']:
            feat.draw(ax,tlay.symbol_dict,odbconf,'b')
        else:
            feat.draw(ax,tlay.symbol_dict,odbconf,'k')

for feat in blinefeats:
    p1 = feat.pt_s 
    p2 = feat.pt_e 
    if p1.y > 0 and p2.y > 0:
        if p1 in net_graphs_bot['HDMI_TXC+']:
            feat.draw(ax,blay.symbol_dict,odbconf,'r:')
        elif p1 in net_graphs_bot['HDMI_TXC-']:
            feat.draw(ax,blay.symbol_dict,odbconf,'b:')
        # else:
            # feat.draw(ax,blay.symbol_dict,odbconf,'k:')

# Trace out a diff pair
# NOTE: For this demo, assume a trace is continuous, and take shortest path

netname1 = 'HDMI_TXC+'
netname2 = 'HDMI_TXC-'
g1 = net_graphs_top[netname1]
g2 = net_graphs_top[netname2]

# Get leaf nodes, the start and end of the chain
leaf_nodes1 = [n for n,deg in g1.degree() if deg == 1]
leaf_nodes2 = [n for n,deg in g2.degree() if deg == 1]

# Get shortest path from leaf to leaf
path1 = nx.shortest_path(g1,source=leaf_nodes1[0],target=leaf_nodes1[1])
path2 = nx.shortest_path(g2,source=leaf_nodes2[0],target=leaf_nodes2[1])
print(f'{netname1}:')
for node in path1:
    print(f'\t({node.x},{node.y})')
print(f'{netname2}:')
for node in path2:
    print(f'\t({node.x},{node.y})')
        
# Plot, with arrows showing order of nodes
fig,ax = plt.subplots()
ax.set_aspect('equal')
ax.set_box_aspect(1)
for feat in tlinefeats:
    p1 = feat.pt_s 
    p2 = feat.pt_e 
    if p1.y > 0 and p2.y > 0:
        if p1 in g1:
            feat.draw(ax,tlay.symbol_dict,odbconf,'r')
        elif p1 in g2:
            feat.draw(ax,tlay.symbol_dict,odbconf,'b')

for n1,n2 in zip(path1,path1[1:]):
    ax.annotate("", xytext=(n1.x, n1.y), xy=(n2.x, n2.y),
            arrowprops=dict(arrowstyle="->"))
for n1,n2 in zip(path2,path2[1:]):
    ax.annotate("", xytext=(n1.x, n1.y), xy=(n2.x, n2.y),
            arrowprops=dict(arrowstyle="->"))

# Make something for EMerge

# g1 is the networkx subgraph with only the nodes of interest, in some order
# path1 is the path of coordinates using nodes from g1
# path2 is the path of coordinates using nodes from g2

def get_turn(p1,p2,p3,deg=True,cw=True):
    """
    Given three points in a path, find the clockwise (default) turn angle going from p1 to p2 to p3
    """
    dir1 = np.around((p2-p1).angle(deg))
    dir2 = np.around((p3-p2).angle(deg))
    turn = dir2-dir1
    if turn > 180:
        turn -= 360
    elif turn < -180:
        turn += 360
    if cw:
        turn *= -1  # make into clockwise angle
    return turn

# NOTE: Segments changing width in turn are not supported (not clear how to define it)
class Segment:
    def __init__(self,p1,p2,w0=0,prev_turn=None,next_turn=None):
        k = odb.get_unit_conversion(odb.ODBUnit.INCH, odb.ODBUnit.MM)
        self.p1 = p1*k
        self.p2 = p2*k
        self.w0 = w0*k
        self.prev_turn = prev_turn
        self.next_turn = next_turn
    def get_length(self,do_correct=True):
        L = (self.p2-self.p1).magnitude()
        if not do_correct:
            return L
        dx1 = 0
        dx2 = 0
        if self.prev_turn is not None:
            dx1 = (self.w0/2)*np.tan(np.deg2rad(self.prev_turn/2))
        if self.next_turn is not None:
            dx2 = (self.w0/2)*np.tan(np.deg2rad(self.next_turn/2))
        return L-abs(dx1)-abs(dx2)

    def get_unit(self):
        vec = self.p2-self.p1
        return vec/vec.magnitude()
    
    def __repr__(self):
        return f'Segment ({self.p1.x},{self.p1.y}) -> ({self.p2.x},{self.p2.y}) with width {self.w0}, prev turn {self.prev_turn}, next turn {self.next_turn}'

# Make segments
def get_segments(path0,layer1,linefeats,g):
    segs1 = []
    for p1,p2 in zip(path0,path0[1:]):
        segs1.append(Segment(p1,p2))  # will update w0 and turns later
    
    # Update w0
    for feat in linefeats:
        p1 = feat.pt_s 
        p2 = feat.pt_e 
        
        if p1 in g:
            w0 = layer1.symbol_dict[feat.sym_num].diameter  # mils
            k1 = odb.get_unit_conversion(odb.ODBUnit.INCH, odb.ODBUnit.MM)
            k2 = odb.get_unit_conversion(odb.ODBUnit.MIL, odb.ODBUnit.MM)
            for i,seg in enumerate(segs1):
                if seg.p1 == (p1*k1) and seg.p2 == (p2*k1):
                    segs1[i].w0 = w0*k2
                elif seg.p2 == p1 and seg.p1 == p2:
                    segs1[i].w0 = w0*k2
    
    # Update prev_turn and next_turn
    for i,(p1,p2,p3) in enumerate(zip(path0,path0[1:],path0[2:])):
        turn = get_turn(p1,p2,p3)
        segs1[i].next_turn = turn
        if i >= 1:
            segs1[i+1].prev_turn = turn
    
    return segs1

segs1 = get_segments(path1,tlay,tlinefeats,g1)
segs2 = get_segments(path2,tlay,tlinefeats,g2)

print(f'# {netname1}:')
# First start with initial coords and direction
uvec = segs1[0].get_unit()
print(f"pcb.new(0, 0, w0_mm, ({uvec.x},{uvec.y})).store('p1') \\")
# commands are .straight(length) and .turn(angle_cw)
for i in range(len(segs1)):
    print(f'    .straight({segs1[i].get_length(False):.5f}) \\')  # go straight first, then figure out turn    
    if segs1[i].next_turn is not None:
        print(f'    .pturn({segs1[i].next_turn},corner_type="square") \\')
print("    .store('p3')")

print(f'# {netname2}:')
# First start with initial coords and direction
uvec = segs2[0].get_unit()
orig = segs2[0].p1-segs1[0].p1
print(f"pcb.new({orig.x:.5f}, {orig.y:.5f}, w0_mm, ({uvec.x},{uvec.y})).store('p2') \\")
# commands are .straight(length) and .turn(angle_cw)
for i in range(len(segs2)):
    print(f'    .straight({segs2[i].get_length(False):.5f}) \\')  # go straight first, then figure out turn    
    if segs2[i].next_turn is not None:
        print(f'    .pturn({segs2[i].next_turn},corner_type="square") \\')
print("    .store('p4')")


