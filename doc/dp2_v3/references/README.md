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
| [`bpz_test_science.md`](bpz_test_science.md) | standalone, non-production COSMOS31 workflow and risk statement |

There is intentionally no `bpz_runs.md` yet. Add it only after a BPZ pilot or
production run has completed and its job IDs, environment, metrics, and output
validation have been retained.

The detailed legacy FlexZBoost command recipes remain in `doc/dp2_v2/`; they
are not duplicated here.
