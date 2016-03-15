from litex.gen import *
from litex.gen.genlib.record import *
from litex.gen.genlib import fifo


def _make_m2s(layout):
    r = []
    for f in layout:
        if isinstance(f[1], (int, tuple)):
            r.append((f[0], f[1], DIR_M_TO_S))
        else:
            r.append((f[0], _make_m2s(f[1])))
    return r


class EndpointDescription:
    def __init__(self, payload_layout, param_layout=[]):
        self.payload_layout = payload_layout
        self.param_layout = param_layout

    def get_full_layout(self):
        reserved = {"stb", "ack", "payload", "param", "eop", "description"}
        attributed = set()
        for f in self.payload_layout + self.param_layout:
            if f[0] in attributed:
                raise ValueError(f[0] + " already attributed in payload or param layout")
            if f[0] in reserved:
                raise ValueError(f[0] + " cannot be used in endpoint layout")
            attributed.add(f[0])

        full_layout = [
            ("payload", _make_m2s(self.payload_layout)),
            ("param", _make_m2s(self.param_layout)),
            ("stb", 1, DIR_M_TO_S),
            ("ack", 1, DIR_S_TO_M),
            ("eop", 1, DIR_M_TO_S)
        ]
        return full_layout


class Endpoint(Record):
    def __init__(self, description_or_layout):
        if isinstance(description_or_layout, EndpointDescription):
            self.description = description_or_layout
        else:
            self.description = EndpointDescription(description_or_layout)
        Record.__init__(self, self.description.get_full_layout())

    def __getattr__(self, name):
        try:
            return getattr(object.__getattribute__(self, "payload"), name)
        except:
            return getattr(object.__getattribute__(self, "param"), name)


class Source(Endpoint):
    pass

class Sink(Endpoint):
    pass


class _FIFOWrapper(Module):
    def __init__(self, fifo_class, layout, depth):
        self.sink = Sink(layout)
        self.source = Source(layout)
        self.busy = Signal()

        # # #

        description = self.sink.description
        fifo_layout = [("payload", description.payload_layout),
                       ("eop", 1)]

        self.submodules.fifo = fifo_class(layout_len(fifo_layout), depth)
        fifo_in = Record(fifo_layout)
        fifo_out = Record(fifo_layout)
        self.comb += [
            self.fifo.din.eq(fifo_in.raw_bits()),
            fifo_out.raw_bits().eq(self.fifo.dout)
        ]

        self.comb += [
            self.sink.ack.eq(self.fifo.writable),
            self.fifo.we.eq(self.sink.stb),
            fifo_in.eop.eq(self.sink.eop),
            fifo_in.payload.eq(self.sink.payload),

            self.source.stb.eq(self.fifo.readable),
            self.source.eop.eq(fifo_out.eop),
            self.source.payload.eq(fifo_out.payload),
            self.fifo.re.eq(self.source.ack)
        ]


class SyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth, buffered=False):
        _FIFOWrapper.__init__(
            self,
            fifo.SyncFIFOBuffered if buffered else fifo.SyncFIFO,
            layout, depth)
        self.level = self.fifo.level


class AsyncFIFO(_FIFOWrapper):
    def __init__(self, layout, depth):
        _FIFOWrapper.__init__(self, fifo.AsyncFIFO, layout, depth)


class Multiplexer(Module):
    def __init__(self, layout, n):
        self.source = Source(layout)
        sinks = []
        for i in range(n):
            sink = Sink(layout)
            setattr(self, "sink"+str(i), sink)
            sinks.append(sink)
        self.sel = Signal(max=n)

        # # #

        cases = {}
        for i, sink in enumerate(sinks):
            cases[i] = sink.connect(self.source)
        self.comb += Case(self.sel, cases)


class Demultiplexer(Module):
    def __init__(self, layout, n):
        self.sink = Sink(layout)
        sources = []
        for i in range(n):
            source = Source(layout)
            setattr(self, "source"+str(i), source)
            sources.append(source)
        self.sel = Signal(max=n)

        # # #

        cases = {}
        for i, source in enumerate(sources):
            cases[i] = self.sink.connect(source)
        self.comb += Case(self.sel, cases)

# TODO: clean up code below
# XXX

from copy import copy
from litex.gen.util.misc import xdir

def _rawbits_layout(l):
    if isinstance(l, int):
        return [("rawbits", l)]
    else:
        return l

def pack_layout(l, n):
    return [("chunk"+str(i), l) for i in range(n)]

def get_endpoints(obj, filt=Endpoint):
    if hasattr(obj, "get_endpoints") and callable(obj.get_endpoints):
        return obj.get_endpoints(filt)
    r = dict()
    for k, v in xdir(obj, True):
        if isinstance(v, filt):
            r[k] = v
    return r

def get_single_ep(obj, filt):
    eps = get_endpoints(obj, filt)
    if len(eps) != 1:
        raise ValueError("More than one endpoint")
    return list(eps.items())[0]


