from migen import *
from migen.genlib.cdc import MultiReg
from litex.gen import LiteXModule, log2_int
from litex.soc.interconnect import stream
from litex.soc.cores.video import video_timing_layout, video_data_layout
from litex.soc.interconnect.csr import CSRStorage, AutoCSR
import random
from math import log2
from math import isqrt

# Seed once for reproducibility
random.seed(0)

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
    def __init__(self, tile_rom_data,
                 screen_w=640, screen_h=480,
                 tile_w=16, tile_h=16,
                 tilemap_data=None):

        # Endpoints
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        # Dimensions
        tiles_x = screen_w // tile_w
        tiles_y = screen_h // tile_h
        num_cells = tiles_x * tiles_y

        # Determine number of tiles
        total_pixels = len(tile_rom_data)
        pixels_per_tile = tile_w * tile_h
        num_tiles = total_pixels // pixels_per_tile

        # Default/random tilemap
        if tilemap_data is None or len(tilemap_data) != num_cells:
            tilemap_data = [random.randrange(num_tiles) for _ in range(num_cells)]

        # Calculate bits for tile index
        max_index = num_tiles - 1 if num_tiles > 1 else 1
        idx_bits = max_index.bit_length()

        # Tilemap ROM
        self.tilemap_rom  = Memory(width=idx_bits, depth=num_cells, init=tilemap_data)
        self.tilemap_port = self.tilemap_rom.get_port(clock_domain="hdmi", has_re=True)
        self.specials += self.tilemap_rom, self.tilemap_port

        # Tile ROM split RGB
        depth = total_pixels
        init_r = [(v >> 16) & 0xFF for v in tile_rom_data]
        init_g = [(v >>  8) & 0xFF for v in tile_rom_data]
        init_b = [ v        & 0xFF for v in tile_rom_data]
        rom_r = Memory(width=8, depth=depth, init=init_r)
        rom_g = Memory(width=8, depth=depth, init=init_g)
        rom_b = Memory(width=8, depth=depth, init=init_b)
        port_r = rom_r.get_port(clock_domain="hdmi")
        port_g = rom_g.get_port(clock_domain="hdmi")
        port_b = rom_b.get_port(clock_domain="hdmi")
        self.specials += rom_r, rom_g, rom_b, port_r, port_g, port_b

        # Signals
        tile_x       = Signal(max=tiles_x)
        tile_y       = Signal(max=tiles_y)
        pixel_x      = Signal(max=tile_w)
        pixel_y      = Signal(max=tile_h)
        tilemap_addr = Signal(max=num_cells)
        tile_id      = Signal(idx_bits)
        tile_id_next = Signal(idx_bits)
        tile_addr    = Signal(max=depth)

        shift_w = int(log2(tile_w))
        shift_h = int(log2(tile_h))
        mask_w  = tile_w - 1
        mask_h  = tile_h - 1

        # Combinatorial logic
        self.comb += [
            tile_x.eq(self.vtg_sink.hcount >> shift_w),
            tile_y.eq(self.vtg_sink.vcount >> shift_h),
            pixel_x.eq(self.vtg_sink.hcount & mask_w),
            pixel_y.eq(self.vtg_sink.vcount & mask_h),

            tilemap_addr.eq(tile_y * tiles_x + tile_x),
            tile_addr.eq(tile_id * pixels_per_tile + pixel_y * tile_w + pixel_x),

            self.tilemap_port.adr.eq(tilemap_addr),
            port_r.adr.eq(tile_addr), port_g.adr.eq(tile_addr), port_b.adr.eq(tile_addr),

            self.vtg_sink.connect(self.source, keep={"valid","ready","last","de","hsync","vsync"}),
            self.source.r.eq(port_r.dat_r),
            self.source.g.eq(port_g.dat_r),
            self.source.b.eq(port_b.dat_r),
        ]

        # Register tile_id with 1-cycle delay
        self.sync.hdmi += [ tile_id_next.eq(self.tilemap_port.dat_r), tile_id.eq(tile_id_next) ]

