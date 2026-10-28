#!/usr/bin/env bash
set -euo pipefail
data_env=${1:?Usage: create_data_env.sh /absolute/path/to/new/venv}
data_repo=$(cd "$(dirname "$0")/.." && pwd)
test ! -e "$data_env"
python3.12 -m venv "$data_env"
"$data_env/bin/python" -m pip install 'pip==25.1.1'
"$data_env/bin/python" -m pip install --index-url https://download.pytorch.org/whl/cpu \
  'torch==2.7.1+cpu' 'torchvision==0.22.1+cpu'
"$data_env/bin/python" -m pip install -r "$data_repo/infra/data-environment.lock"
"$data_env/bin/python" -m pip check
"$data_env/bin/python" -m pip freeze > "$data_env/freeze.txt"
