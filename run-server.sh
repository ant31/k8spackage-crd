#!/bin/bash
PORT=${PORT:-5000}
gunicorn k8spackage.api.wsgi:app -b :$PORT --timeout 120 -w 4 --reload
