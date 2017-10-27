from __future__ import absolute_import, division, print_function

import argparse
import os

from k8spackage.commands.generate import GenerateCmd
from k8spackage.commands.extract import ExtractCmd
from k8spackage.commands.helm import HelmCmd
from k8spackage.commands.version import VersionCmd
from k8spackage.commands.inspect import InspectCmd
from k8spackage.commands.get import GetCmd


def all_commands():
    return {
        HelmCmd.name: HelmCmd,
        VersionCmd.name: VersionCmd,
        ExtractCmd.name: ExtractCmd,
        InspectCmd.name: InspectCmd,
        GenerateCmd.name: GenerateCmd,
        GetCmd.name: GetCmd,
    }


def set_cmd_env(env):
    """ Allow commands to Set environment variables after being called """
    if env is not None:
        for key, value in env.items():
            os.environ[key] = value


def get_parser(commands, parser=None, subparsers=None, env=None):
    set_cmd_env(env)
    if parser is None:
        parser = argparse.ArgumentParser()

    if subparsers is None:
        subparsers = parser.add_subparsers(help='command help')

    for cls in commands.values():
        cls.add_parser(subparsers, env)

    return parser


def cli():
    try:
        parser = get_parser(all_commands())
        unknown = None
        args, unknown = parser.parse_known_args()
        if 'func' not in args:
            parser.print_help()
            return
        if 'parse_unknown' in args and args.parse_unknown:
            args.func(args, unknown)
        else:
            args = parser.parse_args()
            args.func(args)

    except (argparse.ArgumentTypeError, argparse.ArgumentError) as exc:
        if os.getenv("KUBECTL_PACKAGE_DEBUG", "false") == "true":
            raise
        else:
            parser.error(exc)
