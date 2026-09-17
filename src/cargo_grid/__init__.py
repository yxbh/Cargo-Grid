"""Independent parametric cargo-mat geometry; no reference assets are bundled."""

from cargo_grid._version import __version__
from cargo_grid.parameters import BuildVolume, Interface, JointStyle, Tile
from cargo_grid.tiles import make_tile

__all__ = ["BuildVolume", "Interface", "JointStyle", "Tile", "__version__", "make_tile"]
