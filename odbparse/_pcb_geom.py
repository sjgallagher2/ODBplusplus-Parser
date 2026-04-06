# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 15:03:46 2026

@author: SG1295
"""
# std lib
from math import sin,cos,tan
from enum import Enum,auto
from dataclasses import dataclass,field
from pathlib import Path

# dependencies
import numpy as np
import networkx as nx
import matplotlib as mpl
import matplotlib.pyplot as plt
import shapely
from shapely import LineString  # library for performing boolean operations and buffering/offsetting traces
import cadquery as cq

# Module
from ._coordinate2 import Coordinate2
# matrix
from ._odbparse import ODBLayerMatrixType,SIMULATION_LAYER_TYPES,COPPER_LAYER_TYPES
# features
from ._odbparse import ODBPolygonType,ODBPolygon,ODBFeatureSurface,ODBFeatureLine,ODBFeatureArc,ODBPolyCurve,ODBFeaturePadOrientation,ODBFeaturePad
# symbols
from ._odbparse import ODBSymbol,ODBRoundSymbol,ODBSquareSymbol,ODBRectangleSymbol,ODBRoundedRectangleSymbol,ODBOvalSymbol,ODBHalfOvalSymbol,ODBUserSymbol,ODBDiamondSymbol
# packages
from ._odbparse import ODB_EDA_Package,ODB_EDA_Pin,ODB_EDA_CircleRecord,ODB_EDA_SquareRecord,ODB_EDA_RectangleRecord,ODB_EDA_ContourRecord
# higher level
from ._odbparse import ODBLayer,load_ODB,load_user_symbols,ODB_EDA_Data

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

class GeomSubtraceArcOrientation(Enum):
    CW = auto()
    CCW = auto()

class GeomCommand:
    pass

@dataclass
class GeomCommandStart(GeomCommand):
    pt: Coordinate2
    
    def to_mpl_path(self):
        return [(self.pt.x,self.pt.y)],[mpl.path.Path.MOVETO]

@dataclass
class GeomCommandLineTo(GeomCommand):
    pt: Coordinate2 
    
    def to_mpl_path(self):
        return [(self.pt.x,self.pt.y)],[mpl.path.Path.LINETO]

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
    def from_segments_and_symbol(cls,segments: list[ODBFeatureLine|ODBFeatureArc],symbol: ODBSymbol,netname: str):
        """
        Convert segments and a symbol into a subtrace.
        
        This method is complicated by a couple factors:
            1. Segments are generally supplied in arbitrary order
            2. Segments have a pt_s and pt_e (start and end) but this does not
               generally obey any logic
        So we have to make our own path and do a lot of checking. It's ugly but it works. 
        """
        # Parse symbol
        if isinstance(symbol,ODBRoundSymbol):
            join_style = SVGJoinStyle.ROUND 
            cap_style = SVGCapStyle.ROUND
            tracewidth = symbol.diameter
        elif isinstance(symbol,ODBSquareSymbol):
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
            # Try splitting into cycles
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
            if isinstance(feat,ODBFeatureLine):
                # Note: Do NOT use feature here! They can be flipped
                cmds.append(GeomCommandLineTo(edge[1]))
            elif isinstance(feat,ODBFeatureArc):
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
        if isinstance(symbol,ODBRoundSymbol):
            join_style = SVGJoinStyle.ROUND 
            cap_style = SVGCapStyle.ROUND
            tracewidth = symbol.diameter
        elif isinstance(symbol,ODBSquareSymbol):
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
            # Try splitting into cycles
            print("Here")
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
            if isinstance(feat,ODBFeatureLine):
                # Note: Do NOT use feature here! They can be flipped apparently??
                cmds.append(GeomCommandLineTo(edge[1]))
            elif isinstance(feat,ODBFeatureArc):
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
    def __init__(self,netname):
        self.netname = netname or '$NONE$'
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
class GeomSymbolTransform:
    """
    Affine transformation
    Applies scale and rotation, then translation after
    """
    def __init__(self, 
                 scale: float = 1.0,
                 rot_deg: float = 0.0,
                 cw: bool = True,
                 translate_x: float = 0.0,
                 translate_y: float = 0.0,
                 mirror_x: bool = False):
        mat = np.eye(2)*scale
        rrad = np.deg2rad(rot_deg)
        if cw:
            rrad *= -1
        rot = np.array([[cos(rrad), -sin(rrad)], [sin(rrad),cos(rrad)]])
        if mirror_x:
            mat[0,0] *= -1 
        # Calculate matrix, pad it with 1 row of zeros after last, 1 row of cols after last
        # Result is 3x3
        self.matrix = np.pad(mat@rot, ((0,1),(0,1)))
        self.matrix[2,2] = 1
        # Translation
        self.matrix[0,2] = translate_x
        self.matrix[1,2] = translate_y
    
    def set_translate_x(self,x0):
        """Override current x translation (does NOT cascade)"""
        self.matrix[0,2] = x0
    def set_translate_y(self,y0):
        """Override current y translation (does NOT cascade)"""
        self.matrix[1,2] = y0
    def get_translate_x(self):
        return self.matrix[0,2]
    def get_translate_y(self):
        return self.matrix[1,2]
    def get_scale(self):
        return np.linalg.norm(self.matrix[:,0])
        
    def apply(self,vtxs: list[tuple[float]]):
        """Given vertices as a list of (x,y) tuples, apply transformation to all of them, translation last."""
        # Convert vertices to Nx3x1 array with 1 is bottom of column
        x = np.reshape(vtxs,(len(vtxs),2,1))
        xpad = np.ones((len(vtxs),1,1))     # axis chaos
        x = np.concatenate([x,xpad],axis=1) # axis chaos
        
        A = self.matrix
        y = A@x 
        # convert back to list of tuples by reshaping to 2D matrix and taking tuples
        y2 = y.reshape((len(vtxs),3))[:,0:2]  # axis chaos
        return [tuple(r) for r in list(y2)]
    
    def cascade(self,other):
        """
        Cascade other transform on top of current transform.
        """
        if not isinstance(other,GeomSymbolTransform):
            raise ValueError(f"Got unexpected type for cascade: {other}")
        self.matrix = other.matrix @ self.matrix
    
    def copy(self):
        ret = GeomSymbolTransform()
        ret.matrix = self.matrix.copy()
        return ret
    
    def __repr__(self):
        return f"GeomSymbolTransform(matrix={self.matrix})"

class GeomSymbolRound(GeomSymbol):
    def __init__(self, diameter: float, netname: str, transform: GeomSymbolTransform=None):
        super().__init__(netname)
        self.diameter = diameter
        self.transform = transform or GeomSymbolTransform()
    
    def apply_transform(self,xf: GeomSymbolTransform):
        xf = xf.copy()
        self.transform.cascade(xf)
    
    def to_mpl(self, spline=False, resolution=10, **patchkwargs) -> mpl.patches.CirclePolygon:
        rad = self.diameter*self.transform.get_scale()/2.
        if spline:
            patch = mpl.patches.Circle((self.transform.get_translate_x(),
                                        self.transform.get_translate_y()),
                                       radius=rad, **patchkwargs)  # spline circle
        else:
            patch = mpl.patches.CirclePolygon((self.transform.get_translate_x(),
                                               self.transform.get_translate_y()),radius=rad,
                                              resolution=resolution,**patchkwargs)
        return patch
    def to_shapely(self,resolution=10):
        rad = self.diameter*self.transform.get_scale()/2.
        t = np.linspace(0,2*pi,resolution+1)  # N segments requires N+1 points
        x = self.transform.get_translate_x() + rad*np.cos(t) 
        y = self.transform.get_translate_y() + rad*np.sin(t)
        return shapely.Polygon(list(zip(x,y)))
    
class GeomSymbolRectangle(GeomSymbol):
    def __init__(self, width: float, height: float, netname: str, centered=False,transform: GeomSymbolTransform=None):
        """
        Rectangle with width and height. By default, origin is bottom left corner. 
        If centered==True, origin is in the center.
        """
        super().__init__(netname)
        self.width = width
        self.height = height
        self.centered = centered
        self.transform = transform or GeomSymbolTransform()
    
    def apply_transform(self,xf: GeomSymbolTransform):
        xf = xf.copy()
        self.transform.cascade(xf)
    
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

class GeomSymbolDiamond(GeomSymbol):
    def __init__(self, width: float, height: float, netname: str, centered=True, transform: GeomSymbolTransform=None):
        """
        Diamond (skew rectangle rotated 45 degrees) with width and height. By default, origin is the center.
        
        """
        super().__init__(netname)
        self.width = width
        self.height = height
        self.centered = centered
        self.transform = transform or GeomSymbolTransform()
    
    def apply_transform(self,xf: GeomSymbolTransform):
        xf = xf.copy()
        self.transform.cascade(xf)
    
    def _get_vertices(self):
        if self.centered:
            corner_vtxs = [
                (0.0, -self.height/2.),
                (self.width/2., 0.0),
                (0.0, +self.height/2.),
                (-self.width/2., 0.0),
                (0.0, -self.height/2.),
                ]
        else:
            corner_vtxs = [
                (self.width/2., 0.0),
                (self.width, self.height/2.),
                (self.width/2., self.height),
                (0.0, self.height/2.),
                (self.width/2., 0.0),
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
    def __init__(self,width: float, height: float, corner_radius: float, netname: str,
                 corners: list[GeomCorner]=None, centered=False,transform: GeomSymbolTransform=None):
        """
        Rectangle with rounded corners. By default, origin is bottom left corner. 
        If centered==True, origin is in the center.
        If corners==None, all four corners are rounded.
        `corners` has the order [bottom left, bottom right, top right, top left]
        """
        super().__init__(netname)
        self.centered = centered
        self.width = width
        self.height = height
        self.corner_radius = corner_radius
        self.corners = corners or [GeomCorner.BOTTOMLEFT,GeomCorner.BOTTOMRIGHT,GeomCorner.TOPRIGHT,GeomCorner.TOPLEFT]
        self.transform = transform or GeomSymbolTransform()
        
        smallest_dim = self.width 
        if self.height < self.width:
            smallest_dim = self.height
        self.oval = False
        if np.isclose(self.corner_radius,smallest_dim):
            self.oval = True
        elif self.corner_radius > smallest_dim/2.:
            raise ValueError(f"Corner radius {self.corner_radius} is larger than half the smallest side, {smallest_dim/2.}.")
    
    def apply_transform(self,xf: GeomSymbolTransform):
        xf = xf.copy()
        self.transform.cascade(xf)
    
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
    
    def apply_transform(self,xf: GeomSymbolTransform):
        xf = xf.copy()
        self.transform.cascade(xf)
    
    @classmethod
    def from_odb_polygon(cls,feat: ODBPolygon):
        # feat.bs         # start position
        # feat.poly_type  # ODBPolygonType.ISLAND or HOLE
        # feat.segments   # ODBPolyCyrve or a Coordinate2 for a line
        
        cmds = [GeomCommandStart(feat.bs)]
        for seg in feat.segments:
            if isinstance(seg,ODBPolyCurve):
                if seg.cw:
                    cmds.append(GeomCommandArcTo(seg.p2,seg.center,GeomSubtraceArcOrientation.CW))
                else:
                    cmds.append(GeomCommandArcTo(seg.p2,seg.center,GeomSubtraceArcOrientation.CCW))
            else:
                cmds.append(GeomCommandLineTo(seg))
        if feat.poly_type == ODBPolygonType.ISLAND:
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
        vtx_tuples = self.transform.apply(vtx_tuples)
        return vtx_tuples
    
    def to_mpl(self,path_only=False,**patchkwargs) -> mpl.patches.PathPatch:
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
        all_vtxs = self.transform.apply(all_vtxs)
        if path_only:
            return mpl.path.Path(all_vtxs,all_codes)
        #else
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
        vtx_tuples = self.transform.apply(vtx_tuples)
        ls = shapely.LineString(vtx_tuples)
        return ls

class GeomPolygon:
    def __init__(self, shell: GeomSimplePolygon, holes: list[GeomSimplePolygon], netname: str):
        self.shell = shell
        self.holes = holes
        self.netname = netname or '$NONE$'
    
    def apply_transform(self,xf: GeomSymbolTransform):
        xf = xf.copy()
        self.shell.transform.cascade(xf)
        for hole in self.holes:
            hole.transform.cascade(xf)
    
    def to_shapely(self):
        shell_ls = self.shell.to_shapely()
        holes_ls = []
        for hole in self.holes:
            holes_ls.append(hole.to_shapely())
        return shapely.Polygon(shell_ls,holes_ls)
    
    def to_mpl(self,**patchkwargs):
        shell_path = self.shell.to_mpl(path_only=True,**patchkwargs)
        polypath_vtxs = shell_path.vertices
        polypath_codes = shell_path.codes
        polypath_vtxs = np.concatenate([polypath_vtxs,[[0.,0.]]])
        polypath_codes = np.concatenate([polypath_codes,[mpl.path.Path.CLOSEPOLY]])
        
        for hole in self.holes:
            holepath = hole.to_mpl(path_only=True,**patchkwargs)
            polypath_vtxs = np.concatenate([polypath_vtxs,holepath.vertices])
            polypath_codes = np.concatenate([polypath_codes,holepath.codes])
            polypath_vtxs = np.concatenate([polypath_vtxs,[[0.,0.]]])
            polypath_codes = np.concatenate([polypath_codes,[mpl.path.Path.CLOSEPOLY]])
        
        path = mpl.path.Path(polypath_vtxs,polypath_codes)
        patch = mpl.patches.PathPatch(path,**patchkwargs)
        return patch
        

# NOTE: Copy the transform before using it, with .copy()
pad_transform_lookup = {
    ODBFeaturePadOrientation.DEG0_NOMIRROR      :GeomSymbolTransform(),
    ODBFeaturePadOrientation.DEG90_NOMIRROR     :GeomSymbolTransform(rot_deg=90),
    ODBFeaturePadOrientation.DEG180_NOMIRROR    :GeomSymbolTransform(rot_deg=180),
    ODBFeaturePadOrientation.DEG270_NOMIRROR    :GeomSymbolTransform(rot_deg=270),
    ODBFeaturePadOrientation.DEG0_XMIRROR       :GeomSymbolTransform(rot_deg=0,mirror_x=True),
    ODBFeaturePadOrientation.DEG90_XMIRROR      :GeomSymbolTransform(rot_deg=90,mirror_x=True),
    ODBFeaturePadOrientation.DEG180_XMIRROR     :GeomSymbolTransform(rot_deg=180,mirror_x=True),
    ODBFeaturePadOrientation.DEG270_XMIRROR     :GeomSymbolTransform(rot_deg=270,mirror_x=True),
    ODBFeaturePadOrientation.DEGANY_NOMIRROR    :GeomSymbolTransform(),
    ODBFeaturePadOrientation.DEGANY_XMIRROR     :GeomSymbolTransform(mirror_x=True)
    }
def get_pad_transform(pad: ODBFeaturePad):
    """Get pad transform with translation"""
    transform = pad_transform_lookup[pad.orient_def].copy()  # initialize, then update
    if pad.rot_deg is not None:
        tf2 = GeomSymbolTransform(scale=pad.resize_factor,rot_deg=pad.rot_deg,translate_x=pad.p1.x,translate_y=pad.p1.y)
    else:
        tf2 = GeomSymbolTransform(scale=pad.resize_factor,translate_x=pad.p1.x,translate_y=pad.p1.y)
    transform.cascade(tf2)
    return transform


def parse_eda_outline(outline: ODB_EDA_CircleRecord|ODB_EDA_SquareRecord|ODB_EDA_RectangleRecord|ODB_EDA_ContourRecord):
    """Parse an outline record for an EDA package or pin, ignore package and pin transformations"""
    if isinstance(outline,ODB_EDA_CircleRecord):
        #outline.c 
        #outline.radius 
        xf = GeomSymbolTransform(translate_x=outline.c.x,translate_y=outline.c.y)
        return GeomSymbolRound(outline.radius*2,'',xf)
    elif isinstance(outline,ODB_EDA_SquareRecord):
        xf = GeomSymbolTransform(translate_x=outline.c.x,translate_y=outline.c.y)
        return GeomSymbolRectangle(outline.halfside*2, outline.halfside*2, '',centered=True,transform=xf)
    elif isinstance(outline,ODB_EDA_RectangleRecord):
        # NOTE: Unlike Square and Circle outlines, outline.p0 is the bottom left corner, not the center
        xf = GeomSymbolTransform(translate_x=outline.p0.x,translate_y=outline.p0.y)
        return GeomSymbolRectangle(outline.width, outline.height, '',centered=False,transform=xf)
    elif isinstance(outline,ODB_EDA_ContourRecord):
        shell_poly = None
        hole_polys = []
        for poly in outline.polygons:
            if poly.poly_type == ODBPolygonType.ISLAND:
                if shell_poly is not None:
                    print("WARNING: More than one island for surface!")
                shell_poly = GeomSimplePolygon.from_odb_polygon(poly)
                # Update polygon transform
                # shell_poly.transform.cascade(xf)
            else:
                hole_poly = GeomSimplePolygon.from_odb_polygon(poly)
                # Update polygon transform
                # hole_poly.transform.cascade(xf)
                hole_polys.append(hole_poly)
                
        return GeomPolygon(shell_poly,hole_polys,'')
    else:
        raise ValueError(f"Unknown outline record type {outline}")


def get_pkg_outlines(pkg,pkg_xf):
    pkg_outline = parse_eda_outline(pkg.outline_record)
    pkg_outline.apply_transform(pkg_xf)
    pkg_outlines = [pkg_outline]
    for pin in pkg.pins:
        po = parse_eda_outline(pin.outline)
        po.apply_transform(pkg_xf)
        pkg_outlines.append(po)
    return pkg_outlines


def parse_symbol(pad: ODBFeaturePad, symbol: ODBSymbol, netname: str, scale=1e-3):
    def _parse_user_symbol(usersympad: ODBFeaturePad,usersym: ODBSymbol):
        """
        Parse a user symbol into Geom types.
        
        User symbols are defined by their own `features` files with features centered at
        the origin. We will convert these to a list of polygons and translate them to our
        user-symbol-based pad position
        
        Always returns a list of Geom types. 
        """
        xf = get_pad_transform(usersympad)
        symbol_polygons = []
        surface_polygons = []
        for feat in usersym.featfile.features_list:
            if isinstance(feat,ODBFeaturePad):
                symbol_geom = parse_symbol(feat,usersym.featfile.symbol_dict[feat.sym_num],netname,scale)
                symbol_geom.transform.cascade(xf)
                symbol_polygons.append(symbol_geom)
            elif isinstance(feat,ODBFeatureSurface):
                shell_poly = None
                hole_polys = []
                for poly in feat.polygons:
                    if poly.poly_type == ODBPolygonType.ISLAND:
                        if shell_poly is not None:
                            print("WARNING: More than one island for surface!")
                        shell_poly = GeomSimplePolygon.from_odb_polygon(poly)
                        # Update polygon transform
                        shell_poly.transform.cascade(xf)
                    else:
                        hole_poly = GeomSimplePolygon.from_odb_polygon(poly)
                        # Update polygon transform
                        hole_poly.transform.cascade(xf)
                        hole_polys.append(hole_poly)
                        
                surface_polygons.append(GeomPolygon(shell_poly,hole_polys,netname))
            else:
                raise ValueError(f"User symbol with feature other than surface or pad: {feat}")
        if len(surface_polygons) == 1 and len(symbol_polygons) == 0:
            symgeom = surface_polygons[0]
        elif len(surface_polygons) == 0 and len(symbol_polygons) == 1:
            symgeom = symbol_polygons[0]
        else:
            # print("Warning: Symbol with multiple features")
            # print(surface_polygons+symbol_polygons)
            return surface_polygons+symbol_polygons
        return [symgeom]
    
    xf = get_pad_transform(pad)  # rotate, scale, translation
    if isinstance(symbol,ODBRoundSymbol):
        symgeom = GeomSymbolRound(symbol.diameter*scale,netname,transform=xf.copy())
    elif isinstance(symbol,ODBRectangleSymbol):
        symgeom = GeomSymbolRectangle(symbol.width*scale, symbol.height*scale,netname,
                                      centered=True,transform=xf.copy())
    elif isinstance(symbol,ODBSquareSymbol):
        symgeom = GeomSymbolRectangle(symbol.side*scale, symbol.side*scale,netname,
                                      centered=True,transform=xf.copy())
    elif isinstance(symbol,ODBRoundedRectangleSymbol):
        symgeom = GeomSymbolRoundedRectangle(symbol.width*scale, symbol.height*scale, 
                                             symbol.radius*scale,netname,centered=True,transform=xf.copy())
    elif isinstance(symbol,ODBOvalSymbol):
        crad = symbol.width/2
        if symbol.width > symbol.height:
            crad = symbol.height/2
        symgeom = GeomSymbolRoundedRectangle(symbol.width*scale, symbol.height*scale,
                                             crad*scale,netname,centered=True,transform=xf.copy())
    elif isinstance(symbol,ODBHalfOvalSymbol):
        crad = symbol.width/2
        if symbol.width > symbol.height:
            crad = symbol.height/2
        corners = [GeomCorner.BOTTOMRIGHT,GeomCorner.TOPRIGHT]
        symgeom = GeomSymbolRoundedRectangle(symbol.width*scale, symbol.height*scale,
                                             crad*scale,netname,corners,centered=True,transform=xf.copy())
    
    elif isinstance(symbol,ODBDiamondSymbol):
        symgeom = GeomSymbolDiamond(symbol.width*scale, symbol.height*scale, 
                                             netname,centered=True,transform=xf.copy())
    
    elif isinstance(symbol,ODBUserSymbol):
        symgeoms = _parse_user_symbol(pad, symbol)
        return symgeoms

    else:
        raise NotImplementedError(f"Symbol {symbol} not yet implemented.")
    return symgeom

def parse_layer_geom(layer: ODBLayer, user_sym_dict, edadata: ODB_EDA_Data, electrical_only=True):
    """Main method for parsing a layer's features into PCB geometry"""
    # break layer graph up on a per-symbol basis
    layer_symbol_subgraphs = layer.get_partitioned_graph(user_sym_dict,edadata.feat_netname_on_layer)
    # layer_symbol_subgraphs is a dict from symbol number -> list of subgraphs for that symbol

    # make subtraces
    subtraces = {}  # netname : list[subtraces]
    for symnum, sgs in layer_symbol_subgraphs.items():
        for sg in sgs:
            skip_trace = False
            netname = sg.graph['netname']
            if electrical_only:
                if netname == '$NONE$':
                    # Check if this is a non-electrical layer (no subnet)
                    for u,v,data in sg.edges(data=True):
                        if edadata.get_feature_FID(layer.name,data['fnum']) is None:
                            skip_trace = True
                            break
            if not skip_trace:
                if netname not in subtraces.keys():
                    subtraces[netname] = []
                subtraces[netname].append(GeomSubtrace.from_graph(sg))

    # Build subtrace, symbol, and surface geoms
    all_net_polygons = []
    symbol_polygons = []
    surface_polygons = []
    for netnmame,netsubs in subtraces.items():
        for subtrace in netsubs:
            all_net_polygons.append(subtrace)

    # Parse pads and surfaces
    for feat in layer.featfile.features_list:
        netname = None
        if layer.name in edadata.feat_netname_on_layer.keys():
            netname = edadata.feat_netname_on_layer[layer.name].get(feat.fnum)
        if netname is None:
            netname = '$NONE$'
        if netname == '$NONE$':
            if electrical_only:
                if edadata.get_feature_FID(layer.name,feat.fnum) is None:
                    continue
        if isinstance(feat,ODBFeaturePad):
            symbol = layer.featfile.symbol_dict[feat.sym_num]
            symbol_geom = parse_symbol(feat,symbol,netname)
            if isinstance(symbol_geom,list):    
                symbol_polygons += symbol_geom
            else:
                symbol_polygons.append(symbol_geom)
        elif isinstance(feat,ODBFeatureSurface):
            shell_poly = None
            hole_polys = []
            for poly in feat.polygons:
                if poly.poly_type == ODBPolygonType.ISLAND:
                    if shell_poly is not None:
                        print("WARNING: More than one island for surface!")
                    shell_poly = GeomSimplePolygon.from_odb_polygon(poly)
                    # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
                else:
                    hole_polys.append(GeomSimplePolygon.from_odb_polygon(poly))
                    # surface_polygons.append(geom.GeomSimplePolygon.from_odb_polygon(poly).to_shapely())
                    
            surface_polygons.append(GeomPolygon(shell_poly,hole_polys,netname))

    return all_net_polygons+symbol_polygons+surface_polygons


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
    elif polygon.geom_type == 'LineString':
        xx,yy = polygon.coords.xy
        x = xx.tolist()
        y = yy.tolist()
        ax.plot(x,y)


