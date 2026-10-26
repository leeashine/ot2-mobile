#!/usr/bin/env bash
set -euo pipefail

# OT2 Mac launcher. Click the game window before using the keyboard.
# Keys: WASD left stick; arrows D-pad; Return/Space A; Esc/Delete B;
# X/Tab X; Y Y; Q/E L/R; Z/C ZL/ZR; F/G L3/R3; P/O +/-. Cmd-Q quits.
# Save data stays in <OT2_WORK>/run/save; temporary files stay in run/temp.
# Pass the NSP folder, run from it, or set OT2_WORK to <NSP>/<title ID>_build.

GAME_ID=0100A3501946E000
if (( $# > 1 )); then
    printf 'Usage: %s [NSP folder]\n' "$0" >&2
    exit 2
fi
if [[ -n "${OT2_WORK:-}" ]]; then
    WORK="$OT2_WORK"
else
    NSP_DIR="${1:-$PWD}"
    WORK="$NSP_DIR/${GAME_ID}_build"
fi
[[ -d "$WORK" ]] || { printf 'Missing build work directory: %s\nRun the README Mac build first, or set OT2_WORK.\n' "$WORK" >&2; exit 1; }
WORK="$(cd -- "$WORK" && pwd)"
REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HOST="$WORK/tools/dmhost"
PATCHED="$WORK/patched_v0"
ROMFS="$WORK/extract/v0/RomFS"
SAVE="$WORK/run/save"
TEMP="$WORK/run/temp"
MSL="$WORK/shader/cache"
FONT="$WORK/font"
PROFILE="$WORK/nvn-profile/$GAME_ID"
if [[ ! -f "$PROFILE/shader_map.tsv" ]]; then
    PROFILE="$REPO/dm/games/$GAME_ID"
fi

missing() {
    printf 'Missing %s: %s\nRun the README Mac build first.\n' "$1" "$2" >&2
    exit 1
}
[[ -x "$HOST" ]] || missing 'Mac host' "$HOST"
[[ -d "$PATCHED" ]] || missing 'rewritten game modules' "$PATCHED"
[[ -d "$ROMFS" ]] || missing 'extracted RomFS' "$ROMFS"
[[ -f "$PROFILE/shader_map.tsv" ]] || missing 'NVN shader map' "$PROFILE/shader_map.tsv"
[[ -f "$PROFILE/c1_full.tsv" && -f "$PROFILE/cb_extent.tsv" ]] || missing 'shader runtime tables' "$PROFILE"
[[ -f "$FONT/nintendo_ext.ttf" ]] || missing 'Nintendo extension font' "$FONT/nintendo_ext.ttf"
CHAIN="$(python3 "$REPO/dm/gfx/tools/dmsh_chain.py")"
[[ -d "$MSL/b-$CHAIN" ]] || missing 'Mac shader libraries' "$MSL/b-$CHAIN"

mkdir -p "$SAVE" "$TEMP"
printf 'Work directory: %s\nSave directory: %s\n' "$WORK" "$SAVE"
cd -- "$WORK/run"
ENV_ARGS=(
    "OT2_WORK=$WORK"
    "DM_ROOT=$WORK"
    "DM_ROMFS=$ROMFS"
    "DM_SAVE=$SAVE"
    "DM_TEMP=$TEMP"
    "DM_MSL_DIR=$MSL"
    "DM_FONT_DIR=$FONT"
    "DM_NVN_SHMAP=$PROFILE/shader_map.tsv"
    "DM_LANG=${DM_LANG:-en-US}"
    "DM_WINDOW=1"
    "DM_AUDIO=1"
    "OT2_NVN_HLE=1"
    "OT2_NVN_OFFLINE_SHADERS=1"
)
if [[ -d "$WORK/aoc" ]]; then
    ENV_ARGS+=("DM_AOC_DIR=$WORK/aoc")
fi
exec /usr/bin/nice -n 10 /usr/bin/env "${ENV_ARGS[@]}" "$HOST" "$PATCHED"
