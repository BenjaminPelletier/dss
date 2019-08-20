#!/bin/bash

set -e

if [[ "$#" -ne 1 ]]; then
    echo "Usage: $0 NAMESPACE"
    exit 1
fi

NAMESPACE="$1"

set -x

# Paths to directories in which to store certificates and generated YAML files.
DIR="$(pwd)"
CLIENTS_CERTS_DIR="$DIR/generated/$NAMESPACE/client_certs_dir"
NODE_CERTS_DIR="$DIR/generated/$NAMESPACE/node_certs_dir"
CONTEXT="$(kubectl config current-context)"
TEMPLATES_DIR="$DIR/templates"

# Delete previous secrets in case they have changed.
kubectl create namespace "$NAMESPACE" --context "$CONTEXT" || true

kubectl delete secret cockroachdb.client.root --context "$CONTEXT" || true
kubectl delete secret cockroachdb.client.root --namespace "$NAMESPACE" --context "$CONTEXT" || true
kubectl delete secret cockroachdb.node --namespace "$NAMESPACE" --context "$CONTEXT" || true

kubectl create secret generic cockroachdb.client.root --from-file "$CLIENTS_CERTS_DIR" --context "$CONTEXT"
kubectl create secret generic cockroachdb.client.root --namespace "$NAMESPACE" --from-file "$CLIENTS_CERTS_DIR" --context "$CONTEXT"
kubectl create secret generic cockroachdb.node --namespace "$NAMESPACE" --from-file "$NODE_CERTS_DIR" --context "$CONTEXT"