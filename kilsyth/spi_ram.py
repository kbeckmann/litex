# This file is Copyright (c) 2014 Yann Sionneau <ys@m-labs.hk>
# This file is Copyright (c) 2014-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2013-2014 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2015-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c)      2019 Konrad Beckmann <konrad.beckmann@gmail.com>

# License: BSD


from migen import *
from migen.genlib.misc import timeline

from litex.gen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import *
from litex.soc.cores.spi import SPIMaster

# SpiFlash Quad/Dual/Single (memory-mapped) --------------------------------------------------------

_FAST_READ = 0x0b
_WRITE = 0x02
_QIOFW = 0x38
_DIOFR = 0xbb
_QIOFR = 0xeb


def _format_cmd(cmd, spi_width):
    """
    `cmd` is the read instruction. Since everything is transmitted on all
    dq lines (cmd, adr and data), extend/interleave cmd to full pads.dq
    width even if dq1-dq3 are don't care during the command phase:
    For example, for N25Q128, 0xeb is the quad i/o fast read, and
    extended to 4 bits (dq1,dq2,dq3 high) is: 0xfffefeff
    """
    c = 2**(8*spi_width)-1
    for b in range(8):
        if not (cmd>>b)%2:
            c &= ~(1<<(b*spi_width))
    return c


class SpiFlashCommon(Module):
    def __init__(self, pads):
        if not hasattr(pads, "clk"):
            self.clk_primitive_needed = True
            self.clk_primitive_registered = False
            pads.clk = Signal()
        self.pads = pads

    def add_clk_primitive(self, device):
        if not hasattr(self, "clk_primitive_needed"):
            return
        # Xilinx 7-series
        if device[:3] == "xc7":
            self.specials += Instance("STARTUPE2",
                i_CLK=0,
                i_GSR=0,
                i_GTS=0,
                i_KEYCLEARB=0,
                i_PACK=0,
                i_USRCCLKO=self.pads.clk,
                i_USRCCLKTS=0,
                i_USRDONEO=1,
                i_USRDONETS=1)
        # Lattice ECP5
        elif device[:4] == "LFE5":
            self.specials += Instance("USRMCLK",
                i_USRMCLKI=self.pads.clk,
                i_USRMCLKTS=0)
        else:
            raise NotImplementedError
        self.clk_primitive_registered = True

    def do_finalize(self):
        if hasattr(self, "clk_primitive_needed"):
            assert self.clk_primitive_registered == True


