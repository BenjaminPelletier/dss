#!/usr/bin/env bash

echo Reminder: must be run from monitoring folder

AUTH="DummyOAuth(http://host.docker.internal:8085/token,uss1)"
DSS="http://host.docker.internal:8082"
PUBLIC_KEY=""/var/test-certs/auth2.pem""
AUD="localhost"
BASE_URL="http://localhost:8086"
PORT=8086

docker build -t local-interuss/mockuss -f mockuss/Dockerfile .

docker run --name mockuss \
  --rm \
  -e MOCKUSS_AUTH_SPEC="${AUTH}" \
  -e MOCKUSS_DSS_URL="${DSS}" \
  -e MOCKUSS_PUBLIC_KEY="${PUBLIC_KEY}" \
  -e MOCKUSS_TOKEN_AUDIENCE="${AUD}" \
  -e MOCKUSS_BASE_URL="${BASE_URL}" \
  -p ${PORT}:5000 \
  -v `pwd`:/config \
  -v `pwd`/../build/test-certs:/var/test-certs:ro \
  local-interuss/mockuss \
  gunicorn \
    --preload \
    --workers=2 \
    --bind=0.0.0.0:5000 \
    monitoring.mockuss:webapp

# docker container exec -it mockuss cat /app/monitoring/mockuss/workspace/admin_password.txt
