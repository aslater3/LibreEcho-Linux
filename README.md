# LibreEcho Linux for MT8163

This repository is the Linux kernel source for LibreEcho MT8163 targets, kept
on real upstream stable history. It is intentionally separate from
`LibreEcho-Platform`, which
owns ARM32 product tooling, initramfs, feature packaging, OTA verification, and
the historical 3.18 compatibility tree.

> **Status:** this repository replaces
> [LibreEcho-Linux-6.1](https://github.com/aslater3/LibreEcho-Linux-6.1), which
> is a flat snapshot without upstream history
> ([LibreEcho-Linux-6.1#53](https://github.com/aslater3/LibreEcho-Linux-6.1/issues/53)).
> It builds the same kernel as LibreEcho-Linux-6.1 (same sources, same
> configuration); the production pipeline still builds from LibreEcho-Linux-6.1
> until the build is migrated here.

## Provenance and layout

- Upstream: `https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git`
- Branch point: `v6.1.178` (`dc5c83b7f5f83ea99aea5c771b1ec77458263a15`)
- `main` is `v6.1.178` plus the LibreEcho commits, one per subsystem, replayed
  from LibreEcho-Linux-6.1 `ac890a53b229`. The replayed tree matches that
  snapshot except for unreferenced stale copies under
  `arch/arm/boot/dts/mediatek/`, and upstream dotfiles (`.kunitconfig`,
  `.yamllint`, `tools/testing/selftests/arm64/tags`) that were lost when the
  snapshot was imported.
- The MT8163 CONSYS connectivity stack (WMT/STP/BTIF, Wi-Fi, Bluetooth; about
  213k lines of vendor code) lives in
  [LibreEcho-mt8163-connectivity](https://github.com/aslater3/LibreEcho-mt8163-connectivity)
  and is included here as a `git subtree` at
  `drivers/misc/mediatek/mt8163-connectivity`, from its `linux-6.1-in-tree`
  branch. It is still built into the kernel, as in LibreEcho-Linux-6.1. Make
  connectivity changes on that branch, then update the subtree:

  ```sh
  git subtree pull --squash --prefix=drivers/misc/mediatek/mt8163-connectivity \
    https://github.com/aslater3/LibreEcho-mt8163-connectivity linux-6.1-in-tree
  ```

  The connectivity repository's `main` holds the out-of-tree module build,
  which is planned as a later, separately reviewed change.

To list the LibreEcho changes:

```sh
git log --first-parent --no-merges v6.1.178..main
```

## Stable updates

Stable releases are merged, not re-imported:

```sh
git fetch https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git tag v6.1.N
git checkout -b fix/linux-6.1.N main
git merge --no-ff v6.1.N
```

The merge still needs conflict review, the full ARM32 build and contract
checks, and hardware acceptance where relevant. Renovate's
`.github/renovate-upstreams.env` marker remains a review signal only.

## Next LTS canary

`.github/workflows/next-lts-canary.yml` runs `libreecho/next_lts_canary.sh`
every night. The script replays the LibreEcho commits onto the latest 6.18.y
release and reports which ones apply cleanly. The connectivity subtree is not
replayed; the connectivity repository runs its own nightly compile canary
against the same release.

The tree is not a claim that the MT8163 changes are upstream-ready. A clean
kernel source baseline does not by itself constitute a complete boot image or
stable OTA release; those require the paired product tooling and independent
image verification.

## Production audio contract

> **Final hardware-verified contract (2026-08-07):** the programme is mono, but
> PCM 23 must use a **two-channel transport with identical left/right samples**.
> One-channel `MonoRight` / `DACSETUP=0x24` is superseded: live output isolation
> showed clean woofer audio but noise or silence from the tweeter.

The Radar-Puffin speaker path is:

- producer input: stereo `S16_LE`, 48 kHz;
- programme processing: mix/downmix/duck/limit once to mono;
- hardware output: duplicated mono in `S16_LE`, 48 kHz, **2 channels**;
- hardware PCM: PCM 23 / `hw:0,23`;
- board channel configuration: `Stereo`;
- codec route: normal `DACSETUP=0x14` (left slot to left DAC, right slot to right DAC);
- HP/HPL/HPR speaker routes enabled; LO/LOL/LOR line-out routes disabled;
- `Audio_DacMux_Setting=Off`;
- PRB_P2 resource class 12, calibrated crossover, and IFACE3
  `DACMOD2BCLK` are retained.

The shared audio engine renders one mono sample per frame and writes it to both
PCM channels. This is not stereo programme audio; it is the transport required
for the left/HPL tweeter and right/HPR woofer DAC paths. The userspace engine
and packaging live in the separate `LibreEcho-Platform` tooling repository.

## Build boundary

The production pipeline must pass this repository as `LIBREECHO_KERNEL_SRC`
and pass the separate tooling repository as `LIBREECHO_TOOLING_SRC`. Do not use
the tooling repository as the kernel source: it contains a Linux 3.18 tree and
will produce incompatible DTC/build results when used as a 6.1 source.

Use an external output directory, for example:

```sh
make O=/path/to/kernel-output ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- \
  LD=arm-linux-gnueabihf-ld.bfd mt8163_arm32_defconfig
make O=/path/to/kernel-output ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- \
  LD=arm-linux-gnueabihf-ld.bfd olddefconfig
make O=/path/to/kernel-output ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- \
  LD=arm-linux-gnueabihf-ld.bfd zImage dtbs -j8
```

The final LibreEcho pipeline remains the authority for the stock-v184 Android
boot envelope, initramfs, feature payloads, signing, and image verification.
This repository must not be used to flash a device directly.

## Kernel target scaffolding

`libreecho/targets.json` maps `radar_puffin` and `biscuit` to their kernel
`defconfig` and `dtb`. Both currently use `mt8163_arm32_defconfig` and
`libreecho-radar-puffin.dtb`: this is deliberate build parity, **not Biscuit
hardware acceptance**. Biscuit will get its own reviewed DTS and hardware
validation in a later change; no new DTS or audio/config fragments are added here.

Validate the table and exercise its CI planner without hardware:

```sh
python3 -B libreecho/validate_targets.py
python3 -B libreecho/test_targets.py
```

CI reads this table, builds each distinct `(defconfig, dtb)` tuple once, then
uses a publication matrix over both targets to upload
`libreecho-kernel-<target>-zImage`, `-dtb`, `-System.map` and `-config` artifacts.
At parity these are copies of the same build outputs. The legacy Radar bundle
`libreecho-linux-arm32-<sha>` is also retained. Changing Biscuit's tuple to valid
in-tree sources adds a build lane automatically; unknown IDs or missing sources
fail validation. The build still uses `olddefconfig`, `zImage dtbs`, the existing
ARMHF GCC/linker flags and no config fragments, preserving Radar's CI recipe.

## Contract tests

The LibreEcho source contract tests sit next to the code they check. Run them
all with:

```sh
python3 -B libreecho/run_contract_tests.py
```

## MT8163 pstore/ramoops source boundary

Issue #6 is intentionally source-blocked on the current kernel baseline. The
production DT contains platform-owned reserved-memory nodes, including the
vendor `mediatek,ram_console` region, but it does not identify a firmware-owned
region that is safe to hand to `ramoops`. This tree therefore does **not** add a
new memory address, reuse an existing reserved range, or enable only
`CONFIG_PSTORE` / `CONFIG_PSTORE_RAM` in the kernel defconfig.

The production initramfs and its `/data` archival/rotation policy are owned by
the separate `LibreEcho-Platform` repository, not by this kernel source tree.
A complete implementation must be reviewed across all three layers before any
one of them is enabled here:

1. firmware/LK and the production DT must agree on a retained, non-overlapping
   reserved region;
2. `mt8163_arm32_defconfig` must enable both pstore and ramoops support; and
3. the product initramfs must mount `/sys/fs/pstore`, archive records, and apply
   the approved rotation policy.

The host-side boundary is checked with:

```sh
python3 -B tools/mt8163_pstore_contract_test.py
```

That check prevents a partial source integration; it does not claim warm-reset
retention, deliberate-panic capture, or diagnostics-surface availability. Those
remain physical/product integration gates.

## MT8163 Bluetooth HCI contract

The MT8163 Bluetooth bridge is built into the production kernel. The committed
`mt8163_arm32_defconfig` explicitly enables the complete closure:

```text
CONFIG_BT=y
CONFIG_BT_BREDR=y
CONFIG_BT_LE=y
CONFIG_MTK_BTIF=y
CONFIG_MTK_COMBO_BT=y
CONFIG_MTK_MT8163_BLUEZ_HCI=y
```

The bridge registers `hci0` before userspace WMT preparation is complete. It
therefore cancels the automatic HCI setup work queued by `hci_register_dev()`
and marks the controller for deferred setup; the first `SET_POWERED` management
command is allowed through that narrow gate only after WMT has configured the
BTIF transport. The normal HCI open/setup sequence then clears `HCI_SETUP` and
populates the controller information. Without this exception, Linux rejects the
first controller-indexed management command while the transport is deliberately
waiting for userspace preparation.

The source contract can be checked without hardware:

```sh
python3 -B tools/mt8163_bluetooth_contract_test.py
```

This static check does not replace live HCI controller-information, discovery,
pairing, and connection acceptance on the target device.
