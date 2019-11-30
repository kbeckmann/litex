# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Konrad Beckmann <konrad.beckmann@gmail.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("clk16", 0, Pins("P11"), IOStandard("LVCMOS33")),
    ("rst", 0, Pins("T6"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("F15 E16 E15 D16 C16 C15 B16 B15"), IOStandard("LVCMOS33")),

    # Connector("pmod", 2, "D4  C6  B7  C7  - - C4  B6  A7  A8  - -"), # PMOD3
    ("serial", 0,
        # temporary on PMOD3
        Subsignal("tx", Pins("C4"), IOStandard("LVCMOS33")),
        Subsignal("rx", Pins("D4"), IOStandard("LVCMOS33"))
    ),

    # Built-in #1
    # cs="A9", clk="B9", mosi="B10", miso="A10", wp="A11", hold="B8",
    ("spiram", 0,
        Subsignal("cs_n", Pins("A9"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("B10"), IOStandard("LVCMOS33")), # io0
        Subsignal("miso", Pins("A10"), IOStandard("LVCMOS33")), # io1
        Subsignal("clk",  Pins("B9"), IOStandard("LVCMOS33")),
        
        Subsignal("wp",   Pins("A11"), IOStandard("LVCMOS33")), # io2
        Subsignal("hold", Pins("B8"), IOStandard("LVCMOS33")), # io3
    ),
    ("spiram4x", 0,
        Subsignal("cs_n", Pins("A9"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("B9"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("B10 A10 A11 B8"), IOStandard("LVCMOS33")),
    ),

    # Built-in #2
    # cs="A2", clk="A4", mosi="A5", miso="B3", wp="B4", hold="A3",
    ("spiram", 1,
        Subsignal("cs_n", Pins("A2"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("A5"), IOStandard("LVCMOS33")), # io0
        Subsignal("miso", Pins("B3"), IOStandard("LVCMOS33")), # io1
        Subsignal("clk",  Pins("A4"), IOStandard("LVCMOS33")),
        
        Subsignal("wp",   Pins("B4"), IOStandard("LVCMOS33")), # io2
        Subsignal("hold", Pins("A3"), IOStandard("LVCMOS33")), # io3
    ),
    ("spiram4x", 1,
        Subsignal("cs_n", Pins("A2"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("A4"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("A5 B3 B4 A3"), IOStandard("LVCMOS33")),
    ),

    # PMOD1
    # Connector("pmod", 0, "P2  L1  J2  H2  - - N1  L2  J1  G1  - -"), # PMOD1
    ("spiram", 2,
        Subsignal("cs_n", Pins("P2"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("L1"), IOStandard("LVCMOS33")), # io0
        Subsignal("miso", Pins("J2"), IOStandard("LVCMOS33")), # io1
        Subsignal("clk",  Pins("H2"), IOStandard("LVCMOS33")),
        
        Subsignal("wp",   Pins("N1"), IOStandard("LVCMOS33")), # io2
        Subsignal("hold", Pins("L2"), IOStandard("LVCMOS33")), # io3
    ),
    ("spiram4x", 2,
        Subsignal("cs_n", Pins("P2"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("H2"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("L1 J2 N1 L2"), IOStandard("LVCMOS33")),
    ),

    # PMOD2
    # Connector("pmod", 1, "G2  E2  C1  B1  - - F1  D1  C2  B2  - -"), # PMOD2
    ("spiram", 3,
        Subsignal("cs_n", Pins("G2"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("C1"), IOStandard("LVCMOS33")), # io0
        Subsignal("miso", Pins("B1"), IOStandard("LVCMOS33")), # io1
        Subsignal("clk",  Pins("E2"), IOStandard("LVCMOS33")),
        
        Subsignal("wp",   Pins("F1"), IOStandard("LVCMOS33")), # io2
        Subsignal("hold", Pins("D1"), IOStandard("LVCMOS33")), # io3
    ),
    ("spiram4x", 3,
        Subsignal("cs_n", Pins("G2"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("E2"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("C1 B1 F1 D1"), IOStandard("LVCMOS33")),
    ),
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    name = "PergolaRevA0.1"
    identifier = 0x1337
    default_clk_name = "clk16"
    default_clk_period = 1e9/16e6

    # FIXME: Create a "spi flash module" object in the same way we have SDRAM
    spiflash_model = "m25p16"
    # spiflash_model = "n25q128"
    spiflash_read_dummy_bits = 8
    spiflash_clock_div = 2
    spiflash_total_size = int((128/8)*1024*1024) # 128Mbit
    # spiflash_total_size = int((8/8)*1024*1024) # 8Mbit
    spiflash_page_size = 256
    spiflash_sector_size = 0x10000

    def __init__(self, device="LFE5U-25F", **kwargs):
        LatticePlatform.__init__(self, device + "-8BG256", _io, **kwargs)
