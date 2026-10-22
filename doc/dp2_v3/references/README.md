# Scientific and production references

This directory separates scientific provenance from operational instructions.
The YAML files under `../config/` are executable configuration; the science
notes here explain every choice made in those files. The guides under
`../individual/` and `../batch/` explain how to run the workflow.

| document | scope |
|---|---|
| [`fzboost_science.md`](fzboost_science.md) | scientific rationale and provenance for FlexZBoost training and estimation |
| [`fzboost_runs.md`](fzboost_runs.md) | validated FlexZBoost run history, resource rationale, and remaining evidence gaps |
| [`bpz_science.md`](bpz_science.md) | official BPZ scientific rationale and provenance |
| [`bpz_reference_data.md`](bpz_reference_data.md) | official BPZ 136-SED deployment contract |
| [`dnf_science.md`](dnf_science.md) | official DNF scientific configuration, trusted-pickle inspection, and provenance |
| [`bpz_test_science.md`](bpz_test_science.md) | standalone, non-production COSMOS31 workflow and risk statement |
| [`bpz_test_runs.md`](bpz_test_runs.md) | validated BPZ test run history and Stage 2 resource rationale |

There are intentionally no official `bpz_runs.md` or `dnf_runs.md` files yet.
Add one only after the corresponding pilot or production run has completed
and its job IDs, environment, metrics, and output validation have been
retained.

The detailed legacy FlexZBoost command recipes remain in `doc/dp2_v2/`; they
are not duplicated here.
