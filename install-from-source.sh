#!/bin/sh
# SPDX-License-Identifier: AGPL-3.0-only
set -eu
sptl_source_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$sptl_source_root/tools/install_source.py" "$@"
