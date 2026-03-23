# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 15:03:46 2026

@author: SG1295
"""
# std lib
from typing import List
import math
from math import pow,fabs,sin,cos,tan
from enum import Enum,auto
from dataclasses import dataclass
# dependencies
import numpy as np
from numpy import around
import networkx as nx
import matplotlib as mpl
import shapely
from shapely import LineString  # library for performing boolean operations and buffering/offsetting traces

# Module
from coordinate2 import Coordinate2

pi = 3.14159265358979


def deg2rad(angle_deg):
    return angle_deg * pi / 180

def circular_arc_to_path(center: Coordinate2, radius: float, angle_start_deg: float, angle_end_deg: float, cw: bool, standalone=False):
    """
    Outline generated from AI which cites https://github.com/fontello/svgpath
    
    Approximates a circular arc with a sequence of cubic Bezier curves.
    For simplicity, this function assumes the arc is less than 90 degrees.
    For larger arcs, it should be subdivided first.
    
    angles are in degrees, orientation defined by `cw` (clockwise)
    assumes first point has already been added to path, unless standalone==True
    in which case a MOVETO is prepended to the output
    
    Returns (vtxs,codes)
        vtxs  List of 2-tuples with xy coordinates, for use with mpl.path.Path
        codes List of mpl.path.Path codes for the spline. 
    """
    mpl_MOVETO = 1  # definitions from matplotlib
    mpl_CURVE4 = 4  # may be subject to change?
    
    do_flip = False
    if cw:
        angle_start = deg2rad(angle_end_deg)
        angle_end = deg2rad(angle_start_deg)
        do_flip = True
    else:
        angle_start = deg2rad(angle_start_deg)
        angle_end = deg2rad(angle_end_deg)
    
    
    # Calculate start and end points
    p0_x = center.x + radius * cos(angle_start)
    p0_y = center.y + radius * sin(angle_start)
    p3_x = center.x + radius * cos(angle_end)
    p3_y = center.y + radius * sin(angle_end)
    P0 = (p0_x, p0_y)
    P3 = (p3_x, p3_y)

    # Calculate angular span (ensure it's positive and < 90 deg for best results)
    angle_span = angle_end - angle_start
    if angle_span < 0:
        angle_span += 2 * pi # Handle cases where end < start

    # It's highly recommended to subdivide large angles into smaller ones (e.g., <= 90 deg)
    if angle_span > pi / 2 + 1e-5:
        # Handle subdivision in a more complete function (see online resources)
        # print("Warning: Angle span > 90 degrees. Approximation error will be larger.")
        # For a full implementation of arbitrary angles, refer to libraries 
        # or detailed algorithms on [GitHub](https://github.com/fontello/svgpath)
        pass 

    # Calculate the 'L' value
    L = (4/3) * radius * tan(angle_span / 4)

    # Calculate unit tangent vectors at P0 and P3
    # Tangent at angle t is (-sin(t), cos(t)) for ccw
    T0 = (-sin(angle_start), cos(angle_start))
    T3 = (-sin(angle_end), cos(angle_end)) # Tangent vector at P3 needs to point inward for the 'minus L*T1' formula

    # Calculate control points P1 and P2
    P1 = (P0[0] + L * T0[0], P0[1] + L * T0[1])
    P2 = (P3[0] - L * T3[0], P3[1] - L * T3[1]) # Note the minus sign for T3

    if do_flip:
        vtxs = [P0, P1, P2]
    else:
        vtxs = [P1,P2,P3]
    codes = [mpl_CURVE4]*3
    
    if standalone:
        vtxs = [P0] + vtxs
        codes = [mpl_MOVETO] + codes
    
    if do_flip:
        vtxs = vtxs[::-1]
    
    return vtxs,codes



import odbparse as odb

class GeomSubtraceArcOrientation(Enum):
    CW = auto()
    CCW = auto()

class GeomSubtraceCommand:
    pass

@dataclass
class GeomSubtraceStart(GeomSubtraceCommand):
    pt: Coordinate2
    
    def to_mpl_path(self):
        mpl_MOVETO = 1  # definitions from matplotlib
        mpl_LINETO = 2
        mpl_CURVE4 = 4
        return [(self.pt.x,self.pt.y)],[mpl_MOVETO]

@dataclass
class GeomSubtraceLineTo(GeomSubtraceCommand):
    pt: Coordinate2 
    
    def to_mpl_path(self):
        mpl_MOVETO = 1  # definitions from matplotlib
        mpl_LINETO = 2
        mpl_CURVE4 = 4
        return [(self.pt.x,self.pt.y)],[mpl_LINETO]

@dataclass
class GeomSubtraceArcTo(GeomSubtraceCommand):
    end_pt: Coordinate2 
    center_pt: Coordinate2
    orientation: GeomSubtraceArcOrientation
    
    def to_mpl_path(self,prevpt: Coordinate2):
        # Need to convert arc to Bezier path, taking orientation into account
        # vtxs are in translated coordinates, segment is in original coordinates
        vtxs = []
        codes = []
        p1 = prevpt
        p2 = self.end_pt
        cw = self.orientation == GeomSubtraceArcOrientation.CW
        rad = (p1-self.center_pt).magnitude()
        angle_start_deg = (p1-self.center_pt).angle(True)%360
        angle_end_deg = (p2-self.center_pt).angle(True)%360
        
        # Check if we need to break the arc up into smaller (<= 90 degrees) segments
        if cw:
            angle_span = (angle_start_deg - angle_end_deg)
        else:
            angle_span = (angle_end_deg - angle_start_deg)

        if angle_span < 0:
            angle_span += 360  # Positive only

        if angle_span > 180:
            # Break up into segments <= 90 degrees
            start_angles = []
            end_angles = []
            next_angle = angle_start_deg
            if cw:
                # Angles decrease to angle_start_deg-angle_span
                while next_angle > (angle_start_deg - angle_span):
                    start_angles.append(next_angle)
                    next_angle = start_angles[-1] - 90
                    end_angles.append(next_angle)
                end_angles[-1] = angle_start_deg - angle_span
            else:
                # Angles increase to angle_start_deg+angle_span
                while next_angle < (angle_start_deg + angle_span):
                    start_angles.append(next_angle)
                    next_angle = start_angles[-1] + 90
                    end_angles.append(next_angle)
                end_angles[-1] = angle_start_deg + angle_span
            
            # Now generate arcs from start_angle to end_angle for each
            for i in range(len(start_angles)):
                arc_vtxs,arc_codes = circular_arc_to_path(self.center_pt, rad, start_angles[i], end_angles[i],cw)
                vtxs += arc_vtxs
                codes += arc_codes
        else:                    
            arc_vtxs,arc_codes = circular_arc_to_path(self.center_pt, rad, angle_start_deg, angle_end_deg,cw)
            vtxs += arc_vtxs
            codes += arc_codes
        return (vtxs,codes)
    def linearize(self,prevpt: Coordinate2, resolution=10):
        """
        Discretize circular arc into `resolution` segments
        
        Return x,y
        """
        p1 = prevpt
        p2 = self.end_pt
        cw = self.orientation == GeomSubtraceArcOrientation.CW
        rad = (p1-self.center_pt).magnitude()
        angle_start_rad = (p1-self.center_pt).angle(False)%(2*pi)
        angle_end_rad = (p2-self.center_pt).angle(False)%(2*pi)
        
        if cw:
            angle_span = (angle_start_rad - angle_end_rad)
        else:
            angle_span = (angle_end_rad - angle_start_rad)

        if angle_span < 0:
            angle_span += 2*pi  # Positive only
        
        if cw:
            t = np.linspace(angle_start_rad,angle_start_rad-angle_span,resolution)
        else:
            t = np.linspace(angle_end_rad-angle_span,angle_end_rad,resolution)
        x = rad*np.cos(t) + self.center_pt.x
        y = rad*np.sin(t) + self.center_pt.y
        coords = [Coordinate2(*xy) for xy in list(zip(x,y))]
        return coords
        
        

class SVGJoinStyle(Enum):
    MITER = auto()
    ROUND = auto()
    BEVEL = auto()

class SVGCapStyle(Enum):
    BUTT = auto()
    SQUARE = auto()
    ROUND = auto()

@dataclass
class GeomSubtrace:
    """
    A subtrace is a continuous, uniform polyline trace defined by commands (Start, 
    LineTo, or ArcTo), a tracewidth, a join style, and a cap style. 
    """
    cmds: tuple[GeomSubtraceCommand]
    tracewidth: float
    netname: str
    join_style: SVGJoinStyle = SVGJoinStyle.ROUND
    cap_style: SVGCapStyle = SVGCapStyle.ROUND
    
    def to_mpl(self) -> mpl.patches.PathPatch:
        prev_pt = None
        all_vtxs = []
        all_codes = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomSubtraceArcTo):
                vtxs,codes = cmd.to_mpl_path(Coordinate2(*prev_pt))
            else:
                vtxs,codes = cmd.to_mpl_path()
            all_vtxs += vtxs
            all_codes += codes
            prev_pt = vtxs[-1]
        patch = mpl.patches.PathPatch(mpl.path.Path(all_vtxs,all_codes))
        return patch
    
    def to_vtxs(self):
        prev_pt = None 
        all_vtxs = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomSubtraceArcTo):
                vtxs = cmd.linearize(prev_pt)
            else:
                vtxs = [cmd.pt]
            all_vtxs += vtxs
            prev_pt = vtxs[-1]
        
        vtx_tuples = [(c.x,c.y) for c in all_vtxs]
        return vtx_tuples
    
    def to_shapely(self) -> shapely.Polygon:
        prev_pt = None 
        all_vtxs = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomSubtraceArcTo):
                vtxs = cmd.linearize(prev_pt)
            else:
                vtxs = [cmd.pt]
            all_vtxs += vtxs
            prev_pt = vtxs[-1]
        
        vtx_tuples = [(c.x,c.y) for c in all_vtxs]
        ls = LineString(vtx_tuples)
        buf = ls.buffer(self.tracewidth/2*1e-3,quad_segs=2,
                        join_style=self.join_style.name.lower(),
                        cap_style=self.cap_style.name.lower())
        
        return buf
    
    @classmethod
    def from_segments_and_symbol(cls,segments: list[odb.ODBFeatureLine|odb.ODBFeatureArc],symbol: odb.ODBSymbol,netname: str):
        """
        Convert segments and a symbol into a subtrace.
        
        This method is complicated by a couple factors:
            1. Segments are generally supplied in arbitrary order
            2. Segments have a pt_s and pt_e (start and end) but this does not
               generally obey any logic
        So we have to make our own path and do a lot of checking. It's ugly but it works. 
        """
        # Parse symbol
        if isinstance(symbol,odb.ODBRoundSymbol):
            join_style = SVGJoinStyle.ROUND 
            cap_style = SVGCapStyle.ROUND
            tracewidth = symbol.diameter
        elif isinstance(symbol,odb.ODBSquareSymbol):
            join_style = SVGJoinStyle.MITER
            cap_style = SVGCapStyle.SQUARE  # not BUTT assuming symbol is centered on vertices
            tracewidth = symbol.side
        else:
            # Asymmetric symbols like rectangles can only be horizontal or vertical, which
            # unnecessarily constrains polylines, and seems stupid. If this becomes an issue,
            # I will reconsider
            raise NotImplementedError(f"Segments with symbol {symbol} are not implemented. Defaulting to ROUND cap with ROUND join.")
        
        # Everything from here assumes the segments are in any order. If they are ordered,
        # things would be easier, but we lost that information if it was ever dependable
        
        # Parse segments into a graph
        graph = nx.Graph()
        for feat in segments:
            # both Line and Arc has pt_s and pt_e
            graph.add_edge(feat.pt_s,feat.pt_e,feature=feat)
        
        branch_nodes = [n for n,deg in graph.degree() if deg > 2]
        if len(branch_nodes) > 0:
            # Try removing degenerate edges
            for u,v in graph.edges():
                if (u-v).magnitude() < 1e-7:
                    graph.remove_edge(u,v)
        branch_nodes = [n for n,deg in graph.degree() if deg > 2]
        if len(branch_nodes) > 0:
            raise ValueError(f"GeomSubtrace cannot be branching. Net name: {netname}, Graph nodes: {graph.nodes}")
        
        # Get segment vertices in order
        leaf_nodes = [n for n,deg in graph.degree() if deg == 1]
        if len(leaf_nodes) > 2:
            raise ValueError("GeomSubtrace cannot be branching or disjoint.")
        elif len(leaf_nodes) == 0:
            # cycle, no order
            path_edges = nx.find_cycle(graph)
            vtx_path = []
            for e in path_edges:
                vtx_path += [e[0],e[1]]
        elif len(leaf_nodes) == 1:
            raise ValueError("GeomSubtrace cannot be branching.")
        else:
            vtx_path = nx.shortest_path(graph,source=leaf_nodes[0],target=leaf_nodes[1])
            path_edges = list(zip(vtx_path,vtx_path[1:]))
        # Now use the graph to make a `cmds` array
        cmds = [GeomSubtraceStart(vtx_path[0])]  # Initialize with start point
        for edge in path_edges:
            feat = graph.get_edge_data(edge[0],edge[1])['feature']
            if isinstance(feat,odb.ODBFeatureLine):
                # Note: Do NOT use feature here! They can be flipped
                cmds.append(GeomSubtraceLineTo(edge[1]))
            elif isinstance(feat,odb.ODBFeatureArc):
                cw = feat.cw
                if feat.pt_e != edge[1]:
                    cw = not cw  # Feature was backwards, flip cw/ccw
                orient = GeomSubtraceArcOrientation.CCW 
                if cw:
                    orient = GeomSubtraceArcOrientation.CW 
                cmds.append(GeomSubtraceArcTo(edge[1],feat.pt_c,orient))
        cmds = tuple(cmds)
        # Return
        return cls(cmds,tracewidth,netname,join_style,cap_style)
        
    @classmethod 
    def from_graph(cls,graph: nx.Graph):
        netname = graph.graph['netname']
        symbol = graph.graph['symbol']
        # Parse symbol
        if isinstance(symbol,odb.ODBRoundSymbol):
            join_style = SVGJoinStyle.ROUND 
            cap_style = SVGCapStyle.ROUND
            tracewidth = symbol.diameter
        elif isinstance(symbol,odb.ODBSquareSymbol):
            join_style = SVGJoinStyle.MITER
            cap_style = SVGCapStyle.SQUARE  # not BUTT assuming symbol is centered on vertices
            tracewidth = symbol.side
        else:
            # Asymmetric symbols like rectangles can only be horizontal or vertical, which
            # unnecessarily constrains polylines, and seems stupid. If this becomes an issue,
            # I will reconsider
            raise NotImplementedError(f"Segments with symbol {symbol} are not implemented. Defaulting to ROUND cap with ROUND join.")
            
        branch_nodes = [n for n,deg in graph.degree() if deg > 2]
        if len(branch_nodes) > 0:
            # Try removing degenerate edges
            for u,v in graph.edges():
                if (u-v).magnitude() < 1e-7:
                    graph.remove_edge(u,v)
        branch_nodes = [n for n,deg in graph.degree() if deg > 2]
        if len(branch_nodes) > 0:
            raise ValueError(f"GeomSubtrace cannot be branching. Net name: {netname}, Graph nodes: {graph.nodes}")
        
        # Get segment vertices in order
        leaf_nodes = [n for n,deg in graph.degree() if deg == 1]
        if len(leaf_nodes) > 2:
            raise ValueError("GeomSubtrace cannot be branching or disjoint.")
        elif len(leaf_nodes) == 0:
            # cycle, no order
            path_edges = nx.find_cycle(graph)
            vtx_path = []
            for e in path_edges:
                vtx_path += [e[0],e[1]]
        elif len(leaf_nodes) == 1:
            raise ValueError("GeomSubtrace cannot be branching.")
        else:
            vtx_path = nx.shortest_path(graph,source=leaf_nodes[0],target=leaf_nodes[1])
            path_edges = list(zip(vtx_path,vtx_path[1:]))
        # Now use the graph to make a `cmds` array
        cmds = [GeomSubtraceStart(vtx_path[0])]  # Initialize with start point
        for edge in path_edges:
            feat = graph.get_edge_data(edge[0],edge[1])['feature']
            if isinstance(feat,odb.ODBFeatureLine):
                # Note: Do NOT use feature here! They can be flipped apparently??
                cmds.append(GeomSubtraceLineTo(edge[1]))
            elif isinstance(feat,odb.ODBFeatureArc):
                cw = feat.cw
                if feat.pt_e != edge[1]:
                    cw = not cw  # Feature was backwards, flip cw/ccw
                orient = GeomSubtraceArcOrientation.CCW 
                if cw:
                    orient = GeomSubtraceArcOrientation.CW 
                cmds.append(GeomSubtraceArcTo(edge[1],feat.pt_c,orient))
        cmds = tuple(cmds)
        # Return
        return cls(cmds,tracewidth,netname,join_style,cap_style)


# Base class for symbol geometries
class GeomSymbol:
    def __init__(self):
        pass
    def to_mpl(self):
        pass
    def to_shapely(self):
        pass

"""
SYMBOLS:
    Round (a circle) - diameter
    Rectangle - width and height
    Rounded Rectangle - width, height, corner radius, list of corners to round
    Chamfered Rectangle - width, height, corner radius, list of corners to chamfer
    Diamond - width and height
    Octagon - width, height, corner size (defines inner angle, see ODB++ symbol definitions)
    Round Donut - outer diameter, inner diameter
    Rectangle Donut - outer width, outer height, line width
    Square/Round Donut - outer diameter, inner diameter
    Rounded Rectangle Donut - outer width and height, line width, corner radius, list of corners to round
