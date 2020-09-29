#!/usr/bin/env bash

AUTH='DummyOAuth(https://auth.example.com,uss1)'
DSS='https://dss.example.com'
PUBLIC_KEY='https://auth.example.com/.well-known/jwks.json'
AUD='mockuss.example.com'
BASE_URL='https://mockuss.example.com'
PORT=5001

docker run --name mockuss \
  --rm \
  -e MOCKUSS_AUTH_SPEC="${AUTH}" \
  -e MOCKUSS_DSS_URL="${DSS}" \
  -e MOCKUSS_PUBLIC_KEY="${PUBLIC_KEY}" \
  -e MOCKUSS_TOKEN_AUDIENCE="${AUD}" \
  -e MOCKUSS_BASE_URL="${BASE_URL}" \
  -p ${PORT}:5000 \
  -v `pwd`:/config \
  interuss/dss/mockuss \
  gunicorn \
    --preload \
    --workers=2 \
    --bind=0.0.0.0:5000 \
    monitoring.mockuss:webapp
