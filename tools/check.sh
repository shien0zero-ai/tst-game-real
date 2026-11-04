#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if command -v godot >/dev/null 2>&1; then
    engine=godot
elif command -v godot4 >/dev/null 2>&1; then
    engine=godot4
else
    echo "Godot 4.6.3 or later is required (godot / godot4)." >&2
    exit 1
fi

runtime_dir="$project_dir/work/godot"
mkdir -p "$runtime_dir/cache" "$runtime_dir/config" "$runtime_dir/data"
touch "$project_dir/work/.gdignore"
export XDG_CACHE_HOME="$runtime_dir/cache"
export XDG_CONFIG_HOME="$runtime_dir/config"
export XDG_DATA_HOME="$runtime_dir/data"

run_check() {
    check_name=$1
    shift
    if ! "$engine" "$@" > "$runtime_dir/$check_name.log" 2>&1; then
        cat "$runtime_dir/$check_name.log"
        return 1
    fi
    cat "$runtime_dir/$check_name.log"
    # Godot may return success even when a script or resource fails to load.
    if grep -Eq 'SCRIPT ERROR:|(^|[[:space:]])ERROR:' "$runtime_dir/$check_name.log"; then
        return 1
    fi
}

run_check import --headless --path "$project_dir" --editor --quit
run_check smoke --headless --path "$project_dir" --fixed-fps 60 --script res://tests/smoke.gd
run_check shooting --headless --path "$project_dir" --fixed-fps 60 --script res://tests/shooting.gd
run_check settings --headless --path "$project_dir" --fixed-fps 60 --script res://tests/settings.gd
run_check inspection --headless --path "$project_dir" --fixed-fps 60 --script res://tests/inspection.gd
