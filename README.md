# ODB++ Parser

A Python-based ODB++ parser with no guarantees.

This parser was made to read ODB++ v7 files to convert the geometry into something
simulation-friendly. The skeleton is there for expanding to components and such, 
but for now it's mostly ad-hoc as required. There is an example ODB++ archive for 
the [Beaglebone Black](https://github.com/beagleboard/beaglebone-black/tree/master) that
serves as a testing ground for feature completeness. 

Currently, the "documentation" is the `main.py` file and the comments therein. As this
project matures and stabilizes, documentation should follow. 

This ugly file format zips a bunch (sometimes hundreds) of separate files together into 
an archive that can be shared. It seems to be well-supported by software. 
Unlike IPC-2581, this standard is freely available.
- [Version 7](https://odbplusplus.com/wp-content/uploads/sites/2/2020/03/ODB_Format_Description_v7.pdf)
- [Version 8](https://odbplusplus.com/wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf)

They justify the tree structure with this flimsy reasoning:
> The advantages of a directory tree, compared to one large file, are apparent when a product model is being read from disk or saved to disk. The flexible tree structure allows you to read or save exactly the required part of the product model, avoiding the overhead of reading and writing a large file, if only a subset of the information is required.

Note: Avoid the C++ library ODB Design, it's a vibe-coded mess. 

## ODB++ Basics
The ODB++ format stores what they call a **product model** (v8 terminology) or **job** 
(v7 terminology). It contains layer geometry (steps) and layer information. The stackup
is optional. The output you can expect is 2D geometry for each layer. You can either use
the polyline-style paths (no thickness) if you need to extract coordinates for generating
a simulation model, or you can use a library like Shapely or OpenCascade to process the
geometry into something more realistic. Features like traces are represented by a polyline
path, and a *symbol*, like a paintbrush, which specifies the shape to be patterned along 
the path. Most traces will use a round, square, rectangular, etc. symbol, providing the
trace thickness. The symbol size determines the trace width. Pads are represented by
symbols, which can either be standard (rectangles, rounded rectangles, circles, etc) or 
user symbols. Planes and fills are represented by *polygons* which are closed curves made
from line and curve segments. 

Below you'll find some random notes I made while writing this parser. The documentation 
above is obviously the authoritative reference, and it's not too difficult to read.

### Syntax
Entity names/identifiers are alphanumeric, max length 64 characters, can include dash, underscore, dot, and plus, but can't start with dot, dash, or plus, except "system attribute names" (whatever those are) which start with a dot. 

### Required Files
Let's start with the required stuff. There are a few files/directories that are required. For everything here, root `/` will be the product model name. 
```
/matrix/matrix                 A file with layer refs and step ref
/misc/info                     File metadata (job name, odb version, user, date)
/fonts/standard                A standard font to be used
/steps/<step_name>/stphdr      Step header
/steps/<step_name>/layers/<layer_name>/features      CAD features for layer
```

### Matrix

Contains two types of arrays, STEP and LAYER, with info on the corresponding data in the archive. See p. 62 of spec.


### STEP Header
Coordinate system and some other stuff, can be ignored.

Here's an example. This is the full file. 
```
X_DATUM=0
Y_DATUM=0
X_ORIGIN=0
Y_ORIGIN=0

TOP_ACTIVE=0
BOTTOM_ACTIVE=0
RIGHT_ACTIVE=0
LEFT_ACTIVE=0
ONLINE_DRC_NAME=
ONLINE_DRC_MODE=DISABLED
ONLINE_DRC_STAT=GREEN
ONLINE_DRC_TIME=0
ONLINE_DRC_BEEP_VOL=0
ONLINE_DRC_BEEP_TONE=0
ONLINE_NET_MODE=DISABLED
ONLINE_NET_STAT=GREEN
ONLINE_NET_TIME=0
ONLINE_NET_BEEP_VOL=0
ONLINE_NET_BEEP_TONE=0
```

## Reading the ODB++ Archive

The first info we need is the product name, i.e. the archive root directory name. Then we can start parsing files.

The first file we parse is the `/matrix/matrix` file, a structured text file with STEP and LAYER arrays. We get the step name(s), the number of layers, and the layer names, as well as layer polarity, layer type, dielectric type (if applicable), and so on. The layer types are:

- Copper or dielectric
    - SIGNAL (signal layer)
    - POWER_GROUND (power/ground plane)
    - MIXED (signal + power/ground plane)
    - DIELECTRIC
- Manufacturing, assembly, etc
    - SOLDER_MASK
    - SOLDER_PASTE
    - SILK_SCREEN
    - DRILL
    - ROUT
    - DOCUMENT
    - COMPONENT
    - MASK
    - CONDUCTIVE_PASTE

We only care about the component, copper, and dielectric layers for generating simulatable geometry. Maybe the rout and drill layers as well. 