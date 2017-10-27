import os
import json
import tempfile
import logging
import datetime
from copy import deepcopy

import requests
import yaml

from k8spackage.pack import pack_kub, K8spackagePackage
from k8spackage.utils import package_filename, mkdir_p
from k8spackage.exception import PackageAlreadyExists
import k8spackage.kubectl as kubectl

CRD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crd")
logging.basicConfig()
logger = logging.getLogger('k8s_events')
logger.setLevel(logging.DEBUG)


def load_spec(crd_file):
    with open(os.path.join(os.path.dirname(__file__), "crd", crd_file)) as f:
        return yaml.load(f.read())


class CrdModel(object):
    kind = None
    crd_spec = None

    def __init__(self, name):
        self.cr_instance = self.generate_cr(self.kind, name)
        self.status = ''

    def _filename(self):
        raise NotImplementedError

    @property
    def name(self):
        return self.cr_instance['metadata']['name']

    @name.setter
    def name(self, value):
        self.cr_instance['metadata']['name'] = value

    @property
    def spec(self):
        return self.cr_instance['spec']

    @spec.setter
    def spec(self, value):
        self.cr_instance['spec'] = value

    def add_label(self, key, value):
        self.cr_instance['metadata'][key] = value

    def add_field(self, key, value):
        self.cr_instance['spec'][key] = value

    def transform(self):
        pass

    def render(self):
        self.transform()
        self.validate()
        return self.cr_instance

    def write_to_file(self, dest=".", force=True):
        filepath = os.path.join(dest, self._filename() + ".yaml")
        if not force and os.path.isfile(filepath):
            raise PackageAlreadyExists("release-file already exists")
        with open(filepath, "w") as output:
            output.write(yaml.safe_dump(self.render()))
        return filepath

    def generate_cr(self, kind, name, spec=None, labels=None, annotations=None):
        cr_instance = {
            "apiVersion": "manifest.k8s.io/v1alpha1",
            "kind": kind,
            "metadata": {
                "name": name,
                "annotations": {},
                "labels": {}
            },
            "spec": {}
        }

        if spec:
            cr_instance['spec'] = spec
        if labels:
            cr_instance['metadata']['labels'] = labels
        if annotations:
            cr_instance['metadata']['annotations'] = annotations
        return cr_instance

    def validate(self):
        return True


class DescriptorCr(CrdModel):
    kind = "Descriptor"
    crd_spec = load_spec("descriptor.crd.yaml")

    def __init__(self, name, media_type=None):
        super(DescriptorCr, self).__init__(name)
        self.media_type = media_type

    @property
    def media_type(self):
        return self.spec['mediaType']

    @classmethod
    def from_chart(cls, chart):
        descriptor = cls(chart['name'], 'helm')

        for key in [
                'sources', 'maintainers', 'appVersion', 'icon', 'keywords', 'description',
                'appName', "created"
        ]:
            if key in chart:
                descriptor.add_field(key, chart[key])
        return descriptor

    @media_type.setter
    def media_type(self, value):
        self.add_field('mediaType', value)

    def _filename(self):
        return "descriptor.yaml"

    def validate(self):
        if not self.spec.get('mediaType', None):
            raise ValueError('Missing spec.mediaType')
        return True

    def transform(self):
        self.cr_instance['metadata']['labels']['mediaType'] = self.media_type
        for k, v in self.crd_spec['spec']['validation']['openAPIV3Schema']['properties'].items():
            if k not in self.cr_instance['spec']:
                val = ''
                if v['type'] == 'array':
                    val = []
                elif v['type'] == 'object':
                    val = {}
                self.cr_instance['spec'][k] = val  # "# %s # %s" % (val, v.get('description', ''))


