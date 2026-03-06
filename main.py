# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 16:02:08 2026

@author: SG1295
"""

from pathlib import Path
from enum import Enum,auto
from dataclasses import dataclass,field
import re
from typing import Optional
import numpy as np

# For testing only
import matplotlib as mpl
import matplotlib.pyplot as plt

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

SIMULATION_LAYER_TYPES = [ODBLayerMatrixType.COMPONENT,ODBLayerMatrixType.SIGNAL,ODBLayerMatrixType.POWER_GROUND,ODBLayerMatrixType.MIXED,ODBLayerMatrixType.DIELECTRIC]

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
                if val_s.isnumeric():
                    var.value = float(val_s)
                elif val_s == '':
                    var.value = None
                else:
                    var.value = val_s
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
        if val_s.isnumeric():
            var.value = float(val_s)
        elif val_s == '':
            var.value = None
        else:
            var.value = val_s
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
All arguments are integers

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

# I had ChatGPT take a crack at this to save the effort, since it's all nicely
# specified.

class ODBSymbol:
    """Base class for all shapes."""
    pass


# ----------------------------
# Basic Shapes
# ----------------------------

@dataclass
class Round(ODBSymbol):
    diameter: int

    pattern = re.compile(r"^r(?P<d>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("d")))


@dataclass
class Square(ODBSymbol):
    side: int

    pattern = re.compile(r"^s(?P<s>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("s")))


@dataclass
class Rectangle(ODBSymbol):
    width: int
    height: int

    pattern = re.compile(r"^rect(?P<w>\d+)x(?P<h>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("w")), int(m.group("h")))


# ----------------------------
# Rounded / Chamfered Rectangles
# ----------------------------

@dataclass
class RoundedRectangle(ODBSymbol):
    width: int
    height: int
    radius: int
    corners: Optional[str]

    pattern = re.compile(
        r"^rect(?P<w>\d+)x(?P<h>\d+)xr(?P<rad>\d+)(?:x(?P<corners>\w+))?$"
    )

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                int(m.group("w")),
                int(m.group("h")),
                int(m.group("rad")),
                m.group("corners"),
            )


@dataclass
class ChamferedRectangle(ODBSymbol):
    width: int
    height: int
    radius: int
    corners: Optional[str]

    pattern = re.compile(
        r"^rect(?P<w>\d+)x(?P<h>\d+)xc(?P<rad>\d+)(?:x(?P<corners>\w+))?$"
    )

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                int(m.group("w")),
                int(m.group("h")),
                int(m.group("rad")),
                m.group("corners"),
            )


# ----------------------------
# Other Geometry
# ----------------------------

@dataclass
class Oval(ODBSymbol):
    width: int
    height: int

    pattern = re.compile(r"^oval(?P<w>\d+)x(?P<h>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("w")), int(m.group("h")))


@dataclass
class Diamond(ODBSymbol):
    width: int
    height: int

    pattern = re.compile(r"^di(?P<w>\d+)x(?P<h>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("w")), int(m.group("h")))


@dataclass
class Octagon(ODBSymbol):
    width: int
    height: int
    corner: int

    pattern = re.compile(r"^oct(?P<w>\d+)x(?P<h>\d+)x(?P<r>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                int(m.group("w")),
                int(m.group("h")),
                int(m.group("r"))
            )

@dataclass
class Triangle(ODBSymbol):
    base: int
    height: int

    pattern = re.compile(r"^tri(?P<b>\d+)x(?P<h>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("b")), int(m.group("h")))


@dataclass
class Ellipse(ODBSymbol):
    width: int
    height: int

    pattern = re.compile(r"^el(?P<w>\d+)x(?P<h>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("w")), int(m.group("h")))

# ----------------------------
# Donuts
# ----------------------------

@dataclass
class RoundDonut(ODBSymbol):
    outer_diameter: int
    inner_diameter: int

    pattern = re.compile(r"^donut_r(?P<od>\d+)x(?P<id>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("od")), int(m.group("id")))


@dataclass
class SquareDonut(ODBSymbol):
    outer: int
    inner: int

    pattern = re.compile(r"^donut_s(?P<od>\d+)x(?P<id>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("od")), int(m.group("id")))


@dataclass
class SquareRoundDonut(ODBSymbol):
    outer: int
    inner: int

    pattern = re.compile(r"^donut_sr(?P<od>\d+)x(?P<id>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("od")), int(m.group("id")))


# ----------------------------
# Special Shapes
# ----------------------------

@dataclass
class Hole(ODBSymbol):
    diameter: int
    plating: str
    tol_plus: int
    tol_minus: int

    pattern = re.compile(r"^hole(?P<d>\d+)x(?P<p>[pnv])x(?P<tp>\d+)x(?P<tm>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(
                int(m.group("d")),
                m.group("p"),
                int(m.group("tp")),
                int(m.group("tm"))
            )


@dataclass
class NullSymbol(ODBSymbol):
    ext: int

    pattern = re.compile(r"^null(?P<e>\d+)$")

    @classmethod
    def parse(symcls, text):
        m = symcls.pattern.match(text)
        if m:
            return symcls(int(m.group("e")))


# ----------------------------
# Parser / Factory
# ----------------------------

ODBSYMBOL_CLASSES = [
    Round,
    Square,
    Rectangle,
    RoundedRectangle,
    ChamferedRectangle,
    Oval,
    Diamond,
    Octagon,
    RoundDonut,
    SquareDonut,
    SquareRoundDonut,
    Triangle,
    Ellipse,
    Hole,
    NullSymbol,
]


def parse_odb_symbol(text: str) -> ODBSymbol:
    text = text.strip()

    for symcls in ODBSYMBOL_CLASSES:
        symbol = symcls.parse(text)
        if symbol:
            return symbol

    raise ValueError(f"Unknown ODB++ symbopl format: {text}")



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
    def __init__(self,txt):
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
        self.xs = float(txt[1])
        self.ys = float(txt[2])
        self.xe = float(txt[3])
        self.ye = float(txt[4])
        self.sym_num = int(txt[5])
        self.pol = txt[6]
        self.dcode = int(txt[7])
        self.attrtxt = ''
        if len(txt) > 8:
            self.attrtxt = ' '.join(txt[8:])
    
    def draw(self,ax,sym_dict):
        # print(f"Line with symbol {sym_dict[self.sym_num]}")
        ax.plot([self.xs,self.xe],[self.ys,self.ye],'k')
    
    def __repr__(self):
        return f'ODBFeatureLine(xs={self.xs},ys={self.ys},xe={self.xe},ye={self.ye},sym_num={self.sym_num},pol={self.pol},dcode={self.dcode},attrtxt={self.attrtxt})'
        
class ODBFeatureArc(ODBFeatureBase):
    def __init__(self,txt):
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
        if len(txt) != 11:  # A + 10 args
            raise ValueError("Arc feature does not have enough arguments.")
        self.xs = float(txt[1])
        self.ys = float(txt[2])
        self.xe = float(txt[3])
        self.ye = float(txt[4])
        self.xc = float(txt[5])
        self.yc = float(txt[6])
        self.sym_num = int(txt[7])
        self.pol = txt[8]
        self.dcode = int(txt[9])
        self.cw = True 
        if txt[10] == 'N':
            self.cw = False
        self.attrtxt = ''
        if len(txt) > 11:
            self.attrtxt = ' '.join(txt[11:])
        
    def draw(self,ax,sym_dict):
        print(f"Arc with symbol {sym_dict[self.sym_num]}")
        startvec = complex(self.xs,self.ys)
        endvec = complex(self.xe,self.ye)
        centervec = complex(self.xc,self.yc)
        rad = np.abs(startvec-centervec)  # these should be very close
        # rad2 = np.abs(endvec-centervec)
        angle_start_rad = np.angle(startvec-centervec)
        angle_end_rad = np.angle(endvec-centervec)
        
        if self.cw:
            t = np.linspace(angle_end_rad, angle_start_rad + 360,10)
        else:
            t = np.linspace(angle_start_rad, angle_end_rad,10)
        x = rad*np.cos(t)
        y = rad*np.sin(t)
        plt.plot(x,y,'k')
        
        
        ax.plot([self.xs,self.xe],[self.ys,self.ye],'k')
    
    def __repr__(self):
        return f'ODBFeatureArc(xs={self.xs},ys={self.ys},xe={self.xe},ye={self.ye},xc={self.xc},yc={self.yc},sym_num={self.sym_num},pol={self.pol},dcode={self.dcode},cw={self.cw},attrtxt={self.attrtxt})'


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
     The syntax of the polygons description for a surface feature is below
    
    """
    
    @dataclass
    class ODBSurfacePolyCurve:
        p2: complex
        center: complex
        cw: bool
        def make_arc(self,prev_pt:complex):
            p1 = prev_pt
            rad = np.abs(p1-self.center)
            angle_start_deg = np.angle(p1-self.center,deg=True)%360
            angle_end_deg = np.angle(self.p2-self.center,deg=True)%360

            if self.cw:
                arc = mpl.patches.Arc((np.real(self.center),np.imag(self.center)), width=2*rad, height=2*rad, 
                                      angle=0, theta1=angle_end_deg, theta2=angle_start_deg,color='k',lw=1.5)
            else:
                arc = mpl.patches.Arc((np.real(self.center),np.imag(self.center)), width=2*rad, height=2*rad, 
                                      angle=0, theta1=angle_start_deg, theta2=angle_end_deg,color='k',lw=1.5)
            return arc 
        
    class ODBPolygonType(Enum):
        ISLAND=auto()
        HOLE=auto()
    class ODBSurfacePolygon:
        def __init__(self,txt_lines):
            """
            NOTE: txt_lines MUST contain ALL lines for the surface (from OB to OE)
            All lines should be split by spaces ' '
            
            Points are stored as complex numbers
            """
            if txt_lines[0][0] != 'OB' or txt_lines[-1][0] != 'OE':
                raise ValueError(f"Could not find start and end of polygon: {txt_lines}")
            self.xbs = float(txt_lines[0][1])
            self.ybs = float(txt_lines[0][2])
            self.bs = complex(self.xbs,self.ybs)
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
                    self.segments.append(complex(float(line[1]),float(line[2])))
                elif line[0] == 'OC':
                    """
                    Polygon curve
                    OC <xe> <ye> <xc> <yc> <cw>
                    xe, ye          curve end point (previous polygon point is the start point)
                    xc, yc          curve center point
                    cw              Y for clockwise, N for counter clockwise
                    """
                    p1 = complex(float(line[1]),float(line[2]))
                    p2 = complex(float(line[3]),float(line[4]))
                    cw = False
                    if line[5] == 'Y':
                        cw = True
                    
                    self.segments.append(ODBFeatureSurface.ODBSurfacePolyCurve(
                        p1,p2,cw
                        ))
        def draw(self,ax,sym_dict):
            pts = [self.bs]
            for seg in self.segments:
                if isinstance(seg,ODBFeatureSurface.ODBSurfacePolyCurve):
                    arc = seg.make_arc(pts[-1])
                    ax.add_patch(arc)
                    pts.append(seg.p2)
                else:  # line
                    ax.plot([np.real(pts[-1]),np.real(seg)],[np.imag(pts[-1]),np.imag(seg)],'k')
                    pts.append(seg)
            
                    
        def __repr__(self):
            return f'ODBSurfacePolygon(bs={self.bs},segments={self.segments})'
    
    def __init__(self,txt_lines):
        """
        NOTE: txt_lines MUST contain ALL lines for the surface (from S to SE)
        All lines should be split by spaces ' '
        """
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
            self.polygons.append(ODBFeatureSurface.ODBSurfacePolygon(txt_lines[pidxs[0]:pidxs[1]+1]))
    def draw(self,ax,sym_dict):
        for poly in self.polygons:
            poly.draw(ax,sym_dict)  # NOTE: ignoring polarity
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
    def __init__(self,txt):
        """
        txt: list[str] of string split by space ' '
        """
        if len(txt) < 7:
            raise ValueError(f"Found incorrect number of arguments for pad. Text: {txt}")
        self.x = float(txt[1])
        self.y = float(txt[2])
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
    def draw(self,ax,sym_dict):
        pass
        #print(f"Pad with symbol {sym_dict[self.sym_num]}")
    
    def __repr__(self):
        return f'ODBFeaturePad(x={self.x},y={self.y},sym_num={self.sym_num},resize_factor={self.resize_factor},dcode={self.dcode},orient_def={self.orient_def},attrtxt={self.attrtxt})'

    

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



