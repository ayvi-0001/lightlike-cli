#!/usr/bin/env bash

set -euo pipefail

export LIGHTLIKE_CLI_DEV=1
export LIGHTLIKE_CLI_DEV_EXPORT_HELP=1

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOTDIR="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOTDIR" || { echo 'Failed to find rootdir'; exit 2; }


_export_help() {
    local commands dest
    commands=("$@")
    dest=docs/assets/svg/

    python -m lightlike help || return # return if failed to acquire lock on 1st attempt
    mv help.svg "$dest"
    
    # shellcheck disable=SC2086
    for cmd in "${commands[@]}"; do
        python -m lightlike $cmd --help
        file="$(sed -r 's/\s+/_/g' <<< $cmd).svg"
        test -f "$file" && mv "$_" "$dest"
    done
}

declare -a app_commands app_config_commands bq_commands project_commands timer_commands commands

app_commands+=(
    "app"
    "app date-diff"
    "app dir"
    "app parse-date"
    "app run-bq"
    "app sync"
)
app_config_commands+=(
    "app config"
    "app config edit"
    "app config list"
    "app config set"
    "app config set query"
    "app config set query hide-table-render"
    "app config set query mouse-support"
    "app config set query save-query-info"
    "app config set query save-svg"
    "app config set query save-txt"
    "app config set general"
    "app config set general editor"
    "app config set general note-history"
    "app config set general quiet-start"
    "app config set general shell"
    "app config set general stay-logged-in"
    "app config set general timer-add-min"
    "app config set general timezone"
    "app config set general week-start"
)
bq_commands+=(
    "bq"
    "bq init"
    "bq projects"
    "bq query"
    "bq reset"
    "bq show"
    "bq snapshot"
    "bq snapshot create"
    "bq snapshot delete"
    "bq snapshot list"
    "bq snapshot restore"
)
project_commands+=(
    "project"
    "project archive"
    "project create"
    "project delete"
    "project list"
    "project set default-billable"
    "project set description"
    "project set name"
    "project set"
    "project unarchive"
)
timer_commands+=(
    "timer"
    "timer add"
    "timer delete"
    "timer edit"
    "timer get"
    "timer list"
    "timer notes update"
    "timer pause"
    "timer resume"
    "timer run"
    "timer show"
    "timer stop"
    "timer summary csv"
    "timer summary json"
    "timer summary table"
    "timer summary"
    "timer switch"
    "timer update"
)
commands+=(
    "${app_commands[@]}"
    "${app_config_commands[@]}"
    "${bq_commands[@]}"
    "${project_commands[@]}"
    "${timer_commands[@]}"
)


_export_help "${commands[@]}"
