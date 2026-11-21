# Proposed DNF validation plan for official DP2 runs

This note preserves recommendations for future test, development, and
production runs of the official six-band DP2 DNF configuration documented
under [`individual/`](../individual/README.md). It is a planning record, not a
description of the currently implemented official workflow. No official
launcher or scientific contract is changed by this document.

The main objective is to detect numerical and missing-photometry pathologies
without obscuring whether a run reproduces the pinned upstream configuration.
The secondary objective is to retain strong publication checks while keeping
production overhead small and measurable.

## Separate reference and hardened development modes

Development should retain two explicitly named modes:

1. **Reference reproduction** uses the pinned upstream DNF implementation
   without the stable-PDF option. It establishes the behavior of the official
   configuration and remains the comparison baseline.
2. **Hardened diagnostic execution** enables stable Gaussian evaluation and
   its in-memory checks, but retains the default no-photometry policy of
   `error`. Its outputs must be compared with the reference mode wherever the
   direct upstream calculation is numerically defined.

The stable log-space Gaussian is a numerical correction, not merely a metric.
It preserves the fitted `DNF_Z`, `photozerr`, redshift grid, and Gaussian
definition, but it must be reviewed and accepted before becoming part of an
official production contract. Likewise, no policy that replaces science
values with `NaN` should be inherited by the official product without a
separate scientific decision.

Ideally, future implementation work should decouple observation-only DNF
quality accounting from stable PDF generation. This would allow a reference
run to measure input availability, undefined parameters, and the prevalence
of the legacy all-zero underflow mechanism without changing the upstream PDF
calculation.

## Test and development recommendations

Smoke tests and the five-largest-shard pilot should use maximum diagnostic
coverage. Retain:

- missing and unusable photometry counts for every selected band;
- the number of rows with no usable selected magnitude/error pair before
  non-detection replacement;
- counts of non-finite `DNF_Z`, non-finite `photozerr`, and non-positive
  `photozerr`;
- the number of rows for which the direct legacy Gaussian would underflow to
  zero at every grid point;
- exact in-memory checks for finite PDF values, a positive finite integral,
  and unit normalization;
- fitted-redshift-outside-grid and boundary-mode counters;
- completion metadata, row count, row-identifier fingerprint, configuration
  checksums, and environment freeze;
- immediate source-aware validation of each produced shard;
- live Slurm monitoring and complete post-run resource profiling.

The reference and hardened modes should be compared on the same inputs. For
rows where the upstream PDF is finite and normalizable, require numerical
agreement within a documented tolerance. Investigate every mismatch rather
than treating successful job completion as sufficient evidence.

Pilot measurements must quantify the incremental wall time and maximum RSS of
the hardened checks. Production choices should be based on those measurements,
not on the assumption that an in-memory check is free.

## Production recommendations

Keep correctness checks that operate on arrays already resident in memory:

- the approved Gaussian implementation;
- input-availability and numerical-quality counters;
- undefined-parameter failures outside any explicitly approved policy mask;
- full finite/integral/normalization checks while each PDF chunk is in memory;
- completion metadata and row-identity fingerprinting.

These checks avoid rereading the full PDF payload. Their measured pilot cost
should nevertheless be recorded with the accepted production configuration.

Avoid duplicating the source-aware Stage 2 validator inside every production
array task and again after the array. A proposed production layout is:

1. generate each shard with the lightweight in-memory checks and persist its
   counters;
2. after all array tasks finish successfully, run the source-aware validator
   once over the complete manifest;
3. create the Stage 2 readiness contract only after that validation passes;
4. run the complete HATS schema and science-value validator once before
   publication.

Development may continue validating each shard immediately because early
failure localization is more valuable there than minimum throughput.

`slurm-watch` runs outside the scientific jobs and may remain enabled during
production. Post-run `slurm-profile` accounting is also inexpensive relative
to estimation and should be retained for resource provenance. Neither tool
substitutes for scientific output validation.

## Decisions required before adoption

Before changing the official launchers, record explicit answers to the
following questions:

1. Is stable log-space Gaussian evaluation accepted as part of the official
   numerical contract, or only as a diagnostic comparison mode?
2. Must observation-only counters be available without changing upstream PDF
   generation?
3. What is the measured CPU, wall-time, and peak-memory overhead on the
   official pilot shards?
4. What policy, if any, is approved for rows with no usable selected-band
   photometry?
5. Which validator runs inside development tasks, and which runs only once as
   a production publication gate?

Only after these decisions and pilot evidence exist should the corresponding
options be added to the official `individual` launchers and documentation.
