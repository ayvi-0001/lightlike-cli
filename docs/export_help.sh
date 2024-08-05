#!/bin/bash

LIGHTLIKE_CLI_SOURCE_DIR=$(dirname $( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd ))
cd $LIGHTLIKE_CLI_SOURCE_DIR

export LIGHTLIKE_CLI_DEV=1
export LIGHTLIKE_CLI_DEV_EXPORT_HELP=1
export LIGHTLIKE_CLI_DEV_USERNAME=user
export LIGHTLIKE_CLI_DEV_HOSTNAME=host

_export_help() {
    python -m lightlike help || return # return if failed to acquire lock on 1st attempt
    mv help.svg docs/assets/svg/

    for cmd in "${commands[@]}"; do
        python -m lightlike $cmd --help
        mv $(echo "$cmd" | sed -r 's/\s+/_/g').svg docs/assets/svg/
    done
}

commands=(
    "app" "app sync" "app run-bq" "app dir" "app config" "app config list" "app config edit" "app config set"
    "app config set query" "app config set query save_txt" "app config set query save_svg" "app config set query save_query_info"
    "app config set query mouse_support" "app config set query hide_table_render" "app config set general"
    "app config set general week_start" "app config set general timezone" "app config set general timer_add_min" "app config set general stay_logged_in"
    "app config set general shell" "app config set general quiet_start" "app config set general note_history" "app config set general editor"
    "app date-diff" "app parse-date-arg" "app parse-date-opt"
    "bq" "bq snapshot" "bq snapshot restore" "bq snapshot list" "bq snapshot delete" "bq snapshot create" "bq show" "bq reset" "bq query" "bq projects" "bq init"
    "project" "project unarchive" "project set" "project set name" "project set description" "project set default_billable" "project list" "project delete" "project create" "project archive"
    "timer summary" "timer summary table" "timer summary json" "timer summary csv"
    "timer" "timer update" "timer switch" "timer stop" "timer show" "timer run" "timer resume" "timer pause" "timer notes update" "timer list" "timer get" "timer edit" "timer delete" "timer add"
)

_export_help
