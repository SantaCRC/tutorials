from migen import *
from migen.genlib.cdc import MultiReg
from litex.gen import LiteXModule
from litex.soc.interconnect import stream
from litex.soc.cores.video import video_timing_layout, video_data_layout
from math import log2

class WishboneReader(LiteXModule):
    def __init__(self, bus, addr_width=32, data_width=32):
        self.addr  = Signal(addr_width)
        self.start = Signal()
        self.data  = Signal(data_width)
        self.ready = Signal()

        self.bus = bus

        # Internos
        data_reg  = Signal(data_width)
        ready_reg = Signal(reset=1)

        self.fsm = fsm = FSM(reset_state="IDLE")
        self.submodules += fsm

        fsm.act("IDLE",
            self.bus.stb.eq(0),
            self.bus.cyc.eq(0),
            If(self.start,
                NextState("READ")
            )
        )

        fsm.act("READ",
            self.bus.stb.eq(1),
            self.bus.cyc.eq(1),
            self.bus.adr.eq(self.addr >> 2),
            self.bus.sel.eq(0xf),
            self.bus.we.eq(0),
            If(self.bus.ack,
                NextValue(data_reg, self.bus.dat_r),
                NextValue(ready_reg, 1),
                NextState("IDLE")
            )
        )

        self.sync += If(fsm.ongoing("READ") & ~self.bus.ack,
            ready_reg.eq(0)
        )

        self.comb += [
            self.data.eq(data_reg),
            self.ready.eq(ready_reg)
        ]


class TilemapRenderer(LiteXModule):
    def __init__(self, tilemap_data, tile_rom_data, screen_w=640, screen_h=480, tile_w=16, tile_h=16):
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        tiles_x = screen_w // tile_w
        tiles_y = screen_h // tile_h

        # Tilemap ROM (como BRAM, lectura sincrónica)
        self.tilemap_rom = Memory(8, len(tilemap_data), init=tilemap_data)
        self.tilemap_port = self.tilemap_rom.get_port(clock_domain="sys", has_re=True)
        self.specials += self.tilemap_rom, self.tilemap_port

        # Tile ROM (cada tile es 16x16 pixeles de 24 bits)
        self.tile_rom = Memory(24, len(tile_rom_data), init=tile_rom_data)
        self.tile_rom_port = self.tile_rom.get_port(has_re=False)
        self.specials += self.tile_rom, self.tile_rom_port

        # Señales internas
        tile_x = Signal(max=tiles_x)
        tile_y = Signal(max=tiles_y)
        pixel_x = Signal(max=tile_w)
        pixel_y = Signal(max=tile_h)
        tilemap_addr = Signal(max=len(tilemap_data))
        tile_id = Signal(8)
        tile_addr = Signal(max=len(tile_rom_data))

        shift_w = int(log2(tile_w))
        shift_h = int(log2(tile_h))
        mask_w  = tile_w - 1
        mask_h  = tile_h - 1

        # Cálculo de posición de tile y pixel
        self.comb += [
            tile_x.eq(self.vtg_sink.hcount >> shift_w),
            tile_y.eq(self.vtg_sink.vcount >> shift_h),
            pixel_x.eq(self.vtg_sink.hcount & mask_w),
            pixel_y.eq(self.vtg_sink.vcount & mask_h),
            tilemap_addr.eq(tile_y * tiles_x + tile_x),
            self.tile_rom_port.adr.eq(tile_id * tile_w * tile_h + pixel_y * tile_w + pixel_x),
            self.vtg_sink.connect(self.source, keep={"valid", "ready", "last", "de", "hsync", "vsync"}),
            self.source.r.eq(self.tile_rom_port.dat_r[16:24]),
            self.source.g.eq(self.tile_rom_port.dat_r[8:16]),
            self.source.b.eq(self.tile_rom_port.dat_r[0:8])
        ]

        # Acceso sincrónico a tilemap ROM
        self.sync += [
            self.tilemap_port.adr.eq(tilemap_addr),
            tile_id.eq(self.tilemap_port.dat_r)
        ]
        

