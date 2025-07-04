#!/usr/bin/env python3

import os
from migen import *
from litex.gen import *

from platforms import sipeed_tang_nano_9k

from litex.soc.cores.clock.gowin_gw1n import GW1NPLL
from litex.soc.integration.soc_core import *
from litex.soc.integration.soc import SoCRegion
from litex.soc.integration.builder import *
from litex.soc.cores.led import LedChaser
from litex.soc.cores.video import *
from litex.soc.cores.hyperbus import HyperRAM
from litex.soc.cores.gpio import GPIOTristate
from litex.soc.interconnect import wishbone
from patterns import MovingSpritePattern, MovingSpritePatternFromFile, TilemapRenderer

class _CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq, with_video_pll=True):
        self.rst    = Signal()
        self.cd_sys = ClockDomain()

        clk27 = platform.request("clk27")
        rst_n = platform.request("user_btn", 0)

        self.pll = pll = GW1NPLL(devicename=platform.devicename, device=platform.device)
        self.comb += pll.reset.eq(~rst_n)
        pll.register_clkin(clk27, 27e6)
        pll.create_clkout(self.cd_sys, sys_clk_freq)

        if with_video_pll:
            self.video_pll = video_pll = GW1NPLL(devicename=platform.devicename, device=platform.device)
            self.comb += video_pll.reset.eq(~rst_n)
            video_pll.register_clkin(clk27, 27e6)
            self.cd_hdmi   = ClockDomain()
            self.cd_hdmi5x = ClockDomain()
            video_pll.create_clkout(self.cd_hdmi5x, 162e6)
            self.specials += Instance("CLKDIV",
                p_DIV_MODE="5",
                i_RESETN=rst_n,
                i_HCLKIN=self.cd_hdmi5x.clk,
                o_CLKOUT=self.cd_hdmi.clk
            )

class BaseSoC(SoCCore):
    def __init__(self, toolchain="gowin", sys_clk_freq=27e6, bios_flash_offset=0x0,
        with_led_chaser=True,
        with_video_terminal=False,
        **kwargs):

        platform = sipeed_tang_nano_9k.Platform(toolchain=toolchain)
        self.crg = _CRG(platform, sys_clk_freq, with_video_pll=with_video_terminal)

        kwargs["integrated_rom_size"] = 0
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LiteX SoC on Tang Nano 9K HDMI", **kwargs)

        from litespi.modules import W25Q32
        from litespi.opcodes import SpiNorFlashOpCodes as Codes
        self.add_spi_flash(mode="1x", module=W25Q32(Codes.READ_1_1_1), with_master=False)

        self.bus.add_region("rom", SoCRegion(
            origin=self.bus.regions["spiflash"].origin + bios_flash_offset,
            size=64 * KILOBYTE,
            linker=True))
        self.cpu.set_reset_address(self.bus.regions["rom"].origin)

        if not self.integrated_main_ram_size:
            dq = platform.request("IO_psram_dq")
            rwds = platform.request("IO_psram_rwds")
            reset_n = platform.request("O_psram_reset_n")
            cs_n = platform.request("O_psram_cs_n")
            ck = platform.request("O_psram_ck")
            ck_n = platform.request("O_psram_ck_n")

            class HyperRAMPads:
                def __init__(self, n):
                    self.clk = Signal()
                    self.rst_n = reset_n[n]
                    self.dq = dq[8*n:8*(n+1)]
                    self.cs_n = cs_n[n]
                    self.rwds = rwds[n]

            hyperram_pads = HyperRAMPads(0)
            self.comb += ck[0].eq(hyperram_pads.clk)
            self.comb += ck_n[0].eq(~hyperram_pads.clk)

            if not os.path.exists("hyperbus.py"):
                os.system("wget https://github.com/litex-hub/litex-boards/files/8831568/hyperbus.py.txt")
                os.system("mv hyperbus.py.txt hyperbus.py")
            from hyperbus import HyperRAM
            self.hyperram = HyperRAM(hyperram_pads)
            self.bus.add_slave("main_ram", slave=self.hyperram.bus, region=SoCRegion(
                origin=self.mem_map["main_ram"], size=4 * MEGABYTE, mode="rwx"))

        if with_video_terminal:
            self.videophy = VideoGowinHDMIPHY(platform.request("hdmi"), clock_domain="hdmi")
            self.submodules.vtg = VideoTimingGenerator(default_video_timings="640x480@75Hz")

            self.submodules.sprite_pattern = MovingSpritePatternFromFile(
                hres=640,
                vres=480
            )

            self.comb += [
                self.vtg.source.connect(self.sprite_pattern.vtg_sink),
                self.sprite_pattern.source.connect(self.videophy.sink)
            ]

        if with_led_chaser:
            self.leds = LedChaser(
                pads=platform.request_all("user_led"),
                sys_clk_freq=sys_clk_freq)

def main():
    from litex.build.parser import LiteXArgumentParser
    parser = LiteXArgumentParser(platform=sipeed_tang_nano_9k.Platform, description="LiteX SoC on Tang Nano 9K.")
    parser.add_target_argument("--flash", action="store_true", help="Flash Bitstream.")
    parser.add_target_argument("--sys-clk-freq", default=27e6, type=float, help="System clock frequency.")
    parser.add_target_argument("--bios-flash-offset", default="0x0", help="BIOS offset in SPI Flash.")
    parser.add_target_argument("--with-spi-sdcard", action="store_true", help="Enable SPI-mode SDCard support.")
    parser.add_target_argument("--with-video-terminal", action="store_true", help="Enable Video Terminal (HDMI).")
    parser.add_target_argument("--prog-kit", default="openfpgaloader", help="Programmer select from Gowin/openFPGALoader.")
    args = parser.parse_args()

    soc = BaseSoC(
        toolchain=args.toolchain,
        sys_clk_freq=args.sys_clk_freq,
        bios_flash_offset=int(args.bios_flash_offset, 0),
        with_video_terminal=args.with_video_terminal,
        **parser.soc_argdict
    )

    if args.with_spi_sdcard:
        soc.add_spi_sdcard()

    builder = Builder(soc, **parser.builder_argdict)
    if args.build:
        builder.build(**parser.toolchain_argdict)

    if args.load:
        prog = soc.platform.create_programmer(kit=args.prog_kit)
        prog.load_bitstream(builder.get_bitstream_filename(mode="sram"))

    if args.flash:
        prog = soc.platform.create_programmer(kit=args.prog_kit)
        prog.flash(0, builder.get_bitstream_filename(mode="flash", ext=".fs"))
        if args.prog_kit == "openfpgaloader":
            prog.flash(int(args.bios_flash_offset, 0), builder.get_bios_filename(), external=True)

if __name__ == "__main__":
    main()