#!/bin/bash

# Prerequisites
jq --version > /dev/null
if [ $? -ne 0 ]; then
  echo "This script requires the jq utility.  On Debian Linux, install with"
  echo "  sudo apt-get install jq"
  echo "With homebrew, install with"
  echo "  brew install jq"
  exit 1
fi

# Auth server
docker container kill dss_auth_server
docker container rm dss_auth_server

docker image build -f ./authserver/docker/Dockerfile_authserver -t interuss/auth_server ./authserver

docker run -p 8082:8082 --name dss_auth_server -d interuss/auth_server

sleep 1

export ACCESS_TOKEN=`curl --silent -X POST --user uss1:uss1 \
  "http://localhost:8082/oauth/token?grant_type=client_credentials&aud=localhost" \
  | jq -r '.access_token'`

# DSS
docker container kill dss_server
docker container rm dss_server

docker image build -f ./datanode/docker/Dockerfile_dsslogic -t interuss/dsslogic ./datanode

docker run -e INTERUSS_PUBLIC_KEY="`cat ./authserver/docker/public.pem`" -e INTERUSS_TOKEN_AUDIENCE="localhost" -p 8081:8081 --name dss_server -d interuss/dsslogic

sleep 1

# Retrieve Operations currently active on Mauna Loa
echo "DSS response to Mauna Loa Operations query (should be empty operation_references list):"
echo "============="
curl --silent -X POST \
  "http://localhost:8081/dss/v1/operations/query" \
  -H "Content-Type: application/json" \
  --data '{"area_of_interest":{"altitude_lower":{"reference":"W84","units":"M","value":0},"altitude_upper":{"reference":"W84","units":"M","value":3000},"volume":{"outline_polygon":{"type":"Polygon","coordinates":[[[-155.6043,19.4763],[-155.5746,19.4884],[-155.5941,19.4516],[-155.6043,19.4763]]]}}}}' \
  -H "Authorization: Bearer ${ACCESS_TOKEN}"
echo
echo "============="
