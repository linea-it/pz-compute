# Custom DP2-derived runs

This directory contains scientifically reviewed runs derived from DP2 that are
not part of the official DP2 v3 reproduction. Each project is isolated below a
descriptive directory and owns its scientific contract, run-specific
configuration, operational instructions, and validation record.

The official workflows under [`../individual/`](../individual/README.md),
[`../batch/`](../batch/README.md), [`../config/`](../config/), and
[`../scripts/`](../scripts/) remain the reference reproduction path. A custom
project may reuse immutable inputs and generic tools, but it must not place
models, estimates, HATS products, or run-specific configuration in the
official output trees.

## Compatibility rule

Generic code changes needed by a custom project must preserve the existing
defaults and command lines used by the official workflow. Before a custom
launcher is considered production-ready:

1. the repository test suite must pass;
2. the official DP2 smoke and validation paths affected by the change must
   retain their previous behavior;
3. custom behavior must be enabled explicitly rather than by changing an
   official default;
4. official and custom artifacts must remain in separate run directories.

## Projects

- [`dnf_cmodel_griz_riz/`](dnf_cmodel_griz_riz/README.md): two full-catalog
  DNF/ANF runs using SFD-corrected cModel photometry in `griz` and `riz`,
  requested by Nacho Sevilla Noarbe.
