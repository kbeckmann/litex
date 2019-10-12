# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Konrad Beckmann <konrad.beckmann@gmail.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("clk16", 0, Pins("G3"), IOStandard("LVCMOS33")),
    ("rst", 0, Pins("R1"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("A9"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("B9"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("B10"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("A10"), IOStandard("LVCMOS33")),
    ("user_led", 0, Pins("A11"), IOStandard("LVCMOS33")),
    ("user_led", 1, Pins("C10"), IOStandard("LVCMOS33")),
    ("user_led", 2, Pins("B11"), IOStandard("LVCMOS33")),
    ("user_led", 3, Pins("C11"), IOStandard("LVCMOS33")),

    ("serial", 0,
        Subsignal("tx", Pins("F3"), IOStandard("LVCMOS33")),
        Subsignal("rx", Pins("F2"), IOStandard("LVCMOS33"))
    ),

    ("sdram_clock", 0, Pins("F19"), IOStandard("LVCMOS33")),
    ("sdram", 0,
        Subsignal("a", Pins("M20 M19 L20 L19 K20 K19 K18 J20 J19 H20 N19 G20 G19")),
        Subsignal("dq", Pins("U19 U17 U18 U16 R17 T18 T17 U20 E19 C20 D19 D20 E18 F18 J17 J18")),
        Subsignal("we_n", Pins("T20")),
        Subsignal("ras_n", Pins("P18")),
        Subsignal("cas_n", Pins("R20")),
        Subsignal("cs_n", Pins("P20")),
        Subsignal("cke", Pins("F20")),
        Subsignal("ba", Pins("P19 N20")),
        Subsignal("dm", Pins("T19 E20")),
        IOStandard("LVCMOS33"), Misc("SLEWRATE=FAST")
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    default_clk_name = "clk16"
    default_clk_period = 1e9/16e6

    def __init__(self, device="LFE5U-45F", **kwargs):
        LatticePlatform.__init__(self, device + "-6BG381C", _io, **kwargs)