class BinaryActor(Module):
    def __init__(self, *args, **kwargs):
        self.busy = Signal()
        sink = get_single_ep(self, Sink)[1]
        source = get_single_ep(self, Source)[1]
        self.build_binary_control(sink, source, *args, **kwargs)

    def build_binary_control(self, sink, source):
        raise NotImplementedError("Binary actor classes must overload build_binary_control_fragment")


class CombinatorialActor(BinaryActor):
    def build_binary_control(self, sink, source):
        self.comb += [
            source.stb.eq(sink.stb),
            source.eop.eq(sink.eop),
            sink.ack.eq(source.ack),
            self.busy.eq(0)
        ]


class PipelinedActor(BinaryActor):
    def __init__(self, latency):
        self.pipe_ce = Signal()
        BinaryActor.__init__(self, latency)

    def build_binary_control(self, sink, source, latency):
        busy = 0
        valid = sink.stb
        for i in range(latency):
            valid_n = Signal()
            self.sync += If(self.pipe_ce, valid_n.eq(valid))
            valid = valid_n
            busy = busy | valid

        self.comb += [
            self.pipe_ce.eq(source.ack | ~valid),
            sink.ack.eq(self.pipe_ce),
            source.stb.eq(valid),
            self.busy.eq(busy)
        ]
        eop = sink.stb & sink.eop
        for i in range(latency):
            eop_n = Signal()
            self.sync += \
                If(self.pipe_ce,
                    eop_n.eq(eop)
                )
            eop = eop_n
        self.comb += source.eop.eq(eop)


class Buffer(PipelinedActor):
    def __init__(self, layout):
        self.sink = Sink(layout)
        self.source = Source(layout)
        PipelinedActor.__init__(self, 1)
        self.sync += \
            If(self.pipe_ce,
                self.source.payload.eq(self.sink.payload),
                self.source.param.eq(self.sink.param)
            )


class Cast(CombinatorialActor):
    def __init__(self, layout_from, layout_to, reverse_from=False, reverse_to=False):
        self.sink = Sink(_rawbits_layout(layout_from))
        self.source = Source(_rawbits_layout(layout_to))
        CombinatorialActor.__init__(self)

        # # #

        sigs_from = self.sink.payload.flatten()
        if reverse_from:
            sigs_from = list(reversed(sigs_from))
        sigs_to = self.source.payload.flatten()
        if reverse_to:
            sigs_to = list(reversed(sigs_to))
        if sum(len(s) for s in sigs_from) != sum(len(s) for s in sigs_to):
            raise TypeError
        self.comb += Cat(*sigs_to).eq(Cat(*sigs_from))


class Unpack(Module):
    def __init__(self, n, layout_to, reverse=False):
        self.source = source = Source(layout_to)
        description_from = copy(source.description)
        description_from.payload_layout = pack_layout(description_from.payload_layout, n)
        self.sink = sink = Sink(description_from)

        self.busy = Signal()

        # # #

        mux = Signal(max=n)
        last = Signal()
        self.comb += [
            last.eq(mux == (n-1)),
            source.stb.eq(sink.stb),
            sink.ack.eq(last & source.ack)
        ]
        self.sync += [
            If(source.stb & source.ack,
                If(last,
                    mux.eq(0)
                ).Else(
                    mux.eq(mux + 1)
                )
            )
        ]
        cases = {}
        for i in range(n):
            chunk = n-i-1 if reverse else i
            cases[i] = [source.payload.raw_bits().eq(getattr(sink.payload, "chunk"+str(chunk)).raw_bits())]
        self.comb += Case(mux, cases).makedefault()

        for f in description_from.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.comb += dst.eq(src)

        self.comb += source.eop.eq(sink.eop & last)


class Pack(Module):
    def __init__(self, layout_from, n, reverse=False):
        self.sink = sink = Sink(layout_from)
        description_to = copy(sink.description)
        description_to.payload_layout = pack_layout(description_to.payload_layout, n)
        self.source = source = Source(description_to)
        self.busy = Signal()

        # # #

        demux = Signal(max=n)

        load_part = Signal()
        strobe_all = Signal()
        cases = {}
        for i in range(n):
            chunk = n-i-1 if reverse else i
            cases[i] = [getattr(source.payload, "chunk"+str(chunk)).raw_bits().eq(sink.payload.raw_bits())]
        self.comb += [
            self.busy.eq(strobe_all),
            sink.ack.eq(~strobe_all | source.ack),
            source.stb.eq(strobe_all),
            load_part.eq(sink.stb & sink.ack)
        ]

        for f in description_to.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.sync += If(load_part, dst.eq(src))

        demux_last = ((demux == (n - 1)) | sink.eop)

        self.sync += [
            If(source.ack, strobe_all.eq(0)),
            If(load_part,
                Case(demux, cases),
                If(demux_last,
                    demux.eq(0),
                    strobe_all.eq(1)
                ).Else(
                    demux.eq(demux + 1)
                )
            ),
            If(source.stb & source.ack,
                source.eop.eq(sink.eop),
            ).Elif(sink.stb & sink.ack,
                source.eop.eq(sink.eop | source.eop)
            )
        ]


