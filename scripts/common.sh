#!/bin/bash

SCRIPT_DIR=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
source "${SCRIPT_DIR}/logger.sh" || exit 1

load_env() {
    local env_file=$1

    if [ -f $env_file ]; then
        logger INFO "Loading environment variables from $env_file."
        set -a
        source $env_file
        set +a
    else
        logger WARNING "Environment file not found at $env_file. Skipping loading."
    fi
}
