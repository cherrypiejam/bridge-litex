import os
from pathlib import Path
from migen import Module, Signal, Constant, Instance

class RiscvFormalInterface(Module):
    def __init__(
        self,
        xlen=32, ilen=32, nret=1,
        with_clk=True, with_rst=True, with_isn_meta=True, with_int_reg=True,
        with_pc=True, with_mem=True, with_spec_exec=True, csr_names=set(),
    ):
        assert xlen % 8 == 0
        assert ilen % 8 == 0 # perhaps some stronger assertions here?
        assert type(nret) == int and nret >= 1

        # Collect all parameter-value bindings into a dictionary automatically
        # and store that as a member variable:
        import inspect
        parameter_args = set(filter(
            lambda arg: arg != "self",
            inspect.getfullargspec(__class__.__init__).args,
        ))
        self.params = dict(filter(
            lambda local_item: local_item[0] in parameter_args,
            locals().items(),
        ))

        interface = dict()

        if with_clk:
            interface["clk"] = Signal()

        if with_rst:
            interface["rst"] = Signal()

        # Instruction Metadata
        if with_isn_meta:
            interface |= dict(
                rvfi_valid = Signal(nret),
                rvfi_order = Signal(nret * 64),
                rvfi_insn = Signal(nret * ilen),
                rvfi_trap = Signal(nret),
                rvfi_halt = Signal(nret),
                rvfi_intr = Signal(nret),
                rvfi_mode = Signal(nret * 2),
                rvfi_ixl = Signal(nret * 2),
            )

        # Integer Register Read/Write
        if with_int_reg:
            interface |= dict(
                rvfi_rs1_addr = Signal(nret * 5),
                rvfi_rs2_addr = Signal(nret * 5),
                rvfi_rs1_rdata = Signal(nret * xlen),
                rvfi_rs2_rdata = Signal(nret * xlen),
                rvfi_rd_addr = Signal(nret * 5),
                rvfi_rd_wdata = Signal(nret * xlen),
            )

        # Program Counter
        if with_pc:
            interface |= dict(
                rvfi_pc_rdata = Signal(nret * xlen),
                rvfi_pc_wdata = Signal(nret * xlen),
            )

        # Memory Access
        if with_mem:
            interface |= dict(
                rvfi_mem_addr = Signal(nret * xlen),
                rvfi_mem_rmask = Signal(nret * (xlen//8)),
                rvfi_mem_wmask = Signal(nret * (xlen//8)),
                rvfi_mem_rdata = Signal(nret * xlen),
                rvfi_mem_wdata = Signal(nret * xlen),
            )

        # Control and Status Registers (CSRs)
        for csr_name in csr_names:
            interface |= {
                f"rvfi_csr_{csr_name}_rmask": Signal(nret * xlen),
                f"rvfi_csr_{csr_name}_wmask": Signal(nret * xlen),
                f"rvfi_csr_{csr_name}_rdata": Signal(nret * xlen),
                f"rvfi_csr_{csr_name}_wdata": Signal(nret * xlen),
            }

        # Store a set of signal names for programmatic member access and
        # rewriting:
        self.signal_names = set(interface.keys())

        # Also store a subset of signals whose bit width is multiplied by nret,
        # for slicing & splicing:
        self.nret_signal_names = set(filter(
            lambda signal_name: signal_name not in ["clk", "rst"],
            self.signal_names,
        ))

        # Now, store all signals as member variables on this object:
        for k, v in interface.items():
            setattr(self, k, v)

    def slice_nret(self):
        nret = self.params["nret"]
        sliced = []

        for ret_idx in range(0, nret):
            sliced_params = self.params | {
                "nret": 1,
            }

            tgt = __class__(**sliced_params)

            for signal_name in (self.signal_names - self.nret_signal_names):
                self.comb += [
                    getattr(tgt, signal_name).eq(getattr(self, signal_name))
                ]

            for signal_name in self.nret_signal_names:
                nret_signal = getattr(self, signal_name)
                assert (len(nret_signal) / nret).is_integer()
                width = len(nret_signal) // nret
                assert len(getattr(tgt, signal_name)) == width
                self.comb += [
                    getattr(tgt, signal_name).eq(
                        nret_signal[ret_idx*width:(ret_idx+1)*width])
                ]

            sliced += [tgt]

        return sliced

class IbexTracer(Module):
    def __init__(self, rvfi, cpu_hart, platform=None):
        # This can only process 1 instruction at a time. For a CPU which can
        # retire multiple instructions at a time, we'd need to instantiate multiple
        # tracers:
        assert rvfi.params["nret"] == 1

        self.specials += Instance(
            "ibex_tracer",

            i_clk_i          = rvfi.clk,
            i_rst_ni         = ~rvfi.rst,

            i_hart_id_i      = Constant(cpu_hart, bits_sign=32),

            i_rvfi_valid     = rvfi.rvfi_valid,
            i_rvfi_order     = rvfi.rvfi_order,
            i_rvfi_insn      = rvfi.rvfi_insn,
            i_rvfi_trap      = rvfi.rvfi_trap,
            i_rvfi_halt      = rvfi.rvfi_halt,
            i_rvfi_intr      = rvfi.rvfi_intr,
            i_rvfi_mode      = rvfi.rvfi_mode,
            i_rvfi_ixl       = rvfi.rvfi_ixl,
            i_rvfi_rs1_addr  = rvfi.rvfi_rs1_addr,
            i_rvfi_rs2_addr  = rvfi.rvfi_rs2_addr,
            i_rvfi_rs3_addr  = Constant(0, bits_sign=len(rvfi.rvfi_rs1_addr)),
            i_rvfi_rs1_rdata = rvfi.rvfi_rs1_rdata,
            i_rvfi_rs2_rdata = rvfi.rvfi_rs2_rdata,
            i_rvfi_rs3_rdata = Constant(0, bits_sign=len(rvfi.rvfi_rs1_rdata)),
            i_rvfi_rd_addr   = rvfi.rvfi_rd_addr,
            i_rvfi_rd_wdata  = rvfi.rvfi_rd_wdata,
            i_rvfi_pc_rdata  = rvfi.rvfi_pc_rdata,
            i_rvfi_pc_wdata  = rvfi.rvfi_pc_wdata,
            i_rvfi_mem_addr  = rvfi.rvfi_mem_addr,
            i_rvfi_mem_rmask = rvfi.rvfi_mem_rmask,
            i_rvfi_mem_wmask = rvfi.rvfi_mem_wmask,
            i_rvfi_mem_rdata = rvfi.rvfi_mem_rdata,
            i_rvfi_mem_wdata = rvfi.rvfi_mem_wdata,
        )

        if platform is not None:
            import pythondata_cpu_ibex
            base_path = os.path.join(pythondata_cpu_ibex.data_location, "rtl")
            platform.add_source(os.path.join(base_path, "ibex_pkg"))
            platform.add_source(os.path.join(base_path, "ibex_tracer_pkg"))
            platform.add_source(os.path.join(base_path, "ibex_tracer"))
