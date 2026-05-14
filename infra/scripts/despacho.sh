#!/usr/bin/env bash
# Atajo: git add + commit + push. Uso: ./infra/scripts/despacho.sh "mensaje"
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Uso: $0 \"mensaje de commit\""
    exit 1
fi

git add -A
git commit -m "$1"
git push origin "$(git rev-parse --abbrev-ref HEAD)"
