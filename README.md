# Controlled HftBacktest partial-fill patch

This repository pins upstream `nkaz001/hftbacktest` tag `py-v2.4.4` at commit `a244a14250b42d97fc305569c93c4117cd5e1dff` and applies one narrowly scoped accounting fix for upstream issue #316.

The patch makes the local L2 and L3 processors apply every `PartiallyFilled` execution event to state accounting, in addition to terminal `Filled` events. Upstream `order.exec_qty` is a per-response execution quantity, not a cumulative quantity.

Package identity: `2.4.4+carrybot.partialfill1`.

The full upstream source is referenced as a Git submodule pinned to the immutable upstream commit. CI builds native wheels from that commit plus `patches/carrybot-partialfill1.patch` and runs real-engine regression tests.

Upstream copyright and MIT license remain preserved. See `UPSTREAM_LICENSE_NOTICE.md`.
