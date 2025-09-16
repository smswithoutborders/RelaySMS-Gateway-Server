#!/bin/bash

logger() {
    local level=$1
    local message=$2
    local timestamp
    timestamp=$(date +"%Y-%m-%d %H:%M:%S")
    local source=$(basename $(readlink -f ${BASH_SOURCE[1]}))

    case $level in
    INFO)
        echo -e "\033[0;32m[$timestamp] [$source] [INFO] $message\033[0m"
        ;;
    WARNING)
        echo -e "\033[0;33m[$timestamp] [$source] [WARNING] $message\033[0m"
        ;;
    ERROR)
        echo -e "\033[0;31m[$timestamp] [$source] [ERROR] $message\033[0m"
        ;;
    *)
        echo -e "\033[0;37m[$timestamp] [$source] [UNKNOWN] $message\033[0m"
        ;;
    esac
}
