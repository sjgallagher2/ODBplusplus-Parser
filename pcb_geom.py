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
from dataclasses import dataclass,field
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

class GeomCommand:
    pass

@dataclass
class GeomCommandStart(GeomCommand):
    pt: Coordinate2
    
    def to_mpl_path(self):
        mpl_MOVETO = 1  # definitions from matplotlib
        mpl_LINETO = 2
        mpl_CURVE4 = 4
        return [(self.pt.x,self.pt.y)],[mpl_MOVETO]

@dataclass
class GeomCommandLineTo(GeomCommand):
    pt: Coordinate2 
    
    def to_mpl_path(self):
        mpl_MOVETO = 1  # definitions from matplotlib
        mpl_LINETO = 2
        mpl_CURVE4 = 4
        return [(self.pt.x,self.pt.y)],[mpl_LINETO]

@dataclass
class GeomCommandArcTo(GeomCommand):
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
        if p1 == p2:
            # circle
            angle_start_deg = 0
            angle_end_deg = 360
            angle_span = 360
        else:
            angle_start_deg = (p1-self.center_pt).angle(True)%360
            angle_end_deg = (p2-self.center_pt).angle(True)%360
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
    def linearize(self,prevpt: Coordinate2, resolution=15):
        """
        Discretize circular arc into `resolution` segments
        
        Return x,y
        """
        p1 = prevpt
        p2 = self.end_pt
        cw = self.orientation == GeomSubtraceArcOrientation.CW
        rad = (p1-self.center_pt).magnitude()
        if p1 == p2:
            # circle
            angle_start_rad = 0
            angle_end_rad = 2*pi
            angle_span = 2*pi
        else:
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
    cmds: tuple[GeomCommand]
    tracewidth: float
    netname: str
    join_style: SVGJoinStyle = SVGJoinStyle.ROUND
    cap_style: SVGCapStyle = SVGCapStyle.ROUND
    
    def to_mpl(self,**patchkwargs) -> mpl.patches.PathPatch:
        prev_pt = None
        all_vtxs = []
        all_codes = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomCommandArcTo):
                vtxs,codes = cmd.to_mpl_path(Coordinate2(*prev_pt))
            else:
                vtxs,codes = cmd.to_mpl_path()
            all_vtxs += vtxs
            all_codes += codes
            prev_pt = vtxs[-1]
        patch = mpl.patches.PathPatch(mpl.path.Path(all_vtxs,all_codes),**patchkwargs)
        return patch
    
    def to_vtxs(self):
        prev_pt = None 
        all_vtxs = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomCommandArcTo):
                vtxs = cmd.linearize(prev_pt)
            else:
                vtxs = [cmd.pt]
            all_vtxs += vtxs
            prev_pt = vtxs[-1]
        
        vtx_tuples = [(c.x,c.y) for c in all_vtxs]
        return vtx_tuples
    
    def to_shapely(self,do_buffer=True) -> shapely.Polygon:
        prev_pt = None 
        all_vtxs = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomCommandArcTo):
                vtxs = cmd.linearize(prev_pt)
            else:
                vtxs = [cmd.pt]
            all_vtxs += vtxs
            prev_pt = vtxs[-1]
        
        vtx_tuples = [(c.x,c.y) for c in all_vtxs]
        ls = LineString(vtx_tuples)
        # if ls.is_closed:
        #     segs = list(map(shapely.LineString, zip(ls.coords[:-1], ls.coords[1:])))
        #     ls = shapely.MultiLineString(segs)
        if do_buffer:
            buf = ls.buffer(self.tracewidth/2*1e-3,quad_segs=2,
                            join_style=self.join_style.name.lower(),
                            cap_style=self.cap_style.name.lower())
            return buf
        else:
            return ls
    
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
        cmds = [GeomCommandStart(vtx_path[0])]  # Initialize with start point
        for edge in path_edges:
            feat = graph.get_edge_data(edge[0],edge[1])['feature']
            if isinstance(feat,odb.ODBFeatureLine):
                # Note: Do NOT use feature here! They can be flipped
                cmds.append(GeomCommandLineTo(edge[1]))
            elif isinstance(feat,odb.ODBFeatureArc):
                cw = feat.cw
                if feat.pt_e != edge[1]:
                    cw = not cw  # Feature was backwards, flip cw/ccw
                orient = GeomSubtraceArcOrientation.CCW 
                if cw:
                    orient = GeomSubtraceArcOrientation.CW 
                cmds.append(GeomCommandArcTo(edge[1],feat.pt_c,orient))
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
        cmds = [GeomCommandStart(vtx_path[0])]  # Initialize with start point
        for edge in path_edges:
            feat = graph.get_edge_data(edge[0],edge[1])['feature']
            if isinstance(feat,odb.ODBFeatureLine):
                # Note: Do NOT use feature here! They can be flipped apparently??
                cmds.append(GeomCommandLineTo(edge[1]))
            elif isinstance(feat,odb.ODBFeatureArc):
                cw = feat.cw
                if feat.pt_e != edge[1]:
                    cw = not cw  # Feature was backwards, flip cw/ccw
                orient = GeomSubtraceArcOrientation.CCW 
                if cw:
                    orient = GeomSubtraceArcOrientation.CW 
                cmds.append(GeomCommandArcTo(edge[1],feat.pt_c,orient))
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
@dataclass
class GeomSymbolTransform():
    scale: float = 1.0
    rot_deg: float = 0.0
    cw: bool = False
    translate_x: float = 0.0
    translate_y: float = 0.0
    mirror_x: bool = False
    
    def matrix(self):
        mat = np.eye(2)*self.scale
        rrad = np.deg2rad(self.rot_deg)
        if self.cw:
            rrad *= -1
        rot = np.array([[cos(rrad), -sin(rrad)], [sin(rrad),cos(rrad)]])
        if self.mirror_x:
            mat[0,0] *= -1 
        return mat@rot
    def apply(self,vtxs: list[tuple[float]]):
        """Given vertices as a list of (x,y) tuples, apply transformation to all of them"""
        # Convert vertices to Nx2x1 array
        x = np.reshape(vtxs,(len(vtxs),2,1))
        A = self.matrix()
        y = A@x 
        # convert back to list of tuples by reshaping to 2D matrix and taking tuples
        y2 = y.reshape((len(vtxs),2))
        y2[:,0] += self.translate_x
        y2[:,1] += self.translate_y
        return [tuple(r) for r in list(y2)]


