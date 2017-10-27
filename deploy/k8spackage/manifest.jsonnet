local kpm = import "kpm.libjsonnet";

function(
  params={}
)

kpm.package({
   package: {
      name: "ant31/k8spackage",
      expander: "jinja2",
      author: "Antoine Legrand",
      version: "0.1.0-1",
      description: "k8spackage",
      license: "Apache 2.0",
    },

    variables: {
      appname: "k8spackage",
      namespace: 'default',
      image: "quay.io/ant31/k8spackage:v0.1.0",
      svc_type: "LoadBalancer",
    },

    resources: [
      {
        file: "k8spackage-dp.yaml",
        template: (importstr "templates/k8spackage-dp.yaml"),
        name: "k8spackage",
        type: "deployment",
      },

      {
        file: "k8spackage-svc.yaml",
        template: (importstr "templates/k8spackage-svc.yaml"),
        name: "k8spackage",
        type: "service",
      }
      ],


    deploy: [
      {
        name: "$self",
      },
    ],


  }, params)
