#!/usr/bin/env bash
# Build a zip for AWS Lambda Python 3.14 using the official Lambda base image
# so Pillow native wheels match the runtime (glibc / arch).
#
# Usage:
#   ./build-lambda-package.sh           # x86_64 (default)
#   LAMBDA_ARCH=arm64 ./build-lambda-package.sh
#
# Requires: Docker. Upload deployment.zip; set handler to lambda_function.lambda_handler.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
STAGE="${ROOT}/.lambda-package"
ZIP="${ROOT}/deployment.zip"
IMAGE="public.ecr.aws/lambda/python:3.14"
ARCH="${LAMBDA_ARCH:-amd64}"
case "$ARCH" in
  amd64) PLATFORM="linux/amd64" ;;
  arm64) PLATFORM="linux/arm64" ;;
  *)
    echo "LAMBDA_ARCH must be amd64 or arm64 (got: ${LAMBDA_ARCH})" >&2
    exit 1
    ;;
esac

rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE"
cp "${ROOT}/lambda_function.py" "$STAGE/"

docker run --rm --platform "$PLATFORM" \
  --entrypoint /bin/bash \
  -v "${ROOT}/requirements.txt:/tmp/requirements.txt:ro" \
  -v "${STAGE}:/out" \
  "$IMAGE" \
  -c 'pip install --no-cache-dir -r /tmp/requirements.txt -t /out'

( cd "$STAGE" && zip -qr "$ZIP" . )
echo "Wrote ${ZIP} (platform ${PLATFORM}). Match Lambda architecture (x86_64 vs arm64)."
