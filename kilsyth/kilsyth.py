#!/usr/bin/env python3

# This file is Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 David Shah <dave@ds0.me>
# This file is Copyright (c) 2019 Konrad Beckmann <konrad.beckmann@gmail.com>
# License: BSD

import argparse
import os

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.boards.platforms import kilsyth

from litex.soc.cores.clock import *
from litex.soc.cores.spi_flash import *
from litex.soc.integration import SoCCore
from litex.soc.integration.soc_sdram import *
from litex.soc.integration.builder import *

from litedram.modules import SDRAMModule, _TechnologyTimings, _SpeedgradeTimings
from litedram.phy import GENSDRPHY

from litex.soc.cores.gpio import GPIOOut

from kilsyth.spi_ram import SpiRam
from kilsyth.spi_flash import SpiFlashEx

# CRG ----------------------------------------------------------------------------------------------

class _CRG(Module):
    def __init__(self, platform, sys_clk_freq):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_sys_ps = ClockDomain(reset_less=True)

        # # #

        self.cd_sys.clk.attr.add("keep")
        self.cd_sys_ps.clk.attr.add("keep")

        # clk / rst
        clk16 = platform.request("clk16")
        rst = platform.request("rst")
        platform.add_period_constraint(clk16, 1000. / 16)

        # pll
        self.submodules.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(rst)
        pll.register_clkin(clk16, 16e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq, phase=11)
        pll.create_clkout(self.cd_sys_ps, sys_clk_freq, phase=20)
        self.specials += AsyncResetSynchronizer(self.cd_sys, rst)

        # sdram clock
        self.comb += platform.request("sdram_clock").eq(self.cd_sys_ps.clk)

# BaseSoC ------------------------------------------------------------------------------------------

# Should live in litedram/litedram/modules.py but that's another repo so this is easier
class K4S561632J_UC75(SDRAMModule):
    memtype = "SDR"
    # geometry
    nbanks = 2
    nrows  = 8192
    ncols  = 512
    # timings
    technology_timings = _TechnologyTimings(tREFI=64e6/8192, tWTR=(2, None), tCCD=(1, None), tRRD=(None, 15))
    speedgrade_timings = {"default": _SpeedgradeTimings(tRP=40, tRCD=40, tWR=40, tRFC=(None, 128), tFAW=None, tRAS=100)}

# class BaseSoC(SoCSDRAM):
class BaseSoC(SoCCore):

    # Create a default CSR map to prevent values from getting reassigned.
    # This increases consistency across litex versions.
    # SoCCore.csr_map = {
    #     "ctrl":           0,  # provided by default (optional)
    #     "crg":            1,  # user
    #     "uart_phy":       2,  # provided by default (optional)
    #     "uart":           3,  # provided by default (optional)
    #     "identifier_mem": 4,  # provided by default (optional)
    #     "timer0":         5,  # provided by default (optional)
    #     "cpu_or_bridge":  8,
    #     "usb":            9,
    #     "picorvspi":      10,
    #     "touch":          11,
    #     "reboot":         12,
    #     "rgb":            13,
    #     "version":        14,
    # }

    # Statically-define the memory map, to prevent it from shifting across
    # various litex versions.
    SoCCore.mem_map = {
        "rom":      0x00000000,
        "sram":     0x10000000,
        "csr":      0x82000000,

        "spiflash": 0x20000000,  # (default shadow @0xa0000000)
        "sdram":    0x30000000,
        "main_ram": 0x40000000,
    }


    def __init__(self, device="LFE5U-45F", toolchain="trellis", **kwargs):
        platform = kilsyth.Platform(device=device, toolchain=toolchain)
        sys_clk_freq = int(50e6)
        # sys_clk_freq = int(24e6)
        SoCCore.__init__(self, platform, clk_freq=sys_clk_freq,
                        integrated_rom_size= 0x8000,
                        integrated_sram_size=0x8000,
                        **kwargs)

        self.submodules.crg = _CRG(platform, sys_clk_freq)

        self.add_csr("gpio")
        self.leds = platform.request("user_led")
        self.submodules.gpio = GPIOOut(self.leds)

        ################# spiflash

        self.add_csr("spiflash")
        self.submodules.spiflash = SpiFlashEx(
            # platform.request("spiflash"),
            platform.request("spiflash4x"),
#            dummy=platform.spiflash_read_dummy_bits,
            dummy=4,
            div=platform.spiflash_clock_div,
            # div=64,
            endianness="little")

        self.add_constant("SPIFLASH_PAGE_SIZE", platform.spiflash_page_size)
        self.add_constant("SPIFLASH_SECTOR_SIZE", platform.spiflash_sector_size)
        self.register_mem("spiflash", self.mem_map["spiflash"],
            self.spiflash.bus, size=platform.spiflash_total_size)

        ################# spiram

        self.add_csr("main_ram")
        self.submodules.main_ram = SpiRam(
            platform.request("spiram"),
            # platform.request("spiram4x"),
            dummy=platform.spiflash_read_dummy_bits,
            div=platform.spiflash_clock_div,
            endianness="little")

        self.register_mem("main_ram", self.mem_map["main_ram"],
            self.main_ram.bus, size=int((64/8)*1024*1024))

        ################# sdram (not used)

        # if not self.integrated_main_ram_size:
        #     # self.add_csr("sdram")
        #     self.submodules.sdrphy = GENSDRPHY(platform.request("sdram"), cl=2)
        #     sdram_module = K4S561632J_UC75(sys_clk_freq, "1:1")
        #     self.register_sdram(self.sdrphy,
        #                         sdram_module.geom_settings,
        #                         sdram_module.timing_settings)

# Build --------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX SoC on Kilsyth")
    parser.add_argument("--gateware-toolchain", dest="toolchain", default="trellis",
        help='gateware toolchain to use, trellis (default) or diamond')
    parser.add_argument("--device", dest="device", default="LFE5U-45F",
        help='FPGA device, Kilsyth can be populated with LFE5U-45F (default) or LFE5U-25F')
    builder_args(parser)
    soc_sdram_args(parser)
    args = parser.parse_args()

    soc = BaseSoC(device=args.device, toolchain=args.toolchain, **soc_sdram_argdict(args))
    builder = Builder(soc, **builder_argdict(args))
    builder.build()

if __name__ == "__main__":
    main()
