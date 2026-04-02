# ODB++ Parser

A Python-based ODB++ parser with no guarantees.

This parser was made to read ODB++ v7 files to convert the geometry into something
simulation-friendly. It's mostly ad-hoc as required, but has most features you'd want. 
There is an example ODB++ archive for the [Beaglebone Black](https://github.com/beagleboard/beaglebone-black/tree/master) that
serves as a testing ground for feature completeness. 

![Beaglebone Black board rendered by ODB++ Parser](/examples/beaglebone_render1.png)
![Beaglebone Black board rendered by ODB++ Parser](/examples/beaglebone_render2.png)
![Beaglebone Black board rendered by ODB++ Parser](/examples/beaglebone_render3.png)

Currently, the "documentation" is the `example_beaglebone.py` file and the comments therein, this README, and the source. As this
project matures and stabilizes, documentation should follow. 

This file format zips a bunch (sometimes hundreds) of separate files together into 
an archive that can be shared. It seems to be well-supported by software. 
Ironically, unlike IPC-2581, this proprietary standard is freely available.
- [Version 7](https://odbplusplus.com/wp-content/uploads/sites/2/2020/03/ODB_Format_Description_v7.pdf)
- [Version 8](https://odbplusplus.com/wp-content/uploads/sites/2/2024/08/odb_spec_user.pdf)


Notable features of this module:

- Rendering to matplotlib, shapely, and OpenCascade through CadQuery
- Exporting to .step files on a layer-by-layer basis (with color for fun)
- Competitive with HFSS importer in terms of geometry quality
- Unioned trace and pad geometry, simplified arcs (resolution can be adjusted)
- Net and component parsing, in case you want to export only particular nets for an SI simulation
- Graph representation of traces
- Stackup parsing when available

Current limitations: 

- Only the more common standard symbols are implemented, including round, square, rectangle, rounded rectangle, oval, half oval, and diamond; user symbols are however implemented
- Drills are always assumed thru-hole, no hidden or blind vias
- Component rendering is not yet implemented, but the framework is there, just needs to be put together from the packages and components
- Feature attributes are ignored
- Doesn't unzip the tgz archives, but this would be easy to implement with the standard module `tarfile`
- Doesn't parse barcode or text features
- Lots of chunky dependencies (`matplotlib`, `cadquery` and `cadquery-ocp`, `networkx` for graphs, `shapely` for path offsets and unions)
- Hacked together in my spare time and very much _not_ optimized for performance (it's pure Python after all)


## ODB++ Basics
The ODB++ format stores what they call a **product model** or **job**. 
It contains layer geometry (steps) and layer information. The stackup
is optional. The output you can expect is 2D geometry for each layer. You can either use
the polyline-style paths (no thickness) if you need to extract coordinates for generating
a simulation model, or you can use a library like Shapely or OpenCascade to process the
geometry into something more realistic. Features like traces are represented by a polyline
path, and a *symbol*, like a paintbrush, which specifies the shape to be patterned along 
the path. Most traces will use a round or square symbol, providing the
trace thickness, cap style, and join style. The symbol size determines the trace width. Pads are represented by
symbols, which can either be standard (rectangles, rounded rectangles, circles, etc) or 
user symbols. Planes and fills are represented by *polygons* which are closed curves made
from line and curve segments. 

## Ad-Hoc Documentation
A circuit board is a complex beast, and ODB++ archives are complex structures to hold a bunch of PCB-related data, so apologies in advance if the structure of things still leaves something to be desired.

Here's the quick start:
```python
import odbparse as odb

# main object is ODBArchive
ark = odb.ODBArchive('path/to/archiveroot')
# if you don't want the non-electrical parts of the layers, use electrical_only
ark = odb.ODBArchive('path/to/arkroot',electrical_only=True)
```

The main object is the `ODBArchive`. Its constructor loads the top-level information on the archive into `ark.odbconf`, an `ODBConfig` object, then it loads the EDA data (net names and packages), and then the layers - only the simulatable layers by default. 

```python
ark.layers['top']  # get ODBLayer object corresponding to layer with name 'top'
ark.load_layer('sst')  # load a non-default layer (silkscreen top in this case)
ark.layernames     # list of layer names already loaded (same as ark.layers.keys())

# All layer names are printed when you construct the archive
# You can also explore the ODB++ matrix in the `odbconf` config object
matrix = ark.odbconf.matrix  # ODBMatrix object, contains layer info, the "matrix"
# part isn't really important unless there are multiple 'steps' (see standard)

# Get layer properties straight from the matrix (most are available in ODBLayer
# odbjects)
for mat_layer in matrix.matrix_layers:
    # mat_layer is an ODBMatrix.ODBLayerInfo object
    print(mat_layer)
# example: ODBMatrix.ODBLayerInfo(context=<ODBLayerMatrixContext.MISC: 2>,
# layertype=<ODBLayerMatrixType.DOCUMENT: 10>, name='OUTLINE', old_name=None, 
# dielectric_name=None, cu_top=None, cu_bottom=None, ref=None, start_name=None,
# end_name=None, row=18, layerid=None, 
# polarity=<ODBLayerMatrixPolarity.POSITIVE: 1>, dielectric_type=None, 
# form=None, add_type=None, color=0.0)

# You generally only need to access the matrix when a layer is not yet loaded
# Otherwise, use the ODBLayer object in ark.layers
layer = ark.layers['top']
layer.name
layer.attrdict  # dictionary of attribute name : value
# more on attributes below
layer.layertype  # ODBLayerMatrixType
layer.layer_root_path   # Path object to layer directory in /steps/
layer.matrix_layer      # ODBMatrix.ODBLayerInfo object for this layer
layer.matrixrow         # row in matrix for this layer
# etc
# More info below

# Render and export geometry
import matplotlib.pyplot as plt
ark.render_layer('top')  # make axes, plot `top` layer
ark.render_layer('top',color='r')  # pass kwargs to patch plotting

# make your own axes to plot multiple layers
# It's recommended to use equal aspect ratio
fig,ax = plt.subplots(1,1,figsize=(7,7))
ax.set_aspect('equal')
ax.set_box_aspect(1)  # avoid slim axes area
ark.render_layer('profile',ax,color=(0.4,0,0))
ark.render_layer('top',ax,color='b')

# default behavior is to subtract drill holes from all layers. You can disable
# this:
ark.render_layer('profile',subtract_drill=False)

# To export a .step file (3D cad):
ark.export_layer_step('lyr2_gnd')  # default will use layer.thickness, inferred
# from copper weight attribute of layer
# You can set the dielectric width and er manually:
ark.layers['top'].layer_dielectric = 3.6e-3  # dielectric thickness under copper

# You can also provide a z-offset, and convert from inches to mm (default) or not
ark.export_layer_step('lyr3',z_offset=0.0,in_to_mm=False)
```

### Interpreting Layers and Features

To properly interpret ODB++ archives we need to be able to interpret the different layers and features. 

#### Attributes
Most parts of the archive (features, components, layers, steps) have *attributes* as described in Appendix A of the v7.0 standard, *System Attributes*. These can provide additional information, although it is also said that "system attributes are not considered core entities." There's no guarantee that an attribute will actually be filled out, so consider them optional sources of additional information. Examples of useful attributes:
- `/misc/attrlist`
    - `.board_thickness` - PCB thickness
- `/steps/<step>/layers/<layer>/attrlist`
    - `.copper_weight` - Copper weight in oz (imperial) or thickness in microns (metric), or 0 for layers without copper
    - `.layer_dielectric` - Dielectric thickness below a copper layer, in inch or mm
    - `.bulk_resistivity`
    - `.loss_tangent`
    - `.dielectric_constant`
    - `.z0impedance`
- `/steps/<step>/layers/<layer>/features` - See Features section below

#### Matrix
As mentioned above, the matrix file contains some high level information on layers. For example, it assigns as layer type:
- Layer type - `{SIGNAL, POWER_GROUND, DIELECTRIC, MIXED, SOLDER_MASK, SOLDER_PASTE, SILK_SCREEN, DRILL, ROUT, DOCUMENT, COMPONENT, MASK, CONDUCTIVE_PASTE}`
    - Subtypes exist for drill, rout, conductive_paste, document, mask, mixed, signal, and solder_mask types
- Layer polarity - `{POSITIVE, NEGATIVE}`
- Layer dielectric type: `{NONE, PREPREG, CORE}`
- Layer form: `{RIGID, FLEX}`

These are not always specfied, although the layer type seems to always be included. 

#### Features
Features have attributes which can provide some context before you get to the full EDA data. The format is a bit confusing - there's a list of attribute names at the top of the `features` file, which gives the names in order. For example, the `.pad_usage` attribute might be `@1 .pad_usage`. Then, the features themselves will have an attribute list after a semicolon, so you might have `;1=0` which means attribute 1 has value 0. The attributes themselves are parsed according to their data type given in Appendix A of the standard. For an `Option` type, which the `.pad_usage` is, numbers correspond to options. `0` means toeprint, `1` is via, `2` is g_fiducial, `3` is l_fiducial, and 4 is tooling_hole. It's not clear how that attribute relates to the EDA data, but I'd guess it's optional. 

The other information is related to the shapes, for example the polarity of a feature (positive or negative).

#### EDA Data
The `/steps/<step>/eda/data` file maps features to nets. Features are mapped to a *subnet* type as described above:
- toeprint - one pad of a component footprint
- trace - all traces for a net on any layer
- via - one via, with pads stacked and connected to various layers
- plane - one polygonal plane

This file also contains the packages for the different components, meaning their outline and pads. The packages are used by `components` files for component layers, which give the reference designators and orientation for each component with a given package.

To determine if a feature is non-physical (e.g. drawings or text that are not copper), check if its feature id appears in the EDA data file. Physical features will appear in this file, possibly under the net name `$NONE$` if they are floating. Non-physical features will not appear in the file.


### ODB++ Parser for Python - Lower Level

Every parser project should start by specifying the root path as a `pathlib.Path` object, and then call `odb.load_ODB(root_p)`, and finally call `odb.load_user_symbols(odbconf)`, because the user symbols have to be loaded *after* everything else is done (custom symbols are just features like layer geometry, so they depend on `odbconf`). 

Quick version:
```python
from pathlib import Path
import odbparse as odb

root_name = 'examples/beagleboneblack'
root_p = Path(root_name)
odbconf = odb.load_ODB(root_p)
user_sym_dict = odb.load_user_symbols(odbconf)  # Needs to be done manually
```

With comments:
```python

from pathlib import Path
# from coordinate2 import Coordinate2  # optional
import odbparse as odb

# We'll use a local directory as the root. If `beagleboneblack.tgz` was 
# your archive, then `beagleboneblack/` is the root. It should have a bunch 
# of folders in it like `steps/`, `user/`, and `matrix/`. This library doesn't
# unpack tgz archives (yet?).
root_name = 'examples/beagleboneblack'
root_p = Path(root_name)

# load_ODB returns an ODBConfig object that will be used to provide top-level
# info on the archive. This is the initialization step, but no layers or EDA
# data has been parsed yet.
odbconf = odb.load_ODB(root_p)

# This must be called _after_ because user symbols (like other all features)
# depend on odbconf
odb.load_user_symbols(odbconf)  # Needs to be done manually
```

The `odbconf` object stores the *matrix*, which provides some information on layers. 
From the spec:
> The matrix is a representation of the product model in which the rows are the product model layers — sheets on which elements are drawn for plotting, drilling and routing or assembly; and the columns are the product model steps — multi-layer entities such as single images, assembly panels, production panels and coupons.
    
The `/matrix/matrix` file has STEP and LAYER arrays, which provide information about what kind of ECAD (step) and layers are contained in the archive. These have associated dataclasses, accessed by members:
- `matrix_steps`
- `matrix_layers`

The matrix is a bit low-level, so you shouldn't need to access it very often. The most common case is to review the layer names and types:
```python
# Get simulatable layer types
layernames = []
for layer in odbconf.matrix.matrix_layers:
    if layer.layertype in odb.SIMULATION_LAYER_TYPES:
        layernames.append(layer.name.lower())  # lower() because matrix tends to change capitalization
```
`odb.SIMULATION_LAYER_TYPES` is there for convenience, it's a tuple of simulatable layer types. 

It's more convenient to create `ODBLayer` objects. These carry over the most useful layer information from the matrix, and also parse the actual layer *features* (geometry). To construct them, all that is needed is the `odbconf` object and the layer name. Top-level layers like the board profile (outline) need to be marked as `is_toplevel` because their organization is different. 
```python
toplayer = odb.ODBLayer(odbconf,'top')
bottomlayer = odb.ODBLayer(odbconf,'bottom')
profile = odb.ODBLayer(odbconf,'profile',is_toplevel=True)
```
Within each layer you'll find various attributes like copper thickness, bulk resistivity, dielectric type, layer polarity (positive or negative, for lithography), and the *feature file* object, `ODBFeaturesFile`, which contains the actual geometry, stored as e.g. `toplayer.featfile.features_list`. Each feature is one of: line, circular arc, surface (a polygon), pad (a symbol), text, or barcode. The last two are not implemented at the moment. Symbols used for pads can be builtins (round, square, rectangle, oval, round thermal, hole, etc) or custom user symbols, which internally are collections of polygons from a feature file. 

In addition to layer geometry, we also want logical information, like the net names associated with each feature. This is stored in the EDA data file. To load this, simply construct an `ODB_EDA_Data` object (underscores in EDA names to avoid the ugly `ODBEDA_xyz`), optionally with the name of the *step* (a step is a collection of geometry, a typical board would have one with everything in it but you can have multple). 

```python
edadata = odb.ODB_EDA_Data(odbconf)  # parse EDA data
```

This will load package footprints (`edadata.packages`) and nets (`edadata.nets`). You can then explore all that data and compare to the features files. 

Next we have the component layers, which show component footprints and their reference designators. This is not currently implemented because it's not useful for generating simulatable geometry. 

Finally there's the cadnet netlists. These will only be included when a board has named nets with associated test points. Parsing of cadnet netlists is currently partially implemented. It might be redundant because we can already get netnames from the EDA data. 

### Visualizing and Exporting

For doing your own visualization or exporting:
- Draft a symbol library for the standard symbols, including circles, rectangles, rectangles with rounded corners, ellipses, ovals \[i.e. rounded rectangles where the short side is fully rounded, a pill shape], the various thermals, etc
- Organize your line, arc, and polygon drawing primitives
    - Features can be one of: line, circular arc, surface (a polygon with straight or arc segments), pad (a symbol), text, or barcode; in most cases, only lines, arcs, surfaces, and pads will be needed for simulation
    - Lines and arcs have an associated symbol used as a paintbrush, typically a round or square symbol; this gives the trace width, join type, and cap type, to borrow SVG terminology. The symbol doesn't *need* to be symmetric, but there are rules for what to do with asymmetric symbols as paintbrushes, see the ODB++ standard.
    - The symbol dictionary is **specific to each feature file**. There is no universal symbol dictionary. So if you want to draw things in bulk, the coarsest you can go is per-feature-file (so, typically, per layer)
    - Surfaces and package/pin outlines have one primitive, the *polygon*, and each polygon can either add to or subtract from the shape. Polygons can have straight or curved (circular arc) segments. They can be holes or islands.
    - If you need to render using cubic Bezier curves, there's a method called `circular_arc_to_path()` which takes a center point, radius, start angle, and end angle, and a clockwise flag, and converts a circular arc it into a Matplotlib path (either a standalone path or part of a larger path). This can be used as a starting point. 
- For pads, text, and barcodes, you must take into account the orientation (`ODBFeaturePad.orient_def`) and resize factor (`ODBFeaturePad.resize_factor`)
- Get units straightened out, imperial (inch) or metric (mm); some parameters use thousandths (mil or micron). I think it's mostly the symbols that do this. 
- Figure out what information on stackup exists. This will be in the `ODBLayer` objects and *maybe* other places, like an explicit `stackup` file from an older ODB++ archive. Layers have copper thickness, dielectric thickness, resistivity, etc which can be filled out as attributes. If you're lucky, they'll be nicely filled out. 

#### Rendering a Layer

We need a standard symbol library. We'll receive `ODBSymbol` objects, like `ODBRoundSymbol` which has a unit (mils or mm) and a diameter. There is no position information, this is just telling us about the symbol shape itself. That means, to draw a symbol, we'll need to also specify a position, orientation, and size. This should be included in a transform. Finally, the symbol can represent either a positive or negative shape (a polygon or a hole). In general, then, we'll need a way to convert a symbol, position, orientation, and size into a Shapely object, and then we'll need to render that object according to its polarity, something which should be done as late as possible. 

To process the geometry, you want to work with an `ODBLayer` object. This has a `featfile` attribute that contains the data from the parsed feature file. It also has the various attributes for the layer itself. Rendering the layer is essentially a matter of going through the features list of the `featfile` for the layer, and parsing the features (line, arc, surface, pad). Lines and arcs should be processed separately since they usually represent traces and require a lot of additional processing. Pads and surfaces can be parsed fairly directly, but for pads you need to use the `layer.featfile.symbol_dict` dictionary to convert the symbol number to an actual symbol object. This object is position-independent, with the position, orientation, and scale defined by the pad feature. 

Here's an outline to start:

```python
# parse toplayer
for feat in toplayer.featfile.features_list:
    if isinstance(feat,odb.ODBFeaturePad):
        # Pad handling, use toplayer.featfile.symbol_dict 
        # to interpret the symbol numbers
        pass
    elif isinstance(feat,odb.ODBFeatureSurface):
        # Surface handling, parse a polyline (including straight and circular-arc
        # segments) into polygon
        pass
    #elif isinstance(feat,odb.ODBFeatureLine):
    #    pass
    #elif isinstance(feat,odb.ODBFeatureArc):
    #    pass 
    else: 
        pass  # handle lines and arcs separately
```

To make parsing traces easier, the NetworkX library was used to generate graphs representing connected nets on a layer. We use the following terminology:
- A **net** is the set of all traces, pads, and surfaces on any layer which are connected to each other electrically
- A **subnet** is one "species" of a net, including toeprint (one pad of a component footprint), trace (all traces for a net on any layer), via (one via, with pads stacked and connected to various layers), or plane (one polygonal plane)
- A **trace** is one contiguous 'trace' subnet on a single layer, possibly with different tracewidths (i.e. using multiple symbols), and possibly branching
- A **subtrace** is a contiguous, non-branching, uniform (uses one symbol) portion of a trace

This works from a simple polyline type (straight and curved segments in the same plane, exactly zero or two endpoints, can be offset easily) and gradually builds towards more logically convenient types. Subtraces can be unioned into traces, the set of all traces on all layers makes up the trace subnet, these can be unioned with toeprint, via, and plane subnets. The result will be copper layers that can be extracted by netname and which give a unified geometry for simulation.