class GeomSymbolRound(GeomSymbol):
    def __init__(self, center: Coordinate2, diameter: float,transform: GeomSymbolTransform=GeomSymbolTransform()):
        super().__init__()
        self.center = center
        self.diameter = diameter
        self.transform = transform
    def to_mpl(self, spline=False, resolution=10, **patchkwargs) -> mpl.patches.CirclePolygon:
        rad = self.diameter*self.transform.scale/2.
        if spline:
            patch = mpl.patches.Circle((self.center.x,self.center.y),radius=rad, **patchkwargs)  # spline circle
        else:
            patch = mpl.patches.CirclePolygon((self.center.x,self.center.y),radius=rad,resolution=resolution,**patchkwargs)
        return patch
    def to_shapely(self,resolution=10):
        rad = self.diameter*self.transform.scale/2.
        t = np.linspace(0,2*pi,resolution+1)  # N segments requires N+1 points
        x = self.center.x + rad*np.cos(t) 
        y = self.center.y + rad*np.sin(t)
        return shapely.Polygon(list(zip(x,y)))
    
class GeomSymbolRectangle(GeomSymbol):
    def __init__(self, origin: Coordinate2, width: float, height: float, centered=False,transform: GeomSymbolTransform=None):
        """
        Rectangle with width and height. By default, origin is bottom left corner. 
        If centered==True, origin is in the center.
        """
        super().__init__()
        self.width = width
        self.height = height
        self.centered = centered
        self.transform = transform or GeomSymbolTransform()
        self.transform.translate_x += origin.x
        self.transform.translate_y += origin.y
    
    def _get_vertices(self):
        if self.centered:
            corner_vtxs = [
                (self.width/2., -self.height/2.),
                (self.width/2., self.height/2.),
                (-self.width/2., +self.height/2.),
                (-self.width/2., -self.height/2.),
                (self.width/2., -self.height/2.),
                ]
        else:
            corner_vtxs = [
                (0.0,0.0),
                (self.width, 0.0),
                (self.width, self.height),
                (0.0, self.height),
                (0.0,0.0),
                ]
        return corner_vtxs
    
    def to_mpl(self, **patchkwargs) -> mpl.patches.Rectangle:
        vtxs = self._get_vertices()
        vtxs_xf = self.transform.apply(vtxs)
        codes = [mpl.path.Path.MOVETO] + ([mpl.path.Path.LINETO]*(len(vtxs_xf)-1))
        path = mpl.path.Path(vtxs_xf,codes)
        patch = mpl.patches.PathPatch(path,**patchkwargs)
        return patch
    def to_shapely(self):
        vtxs = self._get_vertices()
        vtxs_xf = self.transform.apply(vtxs)
        return shapely.Polygon(vtxs_xf)

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
    def __init__(self,origin: Coordinate2, width: float, height: float, corner_radius: float, 
                 corners: list[GeomCorner]=None, centered=False,transform: GeomSymbolTransform=None):
        """
        Rectangle with rounded corners. By default, origin is bottom left corner. 
        If centered==True, origin is in the center.
        If corners==None, all four corners are rounded.
        `corners` has the order [bottom left, bottom right, top right, top left]
        """
        super().__init__()
        self.centered = centered
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.corners = corners or [GeomCorner.BOTTOMLEFT,GeomCorner.BOTTOMRIGHT,GeomCorner.TOPRIGHT,GeomCorner.TOPLEFT]
        self.transform = transform or GeomSymbolTransform()
        self.transform.translate_x += origin.x
        self.transform.translate_y += origin.y
        
        
        smallest_dim = self.width 
        if self.height < self.width:
            smallest_dim = self.height
        self.oval = False
        if np.isclose(self.corner_radius,smallest_dim):
            self.oval = True
        elif self.corner_radius > smallest_dim/2.:
            raise ValueError(f"Corner radius {self.corner_radius} is larger than half the smallest side, {smallest_dim/2.}.")
        
    def _get_vertices(self):
        if self.centered:
            corner_vtxs = [
                Coordinate2(-self.width/2., -self.height/2.),
                Coordinate2(+self.width/2., -self.height/2.),
                Coordinate2(+self.width/2., +self.height/2.),
                Coordinate2(-self.width/2., +self.height/2.),
                ]
        else:
            corner_vtxs = [
                Coordinate2(0.0,0.0),
                Coordinate2(self.width, 0.0),
                Coordinate2(self.width, self.height),
                Coordinate2(0.0, self.height),
                ]
        return corner_vtxs
    def to_mpl(self, **patchkwargs):
        # First get rectangle vertices
        corner_vtxs = self._get_vertices()
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
        
        # Now apply transformation to vertices
        vtxs_all = self.transform.apply(vtxs_all)
        
        return mpl.patches.PathPatch(mpl.path.Path(vtxs_all,codes_all),**patchkwargs)
    
    
    def to_shapely(self):
        corner_vtxs = self._get_vertices()
        
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
        
        # Now apply transformation to vertices
        vtxs_all = self.transform.apply(vtxs_all)
        
        return shapely.Polygon(vtxs_all)