class HorizontalBarsPattern(LiteXModule):
    def __init__(self):
        self.enable   = Signal(reset=1)
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        enable = Signal()
        self.specials += MultiReg(self.enable, enable)

        bar = Signal(3)

        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.fsm = fsm
        self.comb += fsm.reset.eq(~self.enable)

        fsm.act("IDLE",
            self.vtg_sink.ready.eq(1),
            If(self.vtg_sink.valid & self.vtg_sink.first &
               (self.vtg_sink.hcount == 0) & (self.vtg_sink.vcount == 0),
                NextState("RUN")
            )
        )

        fsm.act("RUN",
            self.vtg_sink.ready.eq(self.source.ready),
            self.source.valid.eq(self.vtg_sink.valid),
            self.source.last.eq(self.vtg_sink.last),
            self.source.de.eq(self.vtg_sink.de),
            self.source.hsync.eq(self.vtg_sink.hsync),
            self.source.vsync.eq(self.vtg_sink.vsync),
            If(self.source.valid & self.source.ready & self.source.de,
                NextValue(bar, self.vtg_sink.vcount[3:])
            )
        )

        color_bar = [
            [0xff, 0xff, 0xff], [0xff, 0xff, 0x00], [0x00, 0xff, 0xff],
            [0x00, 0xff, 0x00], [0xff, 0x00, 0xff], [0xff, 0x00, 0x00],
            [0x00, 0x00, 0xff], [0x00, 0x00, 0x00]
        ]

        cases = {i: [
            self.source.r.eq(color_bar[i][0]),
            self.source.g.eq(color_bar[i][1]),
            self.source.b.eq(color_bar[i][2])
        ] for i in range(8)}
        self.comb += Case(bar, cases)


class SingleSpritePattern(LiteXModule):
    """Pattern with a Single Sprite"""
    def __init__(self):
        self.enable   = Signal(reset=1)
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        enable = Signal()
        self.specials += MultiReg(self.enable, enable)

        # Sprite location and size
        SPRITE_X = 100
        SPRITE_Y = 50
        SPRITE_W = 16
        SPRITE_H = 16

        # Sprite ROM (red square 16x16)
        sprite_data = [(0xff << 16) | (0x00 << 8) | 0x00] * (SPRITE_W * SPRITE_H)
        sprite_mem = Memory(24, SPRITE_W * SPRITE_H, init=sprite_data)
        sprite_port = sprite_mem.get_port(has_re=False)
        self.specials += sprite_mem, sprite_port

        sprite_visible = Signal()
        sprite_x_off   = Signal(max=SPRITE_W)
        sprite_y_off   = Signal(max=SPRITE_H)
        sprite_addr    = Signal(max=SPRITE_W * SPRITE_H)
        sprite_pixel   = Signal(24)

        self.comb += [
            sprite_visible.eq(
                (self.vtg_sink.hcount >= SPRITE_X) & (self.vtg_sink.hcount < SPRITE_X + SPRITE_W) &
                (self.vtg_sink.vcount >= SPRITE_Y) & (self.vtg_sink.vcount < SPRITE_Y + SPRITE_H)
            ),
            sprite_x_off.eq(self.vtg_sink.hcount - SPRITE_X),
            sprite_y_off.eq(self.vtg_sink.vcount - SPRITE_Y),
            sprite_addr.eq(sprite_y_off * SPRITE_W + sprite_x_off),
            sprite_port.adr.eq(sprite_addr)
        ]

        # FSM
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.fsm = fsm
        self.comb += fsm.reset.eq(~self.enable)

        fsm.act("IDLE",
            self.vtg_sink.ready.eq(1),
            If(self.vtg_sink.valid & self.vtg_sink.first &
               (self.vtg_sink.hcount == 0) & (self.vtg_sink.vcount == 0),
                NextState("RUN")
            )
        )

        fsm.act("RUN",
            self.vtg_sink.connect(self.source, keep={"valid", "ready", "last", "de", "hsync", "vsync"}),

            # Mostrar sprite si está dentro del área visible
            If(sprite_visible,
                sprite_pixel.eq(sprite_port.dat_r),
                self.source.r.eq(sprite_port.dat_r[16:24]),
                self.source.g.eq(sprite_port.dat_r[8:16]),
                self.source.b.eq(sprite_port.dat_r[0:8])
            ).Else(
                self.source.r.eq(0),
                self.source.g.eq(0),
                self.source.b.eq(0)
            )
        )


