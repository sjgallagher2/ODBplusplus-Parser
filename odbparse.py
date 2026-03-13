# -*- coding: utf-8 -*-
"""
Created on Wed Mar 11 09:59:38 2026

@author: SG1295
"""

from pathlib import Path
from enum import Enum,auto
from dataclasses import dataclass,field
import re
from typing import Optional
import numpy as np
import networkx as nx  # graph library for mapping nets to lines

# For testing only
import matplotlib as mpl
import matplotlib.pyplot as plt

from coordinate2 import Coordinate2

# os.path https://docs.python.org/3/library/os.path.html
#  isdir()
#  isfile()
#  exists()
# pathlib https://docs.python.org/3/library/pathlib.html

# DEFINITIONS
def enum_contains(eclass: Enum,name: str):
    try:
        eclass[name]
        return True
    except KeyError:
        return False

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
    do_flip = False
    if cw:
        angle_start = np.deg2rad(angle_end_deg)
        angle_end = np.deg2rad(angle_start_deg)
        do_flip = True
    else:
        angle_start = np.deg2rad(angle_start_deg)
        angle_end = np.deg2rad(angle_end_deg)
    
    
    # Calculate start and end points
    p0_x = center.x + radius * np.cos(angle_start)
    p0_y = center.y + radius * np.sin(angle_start)
    p3_x = center.x + radius * np.cos(angle_end)
    p3_y = center.y + radius * np.sin(angle_end)
    P0 = (p0_x, p0_y)
    P3 = (p3_x, p3_y)

    # Calculate angular span (ensure it's positive and < 90 deg for best results)
    angle_span = angle_end - angle_start
    if angle_span < 0:
        angle_span += 2 * np.pi # Handle cases where end < start

    # It's highly recommended to subdivide large angles into smaller ones (e.g., <= 90 deg)
    if angle_span > np.pi / 2 + 1e-5:
        # Handle subdivision in a more complete function (see online resources)
        # print("Warning: Angle span > 90 degrees. Approximation error will be larger.")
        # For a full implementation of arbitrary angles, refer to libraries 
        # or detailed algorithms on [GitHub](https://github.com/fontello/svgpath)
        pass 

    # Calculate the 'L' value
    L = (4/3) * radius * np.tan(angle_span / 4)

    # Calculate unit tangent vectors at P0 and P3
    # Tangent at angle t is (-sin(t), cos(t)) for ccw
    T0 = (-np.sin(angle_start), np.cos(angle_start))
    T3 = (-np.sin(angle_end), np.cos(angle_end)) # Tangent vector at P3 needs to point inward for the 'minus L*T1' formula

    # Calculate control points P1 and P2
    P1 = (P0[0] + L * T0[0], P0[1] + L * T0[1])
    P2 = (P3[0] - L * T3[0], P3[1] - L * T3[1]) # Note the minus sign for T3

    if do_flip:
        vtxs = [P0, P1, P2]
    else:
        vtxs = [P1,P2,P3]
    codes = [mpl.path.Path.CURVE4]*3
    
    if standalone:
        vtxs = [P0] + vtxs
        codes = [mpl.path.Path.MOVETO] + codes
    
    if do_flip:
        vtxs = vtxs[::-1]
    
    return vtxs,codes

        
class ODBLayerMatrixContext(Enum):
    BOARD = auto()
    MISC = auto()
class ODBLayerMatrixType(Enum):
    SIGNAL = auto()
    POWER_GROUND = auto()
    DIELECTRIC = auto()
    MIXED = auto()
    SOLDER_MASK = auto()
    SOLDER_PASTE = auto()
    SILK_SCREEN = auto()
    DRILL = auto()
    ROUT = auto()
    DOCUMENT = auto()
    COMPONENT = auto()
    MASK = auto()
    CONDUCTIVE_PASTE = auto()

SIMULATION_LAYER_TYPES = [ODBLayerMatrixType.COMPONENT,ODBLayerMatrixType.SIGNAL,ODBLayerMatrixType.POWER_GROUND,ODBLayerMatrixType.MIXED,ODBLayerMatrixType.DIELECTRIC,ODBLayerMatrixType.DRILL]

class ODBLayerMatrixPolarity(Enum):
    POSITIVE=auto()
    NEGATIVE=auto()
class ODBLayerMatrixDielectricType(Enum):
    NONE=auto()
    PREPREG=auto()
    CORE=auto()
class ODBLayerMatrixForm(Enum):
    RIGID=auto()
    FLEX=auto()
    
class ODBLayerMatrixLayerRoutSubtype(Enum):
    PUNCH=auto()            # ROUT
class ODBLayerMatrixLayerDrillSubtype(Enum):    
    BACKDRILL=auto()        # DRILL
    DUAL_DIAMETER=auto()    # DRILL
class ODBLayerMatrixLayerConductivePasteSubtype(Enum):
    SILVER_MASK=auto()      # CONDUCTIVE_PASTE
    CARBON_MASK=auto()      # CONDUCTIVE_PASTE
class ODBLayerMatrixLayerDocumentSubtype(Enum):
    AREA=auto()             # DOCUMENT
    DRAWING=auto()          # DOCUMENT
class ODBLayerMatrixLayerMaskSubtype(Enum):
    BEND_AREA=auto()        # MASK
    FLEX_AREA=auto()        # MASK
    RIGID_AREA=auto()       # MASK
    IMMERSION_MASK=auto()   # MASK
    OSP_MASK=auto()         # MASK
    PLATING_MASK=auto()     # MASK
    STIFFENER=auto()        # MASK
    FR4_STIFFENER=auto()    # MASK
    METAL_STIFFENER=auto()  # MASK
    POLYIMIDE_STIFFENER=auto() # MASK
    FILM_SHIELDING=auto()   # MASK
    METAL_SHIELDING=auto()  # MASK
    PSA=auto()              # MASK
    WIRE_BONDING=auto()     # MASK
    EMBEDDED_R=auto()       # MASK
    EMBEDDED_C=auto()       # MASK
class ODBLayerMatrixLayerMixedSubtype(Enum):
    MIXED_FLEX=auto()       # MIXED
class ODBLayerMatrixLayerPowerGroundSubtype(Enum):
    PG_FLEX=auto()          # POWER_GROUND
class ODBLayerMatrixLayerSignalSubtype(Enum):
    SIGNAL_FLEX=auto()      # SIGNAL
class ODBLayerMatrixLayerSolderMaskSubtype(Enum):
    COVERCOAT=auto()        # SOLDER_MASK
    COVERLAY=auto()         # SOLDER_MASK
    LIQUID_PHOTO_IMAGEABLE=auto()  # SOLDER_MASK


# BASIC METHODS
def is_ODB(root: Path):
    """
    Check briefly that path `root` can be read as an ODB++ tree.
    
    We expect the following files to exist ALWAYS for >= v8
    /matrix/matrix                    file with layer refs and step ref
    /misc/info                        file metadata
    /fonts/standard                   standard font to be used
    /steps/.../stphdr                 header, must exist for any step
    /steps/.../layers/.../features    CAD features, must exist for any layers
    
    For v7.x only /matrix/matrix and the /steps/... files are required, but
    /misc/info and /fonts/standard are commonly found too
    """
    ret = True
    ret &= (root/'matrix/matrix').exists()
    ret &= (root/'misc/info').exists()
    ret &= (root/'fonts/standard').exists()
    ret &= (root/'steps').exists()
    return ret

# BASE PARSING
# Methods and classes for extracting key-value pairs from ASCII
@dataclass 
class ODBVariable:
    name: str = ''
    value: any  = None # int, float, or str
    
    
@dataclass
class ODBArray:
    name: str = ''
    variables: list[ODBVariable] = field(default_factory=list)
    
    def asdict(self):
        dout = {}
        for v in self.variables:
            dout[v.name] = v.value
        return dout
    
    
class ODBUnit(Enum):
    INCH=auto()
    MIL=auto()
    MM=auto()
    MICRON=auto() 
# you cant make me do this neater
UNIT_CONVERSION_DICT = {
    (ODBUnit.INCH,ODBUnit.INCH):1.,
    (ODBUnit.INCH,ODBUnit.MIL):1e3,
    (ODBUnit.INCH,ODBUnit.MM):25.4,
    (ODBUnit.INCH,ODBUnit.MICRON):25.4e-3,
    
    (ODBUnit.MIL,ODBUnit.INCH):1e-3,
    (ODBUnit.MIL,ODBUnit.MIL):1.,
    (ODBUnit.MIL,ODBUnit.MM):25.4e-3,
    (ODBUnit.MIL,ODBUnit.MICRON):25.4,
    
    (ODBUnit.MM,ODBUnit.INCH):1/25.4,
    (ODBUnit.MM,ODBUnit.MIL):1/(25.4e-3),
    (ODBUnit.MM,ODBUnit.MM):1.,
    (ODBUnit.MM,ODBUnit.MICRON):1e3,
    
    (ODBUnit.MICRON,ODBUnit.INCH):1/(25.4e3),
    (ODBUnit.MICRON,ODBUnit.MIL):1/25.4,
    (ODBUnit.MICRON,ODBUnit.MM):1e-3,
    (ODBUnit.MICRON,ODBUnit.MICRON):1.,
    }