class GeomPolygonPolarity(Enum):
    POSITIVE = auto()
    NEGATIVE = auto()

@dataclass
class GeomSimplePolygon:
    """
    A polygon is basically identical to a subtrace, but it's closed and filled
    """
    cmds: tuple[GeomCommand]
    # netname: str    # this isn't parsed at the moment
    polarity: GeomPolygonPolarity = GeomPolygonPolarity.POSITIVE
    transform: GeomSymbolTransform = field(default_factory=GeomSymbolTransform)
    
    @classmethod
    def from_odb_polygon(cls,feat: odb.ODBFeaturePolygon):
        # feat.bs         # start position
        # feat.poly_type  # ODBPolygonType.ISLAND or HOLE
        # feat.segments   # ODBPolyCyrve or a Coordinate2 for a line
        
        cmds = [GeomCommandStart(feat.bs)]
        for seg in feat.segments:
            if isinstance(seg,odb.ODBPolyCurve):
                if seg.cw:
                    cmds.append(GeomCommandArcTo(seg.p2,seg.center,GeomSubtraceArcOrientation.CW))
                else:
                    cmds.append(GeomCommandArcTo(seg.p2,seg.center,GeomSubtraceArcOrientation.CCW))
            else:
                cmds.append(GeomCommandLineTo(seg))
        if feat.poly_type == odb.ODBPolygonType.ISLAND:
            polarity = GeomPolygonPolarity.POSITIVE
        else:
            polarity = GeomPolygonPolarity.NEGATIVE
        
        return cls(cmds,polarity)
    
    def to_vtxs(self):
        prev_pt = None 
        all_vtxs = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomCommandArcTo):
                vtxs = cmd.linearize(prev_pt)
            else:
                vtxs = [cmd.pt]
            all_vtxs += vtxs
            prev_pt = vtxs[-1]
        
        vtx_tuples = [(c.x,c.y) for c in all_vtxs]
        return vtx_tuples
    
    def to_mpl(self,**patchkwargs) -> mpl.patches.PathPatch:
        prev_pt = None
        all_vtxs = []
        all_codes = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomCommandArcTo):
                vtxs,codes = cmd.to_mpl_path(Coordinate2(*prev_pt))
            else:
                vtxs,codes = cmd.to_mpl_path()
            all_vtxs += vtxs
            all_codes += codes
            prev_pt = vtxs[-1]
        patch = mpl.patches.PathPatch(mpl.path.Path(all_vtxs,all_codes),**patchkwargs)
        return patch
    
    def to_shapely(self) -> shapely.LineString:
        prev_pt = None 
        all_vtxs = []
        for cmd in self.cmds:
            if isinstance(cmd,GeomCommandArcTo):
                vtxs = cmd.linearize(prev_pt)
            else:
                vtxs = [cmd.pt]
            all_vtxs += vtxs
            prev_pt = vtxs[-1]
        
        vtx_tuples = [(c.x,c.y) for c in all_vtxs]
        ls = shapely.LineString(vtx_tuples)
        return ls

