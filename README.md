# hftbacktest-carrybot

Controlled, reproducible patch of upstream HftBacktest `py-v2.4.4` for partial-fill accounting issue #316.

This repository pins upstream commit `a244a14250b42d97fc305569c93c4117cd5e1dff`, applies the minimal L2/L3 local-accounting fix, builds native wheels, and runs real-engine regression tests.
