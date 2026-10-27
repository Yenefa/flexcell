#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/jazzy/setup.bash
source /opt/flexcell/upstream/install/setup.bash
source "$FLEXCELL_INSTALL/setup.bash"
export GZ_PARTITION=${GZ_PARTITION:-flexcell-ci-$$}
exec "$@"