class GeomPolygon:
    def __init__(self, shell: GeomSimplePolygon, holes: list[GeomSimplePolygon]):
        self.shell = shell
        self.holes = holes
    
    def to_shapely(self):
        shell_ls = self.shell.to_shapely()
        holes_ls = []
        for hole in self.holes:
            holes_ls.append(hole.to_shapely())
        return shapely.Polygon(shell_ls,holes_ls)

def get_pad_transform(pad: odb.ODBFeaturePad):
    dl = {
        odb.ODBFeaturePadOrientation.DEG0_NOMIRROR      :GeomSymbolTransform(),
        odb.ODBFeaturePadOrientation.DEG90_NOMIRROR     :GeomSymbolTransform(rot_deg=90),
        odb.ODBFeaturePadOrientation.DEG180_NOMIRROR    :GeomSymbolTransform(rot_deg=180),
        odb.ODBFeaturePadOrientation.DEG270_NOMIRROR    :GeomSymbolTransform(rot_deg=270),
        odb.ODBFeaturePadOrientation.DEG0_XMIRROR       :GeomSymbolTransform(rot_deg=0,mirror_x=True),
        odb.ODBFeaturePadOrientation.DEG90_XMIRROR      :GeomSymbolTransform(rot_deg=90,mirror_x=True),
        odb.ODBFeaturePadOrientation.DEG180_XMIRROR     :GeomSymbolTransform(rot_deg=180,mirror_x=True),
        odb.ODBFeaturePadOrientation.DEG270_XMIRROR     :GeomSymbolTransform(rot_deg=270,mirror_x=True),
        odb.ODBFeaturePadOrientation.DEGANY_NOMIRROR    :GeomSymbolTransform(rot_deg=pad.rot_deg),
        odb.ODBFeaturePadOrientation.DEGANY_XMIRROR     :GeomSymbolTransform(rot_deg=pad.rot_deg,mirror_x=True)
        }
    # translate_x=pad.p1.x,translate_y=pad.p1.y
    transform = dl[pad.orient_def]  # initialize, then update
    transform.scale = pad.resize_factor
    return transform
    