@dataclass
class ODBConfig:
    root_name: str
    root_path: Path
    default_unit: ODBUnit
    version: float
    matrix: ODBMatrix
    nsteps: int
    nlayers: int
    board_thickness: float = 0.0
    user_symbols: dict|None = None  # Name to symbol object
    

# %% Initialize config
# GLOBAL SETTINGS
ODB_UNIT = ODBUnit.INCH
ODB_VERSION = 0.0  # have to parse this from info

# GET BASIC INFO
root_name = 'examples/beagleboneblack'
root_p = Path(root_name)
# 1. Check if this is a valid ODB++ archive
print(f"Checking if this is an ODB++ archive... {is_ODB(root_p)}\n")

# 2. Parse /matrix/matrix file
matfile = root_p/'matrix/matrix'
print("Parsing matrix file... ",end='')
matrix = ODBMatrix(matfile)
print("Done.")

# Print summary of matrix
nsteps = len(matrix.matrix_steps)
nlayers = len(matrix.matrix_layers)
print(f'Matrix has {nsteps} step(s) and {nlayers} layers.')
for step in matrix.matrix_steps:
    print(f'Step at column {step.col}: {step.name}')
stepname = ''
if nsteps == 1:
    stepname = matrix.matrix_steps[0].name

print("Signal, power, and dielectric layers:")
for layer in matrix.matrix_layers:
    if layer.layertype in SIMULATION_LAYER_TYPES:
        print(f'\t{layer.row} - {layer.name} ({layer.layertype.name}) in context {layer.context.name}')