def get_unit_conversion(src_unit:ODBUnit,dest_unit:ODBUnit):
    return UNIT_CONVERSION_DICT[(src_unit,dest_unit)]

# Reading a structured text file
def read_structured_text(file: Path):
    """Read a structured text file. Ugly, works."""
    lines = []
    with open(file,'r') as f:
        lines = f.readlines()
    # Clean
    lines = [l.strip() for l in lines if l.strip()!='']
    lines = [l for l in lines if not l.startswith('#')]
    # Lines can be (a) an equality, like X_DATUM=0.3, or (b) an array between curly braces {} on multiple lines
    arr_start_idxs = []
    arr_end_idxs = []
    var_idxs = []  # can be within or without array
    for i,l in enumerate(lines):
        if l.endswith('{'):
            arr_start_idxs.append(i)
        elif l.startswith('}'):
            arr_end_idxs.append(i)
        if l.find('=') != -1:
            var_idxs.append(i)
    if len(arr_start_idxs) != len(arr_end_idxs):
        print("Error: Number of curly braces doesn't match.")
    # Zip into (start,end) indices
    arr_idxs = list(zip(arr_start_idxs,arr_end_idxs))
    
    arrs = []
    variables = []
    
    # Parse arrays
    for idxs in arr_idxs:
        idx_start = idxs[0]
        idx_end = idxs[1]
        arr = ODBArray()
        arr.name = lines[idx_start].split(' ')[0]
        used_var_idxs = []
        for i,vidx in enumerate(var_idxs):
            if vidx > idx_start and vidx < idx_end:
                varline = lines[vidx].split('=')
                var = ODBVariable()
                var.name = varline[0].strip()
                val_s = varline[1].strip()
                try:
                    var.value = float(val_s)
                except ValueError:
                    var.value = val_s
                if val_s == '':
                    var.value = None
                used_var_idxs.append(vidx)
                arr.variables.append(var)
        # update var_idxs
        var_idxs = [vidx for vidx in var_idxs if vidx not in used_var_idxs]
        arrs.append(arr)
    
    # Parse any remaining variables
    variables = []
    for i,vidx in enumerate(var_idxs):
        varline = lines[vidx].split('=')
        var = ODBVariable()
        var.name = varline[0].strip()
        val_s = varline[1].strip()
        try:
            var.value = float(val_s)
        except ValueError:
            var.value = val_s
        if val_s == '':
            var.value = None
        variables.append(var)
    return (arrs,variables)

