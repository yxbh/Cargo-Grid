"""Separated inspection samples, not a sliced plate or physical-fit claim."""

from build123d import Compound, Location

from cargo_grid import Interface, Tile, make_tile
from cargo_grid.accessories import Accessory, make_accessory


def gen_step():
    interface = Interface(joint_style="original")
    single = make_tile(Tile(interface=interface))
    nonsquare = make_tile(Tile(2, 1, interface)).moved(Location((85, 0, 0)))
    anchor = make_accessory(Accessory("plate", interface=interface)).moved(Location((30, 115, 20)))
    edge_x = make_accessory(Accessory("edge-x", interface=interface)).moved(Location((85, 100, 0)))
    edge_y = make_accessory(Accessory("edge-y", interface=interface)).moved(Location((85, 130, 0)))
    return Compound(children=[single, nonsquare, anchor, edge_x, edge_y], label="interface_coupons")