def parse_symbol(pad: odb.ODBFeaturePad, symbol: odb.ODBSymbol):
    pos = pad.p1
    xf = get_pad_transform(pad)
    if isinstance(symbol,odb.ODBRoundSymbol):
        symgeom = GeomSymbolRound(pos,symbol.diameter*1e-3,transform=xf)
    elif isinstance(symbol,odb.ODBRectangleSymbol):
        symgeom = GeomSymbolRectangle(pos, symbol.width*1e-3, symbol.height*1e-3,
                                      centered=True,transform=xf)
    elif isinstance(symbol,odb.ODBSquareSymbol):
        symgeom = GeomSymbolRectangle(pos, symbol.side*1e-3, symbol.side*1e-3,
                                      centered=True,transform=xf)
    elif isinstance(symbol,odb.ODBRoundedRectangleSymbol):
        symgeom = GeomSymbolRoundedRectangle(pos, symbol.width*1e-3, symbol.height*1e-3, 
                                             symbol.radius*1e-3,centered=True,transform=xf)
    elif isinstance(symbol,odb.ODBOvalSymbol):
        crad = symbol.width/2
        if symbol.width > symbol.height:
            crad = symbol.height/2
        symgeom = GeomSymbolRoundedRectangle(pos, symbol.width*1e-3, symbol.height*1e-3,
                                             crad*1e-3,centered=True,transform=xf)
    elif isinstance(symbol,odb.ODBHalfOvalSymbol):
        crad = symbol.width/2
        if symbol.width > symbol.height:
            crad = symbol.height/2
        corners = [GeomCorner.BOTTOMRIGHT,GeomCorner.TOPRIGHT]
        symgeom = GeomSymbolRoundedRectangle(pos, symbol.width*1e-3, symbol.height*1e-3,
                                             crad*1e-3,corners,centered=True,transform=xf)
    elif isinstance(symbol,odb.ODBUserSymbol):
        symbol_polygons = []
        surface_polygons = []
        for feat in symbol.featfile.features_list:
            if isinstance(feat,odb.ODBFeaturePad):
                symbol = symbol.featfile.symbol_dict[feat.sym_num]
                symbol_geom = parse_symbol(feat,symbol)
                symbol_polygons.append(symbol_geom)
            elif isinstance(feat,odb.ODBFeatureSurface):
                shell_poly = None
                hole_polys = []
                for poly in feat.polygons:
                    if poly.poly_type == odb.ODBPolygonType.ISLAND:
                        if shell_poly is not None:
                            print("WARNING: More than one island for surface!")
                        shell_poly = GeomSimplePolygon.from_odb_polygon(poly)
                        # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
                    else:
                        hole_polys.append(GeomSimplePolygon.from_odb_polygon(poly))
                        # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
                        
                surface_polygons.append(GeomPolygon(shell_poly,hole_polys))
            else:
                raise ValueError(f"User symbol with feature other than surface or pad: {feat}")
        if len(surface_polygons) == 1 and len(symbol_polygons) == 0:
            symgeom = surface_polygons[0]
        elif len(surface_polygons) == 0 and len(symbol_polygons) == 1:
            symgeom = symbol_polygons[0]
        else:
            print("Warning: Symbol with multiple features")
            print(surface_polygons+symbol_polygons)
            return surface_polygons+symbol_polygons

    else:
        raise NotImplementedError(f"Symbol {symbol} not yet implemented.")
    return symgeom







