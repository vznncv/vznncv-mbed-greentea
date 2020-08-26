#!/usr/bin/env bash
#
# Helper script to run greentea tests with OpenOCD and a separate USB-UART adapter
#
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

##
# Project configuration
##

# custom target name
TARGET_NAME='BLUEPILL'
# hexidemical target code. If you isn't able to extract target id,
# use any constant value that contains at least 4 digits.
TARGET_ID='FFFF00000000000000000000'
# USB-UART adapter USB VID and PID.
# They are used to find corresponding serial port.
# USB-UART model: CH340
TARGET_SERIAL_PORT_USB_VID='1a86'
TARGET_SERIAL_PORT_USB_PID='7523'
# image format to flush (bin, hex or elf)
TARGET_IMAGE_FORMAT='elf'
# OpenOCD path
OPENOCD_PATH='openocd'
# OpenOCD target configuration
OPENOCD_TARGET_CONFIG="$PROJECT_DIR/openocd_target.cfg"

##
# Script code
##

function log_err() {
    echo "ERROR: $*" 1>&2
}

function log_info() {
    echo "INFO: $*" 1>&2
}

function find_serial_port_by_pid_vid() {
    local target_vid="${1,,}"
    local target_pid="${2,,}"
    local device_path
    local device_data
    local device_vid
    local device_pid

    for device_path in "/dev/serial/by-id/"*; do
        device_path=$(readlink -e "$device_path")
        device_data=$(udevadm info --query=property "$device_path")
        device_vid=$(sed -n -E 's/^ID_VENDOR_ID=(.*)$/\1/p' <<<"$device_data")
        device_vid="${device_vid,,}" # ensure that lowercase is used
        device_pid=$(sed -n -E 's/^ID_MODEL_ID=(.*)$/\1/p' <<<"$device_data")
        device_pid="${device_pid,,}" # ensure that lowercase is used
        if [[ "$target_vid" == "$device_vid" && "$target_pid" == "$device_pid" ]]; then
            echo "$device_path"
            break
        fi
    done
}

function list_targets() {
    local target_serial
    target_serial=$(find_serial_port_by_pid_vid "$TARGET_SERIAL_PORT_USB_VID" "$TARGET_SERIAL_PORT_USB_PID")
    if [[ -z "$target_serial" ]]; then
        # no serial interfaces are found. Assumes that we have no devices
        echo "[]"
    else
        # serial interface is found. Assume that device is connected
        echo "[{"
        echo "   \"target_id\": \"$TARGET_ID\","
        echo "   \"target_name\": \"$TARGET_NAME\","
        echo "   \"serial_port\": \"$target_serial\","
        echo "   \"image_format\": \"$TARGET_IMAGE_FORMAT\","
        echo "   \"reset_command\": false"
        echo "}]"
    fi
}

function flash_target() {
    local target_id
    local image_path
    local openocd_cmd

    while [[ $# -gt 0 ]]; do
        case "$1" in
        --target-id)
            target_id="$2"
            shift
            shift
            ;;
        --image-path)
            image_path="$2"
            shift
            shift
            ;;
        *)
            log_err "Unknown argument $1"
            return 1
            ;;
        esac
    done
    if [[ -z "$target_id" ]]; then
        log_err "--target-id isn't set"
        return 1
    fi
    if [[ -z "$image_path" ]]; then
        log_err "--image-path isn't set"
        return 1
    fi

    if [[ "$target_id" != "$TARGET_ID" ]]; then
        log_err "Unknown target $target_id"
        return 1
    fi

    # prepare and run openocd command
    openocd_cmd=("$OPENOCD_PATH" "-f" "$OPENOCD_TARGET_CONFIG" "-c" "program \"$image_path\" verify reset exit")
    log_info "run command \"${openocd_cmd[*]}\""
    "${openocd_cmd[@]}"
    return $?
}

function reset_target() {
    local target_id
    local image_path
    local openocd_cmd

    while [[ $# -gt 0 ]]; do
        case "$1" in
        --target-id)
            target_id="$2"
            shift
            shift
            ;;
        *)
            log_err "Unknown argument $1"
            return 1
            ;;
        esac
    done
    if [[ -z "$target_id" ]]; then
        log_err "--target-id isn't set"
        return 1
    fi

    log_err "Reset functionality isn't implemented"
    return $?
}

# parse command
main_cmd="$1"
shift
case "$main_cmd" in
list)
    list_targets "${@}"
    ret_code=$?
    ;;
flash)
    flash_target "${@}"
    ret_code=$?
    ;;
reset)
    reset_target "${@}"
    ret_code=$?
    ;;
*)
    log_err "Unknown command: $main_cmd"
    exit 1
    ;;
esac
exit "$ret_code"