class ODBMatrix:
    """
    Matrix data from /matrix/matrix. 
    
    From the spec:
        The matrix is a representation of the product model in which the rows are 
        the product model layers — sheets on which elements are drawn for 
        plotting, drilling and routing or assembly; and the columns are the product 
        model steps — multi-layer entities such as single images, assembly panels, 
        production panels and coupons.
    
    The matrix/matrix file has STEP and LAYER arrays, which provide information about 
    what kind of ECAD (step) and layers are contained in the archive. These have
    associated dataclasses, accessed by members:
        matrix_steps
        matrix_layers
    """
    
    @dataclass 
    class ODBStepInfo:
        """
        Step information from /matrix/matrix
        """
        col: int|None = None
        stepid: int|None = None
        name: str = ''
        
        def load(self,sarr: ODBArray):
            sdict = sarr.asdict()
            self.col = int(sdict.get('COL'))
            self.name = sdict.get('NAME')
            self.stepid = sdict.get('ID')

    @dataclass
    class ODBLayerInfo:
        """
        Layer info from /matrix/matrix
        """
        context: ODBLayerMatrixContext|None = None
        layertype: ODBLayerMatrixType|None = None
        name: str = ''
        old_name: str = ''
        dielectric_name: str = ''
        cu_top: str = ''
        cu_bottom: str = ''
        ref: str = ''
        start_name: str = ''
        end_name: str = ''
        row: int|None = None
        layerid: int|None = None
        polarity: ODBLayerMatrixPolarity|None = None
        dielectric_type: ODBLayerMatrixDielectricType|None = None
        form: ODBLayerMatrixForm|None = None
        add_type: ODBLayerMatrixLayerRoutSubtype|ODBLayerMatrixLayerDrillSubtype|ODBLayerMatrixLayerConductivePasteSubtype|ODBLayerMatrixLayerDocumentSubtype|ODBLayerMatrixLayerMaskSubtype|ODBLayerMatrixLayerMixedSubtype|ODBLayerMatrixLayerPowerGroundSubtype|ODBLayerMatrixLayerSignalSubtype|ODBLayerMatrixLayerSolderMaskSubtype|None = None
        color: str = ''
        
        def load(self,larr: ODBArray):
            ldict = larr.asdict()
            self.row = int(ldict.get('ROW'))
            self.name = ldict.get('NAME')
            self.layerid = ldict.get('ID')  # int
            self.dielectric_name = ldict.get('DIELECTRIC_NAME')
            self.cu_top = ldict.get('CU_TOP')
            self.cu_bottom = ldict.get('CU_BOTTOM')
            self.ref = ldict.get('REF')
            self.start_name = ldict.get('START_NAME')
            self.end_name = ldict.get('END_NAME')
            self.old_name = ldict.get('OLD_NAME')
            self.color = ldict.get('COLOR')
            # Enums
            if ldict.get('CONTEXT') is not None:
                self.context = ODBLayerMatrixContext[ldict.get('CONTEXT')]
            if ldict.get('TYPE') is not None:
                self.layertype = ODBLayerMatrixType[ldict.get('TYPE')]
            if ldict.get('POLARITY') is not None:
                self.polarity = ODBLayerMatrixPolarity[ldict.get('POLARITY')]
            if ldict.get('FORM') is not None:
                self.form = ODBLayerMatrixForm[ldict.get('FORM')]
            if ldict.get('DIELECTRIC_TYPE') is not None:
                self.dielectric_type = ODBLayerMatrixDielectricType[ldict.get('DIELECTRIC_TYPE')]
            # Find subtype
            if ldict.get('ADD_TYPE') is not None:
                if enum_contains(ODBLayerMatrixLayerRoutSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerRoutSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerDrillSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerDrillSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerConductivePasteSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerConductivePasteSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerDocumentSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerDocumentSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerMaskSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerMaskSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerMixedSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerMixedSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerPowerGroundSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerPowerGroundSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerSignalSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerSignalSubtype[ldict.get('ADD_TYPE')]
                elif enum_contains(ODBLayerMatrixLayerSolderMaskSubtype,ldict.get('ADD_TYPE')):
                    self.add_type = ODBLayerMatrixLayerSolderMaskSubtype[ldict.get('ADD_TYPE')]
    
    def __init__(self,matfile: Path):
        mat_arrs,mat_vars = read_structured_text(matfile)
        
        step_arrs = [marr for marr in mat_arrs if marr.name == 'STEP']
        layer_arrs = [larr for larr in mat_arrs if larr.name == 'LAYER']

        self.matrix_steps = []
        self.matrix_layers = []
        for sarr in step_arrs:
            step = ODBMatrix.ODBStepInfo()
            step.load(sarr)
            self.matrix_steps.append(step)
        for larr in layer_arrs:
            layer = ODBMatrix.ODBLayerInfo()
            layer.load(larr)
            self.matrix_layers.append(layer)

""" FEATURES
All arguments are integers or floats

Round 
r<d>
d - circle diameter

Square 
s<s>
s - square side

Rectangle 
rect<w>x<h>
w - rectangle width
h - rectangle height

Rounded Rectangle 
rect<w>x<h>xr<rad>x<corners>
w - rectangle width
h - rectangle height
rad - corner radius
corners - a combination of which corners are rounded.
x<corners> is omitted if all corners are rounded.

Chamfered Rectangle 
rect<w>x<h>xc<rad>x<corners>
w - rectangle width
h - rectangle height
rad - corner radius
corners - a combination of which corners are rounded.
x<corners> is omitted if all corners are rounded.

Oval 
oval<w>x<h>
w - oval width
h - oval height

Diamond 
di<w>x<h>
w - diamond width
h - diamond height

Octagon 
oct<w>x<h>x<r>
w - octagon width
h - octagon height
r - corner size

Round Donut 
donut_r<od>x<id>
od - outer diameter
id - inner diameter

Square Donut 
donut_s<od>x<id>
od - outer diameter
id - inner diameter

Square/Round Donut 
donut_sr<od>x<id>
od - outer diameter
id - inner diameter

Rounded Square Donut 
donut_s<od>x<id>x<rad>x<corners>
od - outer diameter
id - inner diameter
rad - corner radius
corners - a combination of which corners are rounded.
x<corners> is omitted if all corners are rounded.

Rectangle Donut 
donut_rc<ow>x<oh>x<lw>
ow - outer width
oh - outer height
lw - line width

Rounded Rectangle Donut 
donut_rc<ow>x<oh>x<lw>x<rad>x
<corners>
ow - outer width
oh - outer height
lw - line width
rad - corner radius
corners - a combination of which corners are rounded.
x<corners> is omitted if all corners are rounded.

Oval Donut 
donut_o<ow>x<oh>x<lw>
ow - outer width
oh - outer height
lw - line width

Horizontal Hexagon 
hex_l<w>x<h>x<r>
w - hexagon width
h - hexagon height
r - corner size

Vertical Hexagon 
hex_s<w>x<h>x<r>
w - hexagon width
h - hexagon height
r - corner size

Butterfly 
bfr<d>
d - diameter

Square Butterfly 
bfs<s>
s - size

Triangle tri<base>x<h>
base - triangle base
h - triangle height

Half Oval oval_h<w>x<h>
w - width
h - height

Ellipse 
el<w>x<h>
w - width
h - height

Moire 
moire<rw>x<rg>x<nr>x<lw>x<ll>x<la>
rw - ring width
rg - ring gap
nr - number of rings
lw - line width
ll - line length
la - line angle

Hole 
hole<d>x<p>x<tp>x<tm>
d - hole diameter
p - plating status (p(lated), n(on-plated) or v(ia))
tp - + tolerance
tm - - tolerance
This symbol is specifically intended for wheels created by the Wheel Template Editor for drill files.

Null 
null<ext>
ext - extension number
This symbol is empty and used as a place holder for non-graphic
features

Round Thermal (Rounded) 
thr<od>x<id>x<angle>x<num_spokes>x<gap>
od - outer diameter
id - inner diameter
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap

Round Thermal (Squared) 
ths<od>x<id>x<angle>x<num_spokes>x<gap>
od - outer diameter
id - inner diameter
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap

Square Thermal 
s_ths<os>x<is>x<angle>x<num_spokes>x<gap>
os - outer size
is - inner size
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap

Square Thermal (Open Corners)
s_tho<od>x<id>x<angle>x<num_spokes>x<gap>
od - outer diameter
id - inner diameter
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap

Square-Round Thermal 
sr_ths<os>x<id>x<angle>x<num_spokes>x<gap>
os - outer size
id - inner diameter
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap

Rectangular Thermal 
rc_ths<w>x<h>x<angle>x<num_spokes>x<gap>x<air_gap>
w - outer width
h - outer height
angle - gap angle from 0deg (angle is limited to multiples of 45 degrees)
num_spokes - number of spokes
gap - size of spoke gap
air_gap - size of laminate

Rectangular Thermal (Open Corners)
rc_tho<w>x<h>x<angle>x<num_spokes>x<gap>x<air_gap>
w - outer width
h - outer height
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap
air gap - size of laminate

Rounded Square Thermal 
s_ths<os>x<is>x<angle>x<num_spokes>x<gap>xr<rad>x<corners>
os - outer size
is - inner size
angle - gap angle angle from 00
num_spokes - number of spokes
gap - size of spoke gap
rad - corner radius
corners - a combination of which corners are rounded. x<corners> is omitted if all corners are rounded.

Rounded Square Thermal (Open Corners)
s_ths<os>x<is>x<angle>x<num_spokes>x<gap>xr<rad>x<corners>
os - outer size
is - inner size
angle - gap angle from 450
num_spokes - number of spokes
gap - size of spoke gap
rad - corner radius
corners - a combination of which corners are rounded. x<corners> is omitted if all corners are rounded.

Rounded Rectangle Thermal
rc_ths<ow>x<oh>x<angle>x<num_spokes>x<gap>x<lw>xr<rad>x<corners>
ow - outer width
oh - outer height
lw - line width
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap
rad - corner radius
corners - a combination of which corners are rounded. x<corners> is omitted if all corners are rounded.

Rounded Rectangle Thermal (Open Corners)
rc_ths<ow>x<oh>x<angle>x<num_spokes>x<gap>x<lw>xr<rad>x<corners>
ow - outer width
oh - outer height
lw - line width
angle - gap angle of 450
num_spokes - number of spokes
gap - size of spoke gap
rad - corner radius
corners - a combination of which corners are rounded. x<corners> is omitted if all corners are rounded.

Oval Thermal 
o_ths<ow>x<oh>x<angle>x<num_spokes>x<gap>x<lw>
ow - outer width
oh - outer height
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap
lw - line width

Oval Thermal (Open Corners)
o_ths<ow>x<oh>x<angle>x<num_spokes>x<gap>x<lw>
ow - outer width
oh - outer height
angle - gap angle from 00
num_spokes - number of spokes
gap - size of spoke gap
lw - line width
"""

class ODBSymbol:
    """Base class for all shapes."""
    pass


# GLOBAL CONFIG
@dataclass
class ODBConfig:
    root_path: Path
    default_unit: ODBUnit
    version: float
    matrix: ODBMatrix
    nsteps: int
    nlayers: int
    board_thickness: float = 0.0
    user_symbols: dict[str,ODBSymbol]|None = None  # Name to symbol object


# ----------------------------
# Basic Shapes
# ----------------------------

@dataclass
class ODBRoundSymbol(ODBSymbol):
    """
    Round (circle) symbol. Can be used for pads or for line and curve features. For pads, 
    a getpatch() method is provided which can be plotted with matplotlib.
    """
    unit: ODBUnit
    diameter: float

    pattern = re.compile(r"^r(?P<d>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit, float(m.group("d")))
    def getpatch(self, pos: Coordinate2, odbconf: ODBConfig, color='k') -> mpl.patches.CirclePolygon:
        scale = get_unit_conversion(self.unit,odbconf.default_unit)
        # patch = mpl.patches.Circle(xy,radius=scale*self.diameter/2.,fill=True,fc=color)  # spline circle
        patch = mpl.patches.CirclePolygon((pos.x,pos.y),radius=scale*self.diameter/2.,resolution=10,fill=True,fc=color)
        return patch


@dataclass
class ODBSquareSymbol(ODBSymbol):
    unit: ODBUnit
    side: float

    pattern = re.compile(r"^s(?P<s>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("s")))
    def getpatch(self, pos: Coordinate2, odbconf: ODBConfig, color='k') -> mpl.patches.Rectangle:
        scale = get_unit_conversion(self.unit,odbconf.default_unit)
        xy = (pos.x-scale*self.side/2, pos.y-scale*self.side/2)
        patch = mpl.patches.Rectangle(xy,width=scale*self.side,height=scale*self.side,fill=True,fc=color)
        return patch

@dataclass
class ODBRectangleSymbol(ODBSymbol):
    unit: ODBUnit
    width: float
    height: float

    pattern = re.compile(r"^rect(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("w")), float(m.group("h")))

    def getpatch(self, pos: Coordinate2, odbconf: ODBConfig, color='k') -> mpl.patches.Rectangle:
        scale = get_unit_conversion(self.unit,odbconf.default_unit)
        xy = (pos.x-scale*self.width/2, pos.y-scale*self.height/2)
        patch = mpl.patches.Rectangle(xy,width=scale*self.width,height=scale*self.height,fill=True,fc=color)
        return patch

# ----------------------------
# Rounded / Chamfered Rectangles
# ----------------------------

@dataclass
class ODBRoundedRectangleSymbol(ODBSymbol):
    unit: ODBUnit
    width: float
    height: float
    radius: float
    corners: Optional[str]  # ignored for now

    pattern = re.compile(
        r"^rect(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)xr(?P<rad>\d+(?:\.\d+)?)(?:x(?P<corners>\w+(?:\.\d+)?))?$"
    )

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                unit,
                float(m.group("w")),
                float(m.group("h")),
                float(m.group("rad")),
                m.group("corners"),
            )
    def getpatch(self, pos: Coordinate2, odbconf: ODBConfig, color='k') -> mpl.patches.FancyBboxPatch:
        scale = get_unit_conversion(self.unit,odbconf.default_unit)
        xy = (pos.x-scale*self.width/2, pos.y-scale*self.height/2)
        patch = mpl.patches.FancyBboxPatch(xy,width=scale*self.width,height=scale*self.height,
                                           boxstyle=f'Round, pad=0, rounding_size={scale*self.radius}',
                                           fill=True,fc=color)
        return patch

@dataclass
class ODBChamferedRectangleSymbol(ODBSymbol):
    unit: ODBUnit
    width: float
    height: float
    radius: float
    corners: Optional[str]

    pattern = re.compile(
        r"^rect(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)xc(?P<rad>\d+(?:\.\d+)?)(?:x(?P<corners>\w+(?:\.\d+)?))?$"
    )

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                unit,
                float(m.group("w")),
                float(m.group("h")),
                float(m.group("rad")),
                m.group("corners"),
            )
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()


# ----------------------------
# Other Geometry
# ----------------------------

@dataclass
class ODBOvalSymbol(ODBSymbol):
    """
    An oval is a rounded rectangle where the radius is equal to the shorter dimension. 
    This creates a pill shape.
    """
    unit: ODBUnit
    width: float
    height: float

    pattern = re.compile(r"^oval(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("w")), float(m.group("h")))
        
    def getpatch(self, pos: Coordinate2, odbconf: ODBConfig, color='k') -> mpl.patches.FancyBboxPatch:
        scale = get_unit_conversion(self.unit,odbconf.default_unit)
        xy = (pos.x-scale*self.width/2, pos.y-scale*self.height/2)
        
        if self.width > self.height:
            patch = mpl.patches.FancyBboxPatch(xy,width=scale*self.width,height=scale*self.height,
                                           boxstyle=f'Round, pad=0, rounding_size={scale*self.height/2}',
                                           fill=True,fc=color)
        else:
            patch = mpl.patches.FancyBboxPatch(xy,width=scale*self.width,height=scale*self.height,
                                           boxstyle=f'Round, pad=0, rounding_size={scale*self.width/2}',
                                           fill=True,fc=color)
        return patch

@dataclass
class ODBDiamondSymbol(ODBSymbol):
    unit: ODBUnit
    width: float
    height: float

    pattern = re.compile(r"^di(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("w")), float(m.group("h")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
    

@dataclass
class ODBOctagonSymbol(ODBSymbol):
    unit: ODBUnit
    width: float
    height: float
    corner: float

    pattern = re.compile(r"^oct(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)x(?P<r>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                unit,
                float(m.group("w")),
                float(m.group("h")),
                float(m.group("r"))
            )
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBTriangleSymbol(ODBSymbol):
    unit: ODBUnit
    base: float
    height: float

    pattern = re.compile(r"^tri(?P<b>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("b")), float(m.group("h")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBEllipseSymbol(ODBSymbol):
    unit: ODBUnit
    width: float
    height: float

    pattern = re.compile(r"^el(?P<w>\d+(?:\.\d+)?)x(?P<h>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("w")), float(m.group("h")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
    
# ----------------------------
# Donuts
# ----------------------------

@dataclass
class ODBRoundDonutSymbol(ODBSymbol):
    unit: ODBUnit
    outer_diameter: float
    inner_diameter: float

    pattern = re.compile(r"^donut_r(?P<od>\d+(?:\.\d+)?)x(?P<id>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("od")), float(m.group("id")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()


@dataclass
class ODBSquareDonutSymbol(ODBSymbol):
    unit: ODBUnit
    outer: float
    inner: float

    pattern = re.compile(r"^donut_s(?P<od>\d+(?:\.\d+)?)x(?P<id>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("od")), float(m.group("id")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()


@dataclass
class ODBSquareRoundDonutSymbol(ODBSymbol):
    unit: ODBUnit
    outer: float
    inner: float

    pattern = re.compile(r"^donut_sr(?P<od>\d+(?:\.\d+)?)x(?P<id>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("od")), float(m.group("id")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()


# ----------------------------
# Special Shapes
# ----------------------------

@dataclass
class ODBHoleSymbol(ODBSymbol):
    unit: ODBUnit
    diameter: float
    plating: str
    tol_plus: float
    tol_minus: float

    pattern = re.compile(r"^hole(?P<d>\d+(?:\.\d+)?)x(?P<p>[pnv])x(?P<tp>\d+(?:\.\d+)?)x(?P<tm>\d+(?:\.\d+)?)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                unit,
                float(m.group("d")),
                m.group("p"),
                float(m.group("tp")),
                float(m.group("tm"))
            )
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()


@dataclass
class ODBNullSymbol(ODBSymbol):
    unit: ODBUnit
    ext: float
    pattern = re.compile(r"^null(?P<e>\d+)$")

    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        m = symcls.pattern.match(text)
        if m:
            return symcls(unit,float(m.group("e")))
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        return None

# -----------------
# Thermals - Not Implemented Yet
# -----------------

@dataclass
class ODBRoundThermalRoundedSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBRoundThermalSquaredSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
        
@dataclass
class ODBSquareThermalSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBSquareThermalOpenCornersSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
        
@dataclass
class ODBSquareRoundThermalSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
        
@dataclass
class ODBRectangularThermalSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
        
@dataclass
class ODBRectangularThermalOpenCornersSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBRoundedSquareThermalSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()
        
@dataclass
class ODBRoundedSquareThermalOpenCornersSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBRoundedRectangleThermalSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBRoundedRectangleThermalOpenCornersSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBOvalThermalSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

@dataclass
class ODBOvalThermalOpenCornersSymbol(ODBSymbol):
    unit: ODBUnit 
    @classmethod
    def parse(symcls, text, unit: ODBUnit):
        raise NotImplementedError()
    def getpatch(self,pos: Coordinate2,odbconf: ODBConfig, color='k'):
        raise NotImplementedError()

# ----------------------------
# Parser / Factory
# ----------------------------

ODBSYMBOL_CLASSES = [                               # IMPLEMENTED
    ODBRoundSymbol,                                 # X
    ODBSquareSymbol,                                # X
    ODBRectangleSymbol,                             # X
    ODBRoundedRectangleSymbol,                      # X
    ODBChamferedRectangleSymbol,                    # -
    ODBOvalSymbol,                                  # X
    ODBDiamondSymbol,                               # -
    ODBOctagonSymbol,                               # -
    ODBRoundDonutSymbol,                            # -
    ODBSquareDonutSymbol,                           # -
    ODBSquareRoundDonutSymbol,                      # -
    ODBTriangleSymbol,                              # -
    ODBEllipseSymbol,                               # -
    ODBHoleSymbol,                                  # -
    ODBNullSymbol,                                  # X
    ODBRoundThermalRoundedSymbol,                   # -
    ODBRoundThermalSquaredSymbol,                   # -
    ODBSquareThermalSymbol,                         # -
    ODBSquareThermalOpenCornersSymbol,              # -
    ODBSquareRoundThermalSymbol,                    # -
    ODBRectangularThermalSymbol,                    # -
    ODBRectangularThermalOpenCornersSymbol,         # -
    ODBRoundedSquareThermalSymbol,                  # -
    ODBRoundedSquareThermalOpenCornersSymbol,       # -
    ODBRoundedRectangleThermalSymbol,               # -
    ODBRoundedRectangleThermalOpenCornersSymbol,    # -
    ODBOvalThermalSymbol,                           # -
    ODBOvalThermalOpenCornersSymbol,                # -
]


def parse_odb_symbol(text: str, unit: ODBUnit) -> ODBSymbol:
    text = text.strip()

    for symcls in ODBSYMBOL_CLASSES:
        try:
            symbol = symcls.parse(text,unit)
        except NotImplementedError:
            # print(f"Warning: Symbol {symcls} not implemented.")
            pass
        if symbol:
            return symbol

    raise ValueError(f"Unknown or unimplemented ODB++ symbol format: {text}")


# PARSING FEATURES
# Features can lines, pads, arcs, text, barcodes, or surfaces (polygons). 
# They can be used in multiple contexts, e.g. a line could represent the path of a 
# net or it could be an edge of the frame of a fab drawing. Things like nets and 
# ground pours need to be defined at a higher level of abstraction.

@dataclass
class ODBSymbolTableEntry:
    serial_num: int
    symbol_name: str 
    unit: ODBUnit 
@dataclass
class ODBAttributeNameEntry:
    serial_num: int
    attribute_name: str
    is_system: bool = False
@dataclass
class ODBAttributeStringsEntry:
    serial_num: int
    text: str 

class ODBFeatureType(Enum):
    L=auto()   # Line
    P=auto()   # Pad
    A=auto()   # Arc
    T=auto()   # Text
    B=auto()   # Barcode
    S=auto()   # Surface

class ODBFeatureBase:
    pass
class ODBFeatureLine(ODBFeatureBase):
    def __init__(self,txt,unit: ODBUnit):
        """
        txt: list[str] split by space
        
        <xs> <ys> <xe> <ye> <sym_num> <polarity> <dcode>
        xs, ys      start point
        xe, ye      end point
        sym_num     A serial number of the symbol in the feature symbol names section
        polarity    P for positive, N for negative
        dcode       gerber dcode number (0 if not defined)
        """
        if len(txt) < 8:  # L + 7 args
            raise ValueError("Line feature does not have enough arguments.")
        self.unit = unit
        xs = float(txt[1])
        ys = float(txt[2])
        self.pt_s = Coordinate2(xs,ys)
        xe = float(txt[3])
        ye = float(txt[4])
        self.pt_e = Coordinate2(xe,ye)
        self.sym_num = int(txt[5])
        self.pol = txt[6]
        self.dcode = int(txt[7])
        self.attrtxt = ''
        if len(txt) > 8:
            self.attrtxt = ' '.join(txt[8:])  # TODO Parse attrtext
        self.netname = ''     # These can be defined later; netname depends on netlist
        self.tracewidth = 0   # tracewidth depends on symbol lookup
    
    def draw(self,ax,sym_dict,odbconf: ODBConfig,*args, **kwargs):
        xs = self.pt_s.x 
        ys = self.pt_s.y 
        xe = self.pt_e.x 
        ye = self.pt_e.y 
        ax.plot([xs,xe],[ys,ye],*args, **kwargs)
    
    def find_netname(self,netpoints):
        for netp in netpoints:
            if self.pt_s == netp.loc or self.pt_e == netp.loc:
                self.netname = netp.netname
    
    def getpatches(self,sym_dict,odbconf: ODBConfig, pos_offset: Coordinate2 = Coordinate2(0,0), **patchkwargs) -> list[mpl.patches.Patch]:
        MOVETO = mpl.path.Path.MOVETO
        LINETO = mpl.path.Path.LINETO
        vtxs = [(self.pt_s.x,self.pt_s.y), (self.pt_e.x,self.pt_e.y)]
        codes = [MOVETO,LINETO]
        linepath = mpl.path.Path(vtxs,codes)
        patch = mpl.patches.PathPatch(linepath,**patchkwargs)
        return [patch]
        
    
    def __repr__(self):
        return f'ODBFeatureLine(pt_s={self.pt_s},pt_e={self.pt_e},sym_num={self.sym_num},pol={self.pol},dcode={self.dcode},attrtxt={self.attrtxt},netname={self.netname},tracewidth={self.tracewidth})'
        
class ODBFeatureArc(ODBFeatureBase):
    def __init__(self,txt,unit: ODBUnit):
        """
        txt: list[str] split by space
        
        <xs> <ys> <xe> <ye> <xc> <yc> <sym_num> <polarity> <dcode> <cw>
        
        xs, ys start point
        ye, ye end point
        yc, yc center point
        sym_num A serial number of the symbol in the feature symbol names section
        polarity P for positive, N for negative
        dcode gerber dcode number (0 if not defined)
        cw Y for clockwise, N for counter clockwise
        """
        self.unit = unit
        if len(txt) < 11:  # A + 10 args
            raise ValueError(f"Arc feature does not have enough arguments: {txt}")
        xs = float(txt[1])
        ys = float(txt[2])
        self.pt_s = Coordinate2(xs,ys)
        xe = float(txt[3])
        ye = float(txt[4])
        self.pt_e = Coordinate2(xe,ye)
        xc = float(txt[5])
        yc = float(txt[6])
        self.pt_c = Coordinate2(xc,yc)
        self.sym_num = int(txt[7])
        self.pol = txt[8]
        self.dcode = int(txt[9])
        self.cw = True 
        if txt[10] == 'N':
            self.cw = False
        self.attrtxt = ''
        if len(txt) > 11:
            self.attrtxt = ' '.join(txt[11:])
    
    def getpatches(self,sym_dict,odbconf: ODBConfig,pos_offset: Coordinate2 = Coordinate2(0,0),**patchkwargs) -> list[mpl.patches.Patch]:
        rad = (self.pt_s-self.pt_c).magnitude()  # should be very close to (pt_e - pt_c).magnitude()
        angle_start_deg = (self.pt_s-self.pt_c).angle(degrees=True)
        angle_end_deg = (self.pt_e-self.pt_c).angle(degrees=True)
        
        if self.cw:
            arc = mpl.patches.Arc((self.pt_c.x,self.pt_c.y), width=2*rad, height=2*rad, 
                                  angle=0, theta1=angle_end_deg, theta2=angle_start_deg,color='k',lw=1.5)
        else:
            arc = mpl.patches.Arc((self.pt_c.x,self.pt_c.y), width=2*rad, height=2*rad, 
                                  angle=0, theta1=angle_start_deg, theta2=angle_end_deg,color='k',lw=1.5)
        arc.set(**patchkwargs)
        return [arc]
    
    def draw(self,ax,sym_dict,odbconf: ODBConfig,**patchkwargs):
        arc = self.getpatches(sym_dict,odbconf,**patchkwargs)[0]
        ax.add_patch(arc)
    
    def find_netname(self,netpoints):
        for netp in netpoints:
            if self.pt_s == netp.loc or self.pt_e == netp.loc:
                self.netname = netp.netname
    
    def __repr__(self):
        return f'ODBFeatureArc(pt_s={self.pt_s},pt_e={self.pt_e},pt_c={self.pt_c},sym_num={self.sym_num},pol={self.pol},dcode={self.dcode},cw={self.cw},attrtxt={self.attrtxt})'




class ODBFeatureSurface(ODBFeatureBase):
    """
    A surface is different from other features; it consists of multiple records:
    S <params> ; <atr>=<value>...
    <polygon 1>
    <polygon n>
    SE
    The <params> section contains: <polarity> <dcode>
    polarity - P for positive, N for negative
    dcode - gerber dcode number (0 if not defined)
    The first line is followed by a list of polygons. Each polygon is a collection of
    segments (lines without width) and curves (arcs without a width). Polygons must
    meet the following restrictions:
    • Intersection is not allowed between edges of the same polygon.
    • Intersection is not allowed between edges of different polygons.
    • The polygons must form a closed shape (e.g, a polygon that contains only 2
    segments is not valid).
    • Holes must be graphically contained inside island polygons. The direction of
    island must be clockwise and of holes must be counter clockwise.
    • The curves must be consistent (the start, end, and center point must construct a
    legal curve).
    If any of the above mentioned violations occurs, the system will not be able to read
    the file, and will return an error.
    """
    
    @dataclass
    class ODBSurfacePolyCurve:
        #p1 : Coordinate2   is actually the previous point
        p2: Coordinate2
        center: Coordinate2
        cw: bool
        def getpatch(self,prev_pt:Coordinate2):
            p1 = prev_pt
            rad = (p1-self.center).magnitude()
            angle_start_deg = (p1-self.center).angle(True)%360
            angle_end_deg = (self.p2-self.center).angle(True)%360

            if self.cw:
                arc = mpl.patches.Arc((self.center.x,self.center.y), width=2*rad, height=2*rad, 
                                      angle=0, theta1=angle_end_deg, theta2=angle_start_deg,color='k',lw=1.5)
            else:
                arc = mpl.patches.Arc((self.center.x,self.center.y), width=2*rad, height=2*rad, 
                                      angle=0, theta1=angle_start_deg, theta2=angle_end_deg,color='k',lw=1.5)
            return arc 
        
    class ODBPolygonType(Enum):
        ISLAND=auto()
        HOLE=auto()
    class ODBSurfacePolygon:
        def __init__(self,txt_lines,unit: ODBUnit):
            """
            NOTE: txt_lines MUST contain ALL lines for the surface (from OB to OE)
            All lines should be split by spaces ' '
            
            Points are stored as complex numbers
            """
            self.unit = unit
            if txt_lines[0][0] != 'OB' or txt_lines[-1][0] != 'OE':
                raise ValueError(f"Could not find start and end of polygon: {txt_lines}")
            xbs = float(txt_lines[0][1])
            ybs = float(txt_lines[0][2])
            self.bs = Coordinate2(xbs,ybs)
            ptype = txt_lines[0][3]
            if ptype == 'I':    
                self.poly_type = ODBFeatureSurface.ODBPolygonType.ISLAND
            elif ptype == 'H':    
                self.poly_type = ODBFeatureSurface.ODBPolygonType.HOLE
            else:
                raise ValueError(f"Unknown polygon type {ptype}")
            
            self.segments = []  # segments and curves
            
            for line in txt_lines[1:]:
                if line[0] == 'OE':
                    """
                    Polygon begin
                    OB <xbs> <ybs> <poly_type>
                    xbs,ybs         polygon start point
                    poly_type       I for island, H for hole
                    """
                    break
                elif line[0] == 'OS':
                    """
                    Polygon segment
                    OS <x> <y>
                    x, y            segment end point
                    (previous polygon point is the start point)
                    """
                    self.segments.append(Coordinate2(float(line[1]),float(line[2])))
                elif line[0] == 'OC':
                    """
                    Polygon curve
                    OC <xe> <ye> <xc> <yc> <cw>
                    xe, ye          curve end point (previous polygon point is the start point)
                    xc, yc          curve center point
                    cw              Y for clockwise, N for counter clockwise
                    """
                    p1 = Coordinate2(float(line[1]),float(line[2]))
                    p2 = Coordinate2(float(line[3]),float(line[4]))
                    cw = False
                    if line[5] == 'Y':
                        cw = True
                    
                    self.segments.append(ODBFeatureSurface.ODBSurfacePolyCurve(
                        p1,p2,cw
                        ))
        def getpatch(self, odbconf: ODBConfig, pos_offset: Coordinate2 = Coordinate2(0,0), **patchkwargs) -> mpl.patches.PathPatch:
            # Need to construct an mpl.path.Path()
            # This requires converting curves to quadratic or cubic Bezier curves
            # Curves are given by center, start, and end. 
            MOVETO = mpl.path.Path.MOVETO
            LINETO = mpl.path.Path.LINETO
            CURVE4 = mpl.path.Path.CURVE4
            
            x0 = pos_offset
            
            # Initialize at start
            vtxs = [(self.bs.x+x0.x,self.bs.y+x0.y)]
            codes = [MOVETO]
            
            for seg in self.segments:
                if isinstance(seg,ODBFeatureSurface.ODBSurfacePolyCurve):
                    # vtxs are in translated coordinates, segment is in original coordinates
                    p1 = Coordinate2(vtxs[-1][0],vtxs[-1][1])
                    p2 = seg.p2 + x0
                    segcenter = seg.center + x0
                    rad = (p1-segcenter).magnitude()
                    angle_start_deg = (p1-segcenter).angle(True)%360
                    angle_end_deg = (p2-segcenter).angle(True)%360
                    
                    # Check if we need to break the arc up into smaller (<= 90 degrees) segments
                    if seg.cw:
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
                        timeout = 10
                        if seg.cw:
                            # Angles decrease to angle_start_deg-angle_span
                            while next_angle > (angle_start_deg - angle_span) and timeout > 0:
                                start_angles.append(next_angle)
                                next_angle = start_angles[-1] - 90
                                end_angles.append(next_angle)
                                timeout -= 1
                            end_angles[-1] = angle_start_deg - angle_span
                        else:
                            # Angles increase to angle_start_deg+angle_span
                            while next_angle < (angle_start_deg + angle_span) and timeout > 0:
                                start_angles.append(next_angle)
                                next_angle = start_angles[-1] + 90
                                end_angles.append(next_angle)
                                timeout -= 1
                            end_angles[-1] = angle_start_deg + angle_span
                        
                        # Now generate arcs from start_angle to end_angle for each
                        for i in range(len(start_angles)):
                            arc_vtxs,arc_codes = circular_arc_to_path(segcenter, rad, start_angles[i], end_angles[i],seg.cw)
                            vtxs += arc_vtxs
                            codes += arc_codes
                            
                        
                    else:                    
                        arc_vtxs,arc_codes = circular_arc_to_path(segcenter, rad, angle_start_deg, angle_end_deg,seg.cw)
                        vtxs += arc_vtxs
                        codes += arc_codes
                else:  # line
                    vtxs.append((seg.x + x0.x,seg.y + x0.y))
                    codes.append(LINETO)
            mplpath = mpl.path.Path(vtxs,codes)
            patch = mpl.patches.PathPatch(mplpath,**patchkwargs)
            return patch
        
        def __repr__(self):
            return f'ODBSurfacePolygon(bs={self.bs},segments={self.segments})'
    
    def __init__(self,txt_lines,unit: ODBUnit):
        """
        NOTE: txt_lines MUST contain ALL lines for the surface (from S to SE)
        All lines should be split by spaces ' '
        """
        self.unit = unit
        if txt_lines[0][0] != 'S' or txt_lines[-1][0] != 'SE':
            raise ValueError(f"Could not find start and end of surface: {txt_lines}")
        # The first line is the surface descriptor itself
        self.pol = txt_lines[0][1]
        self.dcode = txt_lines[0][2]
        self.attrtxt = ''
        if len(txt_lines[0]) > 2:
            self.attrtxt = ' '.join(txt_lines[0][3:])
        self.polygons = []
        poly_beg_idxs = []
        poly_end_idxs = []
        for i,line in enumerate(txt_lines[1:]):
            if line[0] == 'SE':
                """Surface end"""
                break
            elif line[0] == 'OB':
                """Polygon begin"""
                poly_beg_idxs.append(i+1)
            elif line[0] == 'OE':
                """Polygon end"""
                poly_end_idxs.append(i+1)
        poly_idxs = list(zip(poly_beg_idxs,poly_end_idxs))
        for pidxs in poly_idxs:
            self.polygons.append(ODBFeatureSurface.ODBSurfacePolygon(txt_lines[pidxs[0]:pidxs[1]+1],self.unit))
    def draw(self,ax,sym_dict,odbconf: ODBConfig, **patchkwargs):
        for poly in self.polygons:
            ax.add_patch(poly.getpatch(odbconf, **patchkwargs))  # NOTE: ignoring polarity for now, TODO
    def getpatches(self,sym_dict,odbconf: ODBConfig,pos_offset: Coordinate2 = Coordinate2(0,0),**patchkwargs) -> list[mpl.patches.Patch]:
        patches = []
        for poly in self.polygons:
            patches.append(poly.getpatch(odbconf,pos_offset,**patchkwargs))  # NOTE: ignoring polarity for now, TODO
        return patches
            
    def __repr__(self):
        return f'ODBFeatureSurface(polygons={self.polygons},pol={self.pol},dcode={self.dcode},attrtxt={self.attrtxt})'

class ODBFeaturePad(ODBFeatureBase):
    """
    <x> <y> -1 <sym_num> <resize_factor> <polarity> <dcode> <orient_def>      opt 1
    <x> <y> <sym_num> <polarity> <dcode> <orient_def>                         opt 2
    
    x, y        center point
    <apt_def>   This value can be expressed in one of two ways.
                If the symbol is resized apt_def begins with -1 (negative one) and contains
                three numbers. Otherwise, it consists of a single number as in V.6.x -- 
                a serial number of the symbol in the feature symbol names section.
                The resize factor is expressed in thousandths of the units being used (mils or microns).
                
    polarity    P for positive, N for negative
    dcode       gerber dcode number (0 if not defined)
    orient_def  pad orientation. This value is expressed as:
    0|1|2|3|4|5|6|7|8<rotation>|9<rotation>
    0 : 0 degrees, no mirror
    1 : 90 degrees, no mirror
    2 : 180 degrees, no mirror
    3 : 270 degrees, no mirror
    4 : 0 degrees, mirror in X axis
    5 : 90 degrees, mirror in X axis
    6 : 180 degrees, mirror in X axis
    7 : 270 degrees, mirror in X axis
    8 : any angle rotation, no mirror
    9 : any angle rotation, mirror in X axis
                If the first number of orientation definition is an integer from 0
                through 7, it is legacy date from before ODB++ V.7.0 and will be
                handled as in V.6.x. If the first number is 8 or 9, it is a two number
                definition, with the following number representing rotation.
                Note: To maintain backward compatibility, values 0-7 are read
                from legacy data, but saved in the new format.
    """
    def __init__(self,txt,unit: ODBUnit):
        """
        txt: list[str] of string split by space ' '
        """
        if len(txt) < 7:
            raise ValueError(f"Found incorrect number of arguments for pad. Text: {txt}")
        self.unit = unit
        px = float(txt[1])
        py = float(txt[2])
        self.p1 = Coordinate2(px,py)
        if txt[3] == '-1':
            # scaled symbol
            self.sym_num = int(txt[4])
            self.resize_factor = float(txt[5])
            self.polarity = txt[6]
            self.dcode = txt[7]
            self.orient_def = txt[8]
            self.attrtxt = ''
            if len(txt) > 9:
                self.attrtxt = ' '.join(txt[9:])
        else:
            self.sym_num = int(txt[3])
            self.resize_factor = 1.0
            self.polarity = txt[4]
            self.dcode = txt[5]
            self.orient_def = txt[6]
            self.attrtxt = ''
            if len(txt) > 7:
                self.attrtxt = ' '.join(txt[7:])
    
    def getpatches(self,sym_dict,odbconf: ODBConfig,pos_offset: Coordinate2 = Coordinate2(0,0),**patchkwargs) -> list[mpl.patches.Patch]:
        if self.sym_num in sym_dict.keys():
            # For now, only process existing symbols (no user symbols)
            # sym_dict maps serial number to ODBxyzSymbol object
            # if isinstance(sym_dict[self.sym_num],ODBRoundSymbol):
            # TODO include orient_def for pad angle
            sym = sym_dict[self.sym_num]
            if isinstance(sym,ODBUserSymbol):
                patches = sym.getpatches(self.p1,**patchkwargs)  # ODBUserSymbol handles its own position offset
                return patches
            else:
                patch = sym.getpatch(self.p1+pos_offset,odbconf)
                patch.set(**patchkwargs)
                return [patch]          # make into list
    
    def draw(self,ax,sym_dict,odbconf: ODBConfig,**patchkwargs):        
        patches = self.getpatches(sym_dict,odbconf,**patchkwargs)
        if patches is not None:
            for patch in patches:
                ax.add_patch(patch)
        else:
            # print(f"WARNING: Empty patches for symbol {sym_dict[self.sym_num]}")
            pass

    def __repr__(self):
        return f'ODBFeaturePad(p1={self.p1},sym_num={self.sym_num},resize_factor={self.resize_factor},dcode={self.dcode},orient_def={self.orient_def},attrtxt={self.attrtxt})'

    

class ODBFeatureText(ODBFeatureBase):
    """
    <x> <y> <font> <polarity> <orient_def> <xsize> <ysize> <widthfactor> <text> <version>
    
    x, y text location (bottom left of first character for 0 orientation)
    font font name (Currently must be 'standard')
    polarity P for positive, N for negative
    orient_def text orientation. This value is expressed as:
    0|1|2|3|4|5|6|7|8 <rotation>|9<rotation>
    0 : 0 degrees, no mirror
    1 : 90 degrees, no mirror
    2 : 180 degrees, no mirror
    3 : 270 degrees, no mirror
    4 : 0 degrees, mirror in X axis
    5 : 90 degrees, mirror in X axis
    6 : 180 degrees, mirror in X axis
    7 : 270 degrees, mirror in X axis
    8 : any angle rotation, no mirror
    9 : any angle rotation, mirror in X axis
    If the first number of orientation definition is an integer from 0
    through 7, it is legacy date from before ODB++ V.7.0 and will
    be handled as in V.6.x. If the first number is 8 or 9, it is a two
    number definition, with the following number representing
    rotation.
    Note: To maintain backward compatibility, values 0-7 are
    read from legacy data, but saved in the new format.
    xsize,ysize Character size
    width factor width of character segment (in units of 12 mils) i.e. 1 = 12
    mils, 0.5 = 6 mils
    text text string.
    version text field version values:
    0 previous version
    1 current version
    """
    pass

class ODBFeatureBarcode(ODBFeatureBase):
    """
    <x> <y> <barcode> <font> <polarity> <orient_def> E <w> <h> <fasc> <cs> <bg> <astr> <astr_pos> <text>
    
    x,y test location (bottom left of first character for 0 orientation
    barcode barcode name (currently must be UPC39)
    font font name (currently must be 'standard')
    polarity P for positive, N for negative
    orient_def text orientation:
    same as for T (text) records
    E a constant value (reserved for future use)
    w element width
    h barcode height
    fasc Y for full ASCII, N for partial ASCII
    cs Y for checksum, N for no checksum
    bg Y for inverted background, N for no background
    astr Y for an addition of a text string
    astr_pos T for adding the string on top, B for bottom
    Text text string
    """
    pass


class ODBFeatureFile:
    """
    Represents a file containing features. 
    
    For step features, the `odbconf` should contain any custom user symbols to be used.     
    """
    def __init__(self,fpath: Path, odbconf: ODBConfig):
        self.symbol_table = []
        self.symbol_dict = {}
        self.attr_table = []
        self.attr_texts = []
        self.features_list = []
        self.odbconf = odbconf
        self.has_user_symbols = False
        
        
        if not fpath.exists():
            raise ValueError(f"File {fpath} does not exist!")
        lines = []
        with open(fpath,'r') as f:
            lines = f.readlines()
        # Clean
        lines = [l.strip() for l in lines if l.strip()!='']
        lines = [re.split(r'[\s\;]',l) for l in lines if not l.startswith('#')]
        if len(lines) == 0:
            return
        
        # 0. Get units
        # In v7 the first line can be "U INCH" or "U MM", with default INCH
        features_unit = ODBUnit.INCH
        if lines[0][0] == ['U']:
            features_unit = ODBUnit[lines[0][1]]
        
        surf_beg_idxs = []
        surf_end_idxs = []
        
        for i,line in enumerate(lines):
            # 1. Read features - Symbols Table
            # The symbols table contains the names of all symbols used by the features, with corresponding
            # serial numbers for reference
            # Format: $<serial> <symbolname> [I|M]
            if features_unit == ODBUnit.INCH:
                line_unit = ODBUnit.MIL
            else:
                line_unit = ODBUnit.MICRON
            if line[0].startswith('$'):
                serial = int(line[0][1:])
                name = line[1]
                if len(line) == 3:
                    line_unit = line[2]
                    if line_unit == 'I':
                        line_unit = ODBUnit.MIL
                    else:
                        line_unit = ODBUnit.MICRON
                entry = ODBSymbolTableEntry(serial,name,line_unit)
                self.symbol_table.append(entry)
                
            
            # 2. Read features - Attribute Table
            # The attribute table contains the names of attributes used by the features, with SNs
            # Line format:
            #  @<serial> <name>
            elif line[0].startswith('@'):
                serial_num = int(line[0][1:])
                attr_name = line[1]
                is_system = attr_name.startswith('.')
                entry = ODBAttributeNameEntry(serial_num, attr_name,is_system)
                self.attr_table.append(entry)
            
            # 3. Read features - Attribute Texts
            # The attribute texts are lists of text strings with values for text attributes
            # Line format:
            #  &<serial> <text>
            elif line[0].startswith('&'):
                serial_num = int(line[0][1:])
                text = ' '.join(line[1:])
                entry = ODBAttributeStringsEntry(serial_num,text)
                self.attr_texts.append(entry)
                
            
            # 4. Read features - Features List
            # The features list contains the features data
            # Line format:
            #   <type> <params> ; <atr>[=<value>],...
            else:
                # Parse features
                if line[0] == 'L':
                    feat = ODBFeatureLine(line,features_unit)
                    self.features_list.append(feat)
                elif line[0] == 'A':
                    feat = ODBFeatureArc(line,features_unit)
                    self.features_list.append(feat)
                elif line[0] == 'P':
                    feat = ODBFeaturePad(line,features_unit)
                    self.features_list.append(feat)
                elif line[0] == 'S':
                    surf_beg_idxs.append(i)
                    pass
                elif line[0] == 'SE':
                    surf_end_idxs.append(i)
        
        # Go through surfaces
        surf_idxs = list(zip(surf_beg_idxs,surf_end_idxs))
        for sidxs in surf_idxs:
            self.features_list.append(ODBFeatureSurface(lines[sidxs[0]:sidxs[1]+1],features_unit))
        
        
        # Parse symbols
        # print(f'Symbol table:\n{self.symbol_table}\n')
        # Standard symbols
        for entry in self.symbol_table:
            try:
                symobj = parse_odb_symbol(entry.symbol_name,entry.unit)
                self.symbol_dict[entry.serial_num] = symobj
            except ValueError:
                # print(f"Warning: missed symbol {entry.symbol_name}")
                pass
        
        # User symbols
        # These are created from the /symbols/ directory with standard symbols and features.
        # These are FeatureFiles themselves, so they need to be parsed outside of __init__().

        # Update widths of lines based on symbol
        for i,feat in enumerate(self.features_list):
            if isinstance(feat,ODBFeatureLine):
                sym = self.symbol_dict[feat.sym_num]
                if isinstance(sym,ODBRoundSymbol):
                    self.features_list[i].tracewidth = sym.diameter
    
    def add_user_symbols(self,user_sym_dict):
        if len(user_sym_dict) > 0:
            for entry in self.symbol_table:
                if entry.symbol_name in user_sym_dict.keys():                   
                    self.symbol_dict[entry.serial_num] = user_sym_dict[entry.symbol_name]
        self.has_user_symbols = True
    
    def getpatches(self,pos_offset: Coordinate2 = Coordinate2(0,0),**patchkwargs) -> list[mpl.patches.Patch]:
        patches = []
        if 'pos_offset' in patchkwargs.keys():
            patchkwargs['pos_offset'] = pos_offset
        for feat in self.features_list:
            patches += feat.getpatches(self.symbol_dict,self.odbconf,pos_offset=pos_offset,**patchkwargs)
        return patches

    def draw(self,ax,linecolor='k',linestyle='--',**patchkwargs):
        if not self.has_user_symbols:
            print("Warning: No user symbols loaded into feature file. Use add_user_symbols().")        
        ax.set_aspect('equal')
        ax.set_box_aspect(1)
        for feat in self.features_list:
            if isinstance(feat,ODBFeatureLine):
                feat.draw(ax,self.symbol_dict,self.odbconf,color=linecolor)
            else:
                feat.draw(ax,self.symbol_dict,self.odbconf,ec=linecolor,**patchkwargs)

class ODBUserSymbol(ODBSymbol):
    def __init__(self,name: str,featpath: Path, odbconf: ODBConfig):
        self.name = name
        self.featpath = featpath
        self.odbconf = odbconf
        self.featfile = ODBFeatureFile(featpath,self.odbconf)
    def getpatches(self, pos: Coordinate2, **patchkwargs) -> list[mpl.patches.Patch]:
        """Convert features in featfile to patches for matplotlib"""
        if 'fc' in patchkwargs.keys():
            patchkwargs['fc'] = 'g'
        if 'pos_offset' in patchkwargs.keys():
            patchkwargs['pos_offset'] = pos
        # print(f"Getting patches for symbol {self.name} at {pos}")
        self.patches = self.featfile.getpatches(pos_offset=pos,**patchkwargs)
        
        return self.patches

def load_user_symbols(odbconf: ODBConfig):
    print("Loading user symbols... ",end='')
    user_sym_root = odbconf.root_path/'symbols'
    all_sym_dirpaths = list(user_sym_root.glob('*'))
    user_sym_paths = {}
    for p in all_sym_dirpaths:
        if p.is_dir():
            user_sym_paths[p.name] = p
    usersym_dict = {}
    for name,sympath in user_sym_paths.items():
        # Try reading a feature file
        usersym_dict[name] = ODBUserSymbol(name,sympath/'features',odbconf)
    print(f'Done. Found {len(usersym_dict)} symbols.')
    return usersym_dict


class ODBLayer:
    """
    Class representing a PCB layer with features from an ODB++ archive
    """
    def __init__(self,odbconf: ODBConfig, layername: str, is_toplevel=False, stepname = '', stepidx = 0):
        """
        Given ODB++ config and name or index of step to use (index is for `odbconf.matrix.matrix_steps`, 
        use default if only one step is present, otherwise stepname is preferred), 
        parse the layer geometry and properties using its `features` file and `attrlist`.
        
        NOTE: The matrix has (`odbconf.matrix`) has raw-parsed information on different layers.     
        
        To parse e.g. the `profile` file, set `is_toplevel=True`.  
        """
        self.odbconf = odbconf
        self.name = layername
        rp = odbconf.root_path
        if stepname == '':
            stepname = odbconf.matrix.matrix_steps[stepidx].name  # The rest is unnecessary technically but it gives nice feedback on error
        # Find matching step path, case-insensitive
        self.step_path = None
        step_paths = list((rp/'steps').glob('*'))
        step_path_names = [p.name for p in step_paths]
        for i in range(len(step_path_names)):
            if step_path_names[i].lower() == stepname.lower():
                self.step_path = step_path_names[i]
        if self.step_path is None:
            raise ValueError(f"Could not find stepfile with name {stepname} out of options: {step_path_names}.")
        
        self.layer_root_path = rp/f'steps/{stepname}/layers/{layername}'
        mat_layernames = [lay.name for lay in odbconf.matrix.matrix_layers]
        layer_paths = list((rp/f'steps/{stepname}/layers').glob('*'))
        layer_paths = [lp for lp in layer_paths if lp.is_dir()]
        layer_path_names = [lp.name for lp in layer_paths]
        if not self.layer_root_path.exists():
            raise ValueError(f"Could not find layer with name {layername}. Known layers: {mat_layernames}; layer root paths: {layer_path_names}")
        
        self.featfile = ODBFeatureFile(self.layer_root_path/'features', self.odbconf)
        self.attrlist_path = self.layer_root_path/'attrlist'
        self.attrlist = []
        self.attrdict = {}
        if self.attrlist_path.exists():
            attrlist_arrs,attrlist_vars = read_structured_text(self.attrlist_path)  # should only be vars
            self.attrlist = attrlist_vars  # list of ODBVariable objects
            for attr in self.attrlist:
                self.attrdict[attr.name] = attr.value
                    
        # Look for various attributes
        
            
        
        
        # boardoutline_path = odbconf.root_path/f'steps/{stepname}/profile'  # example 1
        # boardoutline_featfile = odb.ODBFeatureFile(boardoutline_path,odbconf)
        # boardoutline_featfile.add_user_symbols(user_sym_dict)
        # for layer in odbconf.matrix.matrix_layers:
        #     if layer.layertype in odb.SIMULATION_LAYER_TYPES:
        #         featpath = root_p/f'steps/{stepname}/layers/{layer.name.lower()}/features'
        #         featfile = odb.ODBFeatureFile(featpath,odbconf)
        #         featfile.add_user_symbols(user_sym_dict)
        #         layer_featfiles[layer.name.lower()] = featfile

    

@dataclass 
class ODBNetPoint:
    net_num: int
    radius: float
    loc: Coordinate2
    side: str
    netname: str

class ODBNetlistFile:
    def __init__(self,fpath: Path):
        """
        Note: "staggered" = points that were staggered by an algorithm to make them accessible to test probes
        First line:
            H optimize <y|n>     yes/no to reflect whether the netlist was optimized

        """
        self.netnames_dict = {}  # dict from serial to netname
        self.net_points = []     # list of ODBNetPoint objects representing the location and radius of a net testpoint
        if not fpath.exists():
            raise ValueError(f"File {fpath} does not exist!")
        lines = []
        with open(fpath,'r') as f:
            lines = f.readlines()
        # Clean
        lines = [l.strip() for l in lines if l.strip()!='']
        lines = [re.split(r'[\s\;]',l) for l in lines if not l.startswith('#')]
        if len(lines) == 0:
            raise ValueError("No length")  # for interactive testing only
        
        # 0. Get optimized/staggered
        # Probably can skip this
        # In v7 the first line is "H optimize <Y|N> [staggered <Y|N>]"
        if lines[0][0] != 'H':
            raise ValueError(f"Expected first line to start with `H`, found: {lines[0]}")
        
        for i,line in enumerate(lines):
            if line[0].startswith('$'):
                serial = int(line[0][1:])
                name = line[1]
                # self.netnames.append((serial,name))
                self.netnames_dict[serial]=name
        
        """
        All other lines have the format:
            <net_num> <radius> <x> <y> <side> [ <w> <h> ] <epoint> <exp> [ <c> ] [staggerred <sx> <sy> <sr>] [v] [f] [t] [m][<x>] [<e>] [<by>]
        
        net_num     The number of the net (start from -1), corresponding to the
                    previously defined netlist section (when a feature does not belong
                    to a net it is defined as $NONE$). Net numbers start from -1
                    (-1 represents a tooling hole).
        radius  Drill radius (inches) or 0.002 for SMD pads
        x,y     point coordinates (inches)
        side    'T' for top, 'D' for bottom, 'B' for both
        w,h     (opt) Width and height of non-drilled pads (only when radius = 0)
        epoint  'e' for net end point, 'm' for net mid point
        exp     'e' for solder mask exposed point
                'c' for solder mask covered point
                'p' for solder mask covered primary point on top layer
                's' for solder mask covered secondary point on bottom layer
        'c'     Comment point
        sx,sy   Coordinates of staggered point
        sr      Radius of staggered point
        v       'v' for a via point
        f       Fiducial point
        t       Test point
        m       Appears when a netlist point is designated as a test point by
                assigning it the .critical_tp attribute. Normally this is
                applied to mid-points that need to be tested. The Netlist Optimizer
                determines mid-points to be not testable unless assigned this
                attribute. If both .non_tp and .critical_tp are assigned to
                the same point, .critical_tp takes precedence and the mid
                point is tested. In case of a drilled pad, the attribute must be
                added to the drill hole.
        x       ‘eXtended' appears if net point is extended
        e       ‘<Extension>' appears if net point is an extension
        by      { c s b n }
                c - test from component side
                s - test from solder side
                b - test from both sides
                a - test from any one side.
                n - side not defined
                (if <by> value not defined, n is assumed)
        arsize_top  'Annular Ring size for Top' represents the minimum width of
                    exposed copper (from solder mask) around a drill hole on the top
                    outer layer.
        arsize_bot  Same as for arsize_top but for bottom part of the hole.
                    If hole does not go through top / bottom layer, the corresponding
                    parameter (arsize_top / arsize_bot) should not be defined
                    or set to 0. Parameters are keyword parameters and may be
                    placed at any place after the positional ones.
        is_shrink   Y - point size was shrunk to fit solder-mask opening.
                    N - point size is limited only by pad size.
        """
        
        # We're going to just extract the location for now. TODO.
        for i,line in enumerate(lines):
            if line[0][0] not in ['$','H']:
                net_num = int(line[0])
                radius = float(line[1])
                x = float(line[2])
                y = float(line[3])
                side = line[4]
                netpt = ODBNetPoint(net_num,radius,Coordinate2(x,y),side,self.netnames_dict[net_num])
                self.net_points.append(netpt)


def load_ODB(root_p: Path,verbose = True) -> ODBConfig:
    """
    Given the path to the ODB++ root directory (uncompressed), verify info and create
    an ODBConfig object. 
    """
    ODB_UNIT = ODBUnit.INCH
    ODB_VERSION = 0.0  # have to parse this from info
    
    # GET BASIC INFO
    # 1. Check if this is a valid ODB++ archive
    if verbose:
        print(f"Checking if this is an ODB++ archive... {is_ODB(root_p)}\n")
    
    # 2. Parse /matrix/matrix file
    matfile = root_p/'matrix/matrix'
    if verbose:
        print("Parsing matrix file... ",end='')
    matrix = ODBMatrix(matfile)
    if verbose:
        print("Done.")
    
    # Print summary of matrix
    nsteps = len(matrix.matrix_steps)
    nlayers = len(matrix.matrix_layers)
    if verbose:
        print(f'Matrix has {nsteps} step(s) and {nlayers} layers.')
    for step in matrix.matrix_steps:
        if verbose:
            print(f'Step at column {step.col}: {step.name}')
    
    if verbose:
        print("Signal, power, and dielectric layers:")
    for layer in matrix.matrix_layers:
        if layer.layertype in SIMULATION_LAYER_TYPES:
            if verbose:
                print(f'\t{layer.row} - {layer.name} ({layer.layertype.name}) in context {layer.context.name}')
    
    if verbose:
        print("Other layers:")
    for layer in matrix.matrix_layers:
        if layer.layertype not in SIMULATION_LAYER_TYPES:
            if verbose:
                print(f'\t{layer.row} - {layer.name} ({layer.layertype.name}) in context {layer.context.name}')
    
    
    # 3. Parse info file for ODB version
    if verbose:
        print("\nParsing info file... ",end='')
    infofile = root_p/'misc/info'""
    info_arrs,info_vars = read_structured_text(infofile)  # should only be vars
    if verbose:
        print("Done.")
    if verbose:
        print("Info variables:")
    odb_ver_maj = ''
    odb_ver_min = ''
    for iv in info_vars:
        if verbose:
            print(f'\t{iv.name}={iv.value}')
        if iv.name == 'ODB_VERSION_MAJOR':
            odb_ver_maj = iv.value 
        elif iv.name == 'ODB_VERSION_MINOR':
            odb_ver_min = iv.value 
    
    ODB_VERSION = odb_ver_maj+odb_ver_min
    if verbose:
        print(f"ODB VERSION: {ODB_VERSION}")
    if ODB_VERSION < 8:
        ODB_UNIT = ODBUnit.INCH  # update global unit
    
    # 4. Parse attrlist and check for a `.board_thickness` variable
    # NOTE: This depends on ODB version for units. If v7.x, units default to inches, 
    # if v8.0 the UNITS directive must be present
    if verbose:
        print("\nParsing attrlist file... ",end='')
    attrlistfile = root_p/'misc/attrlist'""
    attrlist_arrs,attrlist_vars = read_structured_text(attrlistfile)  # should only be vars
    if verbose:
        print("Done.")
    
    board_thickness = 0.
    unit = ODB_UNIT
    for alv in attrlist_vars:
        if verbose:
            print(f'\t{alv.name}={alv.value}')
        if alv.name == 'UNITS':  # only required for v8+
            unit = ODBUnit[alv.value]
        elif alv.name == '.board_thickness':
            scale = get_unit_conversion(unit,ODB_UNIT)
            board_thickness = float(alv.value)*scale
    
    if verbose:
        print(f"Found board thickness: {board_thickness} with unit {ODB_UNIT.name}")
    # NOTE: the UNITS variable is required for v8, but not for v7
    
    odbconf = ODBConfig(root_p, ODB_UNIT, ODB_VERSION, matrix, nsteps, nlayers,board_thickness=board_thickness)
    return odbconf
