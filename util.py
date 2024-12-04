from abc import ABC
import argparse
import importlib.util
import sys
from pathlib import Path

from migen import Module, Replicate, Constant
from liteeth.phy.xgmii import XGMII_IDLE

from litex.soc.integration.builder import Builder, builder_argdict
from litex.soc.integration.builder import builder_args as builder_argparse_fn

class LiteXTarget(ABC):
    target_name = "Dummy LiteX SoC"

    def __init__(self):
        pass

    def target_args(parser):
        pass

    @classmethod
    def run(cls):
        # Instantiate the argument parser and add global options
        parser = argparse.ArgumentParser(
            description="Composite SoC",
            add_help=False,
        )
        parser.add_argument(
            "--help", default=False, action="store_true",
            help="Show this message",
        )

        # Store the base set of arguments, to be able to distinguish argument
        # groups from it.
        base_args = {action.dest for action in parser._actions}

        # First pass of argument parsing, to extract the ethcore which
        # should be instantiated.
        partial_args = parser.parse_known_args()[0]

        # Store the additional arguments added as part of this group
        base_args = {action.dest for action in parser._actions}

        # Add options for the target (specialization of this class)
        target_group = parser.add_argument_group(
            "target arguments (for {})".format(cls.target_name)
        )
        cls.target_args(target_group)

        # Store the additional arguments added as part of this group
        target_args = {action.dest for action in parser._actions} - base_args
        base_args = {action.dest for action in parser._actions}

        full_args = parser.parse_args()
        if full_args.help:
            parser.print_help()
            sys.exit(0)

        # Instantiate the target and start building
        target = cls(**{
            k: v
            for k, v in vars(full_args).items()
            if k in target_args
        })
        target.build_soc()

    # This method cannot be called build, as it would conflict with
    # SoCCore.build()
    def build_soc(self):
        # Get the default set of builder arguments
        from litex.build.parser import LiteXArgumentParser
        dummy_parser = LiteXArgumentParser()
        litex_builder_parsed_dummy_args = dummy_parser.parse_args([])
        builder_args = builder_argdict(litex_builder_parsed_dummy_args)


        # Builder
        builder_args["csr_csv"] = Path(__file__).parent.resolve() \
            / "build" / "netfpga_sume_platform" / "csr.csv"

        builder = Builder(self, **builder_args)
        builder.build(run=False, copy_deps=True)
        pass