class BarsRenderer(LiteXModule):
    """
    Dibuja N franjas verticales (una por cada tile de 16×16) en pantalla,
    usando todo el tileset de tu ROM.
    Cada franja repite el tile completo a lo largo de su ancho.
    """
    def __init__(self, tile_rom_data,
                 screen_w=640, screen_h=480,
                 tile_w=16,   tile_h=16):
        # Video endpoints
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        # Parámetros del tileset
        pixels_per_tile = tile_w * tile_h
        total_pixels    = len(tile_rom_data)
        total_tiles     = total_pixels // pixels_per_tile
        stripes_count   = total_tiles                          # uno por cada tile
        stripe_width    = max(1, screen_w // stripes_count)    # ancho de cada franja

        # Carga ROM RGB completa
        depth = total_pixels
        init_r = [(c >> 16) & 0xFF for c in tile_rom_data]
        init_g = [(c >>  8) & 0xFF for c in tile_rom_data]
        init_b = [ c        & 0xFF for c in tile_rom_data]
        rom_r = Memory(width=8, depth=depth, init=init_r)
        rom_g = Memory(width=8, depth=depth, init=init_g)
        rom_b = Memory(width=8, depth=depth, init=init_b)
        port_r = rom_r.get_port(has_re=False)
        port_g = rom_g.get_port(has_re=False)
        port_b = rom_b.get_port(has_re=False)
        self.specials += rom_r, rom_g, rom_b, port_r, port_g, port_b

        # Señales de coordenadas
        h = self.vtg_sink.hcount
        v = self.vtg_sink.vcount
        mask_w = tile_w - 1
        mask_h = tile_h - 1

        # Índice de franja (0..stripes_count-1) usando Mux encadenado
        bar_idx = Signal(max=stripes_count)
        expr = 0
        # iterar de 1 a stripes_count-1
        for i in range(1, stripes_count):
            expr = Mux(h >= i * stripe_width, i, expr)
        self.comb += bar_idx.eq(expr)

        # Dirección en ROM: bloque + offset dentro del bloque
        addr = Signal(max=depth)
        self.comb += addr.eq(
            bar_idx * pixels_per_tile +
            (v & mask_h) * tile_w +
            (h & mask_w)
        )

        # Conexión a puertos y salida de video
        self.comb += [
            port_r.adr.eq(addr),
            port_g.adr.eq(addr),
            port_b.adr.eq(addr),
            self.vtg_sink.connect(self.source,
                keep={"valid","ready","last","de","hsync","vsync"}),
            self.source.r.eq(port_r.dat_r),
            self.source.g.eq(port_g.dat_r),
            self.source.b.eq(port_b.dat_r),
        ]


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

class BarsC(LiteXModule, AutoCSR):
    """
    Dibuja N franjas verticales (una por cada tile de 16×16) en pantalla,
    usando todo el tileset de tu ROM. La posición de cada barra se controla
    desde la CPU vía CSRs start_0…start_N-1.
    """
    def __init__(self, tile_rom_data,
                 screen_w=640, screen_h=480,
                 tile_w=16,   tile_h=16):
        # Endpoints de video
        self.vtg_sink = stream.Endpoint(video_timing_layout)
        self.source   = stream.Endpoint(video_data_layout)

        # Parámetros del tileset
        pixels_per_tile = tile_w * tile_h
        total_pixels    = len(tile_rom_data)
        total_tiles     = total_pixels // pixels_per_tile

        # Número de franjas = número de tiles
        stripes_count = total_tiles

        # Crear CSRs individualmente para cada franja
        for i in range(stripes_count):
            csr = CSRStorage(size=32,
                             reset=i * (screen_w // stripes_count),
                             name=f"start_{i}")
            setattr(self, f"start_{i}", csr)
        # Memorias RGB de todo el tileset
        depth = total_pixels
        init_r = [(c >> 16) & 0xFF for c in tile_rom_data]
        init_g = [(c >>  8) & 0xFF for c in tile_rom_data]
        init_b = [ c        & 0xFF for c in tile_rom_data]
        rom_r = Memory(width=8, depth=depth, init=init_r)
        rom_g = Memory(width=8, depth=depth, init=init_g)
        rom_b = Memory(width=8, depth=depth, init=init_b)
        port_r = rom_r.get_port(has_re=False)
        port_g = rom_g.get_port(has_re=False)
        port_b = rom_b.get_port(has_re=False)
        self.specials += rom_r, rom_g, rom_b, port_r, port_g, port_b

        # Señales de coordenadas
        h = self.vtg_sink.hcount
        v = self.vtg_sink.vcount
        mask_w = tile_w - 1
        mask_h = tile_h - 1

        # Mux encadenado: busca el último i tal que h >= start_x[i]
        bar_idx = Signal(max=stripes_count)
        expr = 0
        for i in range(stripes_count):
            start_sig = getattr(self, f"start_{i}").storage
            expr = Mux(h >= start_sig, i, expr)
        self.comb += bar_idx.eq(expr)

        # Dirección en ROM: bloque + offset dentro del bloque
        addr = Signal(max=depth)
        self.comb += addr.eq(
            bar_idx * pixels_per_tile +
            (v & mask_h) * tile_w +
            (h & mask_w)
        )

        # Conexión a video
        self.comb += [
            port_r.adr.eq(addr),
            port_g.adr.eq(addr),
            port_b.adr.eq(addr),
            self.vtg_sink.connect(self.source,
                keep={"valid","ready","last","de","hsync","vsync"}),
            self.source.r.eq(port_r.dat_r),
            self.source.g.eq(port_g.dat_r),
            self.source.b.eq(port_b.dat_r),
        ]