class PackageCr(DescriptorCr):
    kind = "Package"
    crd_plural = 'packages'
    crd_group = 'manifest.k8s.io'
    crd_version = 'v1alpha1'
    columns = [
        ('name', "metadata.name"),
        ("app", "spec.packageName"),
        ("version", "spec.packageVersion"),
        ("mediatype", "spec.mediaType"),
        ("digest", "spec.content.digest"),
    ]
    crd_spec = load_spec("package.crd.yaml")

    def __init__(self, name=None, version=None, media_type=None, descriptor=None):
        super(PackageCr, self).__init__(name, media_type)
        if descriptor:
            self.descriptor = deepcopy(descriptor)
            self.spec.update(self.descriptor['spec'])
            self.cr_instance['metadata']['labels'].update(self.descriptor['metadata']['labels'])
            self.cr_instance['metadata']['annotations'].update(
                self.descriptor['metadata']['annotations'])
            if not name:
                name = self.descriptor['metadata']['name']
            if not version:
                version = self.descriptor['spec']['packageVersion']
            if not media_type:
                media_type = self.descriptor['spec']['mediaType']
        if not (name and version and media_type):
            raise ValueError("name, version and media_type are required %s,%s,%s" % (name, version,
                                                                                     media_type))

        self.add_field('packageName', name)
        self.add_field('packageVersion', version)
        self.add_field('created', str(datetime.datetime.utcnow()))
        self._k8spackage_package = None

    @classmethod
    def load(cls, resource):
        return cls(resource['spec']['packageName'], resource['spec']['packageVersion'],
                   descriptor=resource)

    def transform(self):
        self.name = "%s.%s" % (self.spec['packageName'], self.version)
        self.cr_instance['metadata']['labels']['digest'] = self.cr_instance['spec']['content'][
            'digest'][0:10]
        self.cr_instance['metadata']['labels']['packageName'] = self.package_name
        self.cr_instance['metadata']['labels']['mediaType'] = self.media_type

    @classmethod
    def from_helm_index(cls, index, offline=False):
        packages = []
        missed = []
        for name, releases in index['entries'].items():
            for release in releases:
                descriptor = DescriptorCr.from_chart(release).render()
                version = release['version']
                package = cls(name, version, 'helm', descriptor=descriptor)
                urls = release['urls']
                try:
                    logger.info("- %s.%s" % (name, version))
                    package.add_url(urls[0], offline)
                    packages.append(package.render())
                    if package.content['digest'] != release['digest']:
                        logger.error("warning: %s.%s" % (name, version))
                        logger.error("%s != %s" % (package.content['digest'], release['digest']))
                except requests.exceptions.RequestException as e:
                    missed.append((name, version))
        list_packages = {
            "apiVersion": "v1",
            "items": packages,
            "kind": "List",
            "metadata": {
                "resourceVersion": "",
                "selfLink": ""
            }
        }

        return list_packages

    @property
    def version(self):
        return self.spec['packageVersion']

    @version.setter
    def version(self, value):
        self.add_field('packageVersion', value)

    @property
    def package_name(self):
        return self.spec['packageName']

    def validate(self):
        if self.name != "%s.%s" % (self.package_name, self.version):
            raise ValueError("name must be packageName.packageVersion")
        if not self.version:
            raise ValueError("Missing spec.packageVersion")
        if not self.spec.get('mediaType', None):
            raise ValueError('Missing spec.mediaType')
        if not self.spec.get('content', None):
            raise ValueError('Missing spec.content')
        if not self.spec['content'].get('size', None):
            raise ValueError('Missing spec.content.size')
        if not self.spec['content'].get('digest', None):
            raise ValueError('Missing spec.content.digest')
        if not self.spec['content'].get('source', None):
            raise ValueError('Missing spec.content.source')

        return True

    def _filename(self):
        return package_filename(self.package_name, self.version, self.media_type)

    def prepare_content(self, path=".", prefix=None):
        filename = self._filename()
        kubepath = os.path.join(tempfile.gettempdir(), filename + ".tar.gz")
        pack_kub(kubepath, srcpath=path, prefix=prefix)
        with open(kubepath, 'rb') as kubefile:
            k8spackage_package = K8spackagePackage(kubefile.read(), b64_encoded=False)
        os.remove(kubepath)
        return k8spackage_package

    def add_blob(self, srcpath=".", prefix=None):
        k8spackage_package = self.prepare_content(srcpath, prefix)
        self._add_source(k8spackage_package, {'blob': k8spackage_package.b64blob})

    def _add_source(self, k8spackage_package, source):
        self.add_field('content', {
            'source': source,
            'size': k8spackage_package.size,
            'digest': k8spackage_package.digest
        })

    def add_url(self, url, offline=False):
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        k8spackage_package = K8spackagePackage(resp.raw.data, b64_encoded=False)
        if offline:
            self._add_source(k8spackage_package, {'blob': k8spackage_package.b64blob})
        else:
            self._add_source(k8spackage_package, {'urls': [url]})

    @property
    def content(self):
        return self.spec.get('content', None)

    @property
    def content_source(self):
        return self.spec.get('content', {}).get('source', {})

    @property
    def k8spackage_package(self):
        if self._k8spackage_package is None:
            if 'blob' in self.content_source:
                self._k8spackage_package = K8spackagePackage(self.content_source['blob'],
                                                             b64_encoded=True)
            elif 'urls' in self.content_source:
                resp = requests.get(self.content_source['urls'][0], stream=True)
                resp.raise_for_status()
                self._k8spackage_package = K8spackagePackage(resp.content, b64_encoded=False)
            else:
                raise ValueError("missing content")
        return self._k8spackage_package

    def extract(self, dest=".", tarball=True):
        k8spackage_package = self.k8spackage_package
        if not tarball:
            k8spackage_package.extract(dest)
        else:
            mkdir_p(dest)
            dest = os.path.join(dest, self._filename() + ".tar.gz")
            k8spackage_package.pack(dest)
        return dest

    @classmethod
    def get(cls, name, namespace='default'):
        return cls.load(json.loads(kubectl.get(cls.crd_plural, name, namespace, ["-o", "json"])))

    @classmethod
    def delete(cls, name, namespace='default'):
        return kubectl.delete(cls.crd_plural, name, namespace)

    @classmethod
    def list(cls, name=None, namespace='default', output='text', filters=None, opts=None):
        if not opts:
            opts = []
        if not filters:
            filters = {}
        labels = []
        for k, v in filters.items():
            labels.append("%s=%s" % (k, v))

        opts += ['-l', ','.join(labels)]
        if name:
            opts.append(name)

        if output == 'text':
            opts = opts + [
                '-o',
                'custom-columns=%s' % ','.join(["%s:%s" % (k.upper(), v) for k, v in cls.columns])
            ]
        else:
            opts = opts + ['-o', output]
        res = kubectl.list(cls.crd_plural, namespace, opts)
        if output == "yaml":
            return yaml.load(res)
        elif output == "json":
            return json.loads(res)
        else:
            return res

    @classmethod
    def find(cls, filters, namespace="default"):
        results = cls.list(filters=filters, output='json', namespace=namespace)
        if not results['items']:
            return None
        else:
            return cls.load(results['items'][0])