class Chunkerize(CombinatorialActor):
    def __init__(self, layout_from, layout_to, n, reverse=False):
        self.sink = Sink(layout_from)
        if isinstance(layout_to, EndpointDescription):
            layout_to = copy(layout_to)
            layout_to.payload_layout = pack_layout(layout_to.payload_layout, n)
        else:
            layout_to = pack_layout(layout_to, n)
        self.source = Source(layout_to)
        CombinatorialActor.__init__(self)

        # # #

        for i in range(n):
            chunk = n-i-1 if reverse else i
            for f in self.sink.description.payload_layout:
                src = getattr(self.sink, f[0])
                dst = getattr(getattr(self.source, "chunk"+str(chunk)), f[0])
                self.comb += dst.eq(src[i*len(src)//n:(i+1)*len(src)//n])

        for f in self.sink.description.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.comb += dst.eq(src)


class Unchunkerize(CombinatorialActor):
    def __init__(self, layout_from, n, layout_to, reverse=False):
        if isinstance(layout_from, EndpointDescription):
            fields = layout_from.payload_layout
            layout_from = copy(layout_from)
            layout_from.payload_layout = pack_layout(layout_from.payload_layout, n)
        else:
            fields = layout_from
            layout_from = pack_layout(layout_from, n)
        self.sink = Sink(layout_from)
        self.source = Source(layout_to)
        CombinatorialActor.__init__(self)

        # # #

        for i in range(n):
            chunk = n-i-1 if reverse else i
            for f in fields:
                src = getattr(getattr(self.sink, "chunk"+str(chunk)), f[0])
                dst = getattr(self.source, f[0])
                self.comb += dst[i*len(dst)//n:(i+1)*len(dst)//n].eq(src)

        for f in self.sink.description.param_layout:
            src = getattr(self.sink, f[0])
            dst = getattr(self.source, f[0])
            self.comb += dst.eq(src)


class Converter(Module):
    def __init__(self, layout_from, layout_to, reverse=False):
        self.sink = Sink(layout_from)
        self.source = Source(layout_to)

        # # #

        width_from = len(self.sink.payload.raw_bits())
        width_to = len(self.source.payload.raw_bits())

        # downconverter
        if width_from > width_to:
            if width_from % width_to:
                raise ValueError
            ratio = width_from//width_to
            self.submodules.chunkerize = Chunkerize(layout_from, layout_to, ratio, reverse)
            self.submodules.unpack = Unpack(ratio, layout_to)

            self.submodules += Pipeline(self.sink,
                                        self.chunkerize,
                                        self.unpack,
                                        self.source)
        # upconverter
        elif width_to > width_from:
            if width_to % width_from:
                raise ValueError
            ratio = width_to//width_from
            self.submodules.pack = Pack(layout_from, ratio)
            self.submodules.unchunkerize = Unchunkerize(layout_from, ratio, layout_to, reverse)

            self.submodules += Pipeline(self.sink,
                                        self.pack,
                                        self.unchunkerize,
                                        self.source)
        # direct connection
        else:
            self.comb += self.sink.connect(self.source)


class Pipeline(Module):
    def __init__(self, *modules):
        n = len(modules)
        m = modules[0]
        # expose sink of first module
        # if available
        if hasattr(m, "sink"):
            self.sink = m.sink
        for i in range(1, n):
            m_n = modules[i]
            if isinstance(m, Endpoint):
                source = m
            else:
                source = m.source
            if isinstance(m_n, Endpoint):
                sink = m_n
            else:
                sink = m_n.sink
            if m is not m_n:
                self.comb += source.connect(sink)
            m = m_n
        # expose source of last module
        # if available
        if hasattr(m, "source"):
            self.source = m.source


# Add buffers on Endpoints (can be used to improve timings)
class BufferizeEndpoints(ModuleTransformer):
    def __init__(self, *names):
        self.names = names

    def transform_instance(self, submodule):
        endpoints = get_endpoints(submodule)
        sinks = {}
        sources = {}
        for name, endpoint in endpoints.items():
            if not self.names or name in self.names:
                if isinstance(endpoint, Sink):
                    sinks.update({name: endpoint})
                elif isinstance(endpoint, Source):
                    sources.update({name: endpoint})

        # add buffer on sinks
        for name, sink in sinks.items():
            buf = Buffer(sink.description)
            submodule.submodules += buf
            setattr(submodule, name, buf.sink)
            submodule.comb += buf.source.connect(sink)

        # add buffer on sources
        for name, source in sources.items():
            buf = Buffer(source.description)
            submodule.submodules += buf
            submodule.comb += source.connect(buf.sink)
            setattr(submodule, name, buf.source)

# XXX
