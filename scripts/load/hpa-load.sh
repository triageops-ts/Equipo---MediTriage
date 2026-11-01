#!/usr/bin/env bash
# Genera carga sobre el backend para probar el HPA
kubectl run carga -n triageops --rm -it --image=busybox:1.36 --restart=Never -- \
  sh -c 'for i in 1 2 3 4 5; do (while true; do wget -q -O- http://meditriage-backend/api/v1/health >/dev/null; done) & done; wait'