class ODBArchive:
    """
    Top level ODB++ archive class.
    It's a bit hacky but it gets the job done and performance isn't an issue.
    """
    def __init__(self,root_name,electrical_only=True):
        self.root_p = Path(root_name)
        
        self.odbconf = load_ODB(self.root_p)
        self.user_sym_dict = load_user_symbols(self.odbconf)  # Needs to be done manually
        
        # Load EDA data
        print("Loading EDA data...")
        self.edadata = ODB_EDA_Data(self.odbconf)
        
        # Get simulatable layer types
        print("Loading layers...")
        self.layernames = []
        self.layers = {}
        self.geoms_on_layer = {}
        self._drill_shapelys = None
        for layer in self.odbconf.matrix.matrix_layers:
            if layer.type in SIMULATION_LAYER_TYPES:
                lname = layer.name.lower()
                print(f'\tLayer: {lname}')
                self.layernames.append(lname)  # lower() because matrix tends to change capitalization
                self.layers[lname] = ODBLayer(self.odbconf,layer.name.lower(),self.user_sym_dict)
                if lname not in ['comp_+_top','comp_+_bot']:
                    self.geoms_on_layer[lname] = parse_layer_geom(self.layers[lname],self.user_sym_dict,self.edadata,electrical_only)
                else:
                    # geoms on layer requires parsing packages
                    pass
                
            if layer.type == ODBLayerMatrixType.DRILL:
                # Add drill shapely
                self._drill_shapelys = self.get_layer_shapelys(layer.name.lower(),do_union=False,subtract_drill=False)
        # Add top-level board profile
        print("Loading profile...")
        profile = ODBLayer(self.odbconf,'profile',self.user_sym_dict,is_toplevel=True)
        self.layers['profile'] = profile
        self.layernames.append('profile')
        self.geoms_on_layer['profile'] = parse_layer_geom(self.layers['profile'],self.user_sym_dict,self.edadata,electrical_only=False)
        
        self.recalculate_stackup()
        
        print("ODB++ archive loaded.")
    
    def recalculate_stackup(self):
        # Get layer order and stackup info
        layernames = []
        layerrows = []
        for name,layer in self.layers.items():
            if layer.type in COPPER_LAYER_TYPES or layer.type == ODBLayerMatrixType.DIELECTRIC:
                layernames.append(name)
                layerrows.append(layer.matrixrow)
        layeridxs = np.argsort(layerrows)  # get stackup-order of layers, top to bottom
        # layer order from top to bottom
        self.copper_layer_order = list(np.take(layernames,layeridxs))
        
        # Get layer stackup
        top_thickness = np.around(self.layers[self.copper_layer_order[0]].thickness,6)
        bottom_thickness = np.around(self.layers[self.copper_layer_order[-1]].thickness,6)
        # get total board thickness
        board_thickness = 0.0
        for name in self.copper_layer_order[:-1]:  # exclude bottom
            layer = self.layers[name]
            if layer.dielectric_thickness is not None:
                board_thickness += (layer.thickness + layer.dielectric_thickness)
            else:
                board_thickness += layer.thickness
        board_thickness += bottom_thickness  # only add bottom copper thickness,
        board_thickness = np.around(board_thickness,6)  # round to 0.001 mil
        # refine board thickness
        if self.odbconf.board_thickness != board_thickness:
            if self.odbconf.board_thickness > board_thickness*3:
                print(f"NOTE: ODB++ archive board thickness was {self.odbconf.board_thickness*1e3}mil but layer stackup gives {np.around(board_thickness*1e3,6)}mil. Using ODB++ archive value.")
                board_thickness = self.odbconf.board_thickness
            else:
                print(f"NOTE: ODB++ archive board thickness was {self.odbconf.board_thickness*1e3}mil but layer stackup gives {np.around(board_thickness*1e3,6)}mil. Using layer stackup value.")
                self.odbconf.board_thickness = board_thickness
        self.layers['profile'].thickness = board_thickness - top_thickness - bottom_thickness
        # repeat and get z_offset for each copper layer
        self.layer_zoffsets = {}
        # z_offset is top of board, then we subtract layer copper, use that as the z_offset of the
        # layer, then subtract the dielectric thickness to get ready for the next layer
        z_offset = self.odbconf.board_thickness
        for name in self.copper_layer_order:
            layer = self.layers[name]
            z_offset = np.around(z_offset - layer.thickness, 6)
            # copper layer z_offset is bottom plane of copper layer
            self.layer_zoffsets[name] = z_offset
            if layer.dielectric_thickness is not None:
                z_offset -= layer.dielectric_thickness
        # add profile even though it's not copper
        self.layer_zoffsets['profile'] = self.layers[self.copper_layer_order[-1]].thickness  # thickness of bottom layer
    
    def load_layer(self,layername):
        self.layernames.append(layername.lower())
        self.layers[layername.lower()] = ODBLayer(self.odbconf,layername.lower(),self.user_sym_dict)
        self.geoms_on_layer[layername.lower()] = parse_layer_geom(self.layers[layername.lower()],
                                                                  self.user_sym_dict,self.edadata,electrical_only=False)
    
    def _get_component_outlines(self,refdes: str,layer: ODBLayer|None=None):
        if layer is None:
            for layer in self.layers:
                if layer.type == ODBLayerMatrixType.COMPONENT:
                    if refdes in layer.compfile.components.keys():
                        comp = layer.compfile.components[refdes]
                        break
        else:
            comp = layer.compfile.components[refdes]
        comp_xf = GeomSymbolTransform(translate_x=comp.loc.x,translate_y=comp.loc.y,rot_deg=comp.rot_deg,mirror_x=comp.mirror)
        comp_pkg_name = self.edadata.package_number_name_lookup[comp.pkg_ref]
        comp_pkg = self.edadata.packages[comp_pkg_name]
        comp_outlines = get_pkg_outlines(comp_pkg,comp_xf)
        return comp_outlines
    
    def render_components(self,layername,refdes_list,ax=None,**patchkwargs):
        if layername not in self.layernames:
            raise ValueError(f"Could not find layer '{layername}' in layers. Known layers: {self.layernames}")
        White = (0.8,0.8,0.8)  # actually grey now
        if self.layers[layername].type == ODBLayerMatrixType.COMPONENT:
            if 'color' not in patchkwargs:
                patchkwargs['color']=White
        # Plot
        if ax is None:
            fig,ax = plt.subplots(1,1,figsize=(7,7))
            ax.set_aspect('equal')
            ax.set_box_aspect(1)
        
        if self.layers[layername].type == ODBLayerMatrixType.COMPONENT:
            color = White
            if 'fill' not in patchkwargs:
                patchkwargs['fill'] = False
            if 'linewidth' not in patchkwargs and 'lw' not in patchkwargs:
                patchkwargs['lw'] = 2
            if 'edgecolor' not in patchkwargs and 'ec' not in patchkwargs:
                patchkwargs['ec'] = patchkwargs['color']
            if 'alpha' not in patchkwargs:
                patchkwargs['alpha'] = 1.0
            #self.layers[layername].compfile.components.keys()
            for refdes in refdes_list:
                outlines = self._get_component_outlines(refdes,self.layers[layername])
                for po in outlines:
                    ax.add_patch(po.to_mpl(**patchkwargs))
                comp = self.layers[layername].compfile.components[refdes]
                # Annotate refdes
                annot = ax.annotate(
                    refdes,
                    xy=(comp.loc.x,comp.loc.y),
                    xytext=(0,0),
                    xycoords='data',
                    textcoords='offset points',
                    ha='center',
                    va='center',
                    annotation_clip=True,
                    color=patchkwargs['color'],
                    alpha=patchkwargs['alpha'],
                    weight='bold'
                    )
        
    
    def render_layer(self,layername,ax=None,subtract_drill=True,do_union=True,**patchkwargs):
        if layername not in self.layernames:
            raise ValueError(f"Could not find layer '{layername}' in layers. Known layers: {self.layernames}")
        # Get geometry
        if self.layers[layername].type != ODBLayerMatrixType.COMPONENT:
            layer_shapelys = self.get_layer_shapelys(layername,do_union=True,subtract_drill=subtract_drill)
        
        SpringGreen4 = (0.,0.55,0.27)
        Gold1 = (1.,0.843,0)
        White = (0.8,0.8,0.8)  # actually grey now
        if layername == 'profile':
            if 'color' not in patchkwargs:
                patchkwargs['color']=SpringGreen4
        elif self.layers[layername].type in COPPER_LAYER_TYPES:
            if 'color' not in patchkwargs:
                patchkwargs['color']=Gold1
        elif self.layers[layername].type == ODBLayerMatrixType.COMPONENT:
            if 'color' not in patchkwargs:
                patchkwargs['color']=White
        
        # Plot
        if ax is None:
            fig,ax = plt.subplots(1,1,figsize=(7,7))
            ax.set_aspect('equal')
            ax.set_box_aspect(1)
            
        # Handle Component layers separately
        if self.layers[layername].type == ODBLayerMatrixType.COMPONENT:
            color = White
            if 'fill' not in patchkwargs:
                patchkwargs['fill'] = False
            if 'linewidth' not in patchkwargs and 'lw' not in patchkwargs:
                patchkwargs['lw'] = 2
            if 'edgecolor' not in patchkwargs and 'ec' not in patchkwargs:
                patchkwargs['ec'] = patchkwargs['color']
            if 'alpha' not in patchkwargs:
                patchkwargs['alpha'] = 1.0
            for refdes in self.layers[layername].compfile.components.keys():
                outlines = self._get_component_outlines(refdes,self.layers[layername])
                for po in outlines:
                    ax.add_patch(po.to_mpl(**patchkwargs))
                comp = self.layers[layername].compfile.components[refdes]
                # Annotate refdes
                annot = ax.annotate(
                    refdes,
                    xy=(comp.loc.x,comp.loc.y),
                    xytext=(0,0),
                    xycoords='data',
                    textcoords='offset points',
                    ha='center',
                    va='center',
                    annotation_clip=True,
                    color=patchkwargs['color'],
                    alpha=patchkwargs['alpha'],
                    weight='bold'
                    )

        # Profile and copper layers
        else:
            if do_union:
                big_union = shapely.disjoint_subset_union_all(layer_shapelys)
                if isinstance(big_union,shapely.Polygon):
                    plot_shapely_as_patch(big_union,ax,**patchkwargs)
                else:
                    for buf in big_union.geoms:
                        plot_shapely_as_patch(buf,ax,**patchkwargs)
            else:
                for shape in layer_shapelys.geoms:    
                    plot_shapely_as_patch(shape, ax, **patchkwargs)
        ax.autoscale()

    def get_layer_shapelys(self,layername,do_union=True,subtract_drill=True):
        """Call to_shapely() on all geometries on layer and optionally union them."""
        if layername not in self.layernames:
            raise ValueError(f"Could not find layer '{layername}' in layers. Known layers: {self.layernames}")
        # Get geometry
        layer_shapelys = []
        for gg in self.geoms_on_layer[layername]:
            geom = gg.to_shapely()
            if geom.is_valid:
                layer_shapelys.append(geom)
            else:
                layer_shapelys.append(geom.buffer(0))  # seems to fix things when unions fail
        if do_union:
            layer_shapelys = shapely.disjoint_subset_union_all(layer_shapelys)
        else:
            layer_shapelys = shapely.MultiPolygon(layer_shapelys)
        if subtract_drill and do_union:
            if self._drill_shapelys is not None:
                layer_shapelys = layer_shapelys - self._drill_shapelys
            else:
                print("Warning: subtract_drill specified but no drill shapes loaded.")
        return layer_shapelys
    
    def _get_shapely_cad(self,polygon,thickness,z_offset:float=0.0, in_to_mm=True):
        """
        Convert a 2D shapely polygon with shell and holes into a extrusion of height `thickness`.
        If thickness < 0, extrude down; otherwise extrude up. 
        
        If `z_offset` is nonzero, use that as the plane to extrude from. The z-offset 
        is applied before the `in_to_mm` conversion. 
        
        If in_to_mm==True, scale the CAD by 25.4x right before returning. 
        """
        if polygon.geom_type != 'Polygon':
            print(f"Warning! Found shape other than Polygon: {polygon.geom_type}. Skipping.")
            return None
        xx,yy = polygon.exterior.coords.xy
        x = xx.tolist()
        y = yy.tolist()
        shell_vtxs = list(zip(x,y))
        holes_vtxs = []
        for polyint in polygon.interiors:
            xx,yy = polyint.coords.xy
            x = xx.tolist()
            y = yy.tolist()
            hole_vtxs = list(zip(x,y))
            holes_vtxs.append(hole_vtxs)
        
        # Now we have shell_vtxs and holes_vtxs
        # holes_vtxs is a list of list-of-vertices
        try:
            cadpoly = cq.Workplane("front").workplane(z_offset).polyline(shell_vtxs).close()
            # Now cut holes out
            for hole_vtxs in holes_vtxs:
                cadpoly = cadpoly.polyline(hole_vtxs).close()
            cadpoly = cadpoly.extrude(thickness)
            if in_to_mm:
                cadpoly = cadpoly.val().scale(25.4)
            return cadpoly
        except:
            print("Bad geometry, simplifying with tolerance 0.1 mil...")
            poly_simpl = shapely.simplify(polygon,1e-4)
            xx,yy = poly_simpl.exterior.coords.xy
            x = xx.tolist()
            y = yy.tolist()
            shell_vtxs = list(zip(x,y))
            holes_vtxs = []
            for polyint in poly_simpl.interiors:
                xx,yy = polyint.coords.xy
                x = xx.tolist()
                y = yy.tolist()
                hole_vtxs = list(zip(x,y))
                holes_vtxs.append(hole_vtxs)
            cadpoly = cq.Workplane("front").workplane(z_offset).polyline(shell_vtxs).close()
            # Now cut holes out
            for hole_vtxs in holes_vtxs:
                cadpoly = cadpoly.polyline(hole_vtxs).close()
            cadpoly = cadpoly.extrude(thickness)
            if in_to_mm:
                cadpoly = cadpoly.val().scale(25.4)
            return cadpoly
            print("Success")
    
    def _get_copper_layer_cad(self,layername,z_offset: float = 0.0, in_to_mm=True, subtract_drill=False):
        if layername not in self.layernames:
            raise ValueError(f"Could not find layer '{layername}' in layers. Known layers: {self.layernames}")
        layer_shapelys = self.get_layer_shapelys(layername,do_union=True,subtract_drill=subtract_drill)
        cadpolys = []
        
        if isinstance(layer_shapelys,shapely.Polygon):
            thickness = self.layers[layername].thickness
            cadpoly = self._get_shapely_cad(layer_shapelys,thickness,z_offset=z_offset,in_to_mm=in_to_mm)
            if cadpoly is not None:
                cadpolys.append(cadpoly)
        else:
            for i,polygon in enumerate(layer_shapelys.geoms):
                print(f"{layername}: Polygon {i+1}/{len(layer_shapelys.geoms)}")
                if polygon.geom_type != 'Polygon':
                    print(f"Warning! Found shape other than Polygon: {polygon.geom_type}. Skipping.")
                    continue
                thickness = self.layers[layername].thickness
                cadpoly = self._get_shapely_cad(polygon,thickness,z_offset=z_offset,in_to_mm=in_to_mm)
                if cadpoly is not None:
                    cadpolys.append(cadpoly)
        return cadpolys
    
    def _get_profile_cad(self,z_offset:float=0.0,in_to_mm=True,subtract_drill=False):
        if 'profile' not in self.layernames:
            raise ValueError(f"Could not find profile in layers. Known layers: {self.layernames}")
        layer_shapelys = self.get_layer_shapelys('profile',do_union=True,subtract_drill=subtract_drill)
        cadpolys = []
        thickness = self.layers['profile'].thickness
        if thickness < 1e-13:
            raise ValueError("Layer 'profile' cannot have zero thickness. Update the stackup before exporting step files.")
        
        cadpoly = self._get_shapely_cad(layer_shapelys,thickness,z_offset=z_offset,in_to_mm=in_to_mm)
        if cadpoly is not None:
            cadpolys.append(cadpoly)
        return cadpolys
    
    def _get_drill_cad(self,layername: str, in_to_mm=True):
        layer_shapelys = self._drill_shapelys
        cadpolys = []
        thickness = self.odbconf.board_thickness 
                
        for i,polygon in enumerate(layer_shapelys.geoms):
            print(f"{layername}: Polygon {i+1}/{len(layer_shapelys.geoms)}")
            if polygon.geom_type != 'Polygon':
                print(f"Warning! Found shape other than Polygon: {polygon.geom_type}. Skipping.")
                continue
            cadpoly = self._get_shapely_cad(polygon,thickness,in_to_mm=in_to_mm)
            if cadpoly is not None:
                cadpolys.append(cadpoly)
                
        return cadpolys
    
    def export_layer_step(self,layername,z_offset: float = 0.0, subtract_drill=False, in_to_mm=True):
        if layername not in self.layernames:
            raise ValueError(f"Could not find layer '{layername}' in layers. Known layers: {self.layernames}")
        type = self.layers[layername].type
        
        assycolor = None
        if type in [ODBLayerMatrixType.POWER_GROUND,
                         ODBLayerMatrixType.SIGNAL,
                         ODBLayerMatrixType.MIXED]:
            cadpolys = self._get_copper_layer_cad(layername,z_offset,in_to_mm,subtract_drill)
            assycolor = cq.Color('Gold1')
        elif layername == 'profile':
            cadpolys = self._get_profile_cad(z_offset,in_to_mm,subtract_drill)
            assycolor = cq.Color('SpringGreen4')
        elif type == ODBLayerMatrixType.DRILL:
            cadpolys = self._get_drill_cad(layername,in_to_mm)
        elif type == ODBLayerMatrixType.ROUT:
            raise NotImplementedError("Routing layer not yet implemented.")
        elif type == ODBLayerMatrixType.DIELECTRIC:
            raise NotImplementedError("Dielectric layer not yet implemented.")
        elif type in [ODBLayerMatrixType.CONDUCTIVE_PASTE,
                           ODBLayerMatrixType.MASK,
                           ODBLayerMatrixType.SILK_SCREEN,
                           ODBLayerMatrixType.SOLDER_MASK,
                           ODBLayerMatrixType.SOLDER_PASTE]:
            raise NotImplementedError(f"Layer type {type} not yet implemented.")

        print("Assembling...")
        assy = cq.Assembly()
        assy.name = layername
        
        for wp in cadpolys:
            if assycolor is not None:
                assy.add(wp,color=assycolor)
            else:
                assy.add(wp)
        print("Assembly complete. Exporting to STEP...")
        step_path = self.root_p.parent/f'{self.root_p.name}_{layername}.step'
        assy.export(str(step_path))
        print(f"Export complete to path: {str(step_path)}")

