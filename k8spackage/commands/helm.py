from __future__ import absolute_import, division, print_function

import argparse
import os
import tempfile
import subprocess
from copy import copy
from k8spackage.commands.command_base import CommandBase
from k8spackage.commands.extract import ExtractCmd

LOCAL_DIR = os.path.dirname(__file__)


def helm_description(cmd, examples):
    return """
Fetch a Chart from the app-registry and execute `helm {cmd}`.
Helm's options can be passed on the command:
$ k8spackage helm {cmd} [K8SPACKAGE_OPTS] -- [HELM_OPTS]
{examples}

""".format(cmd=cmd, examples=examples)


class Helm(object):
    def __init__(self):
        pass

    def action(self, cmd, package_path, helm_opts=None):
        cmd = [cmd]
        if helm_opts:
            cmd = cmd + helm_opts
        cmd.append(package_path)
        return self._call(cmd)

    def _call(self, cmd):
        command = ['helm'] + cmd
        return subprocess.check_output(command, stderr=subprocess.STDOUT)


class HelmCmd(CommandBase):
    name = 'helm'
    help_message = 'Deploy with Helm on Kubernetes'
    parse_unknown = True
    plugin_subcommands = ['dep', 'install', 'upgrade']

    def __init__(self, options, unknown=None):
        super(HelmCmd, self).__init__(options, unknown)
        self.status = {}

    def exec_helm_cmd(self, cmd, options, helm_opts):
        pull_cmd = ExtractCmd(options)
        pull_cmd.exec_cmd(render=False)
        helm_cli = Helm()
        try:
            output = helm_cli.action(cmd, pull_cmd.path, helm_opts)
        except subprocess.CalledProcessError as exc:
            payload = {"message": str(exc.output)}
            self.render_error(payload)
            exit(exc.returncode)
        self.status = {'result': output}
        self.render()

    @classmethod
    def _install(cls, options, unknown=None):
        cmd = cls(options)
        cmd.exec_helm_cmd('install', options, unknown)

    @classmethod
    def _upgrade(cls, options, unknown=None):
        cmd = cls(options)
        cmd.exec_helm_cmd('upgrade', options, unknown)

    @classmethod
    def _init_args(cls, subcmd):
        cls._add_output_option(subcmd)
        src_group = subcmd.add_mutually_exclusive_group()
        src_group.add_argument("--digest", default=None, help="get by digest")
        src_group.add_argument("--from-file", default=None, help="Read content from a local file")
        src_group.add_argument("resource", nargs='?', default=None,
                               help="kubernetes resource name")
        subcmd.add_argument("-n", "--namespace", default="default", help="kubernetes namespace")
        subcmd.add_argument('-t', '--media-type', default='helm', help=argparse.SUPPRESS)

        subcmd.add_argument('--dest', default=tempfile.gettempdir(),
                            help='directory used to extract resources')
        subcmd.add_argument('--tarball', action='store_true', default=True, help=argparse.SUPPRESS)

    @classmethod
    def _add_arguments(cls, parser):
        from k8spackage.commands.cli_pkg import get_parser, all_commands
        sub = parser.add_subparsers()
        install_cmd = sub.add_parser(
            'install', help="Fetch the Chart and execute `helm install`",
            formatter_class=argparse.RawDescriptionHelpFormatter, description=helm_description(
                "install",
                "$ k8spackage helm install quay.io/ant31/cookieapp -- --set imageTag=v0.4.5 --namespace demo"
            ), epilog="\nhelm options:\n  See 'helm install --help'")
        upgrade_cmd = sub.add_parser(
            'upgrade', help="Fetch the Chart and execute `helm upgrade`",
            formatter_class=argparse.RawDescriptionHelpFormatter, description=helm_description(
                "upgrade",
                "$ k8spackage helm upgrade quay.io/ant31/cookieapp -- release-name --set foo=bar --set foo=newbar"
            ), epilog="\nhelm options:\n  See 'helm upgrade --help'")
        cls._init_args(install_cmd)
        cls._init_args(upgrade_cmd)
        install_cmd.set_defaults(func=cls._install)
        upgrade_cmd.set_defaults(func=cls._upgrade)

        other_cmds = copy(all_commands())
        other_cmds.pop("helm")
        get_parser(other_cmds, parser, sub, env={'K8SPACKAGE_DEFAULT_MEDIA_TYPE': 'helm'})

    def _render_dict(self):
        return self.status

    def _render_console(self):
        return self.status['result']
