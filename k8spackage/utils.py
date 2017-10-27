from __future__ import absolute_import, division, print_function
import sys
import collections
import errno
import os
import os.path
import itertools


def package_filename(name, version, media_type):
    return "%s_%s_%s" % (name.replace("/", "_"), version, media_type)


def getenv(value, envname, default=None):
    if not value:
        if default:
            value = os.getenv(envname, default)
        else:
            value = os.environ[envname]
    return value


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def convert_utf8(data):
    try:
        if isinstance(data, basestring):
            return str(data)
        elif isinstance(data, collections.Mapping):
            return dict(map(convert_utf8, data.items()))
        elif isinstance(data, collections.Iterable):
            return type(data)(map(convert_utf8, data))
        else:
            return data
    except UnicodeEncodeError:
        return data


def flatten(array):
    return list(itertools.chain(*array))


def isbundled():
    return getattr(sys, 'frozen', False)


def get_current_script_path():
    executable = sys.executable
    if os.path.basename(executable) == "k8s-package":
        path = executable
    else:
        path = sys.argv[0]
    return os.path.realpath(path)


def abspath(relative_path):
    """ Get absolute path """
    if isbundled():
        base_path = sys.executable
    else:
        base_path = os.path.abspath(".")

    return os.path.realpath(os.path.join(base_path, relative_path))
