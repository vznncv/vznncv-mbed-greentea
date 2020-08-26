#!/usr/bin/env bash
function log_err() {
    echo "ERROR: $*" 1>&2
}

function log_info() {
    echo "INFO: $*" 1>&2
}

# check test configuration
if [[ -z "$TEST_TARGET_NAME" ]]; then
    log_err "TEST_TARGET_NAME isn't set"
    exit 1
fi
if [[ -z "$TEST_TARGET_ID" ]]; then
    log_err "TEST_TARGET_ID isn't set"
    exit 1
fi
if [[ -z "$TEST_SERIAL_PORT" ]]; then
    log_err "TEST_SERIAL_PORT isn't set"
    exit 1
fi
if [[ -z "$TEST_IMAGE_FORMAT" ]]; then
    log_err "TEST_IMAGE_FORMAT isn't set"
fi
if [[ -z "$TEST_RESET_METHOD" ]]; then
    log_err "TEST_RESET_METHOD isn't set"
fi
if [[ "$TEST_TARGET_IS_CONNECTED" != "1" ]]; then
    TEST_TARGET_IS_CONNECTED=0
fi

function list_targets() {
    if [[ "$TEST_TARGET_IS_CONNECTED" == "1" ]]; then
        echo "[{"
        echo "   \"target_id\": \"$TEST_TARGET_ID\","
        echo "   \"target_name\": \"$TEST_TARGET_NAME\","
        echo "   \"serial_port\": \"$TEST_SERIAL_PORT\","
        echo "   \"image_format\": \"$TEST_IMAGE_FORMAT\","
        echo "   \"reset_command\": $TEST_RESET_METHOD"
        echo "}]"
    else
        echo "[]"
    fi
}

function flash_target() {
    local target_id
    local image_path

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

    if [[ "$target_id" != "$TEST_TARGET_ID" ]]; then
        log_err "Unknown target $target_id"
        return 1
    fi

    if [[ ! -f "$image_path" ]]; then
        log_err "image \"$image_path\" doesn't exists"
        return 1
    fi
    local image_name
    image_name=$(basename "$image_path")
    local image_ext="${image_name##*.}"
    if [[ "$image_ext" != "$TEST_IMAGE_FORMAT" ]]; then
        log_err "Expected image with extension \"$image_ext\", but it was \"$TEST_IMAGE_FORMAT\"."
        return 1
    fi

    log_info "flash command is invoked"
    return 0
}

function reset_target() {
    local target_id
    local image_path

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

    if [[ "$target_id" != "$TEST_TARGET_ID" ]]; then
        log_err "Unknown target $target_id"
        return 1
    fi

    log_info "flash command is invoked"
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
