#!/usr/bin/env bash
set -e
#
# helper wrappers around "vznncv-mbedgtw" command that adds default values for some parameters
#
VZNNCV_MBEDGTW_PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
VZNNCV_MBEDGTW_BOARD_MANAGER_SCRIPT="board_srcipt_manager.sh"
VZNNCV_MBEDGTW_TESTS_BY_NAME="TESTS-*"
export VZNNCV_MBEDGTW_PROJECT_DIR
export VZNNCV_MBEDGTW_BOARD_MANAGER_SCRIPT
export VZNNCV_MBEDGTW_TESTS_BY_NAME
# invoke command
vznncv-mbedgtw "$@"
