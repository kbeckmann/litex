# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2019 Konrad Beckmann <konrad.beckmann@gmail.com>
# License: BSD

from litex.build.generic_platform import *
from litex.build.lattice import LatticePlatform

# IOs ----------------------------------------------------------------------------------------------

_io = [
    ("clk16", 0, Pins("G3"), IOStandard("LVCMOS33")),
    ("rst", 0, Pins("R1"), IOStandard("LVCMOS33")),

    ("user_led", 0, Pins("A9 B9 B10 A10 A11 C10 B11 C11"), IOStandard("LVCMOS33")),

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

    # PMOD1
    ("spiflash", 0,
        Subsignal("cs_n", Pins("A14"), IOStandard("LVCMOS33")),
        Subsignal("mosi", Pins("B15"), IOStandard("LVCMOS33")), # io0
        Subsignal("miso", Pins("C15"), IOStandard("LVCMOS33")), # io1
        Subsignal("clk",  Pins("B16"), IOStandard("LVCMOS33")),
        
        Subsignal("wp",   Pins("C14"), IOStandard("LVCMOS33")), # io2
        Subsignal("hold", Pins("D15"), IOStandard("LVCMOS33")), # io3
    ),
    ("spiflash4x", 0,
        Subsignal("cs_n", Pins("A14"), IOStandard("LVCMOS33")),
        Subsignal("clk",  Pins("B16"), IOStandard("LVCMOS33")),
        Subsignal("dq",   Pins("B15 C15 C14 D15"), IOStandard("LVCMOS33")),
    ),
    # ("i2c", 0,
    #     Subsignal("scl", Pins("12"), IOStandard("LVCMOS18")),
    #     Subsignal("sda", Pins("20"), IOStandard("LVCMOS18")),
    # ),
    
]

# Platform -----------------------------------------------------------------------------------------

class Platform(LatticePlatform):
    name = "KilsythRevA"
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

    def __init__(self, device="LFE5U-45F", **kwargs):
        LatticePlatform.__init__(self, device + "-6BG381C", _io, **kwargs)
