# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Konrad Beckmann <konrad.beckmann@gmail.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("clk16", 0, Pins("P11"), IOStandard("LVCMOS33")),
    ("rst", 0, Pins("R1"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("F15 E16 E15 D16 C16 C15 B16 B15"), IOStandard("LVCMOS33")),

    ("serial", 0,
        # temporary on PMOD3
        Subsignal("tx", Pins("D4"), IOStandard("LVCMOS33")),
        Subsignal("rx", Pins("C6"), IOStandard("LVCMOS33"))
    ),

    # PMOD0
    ("spiram", 0,
        Subsignal("cs_n", Pins("A12"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("D12"), IOStandard("LVCMOS33")), # io0
        Subsignal("miso", Pins("A13"), IOStandard("LVCMOS33")), # io1
        Subsignal("clk",  Pins("D13"), IOStandard("LVCMOS33")),
        
        Subsignal("wp",   Pins("B12"), IOStandard("LVCMOS33")), # io2
        Subsignal("hold", Pins("C12"), IOStandard("LVCMOS33")), # io3
    ),
    ("spiram4x", 0,
        Subsignal("cs_n", Pins("A12"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("D13"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("D12 A13 B12 C12"), IOStandard("LVCMOS33")),
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    name = "PergolaRevA0.1"
    identifier = 0x1337
    default_clk_name = "clk16"
    default_clk_period = 1e9/16e6

    def __init__(self, device="LFE5U-25F", **kwargs):
        LatticePlatform.__init__(self, device + "-8BG256", _io, **kwargs)