print("Other layers:")
for layer in matrix.matrix_layers:
    if layer.layertype not in SIMULATION_LAYER_TYPES:
        print(f'\t{layer.row} - {layer.name} ({layer.layertype.name}) in context {layer.context.name}')


# 3. Parse info file just in case we want anything from there
print("\nParsing info file... ",end='')
infofile = root_p/'misc/info'""
info_arrs,info_vars = read_structured_text(infofile)  # should only be vars
print("Done.")
print("Info variables:")
odb_ver_maj = ''
odb_ver_min = ''
for iv in info_vars:
    print(f'\t{iv.name}={iv.value}')
    if iv.name == 'ODB_VERSION_MAJOR':
        odb_ver_maj = iv.value 
    elif iv.name == 'ODB_VERSION_MINOR':
        odb_ver_min = iv.value 

ODB_VERSION = odb_ver_maj+odb_ver_min
print(f"ODB VERSION: {ODB_VERSION}")
if ODB_VERSION < 8:
    ODB_UNIT = ODBUnit.INCH  # update global unit

# 4. Parse attrlist and check for a `.board_thickness` variable
# NOTE: This depends on ODB version for units. If v7.x, units default to inches, 
# if v8.0 the UNITS directive must be present
print("\nParsing attrlist file... ",end='')
attrlistfile = root_p/'misc/attrlist'""
attrlist_arrs,attrlist_vars = read_structured_text(attrlistfile)  # should only be vars
print("Done.")

