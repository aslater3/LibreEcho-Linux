#!/usr/bin/env bash
# Replay the LibreEcho series onto the latest stable release of the next LTS
# and report which commits apply cleanly.  If every commit applies, also try
# to build the production defconfig.
#
# Our commits are the non-merge commits on the first-parent chain since the
# 6.1 branch point: stable updates arrive as merges and are skipped.
#
#   libreecho/next_lts_canary.sh [--strict] [NEXT_LTS]    (default 6.18)
#
# Writes a Markdown report to stdout (and to $GITHUB_STEP_SUMMARY when set).
# Exits non-zero on infrastructure errors; with --strict, also when a commit
# does not apply or the build fails.
set -euo pipefail

STRICT=0
if [ "${1:-}" = "--strict" ]; then
	STRICT=1
	shift
fi
NEXT_LTS=${1:-6.18}
BRANCH_POINT=${BRANCH_POINT:-v6.1.178}
STABLE_URL=${STABLE_URL:-https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git}
WORK=${WORK:-$(mktemp -d)}

root=$(git rev-parse --show-toplevel)
cd "$root"

if ! git rev-parse -q --verify "refs/tags/$BRANCH_POINT" >/dev/null; then
	git fetch -q --depth 1 "$STABLE_URL" "refs/tags/$BRANCH_POINT:refs/tags/$BRANCH_POINT"
fi
tag=$(git ls-remote --tags --refs "$STABLE_URL" "v$NEXT_LTS.*" |
	awk -F/ '{print $3}' | sort -V | tail -1)
[ -n "$tag" ] || { echo "no v$NEXT_LTS.y tag found" >&2; exit 2; }
git fetch -q --depth 1 "$STABLE_URL" "refs/tags/$tag:refs/tags/$tag"

mapfile -t series < <(git rev-list --reverse --first-parent --no-merges "$BRANCH_POINT..HEAD")
[ "${#series[@]}" -gt 0 ] || { echo "no LibreEcho commits since $BRANCH_POINT" >&2; exit 2; }

tree="$WORK/tree"
git worktree add -q --detach "$tree" "$tag"
trap 'git -C "$root" worktree remove --force "$tree" >/dev/null 2>&1 || true' EXIT

report="$WORK/report.md"
applied=0
failed=0
{
	echo "## LibreEcho series on $tag"
	echo
	echo "| Result | Commit | Conflicting files |"
	echo "|---|---|---|"
} > "$report"

for c in "${series[@]}"; do
	subject=$(git log -1 --format=%s "$c" | sed 's/|/\\|/g')
	short=$(git rev-parse --short=12 "$c")
	if git -C "$tree" -c user.name=canary -c user.email=canary@invalid \
		cherry-pick --allow-empty "$c" >/dev/null 2>&1; then
		applied=$((applied + 1))
		echo "| ok | \`$short\` $subject | |" >> "$report"
	else
		files=$(git -C "$tree" diff --name-only --diff-filter=U | sed 's/^/`/; s/$/`/' | paste -sd ' ')
		git -C "$tree" cherry-pick --abort
		failed=$((failed + 1))
		echo "| **conflict** | \`$short\` $subject | $files |" >> "$report"
	fi
done

{
	echo
	echo "$applied of ${#series[@]} commits apply cleanly; $failed need porting."
	echo "A commit is applied on top of the ones above that applied, so a"
	echo "conflict can come from an earlier commit that did not."
} >> "$report"

build_failed=0
if [ "$failed" -eq 0 ]; then
	out="$WORK/out"
	kmake() {
		make -C "$tree" O="$out" ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- \
			LD=arm-linux-gnueabihf-ld.bfd "$@"
	}
	if kmake mt8163_arm32_defconfig >"$WORK/build.log" 2>&1 &&
		kmake olddefconfig >>"$WORK/build.log" 2>&1 &&
		kmake -j"$(nproc)" zImage dtbs modules >>"$WORK/build.log" 2>&1; then
		echo "Build of mt8163_arm32_defconfig: **ok**." >> "$report"
	else
		build_failed=1
		{
			echo "Build of mt8163_arm32_defconfig: **failed**."
			echo
			echo '```'
			grep -E ' error: |Error [0-9]' "$WORK/build.log" | head -50
			echo '```'
		} >> "$report"
	fi
fi

cat "$report"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
	cat "$report" >> "$GITHUB_STEP_SUMMARY"
fi

if [ "$STRICT" -eq 1 ] && { [ "$failed" -ne 0 ] || [ "$build_failed" -ne 0 ]; }; then
	exit 1
fi