"""

class GeomSymbolRound(GeomSymbol):
    def __init__(self, center: Coordinate2, diameter: float):
        super().__init__()
        self.center = center
        self.diameter = diameter
    def to_mpl(self, spline=False, resolution=10, **patchkwargs) -> mpl.patches.CirclePolygon:
        if spline:
            patch = mpl.patches.Circle((self.center.x,self.center.y),radius=self.diameter/2., **patchkwargs)  # spline circle
        else:
            patch = mpl.patches.CirclePolygon((self.center.x,self.center.y),radius=self.diameter/2.,resolution=resolution,**patchkwargs)
        return patch
    def to_shapely(self,resolution=10):
        t = np.linspace(0,2*pi,resolution+1)  # N segments requires N+1 points
        x = self.center.x + self.diameter*np.cos(t)/2 
        y = self.center.y + self.diameter*np.sin(t)/2
        return shapely.Polygon(list(zip(x,y)))
    
class GeomSymbolRectangle(GeomSymbol):
    def __init__(self, origin: Coordinate2, width: float, height: float, centered=False):
        """
        Rectangle with width and height. By default, origin is bottom left corner. 
        If centered==True, origin is in the center.
        """
        super().__init__()
        self.origin = origin
        self.width = width
        self.height = height
        self.centered = centered
        
    def to_mpl(self, **patchkwargs) -> mpl.patches.Rectangle:
        if self.centered:
            xy = (self.origin.x-self.width/2., self.origin.y-self.height/2.)
        else:
            xy = (self.origin.x, self.origin.y)
        patch = mpl.patches.Rectangle(xy,self.width,self.height,**patchkwargs)
        return patch
    def to_shapely(self):
        if self.centered:
            vtxs = [
                (self.origin.x-self.width/2., self.origin.y-self.height/2.), 
                (self.origin.x+self.width/2., self.origin.y-self.height/2.),
                (self.origin.x+self.width/2., self.origin.y+self.height/2.),
                (self.origin.x-self.width/2., self.origin.y+self.height/2.),
                (self.origin.x-self.width/2., self.origin.y-self.height/2.)
                ]
        else:
            vtxs = [
                (self.origin.x,self.origin.y),
                (self.origin.x+self.width, self.origin.y),
                (self.origin.x+self.width, self.origin.y+self.height),
                (self.origin.x, self.origin.y+self.height),
                (self.origin.x,self.origin.y)
                ]
        return shapely.Polygon(vtxs)

class GeomCorner(Enum):
    BOTTOMLEFT = auto()
    BOTTOMRIGHT = auto()
    TOPRIGHT = auto()
    TOPLEFT = auto()

def get_bezier_rounded_corner(pos: Coordinate2, corner: GeomCorner, radius: float):
    """
    Given corner vertex `pos`, corner type `corner`, and corner radius `radius`, calculate cubic Bezier control 
    points for a rounded corner
    """
    mpl_CURVE4 = mpl.path.Path.CURVE4
    a=radius
    c = radius*4/3 * (np.sqrt(2) - 1)
    # c=0.55228474983079

    # transform manually
    if corner == GeomCorner.BOTTOMLEFT:
        x=pos.x+radius
        y=pos.y+radius
        vtxs = [(x-a,y),(x-a,y-c),(x-c,y-a),(x,y-a)]
    elif corner == GeomCorner.BOTTOMRIGHT:
        x=pos.x-radius
        y=pos.y+radius
        vtxs = [(x,y-a),(x+c,y-a),(x+a,y-c),(x+a,y)]
    elif corner == GeomCorner.TOPRIGHT:
        x=pos.x-radius
        y=pos.y-radius
        vtxs = [(x+a,y),(x+a,y+c),(x+c,y+a),(x,y+a)]
    elif corner == GeomCorner.TOPLEFT:
        x=pos.x+radius
        y=pos.y-radius
        vtxs = [(x,y+a),(x-c,y+a),(x-a,y+c),(x-a,y)]
    codes = [mpl_CURVE4,mpl_CURVE4,mpl_CURVE4]  # NOTE: No MOVETO, must be added manually, in case you don't want it
    
    # transform
    # ([np.array(vtx).reshape((2,1)) for vtx in vtxs])
    return vtxs,codes

def get_polygon_rounded_corner(pos: Coordinate2, corner: GeomCorner, radius: float, resolution: int =5):
    """
    Given corner vertex `pos`, corner type `corner`, and corner radius `radius`, calculate 
    polygonal vertices for a rounded corner, inclusive of both end points. Always
    goes counterclockwise.
    Returns vertices as (x,y) tuples.
    """
    # transform manually
    if corner == GeomCorner.BOTTOMLEFT:
        x0=pos.x+radius
        y0=pos.y+radius
        tstart = pi
        tstop = 3*pi/2
    elif corner == GeomCorner.BOTTOMRIGHT:
        x0=pos.x-radius
        y0=pos.y+radius
        tstart = 3*pi/2
        tstop = 2*pi
    elif corner == GeomCorner.TOPRIGHT:
        x0=pos.x-radius
        y0=pos.y-radius
        tstart = 0
        tstop = pi/2
    elif corner == GeomCorner.TOPLEFT:
        x0=pos.x+radius
        y0=pos.y-radius
        tstart = pi/2
        tstop = pi
    x = x0+radius*np.cos(np.linspace(tstart,tstop,resolution+1))
    y = y0+radius*np.sin(np.linspace(tstart,tstop,resolution+1))
    return list(zip(x,y))

class GeomSymbolRoundedRectangle(GeomSymbol):
    def __init__(self,origin: Coordinate2, width: float, height: float, corner_radius: float, corners: list[GeomCorner]=None, centered=False):
        """
        Rectangle with rounded corners, . By default, origin is bottom left corner. 
        If centered==True, origin is in the center.
        If corners==None, all four corners are rounded.
        `corners` has the order [bottom left, bottom right, top right, top left]
        """
        super().__init__()
        self.origin = origin
        self.centered = centered
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.corners = corners or [GeomCorner.BOTTOMLEFT,GeomCorner.BOTTOMRIGHT,GeomCorner.TOPRIGHT,GeomCorner.TOPLEFT]
        
        smallest_dim = self.width 
        if self.height < self.width:
            smallest_dim = self.height
        self.oval = False
        if np.isclose(self.corner_radius,smallest_dim):
            self.oval = True
        elif self.corner_radius > smallest_dim/2.:
            raise ValueError(f"Corner radius {self.corner_radius} is larger than half the smallest side, {smallest_dim/2.}.")
        
        
    def to_mpl(self, **patchkwargs):
        # First get rectangle vertices
        if self.centered:
            corner_vtxs = [
                Coordinate2(self.origin.x-self.width/2., self.origin.y-self.height/2.),
                Coordinate2(self.origin.x+self.width/2., self.origin.y-self.height/2.),
                Coordinate2(self.origin.x+self.width/2., self.origin.y+self.height/2.),
                Coordinate2(self.origin.x-self.width/2., self.origin.y+self.height/2.),
                ]
        else:
            corner_vtxs = [
                Coordinate2(self.origin.x,self.origin.y),
                Coordinate2(self.origin.x+self.width, self.origin.y),
                Coordinate2(self.origin.x+self.width, self.origin.y+self.height),
                Coordinate2(self.origin.x, self.origin.y+self.height),
                ]
        # Draw path, starting at bottom left, moving CCW
        vtxs_all = []
        codes_all = []
        if GeomCorner.BOTTOMLEFT in self.corners:
            vtxs,codes = get_bezier_rounded_corner(corner_vtxs[0], GeomCorner.BOTTOMLEFT, self.corner_radius)
            vtxs_all = vtxs
            codes_all = [mpl.path.Path.MOVETO]+codes
        else:
            vtxs_all.append((corner_vtxs[0].x,corner_vtxs[0].y))
            codes_all.append(mpl.path.Path.MOVETO)
        
        if GeomCorner.BOTTOMRIGHT in self.corners:
            vtxs,codes = get_bezier_rounded_corner(corner_vtxs[1], GeomCorner.BOTTOMRIGHT, self.corner_radius)
            vtxs_all = vtxs_all + vtxs
            codes_all = codes_all+[mpl.path.Path.LINETO]+codes
        else:
            vtxs_all.append((corner_vtxs[1].x,corner_vtxs[1].y))
            codes_all.append(mpl.path.Path.LINETO)
        
        if GeomCorner.TOPRIGHT in self.corners:
            vtxs,codes = get_bezier_rounded_corner(corner_vtxs[2], GeomCorner.TOPRIGHT, self.corner_radius)
            vtxs_all = vtxs_all + vtxs
            codes_all = codes_all+[mpl.path.Path.LINETO]+codes
        else:
            vtxs_all.append((corner_vtxs[2].x,corner_vtxs[2].y))
            codes_all.append(mpl.path.Path.LINETO)
        
        if GeomCorner.TOPLEFT in self.corners:
            vtxs,codes = get_bezier_rounded_corner(corner_vtxs[3], GeomCorner.TOPLEFT, self.corner_radius)
            vtxs_all = vtxs_all + vtxs
            codes_all = codes_all+[mpl.path.Path.LINETO]+codes
        else:
            vtxs_all.append((corner_vtxs[3].x,corner_vtxs[3].y))
            codes_all.append(mpl.path.Path.LINETO)
        
        # Finish
        vtxs_all.append(vtxs_all[0])
        codes_all.append(mpl.path.Path.LINETO)
        
        return mpl.patches.PathPatch(mpl.path.Path(vtxs_all,codes_all),**patchkwargs)
    
    
    def to_shapely(self):
        if self.centered:
            corner_vtxs = [
                Coordinate2(self.origin.x-self.width/2., self.origin.y-self.height/2.), 
                Coordinate2(self.origin.x+self.width/2., self.origin.y-self.height/2.),
                Coordinate2(self.origin.x+self.width/2., self.origin.y+self.height/2.),
                Coordinate2(self.origin.x-self.width/2., self.origin.y+self.height/2.),
                ]
        else:
            corner_vtxs = [
                Coordinate2(self.origin.x,self.origin.y),
                Coordinate2(self.origin.x+self.width, self.origin.y),
                Coordinate2(self.origin.x+self.width, self.origin.y+self.height),
                Coordinate2(self.origin.x, self.origin.y+self.height),
                ]
        
        vtxs_all = []
        if GeomCorner.BOTTOMLEFT in self.corners:
            vtxs_all = vtxs_all + get_polygon_rounded_corner(corner_vtxs[0], GeomCorner.BOTTOMLEFT, self.corner_radius)
        else:
            vtxs_all.append((corner_vtxs[0].x,corner_vtxs[0].y))
        if GeomCorner.BOTTOMRIGHT in self.corners:
            vtxs_all = vtxs_all + get_polygon_rounded_corner(corner_vtxs[1], GeomCorner.BOTTOMRIGHT, self.corner_radius)
        else:
            vtxs_all.append((corner_vtxs[1].x,corner_vtxs[1].y))
        if GeomCorner.TOPRIGHT in self.corners:
            vtxs_all = vtxs_all + get_polygon_rounded_corner(corner_vtxs[2], GeomCorner.TOPRIGHT, self.corner_radius)
        else:
            vtxs_all.append((corner_vtxs[2].x,corner_vtxs[2].y))
        if GeomCorner.TOPLEFT in self.corners:
            vtxs_all = vtxs_all + get_polygon_rounded_corner(corner_vtxs[3], GeomCorner.TOPLEFT, self.corner_radius)
        else:
            vtxs_all.append((corner_vtxs[3].x,corner_vtxs[3].y))
        
        vtxs_all.append(vtxs_all[0])  # close
        
        return shapely.Polygon(vtxs_all)
        