board_thickness = 0.
unit = ODB_UNIT
for alv in attrlist_vars:
    print(f'\t{alv.name}={alv.value}')
    if alv.name == 'UNITS':  # only required for v8+
        unit = ODBUnit[alv.value]
    elif alv.name == '.board_thickness':
        scale = get_unit_conversion(unit,ODB_UNIT)
        board_thickness = float(alv.value)*scale

print(f"Found board thickness: {board_thickness} with unit {ODB_UNIT.name}")
# NOTE: the UNITS variable is required for v8, but not for v7

GLOBAL_CONFIG = ODBConfig(root_name, root_p, ODB_UNIT, ODB_VERSION, matrix, nsteps, nlayers,board_thickness=board_thickness)


# %% Parse a features file

symbol_table = []
symbol_dict = {}
attr_table = []
attr_texts = []
features_list = []

# Reading a line record text file
stepname = matrix.matrix_steps[0].name
file = root_p/f'steps/{stepname}/profile'  # example 1
file = root_p/f'steps/{stepname}/layers/plane_1/features'  # example 2
# file = root_p/f'steps/{stepname}/layers/ddt/features'  # example 3
# file = root_p/'symbols/homeplate_25x20_for_0402_stencil/features'

if not file.exists():
    raise ValueError(f"File {file} does not exist!")
