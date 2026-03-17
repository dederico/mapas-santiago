#!/bin/sh
set -eu

cd "$(dirname "$0")"
PORT="${PORT:-8081}" python3 server.py
