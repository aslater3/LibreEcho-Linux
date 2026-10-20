#!/usr/bin/env bash
# Build this tree and the reference tree in libreecho/parity.json with the
# same toolchain and pinned build metadata, and require byte-identical
# outputs.  This holds while LibreEcho-Linux is meant to build exactly the
# production kernel from LibreEcho-Linux-6.1.
#
#   libreecho/parity_check.sh REFERENCE_CHECKOUT [WORK_DIR]
#
# REFERENCE_CHECKOUT must already be at the pinned ref.
set -euo pipefail

root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
ref_src=$(cd "${1:?usage: parity_check.sh REFERENCE_CHECKOUT [WORK_DIR]}" && pwd)
work=${2:-$(mktemp -d)}
manifest="$root/libreecho/parity.json"

want=$(jq -er .ref "$manifest")
have=$(git -C "$ref_src" rev-parse HEAD)
[ "$have" = "$want" ] || { echo "reference is at $have, expected $want" >&2; exit 2; }
defconfig=$(jq -er .defconfig "$manifest")
mapfile -t outputs < <(jq -er '.outputs[]' "$manifest")

# Pin everything the kernel build bakes in from the environment.
export KBUILD_BUILD_TIMESTAMP='Thu Jan  1 00:00:00 UTC 2026'
export KBUILD_BUILD_USER=libreecho KBUILD_BUILD_HOST=parity KBUILD_BUILD_VERSION=1
export SOURCE_DATE_EPOCH=1767225600

build() {
	local src=$1 out=$2
	local kmake=(make -C "$src" O="$out" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-
		LD=arm-linux-gnueabihf-ld.bfd)
	"${kmake[@]}" -s "$defconfig"
	"${kmake[@]}" -s olddefconfig
	"${kmake[@]}" -j"$(nproc)" zImage dtbs >"$out.log" 2>&1 ||
		{ tail -40 "$out.log" >&2; return 1; }
}

build "$ref_src" "$work/reference"
build "$root" "$work/this"

status=0
report="$work/parity.md"
{
	echo "## Build parity with $(jq -r .repository "$manifest") ${want:0:12}"
	echo
	echo "| Output | Result | sha256 |"
	echo "|---|---|---|"
} >"$report"
for f in "${outputs[@]}"; do
	sum=$(sha256sum "$work/this/$f" | cut -c1-16)
	if cmp -s "$work/reference/$f" "$work/this/$f"; then
		echo "| \`$f\` | identical | \`$sum\` |" >>"$report"
	else
		echo "| \`$f\` | **differs** | \`$sum\` |" >>"$report"
		status=1
	fi
done
cat "$report"
[ -z "${GITHUB_STEP_SUMMARY:-}" ] || cat "$report" >> "$GITHUB_STEP_SUMMARY"
exit "$status"