lines = []
with open(file,'r') as f:
    lines = f.readlines()
# Clean
lines = [l.strip() for l in lines if l.strip()!='']
lines = [l.split() for l in lines if not l.startswith('#')]

# 0. Get units
# In v7 the first line can be "U INCH" or "U MM", with default INCH
features_unit = ODB_UNIT
features_scale = 1.0#get_unit_conversion(ODB_UNIT,features_unit)  # default to inch
if lines[0][0] == ['U']:
    features_unit = ODBUnit[lines[0][1]]
    features_scale = get_unit_conversion(unit, ODB_UNIT)  # override if necessary

surf_beg_idxs = []
surf_end_idxs = []

for i,line in enumerate(lines):
    # 1. Read features - Symbols Table
    # The symbols table contains the names of all symbols used by the features, with corresponding
    # serial numbers for reference
    # Format: $<serial> <symbolname> [I|M]
    line_unit = features_unit 
    line_scale = 1.0
    if line[0].startswith('$'):
        serial = int(line[0][1:])
        name = line[1]
        if len(line) == 3:
            line_unit = line[2]
            if line_unit == 'I':
                line_unit = ODBUnit.MIL
            else:
                line_unit = ODBUnit.MICRON
            line_scale = get_unit_conversion(features_unit, line_unit)
        entry = ODBSymbolTableEntry(serial,name,line_unit)
        symbol_table.append(entry)
        
    
    # 2. Read features - Attribute Table
    # The attribute table contains the names of attributes used by the features, with SNs
    # Line format:
    #  @<serial> <name>
    elif line[0].startswith('@'):
        serial_num = int(line[0][1:])
        attr_name = line[1]
        is_system = attr_name.startswith('.')
        entry = ODBAttributeNameEntry(serial_num, attr_name,is_system)
        attr_table.append(entry)
    
    # 3. Read features - Attribute Texts
    # The attribute texts are lists of text strings with values for text attributes
    # Line format:
    #  &<serial> <text>
    elif line[0].startswith('&'):
        serial_num = int(line[0][1:])
        text = ' '.join(line[1:])
        entry = ODBAttributeStringsEntry(serial_num,text)
        attr_texts.append(entry)
        
    
    # 4. Read features - Features List
    # The features list contains the features data
    # Line format:
    #   <type> <params> ; <atr>[=<value>],...
    else:
        # Parse features
        if line[0] == 'L':
            feat = ODBFeatureLine(line)
            features_list.append(feat)
        elif line[0] == 'A':
            feat = ODBFeatureArc(line)
            features_list.append(feat)
        elif line[0] == 'P':
            feat = ODBFeaturePad(line)
            features_list.append(feat)
        elif line[0] == 'S':
            surf_beg_idxs.append(i)
            pass
        elif line[0] == 'SE':
            surf_end_idxs.append(i)

# Go through surfaces
surf_idxs = list(zip(surf_beg_idxs,surf_end_idxs))
for sidxs in surf_idxs:
    features_list.append(ODBFeatureSurface(lines[sidxs[0]:sidxs[1]+1]))


# Parse symbols
# print(f'Symbol table:\n{symbol_table}\n')
# Standard symbols
for entry in symbol_table:
    try:
        symobj = parse_odb_symbol(entry.symbol_name)
        symbol_dict[entry.serial_num] = symobj
    except ValueError:
        print(f"Warning: missed symbol {entry.symbol_name}")
        # pass

# User symbols
# These are created from the /symbols/ directory with standard symbols and features, so we'll leave them
# alone for now. 

# print(f'Attribute table:\n{attr_table}\n')
# print(f'Attribute text strings:\n{attr_texts}\n')
# %% Test lines and arcs
fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ax.set_box_aspect(1)

for feat in features_list:
    feat.draw(ax,symbol_dict)