class MovingSpritePattern(LiteXModule):
    def __init__(self, hres=640, vres=480):
        self.enable   = Signal(reset=1)
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        enable = Signal()
        self.specials += MultiReg(self.enable, enable)

        SPRITE_W = 16
        SPRITE_H = 16

        # Sprite ROM: cuadrado rojo
        sprite_data = [(0xff << 16) | (0x00 << 8) | 0x00] * (SPRITE_W * SPRITE_H)
        sprite_mem = Memory(24, SPRITE_W * SPRITE_H, init=sprite_data)
        sprite_port = sprite_mem.get_port(has_re=False)
        self.specials += sprite_mem, sprite_port

        # Sprite posición y dirección
        sprite_x = Signal(max=hres)
        sprite_y = Signal(max=vres)
        dir_x = Signal(reset=1)  # 1: derecha, 0: izquierda
        dir_y = Signal(reset=1)  # 1: abajo,   0: arriba

        # Detectar flanco de vsync
        vsync_prev = Signal()
        vsync_rise = Signal()
        self.sync += vsync_prev.eq(self.vtg_sink.vsync)
        self.comb += vsync_rise.eq(self.vtg_sink.vsync & ~vsync_prev)

        # Movimiento del sprite sincronizado con vsync
        self.sync += If(vsync_rise,
            # Horizontal
            If(dir_x,
                If(sprite_x + SPRITE_W >= hres - 1,
                    dir_x.eq(0)
                ).Else(
                    sprite_x.eq(sprite_x + 1)
                )
            ).Else(
                If(sprite_x == 0,
                    dir_x.eq(1)
                ).Else(
                    sprite_x.eq(sprite_x - 1)
                )
            ),
            # Vertical
            If(dir_y,
                If(sprite_y + SPRITE_H >= vres - 1,
                    dir_y.eq(0)
                ).Else(
                    sprite_y.eq(sprite_y + 1)
                )
            ).Else(
                If(sprite_y == 0,
                    dir_y.eq(1)
                ).Else(
                    sprite_y.eq(sprite_y - 1)
                )
            )
        )

        # Lógica de visibilidad y direccionamiento del sprite
        sprite_visible = Signal()
        sprite_x_off   = Signal(max=SPRITE_W)
        sprite_y_off   = Signal(max=SPRITE_H)
        sprite_addr    = Signal(max=SPRITE_W * SPRITE_H)

        self.comb += [
            sprite_visible.eq(
                (self.vtg_sink.hcount >= sprite_x) & (self.vtg_sink.hcount < sprite_x + SPRITE_W) &
                (self.vtg_sink.vcount >= sprite_y) & (self.vtg_sink.vcount < sprite_y + SPRITE_H)
            ),
            sprite_x_off.eq(self.vtg_sink.hcount - sprite_x),
            sprite_y_off.eq(self.vtg_sink.vcount - sprite_y),
            sprite_addr.eq(sprite_y_off * SPRITE_W + sprite_x_off),
            sprite_port.adr.eq(sprite_addr)
        ]

        # FSM para salida de video
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.fsm = fsm
        self.comb += fsm.reset.eq(~self.enable)

        fsm.act("IDLE",
            self.vtg_sink.ready.eq(1),
            If(self.vtg_sink.valid & self.vtg_sink.first &
               (self.vtg_sink.hcount == 0) & (self.vtg_sink.vcount == 0),
                NextState("RUN")
            )
        )

        fsm.act("RUN",
            self.vtg_sink.connect(self.source, keep={"valid", "ready", "last", "de", "hsync", "vsync"}),
            If(sprite_visible,
                self.source.r.eq(sprite_port.dat_r[16:24]),
                self.source.g.eq(sprite_port.dat_r[8:16]),
                self.source.b.eq(sprite_port.dat_r[0:8])
            ).Else(
                self.source.r.eq(0),
                self.source.g.eq(0),
                self.source.b.eq(0)
            )
        )

