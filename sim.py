#!/usr/bin/env python3

import math
import argparse
import gc
from pathlib import Path

from migen import ClockSignal, Signal, If

from litex.tools.litex_sim import SimSoC, generate_gtkw_savefile, \
    sim_args as litex_sim_args, Platform as LiteXSimPlatform
from litex.build.sim import SimPlatform
from litex.build.sim.config import SimConfig
from litex.soc.integration.soc_core import soc_core_args, soc_core_argdict
from litex.soc.integration.builder import Builder, builder_args, builder_argdict
from litex.soc.integration.common import get_mem_data, get_boot_address
from litex.soc.cores.cpu import CPUS
from litex.soc.cores.cpu.vexriscv_bridge import VexRiscvBridge

from util import LiteXTarget
from rvfi import RiscvFormalInterface, IbexTracer


class BridgeSimShell(SimSoC, LiteXTarget):
    def target_args(parser):
        LiteXTarget.target_args(parser)

        parser.add_argument(
            "--sys-clk-freq", default=1e6,
            help="Simulated SoC system clock frequency",
        )
        parser.add_argument(
            "--trace", action="store_true", default=False,
            help="Generate a FST trace file",
        )

    def __init__(self, sys_clk_freq, trace):
        # Call the LiteXTarget constructor first to do any required basic
        # initialization
        LiteXTarget.__init__(self)

        # Clean and validate arguments
        sys_clk_freq = int(sys_clk_freq)

        # Call the regular SimSoC constructor, but modify some of the SoCCore
        # default arguments to influence the defaults of SimSoC / SoCCore /
        # SoC. We base our parameters on the set of generic default args
        # obtained when invocing the litex_sim binary with no arguments passed.
        from litex.build.parser import LiteXArgumentParser
        dummy_parser = LiteXArgumentParser(add_help=False)
        dummy_parser.set_platform(LiteXSimPlatform)
        litex_sim_args(dummy_parser)
        litex_sim_parsed_dummy_args = dummy_parser.parse_args([])
        soc_args = soc_core_argdict(litex_sim_parsed_dummy_args)

        # However, to get a serial compatible with the serial2console component,
        # we must override its name.
        # assert "uart_name" in soc_args
        soc_args["uart_name"] = "sim"

        # Set the proper sys clock speed
        soc_args["sys_clk_freq"] = sys_clk_freq

        # We'd like a DRAM, please!
        # soc_args["with_sdram"] = True

        # Load the tock kernel & applications into flash
        soc_args["integrated_rom_size"] = 0x100000
        # rom_init = Path(__file__).parent.resolve() / "demo/demo.bin"
        # soc_args["integrated_rom_init"] = str(Path(__file__).parent.resolve() / "demo/demo.bin")
        # soc_args["integrated_rom_init"] = get_mem_data(
        #     ram_init,
        #     data_width = conf_soc.bus.data_width,
        #     endianness = conf_soc.cpu.endianness,
        #     offset     = conf_soc.mem_map["rom"]
        # )

        # Other arguments required for Tock:
        soc_args["with_ethernet"] = True
        soc_args["integrated_main_ram_size"] = 0x10000000
        soc_args["timer_uptime"] = True
        soc_args["with_gpio"] = True

        # Ensure we get a CPU exposing the RVFI interface:
        soc_args["cpu_type"] = "vexriscv_bridge"
        soc_args["cpu_variant"] = "standard"

        # Bus
        soc_args["bus_interconnect"] = "crossbar"

        conf_soc = SimSoC(**soc_args)
        rom_init = Path(__file__).parent.resolve() / "demo.bin"
        # rom_init = "/home/cherrypie/hack/tock/tock/target/riscv32imc-unknown-none-elf/release/litex_sim.bin"
        soc_args["integrated_rom_init"] = get_mem_data(
            rom_init,
            data_width = conf_soc.bus.data_width,
            endianness = conf_soc.cpu.endianness,
        )
        rom_boot_address = conf_soc.mem_map["rom"]

        # ram_init = Path(__file__).parent.resolve() / "demo/demo.bin"
        # soc_args["integrated_main_ram_init"] = get_mem_data(
        #     ram_init,
        #     data_width = conf_soc.bus.data_width,
        #     endianness = conf_soc.cpu.endianness,
        #     offset     = conf_soc.mem_map["main_ram"]
        # )
        # ram_boot_address = get_boot_address(ram_init)
        # if ram_boot_address == 0:
        #     ram_boot_address = conf_soc.mem_map["main_ram"]

        # Instantiate the regular SimSoC
        SimSoC.__init__(self, **soc_args)

        cpu_parser = argparse.ArgumentParser()
        VexRiscvBridge.args_fill(cpu_parser)
        cpu_args = cpu_parser.parse_args([])
        cpu_args.cpu_count = 2
        cpu_args.icache_width = 32
        cpu_args.dcache_width = 32
        cpu_args.dcache_size  = 4096
        cpu_args.icache_size  = 4096
        cpu_args.dcache_ways  = 1
        cpu_args.icache_ways  = 1
        cpu_args.with_wishbone_memory = True
        cpu_args.with_rvc             = True
        cpu_args.without_coherent_dma = True
        cpu_args.with_formal          = False
        cpu_args.hardware_breakpoints = 0
        cpu_args.jtag_tap = False
        VexRiscvBridge.args_read(cpu_args)

        # self.add_constant("ROM_BOOT_ADDRESS", rom_boot_address)

        # # Create an RVFI bus instance and attach it to the CPU, as well as the
        # # CPU clock and reset lines:
        # self.submodules.cpu_rvfi = RiscvFormalInterface(
        #     xlen       = 32,
        #     ilen       = 32,
        #     nret       = cpu_args.cpu_count,
        # )
        # self.cpu.cpu_params |= {
        #     f"i_{sn}": getattr(self.cpu_rvfi, sn)
        #     for sn in filter(
        #         lambda sn: sn not in ["clk", "rst"],
        #         self.cpu_rvfi.signal_names,
        #     )
        # }

        # self.comb += [
        #     self.cpu_rvfi.clk.eq(self.cpu.cpu_params["i_debugCd_external_clk"]),
        #     self.cpu_rvfi.rst.eq(self.cpu.cpu_params["i_debugCd_external_reset"]),
        # ]

        # cpu_rvfi_slices = self.cpu_rvfi.slice_nret()

        # # Trace instructions into CSV file
        # for ret_idx, cpu_rvfi in enumerate(cpu_rvfi_slices):
        #     setattr(self.submodules, f"tracer_{ret_idx}", IbexTracer(
        #         cpu_rvfi,
        #         cpu_hart = ret_idx,
        #         platform = self.platform,
        #     ))

        # Store required parameters for the build phase
        self.build_args = {
            "default_builder_argdict": builder_argdict(litex_sim_parsed_dummy_args),
            "sys_clk_freq": sys_clk_freq,
            "trace": trace,
        }

    def build_soc(self):
        sim_config = SimConfig()
        sim_config.add_clocker("sys_clk", freq_hz=self.build_args["sys_clk_freq"])
        sim_config.add_module("serial2console", "serial")

        def pre_run_callback(vns):
            if self.build_args["trace"]:
                generate_gtkw_savefile(
                    builder, vns,
                    # Output fst file
                    True,
                )

        self.build_args["default_builder_argdict"]["csr_csv"] = \
            Path(__file__).parent.resolve() / "build" \
                / self.platform.name / "csr.csv"

        builder = Builder(self, **self.build_args["default_builder_argdict"])

        builder.build(
            threads          = 1,
            sim_config       = sim_config,
            opt_level        = "O3",
            trace            = self.build_args["trace"],
            trace_fst        = True,
            interactive      = True,
            pre_run_callback = pre_run_callback,
            verbose = True,
        )

if __name__ == "__main__":
    BridgeSimShell.run()