class SpiRamSingle(SpiFlashCommon, AutoCSR):
    def __init__(self, pads, dummy=15, div=2, endianness="big"):
        """
        Simple SPI ram.
        Supports 1-bit reads. Only supports mode0 (cpol=0, cpha=0).
        And writes.
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()

        # # #

        if hasattr(pads, "wp"):
            self.comb += pads.wp.eq(1)

        if hasattr(pads, "hold"):
            self.comb += pads.hold.eq(1)

        cs_n = Signal(reset=1)
        clk = Signal()
        wbone_width = len(bus.dat_r)

        read_cmd = _FAST_READ
        cmd_width = 8
        addr_width = 24

        sr = Signal(max(cmd_width, addr_width, wbone_width))
        if endianness == "big":
            self.comb += bus.dat_r.eq(sr)
        else:
            self.comb += bus.dat_r.eq(reverse_bytes(sr))

        hw_read_logic = [
            pads.clk.eq(clk),
            pads.cs_n.eq(cs_n),
            pads.mosi.eq(sr[-1:])
        ]

        self.comb += hw_read_logic

        if div < 2:
            raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))
        else:
            i = Signal(max=div)
            miso = Signal()
            self.sync += [
                If(i == div//2 - 1,
                    clk.eq(1),
                    miso.eq(pads.miso),
                ),
                If(i == div - 1,
                    i.eq(0),
                    clk.eq(0),
                    sr.eq(Cat(miso, sr[:-1]))
                ).Else(
                    i.eq(i + 1),
                ),
            ]

        # spi is byte-addressed, prefix by zeros
        z = Replicate(0, log2_int(wbone_width//8))

        
        seq = [
            (cmd_width*div,
                [cs_n.eq(0), sr[-cmd_width:].eq(read_cmd)]),
            (addr_width*div,
                [sr[-addr_width:].eq(Cat(z, bus.adr))]),
            ((dummy + wbone_width)*div,
                []),
            (1,
                [bus.ack.eq(1), cs_n.eq(1)]),
            (div, # tSHSL!
                [bus.ack.eq(0)]),
            (0,
                []),
        ]

        # accumulate timeline deltas
        t, tseq = 0, []
        for dt, a in seq:
            tseq.append((t, a))
            t += dt

        self.sync += timeline(~bus.we & bus.cyc & bus.stb & (i == div - 1), tseq)

        ##### write

        # TODO: Make this nicer somehow.
        for write_width, addr_offset, mask in [
                (8,   0, 0b0001),
                (8,   1, 0b0010),
                (8,   2, 0b0100),
                (8,   3, 0b1000),
                (16,  0, 0b0011),
                (16,  2, 0b1100),
                (32,  0, 0b1111)
            ]:

            dat_w_endian = Signal(write_width)
            if endianness == "big":
                self.comb += dat_w_endian.eq(bus.dat_w)
            else:
                self.comb += dat_w_endian.eq(reverse_bytes(bus.dat_w))

            sec2 = [
                    (cmd_width*div,
                        [cs_n.eq(0), sr[-cmd_width:].eq(_WRITE)]),
                    (addr_width*div,
                        [sr[-addr_width:].eq(Cat(z, bus.adr) + addr_offset)]),
                    (write_width*div,
                        [sr[-write_width:].eq(dat_w_endian)]),
                    (1,
                        [bus.ack.eq(1), cs_n.eq(1)]),
                    (div, # tSHSL!
                        [bus.ack.eq(0)]),
                    (0,
                        []),
                ]

            # accumulate timeline deltas
            t2, tseq2 = 0, []
            for dt, a in sec2:
                tseq2.append((t2, a))
                t2 += dt

            self.sync += timeline(bus.we & bus.cyc & bus.stb & (bus.sel == mask) & (i == div - 1), tseq2)

class SpiRamQuad(SpiFlashCommon, AutoCSR):
    def __init__(self, pads, dummy=15, div=2, endianness="big"):
        """
        Simple SPI flash.
        Supports multi-bit pseudo-parallel reads (aka Dual or Quad I/O Fast
        Read). Only supports mode0 (cpol=0, cpha=0).
        """
        SpiFlashCommon.__init__(self, pads)
        self.bus = bus = wishbone.Interface()
        spi_width = len(pads.dq)
        assert spi_width == 4

        # # #

        # 1. Enable Quad (0x35)
        # 2. Read (0xeb)

        cs_n = Signal(reset=1)
        clk = Signal()
        clk_en = Signal()
        dq_oe = Signal()
        wbone_width = len(bus.dat_r)

        # Enable quad mode
        quad_enable_cmd = _format_cmd(0x35, spi_width)
        quad_enable_width = spi_width * 8

        read_cmd = _QIOFR
        read_cmd_width = 8

        write_cmd = _QIOFW
        write_cmd_width = 8

        addr_width = 24

        dq = TSTriple(spi_width)
        self.specials.dq = dq.get_tristate(pads.dq)

        sr = Signal(max(read_cmd_width, addr_width, wbone_width))
        if endianness == "big":
            self.comb += bus.dat_r.eq(sr)
        else:
            self.comb += bus.dat_r.eq(reverse_bytes(sr))

        hw_read_logic = [
            pads.clk.eq(clk & clk_en),
            pads.cs_n.eq(cs_n),
            dq.o.eq(sr[-spi_width:]),
            dq.oe.eq(dq_oe)
        ]
        self.comb += hw_read_logic

        if div < 2:
            raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))
        else:
            i = Signal(max=div)
            dqi = Signal(spi_width)
            self.sync += [
                If(i == div//2 - 1,
                    clk.eq(1),
                    dqi.eq(dq.i),
                ),
                If(i == div - 1,
                    i.eq(0),
                    clk.eq(0),
                    sr.eq(Cat(dqi, sr[:-spi_width]))
                ).Else(
                    i.eq(i + 1),
                ),
            ]

        # spi is byte-addressed, prefix by zeros
        z = Replicate(0, log2_int(wbone_width//8))

        quad_enabled = Signal()

        enable_quad = [
            # 1. Write 0x35
            (quad_enable_width//spi_width*div,
                [clk_en.eq(1), dq_oe.eq(1), cs_n.eq(0), sr[-quad_enable_width:].eq(quad_enable_cmd)]),
            (div,
                [clk_en.eq(0), cs_n.eq(1), dq_oe.eq(1), quad_enabled.eq(1)]),
        ]

        seq = [
            # 3. Perform the read
            (read_cmd_width//spi_width*div,
                [clk_en.eq(1), dq_oe.eq(1), cs_n.eq(0), sr[-read_cmd_width:].eq(read_cmd)]),
            (addr_width//spi_width*div,
                [sr[-addr_width:].eq(Cat(z, bus.adr))]),
            ((dummy + wbone_width//spi_width)*div,
                [dq_oe.eq(0)]),
            (1,
                [bus.ack.eq(1), clk_en.eq(0), cs_n.eq(1)]),
            (div, # tSHSL!
                [bus.ack.eq(0)]),
            (0,
                []),
        ]

        # accumulate timeline deltas
        t, tseq = 0, []
        for dt, a in seq:
            tseq.append((t, a))
            t += dt

        # accumulate timeline deltas
        t, tseq_enable_quad = 0, []
        for dt, a in enable_quad + seq:
            tseq_enable_quad.append((t, a))
            t += dt

        self.sync += timeline(~bus.we & bus.cyc & bus.stb & quad_enabled  & (i == div - 1), tseq)
        self.sync += timeline(~bus.we & bus.cyc & bus.stb & ~quad_enabled & (i == div - 1), tseq_enable_quad)



        # TODO: Make this nicer somehow.
        for write_width, addr_offset, mask in [
                (8,   0, 0b0001),
                (8,   1, 0b0010),
                (8,   2, 0b0100),
                (8,   3, 0b1000),
                (16,  0, 0b0011),
                (16,  2, 0b1100),
                (32,  0, 0b1111)
            ]:

            dat_w_endian = Signal(write_width)
            if endianness == "big":
                self.comb += dat_w_endian.eq(bus.dat_w)
            else:
                self.comb += dat_w_endian.eq(reverse_bytes(bus.dat_w))

            sec2 = [
                    (write_cmd_width//spi_width*div,
                        [clk_en.eq(1), cs_n.eq(0), dq_oe.eq(1), sr[-write_cmd_width:].eq(write_cmd)]),
                    (addr_width//spi_width*div,
                        [sr[-addr_width:].eq(Cat(z, bus.adr) + addr_offset)]),
                    (write_width//spi_width*div,
                        [sr[-write_width:].eq(dat_w_endian)]),
                    (div,
                        [clk_en.eq(0), cs_n.eq(1)]),
                    (1,
                        [bus.ack.eq(1), dq_oe.eq(0)]),
                    (div, # tSHSL!
                        [bus.ack.eq(0)]),
                    (0,
                        []),
                ]

            # accumulate timeline deltas
            t2, tseq2 = 0, []
            for dt, a in sec2:
                tseq2.append((t2, a))
                t2 += dt

            # accumulate timeline deltas
            t2, tseq2_quad = 0, []
            for dt, a in enable_quad + sec2:
                tseq2_quad.append((t2, a))
                t2 += dt

            self.sync += timeline(bus.we & bus.cyc & bus.stb & quad_enabled  & (bus.sel == mask) & (i == div - 1), tseq2)
            self.sync += timeline(bus.we & bus.cyc & bus.stb & ~quad_enabled & (bus.sel == mask) & (i == div - 1), tseq2_quad)



def SpiRam(pads, *args, **kwargs):
    if hasattr(pads, "mosi"):
        return SpiRamSingle(pads, *args, **kwargs)
    else:
        return SpiRamQuad(pads, *args, **kwargs)