class MovingSpritePatternFromFile(LiteXModule):
    def __init__(self, hres=640, vres=480):
        self.enable   = Signal(reset=1)
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        enable = Signal()
        self.specials += MultiReg(self.enable, enable)

        SPRITE_W = 64
        SPRITE_H = 64

        # Sprite ROM: file
        with open("logo.mem") as f:
            sprite_data = [int(line.strip(), 16) for line in f if line.strip()]

        sprite_mem = Memory(24, SPRITE_W * SPRITE_H, init=sprite_data)  # Ajusta tamaño real
        sprite_port = sprite_mem.get_port(has_re=False)
        self.specials += sprite_mem, sprite_port

        # Sprite posición y dirección
        sprite_x = Signal(max=hres)
        sprite_y = Signal(max=vres)
        dir_x = Signal(reset=1)  # 1: derecha, 0: izquierda
        dir_y = Signal(reset=1)  # 1: abajo,   0: arriba

        # Detectar flanco de vsync
        vsync_prev = Signal()
        vsync_rise = Signal()
        vsync_sig = Signal()
        self.comb += vsync_sig.eq(self.vtg_sink.vsync)  # si estás propagando vsync del VTG a tu patrón

        self.sync += vsync_prev.eq(vsync_sig)
        self.comb += vsync_rise.eq(vsync_sig & ~vsync_prev)

        # Movimiento del sprite sincronizado con vsync
        self.sync += If(vsync_rise,
            # Horizontal
            If(dir_x,
                If(sprite_x + SPRITE_W >= hres - 1,
                    dir_x.eq(0)
                ).Else(
                    sprite_x.eq(sprite_x + 1)
                )
            ).Else(
                If(sprite_x == 0,
                    dir_x.eq(1)
                ).Else(
                    sprite_x.eq(sprite_x - 1)
                )
            ),
            # Vertical
            If(dir_y,
                If(sprite_y + SPRITE_H >= vres - 1,
                    dir_y.eq(0)
                ).Else(
                    sprite_y.eq(sprite_y + 1)
                )
            ).Else(
                If(sprite_y == 0,
                    dir_y.eq(1)
                ).Else(
                    sprite_y.eq(sprite_y - 1)
                )
            )
        )

        # Lógica de visibilidad y direccionamiento del sprite
        sprite_visible = Signal()
        sprite_x_off   = Signal(max=SPRITE_W)
        sprite_y_off   = Signal(max=SPRITE_H)
        sprite_addr    = Signal(max=SPRITE_W * SPRITE_H)

        self.comb += sprite_visible.eq(
            (self.vtg_sink.hcount >= sprite_x) & (self.vtg_sink.hcount < sprite_x + SPRITE_W) &
            (self.vtg_sink.vcount >= sprite_y) & (self.vtg_sink.vcount < sprite_y + SPRITE_H)
        )

        self.comb += [
            sprite_x_off.eq(Mux(sprite_visible, self.vtg_sink.hcount - sprite_x, 0)),
            sprite_y_off.eq(Mux(sprite_visible, self.vtg_sink.vcount - sprite_y, 0)),
            sprite_addr.eq(sprite_y_off * SPRITE_W + sprite_x_off),
            sprite_port.adr.eq(sprite_addr)
        ]


        # FSM para salida de video
        fsm = FSM(reset_state="IDLE")
        fsm = ResetInserter()(fsm)
        self.fsm = fsm
        self.comb += fsm.reset.eq(~self.enable)

        fsm.act("IDLE",
            self.vtg_sink.ready.eq(1),
            If(self.vtg_sink.valid & self.vtg_sink.first &
               (self.vtg_sink.hcount == 0) & (self.vtg_sink.vcount == 0),
                NextState("RUN")
            )
        )

        fsm.act("RUN",
            self.vtg_sink.connect(self.source, keep={"valid", "ready", "last", "de", "hsync", "vsync"}),
            If(sprite_visible,
                self.source.r.eq(sprite_port.dat_r[16:24]),
                self.source.g.eq(sprite_port.dat_r[8:16]),
                self.source.b.eq(sprite_port.dat_r[0:8])
            ).Else(
                self.source.r.eq(0),
                self.source.g.eq(0),
                self.source.b.eq(0)
            )
        )