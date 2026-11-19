# DNF cModel QA notebook

`dnf_cmodel_griz_riz_qa.ipynb` builds a compact, delivery-oriented QA report
for the completed `griz` and `riz` scalar HATS catalogs. It reads the final
HATS products, their Stage 3 validation records, and the persisted Stage 2 DNF
quality counters. It does not modify any run artifact.

The report deliberately distinguishes exact catalog-wide counts from
descriptive statistics computed on a deterministic hash sample. Histograms,
integrity counts, missing-photometry counts, and DNF diagnostic counters are
exact. Quantiles and the object-by-object `griz`/`riz` comparison use the
sample and are labeled accordingly.

After both Stage 3 products validate, render the delivery artifacts with:

```bash
source /scripts/$(whoami)/ondemand/env-dp2-stage3-hats.sh
export PZ_DP2_ROOT=${PZ_DP2_ROOT:-$PZ_RUN_ROOT/dp2-v3}
export PZ_DP2_CUSTOM_ROOT=${PZ_DP2_CUSTOM_ROOT:-$PZ_RUN_ROOT/dp2-v3/custom/dnf-cmodel-griz-riz}
export PZ_DP2_INPUT_DATASET=/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset
cd "$PZ_COMPUTE_DIR"

doc/dp2_v3/custom/dnf_cmodel_griz_riz/notebooks/render-qa.sh
```

By default the command writes below `$PZ_DP2_CUSTOM_ROOT/qa/delivery`. Override
that location with `PZ_QA_OUTPUT_DIR`. The selected `PZ_PY` environment must
provide `nbclient`, `nbconvert`, and `nbformat`; the renderer fails before
creating artifacts if those Jupyter components are unavailable. The result
contains:

```text
dnf_cmodel_griz_riz_qa.ipynb  # executed notebook with code and outputs
dnf_cmodel_griz_riz_qa.html   # rendered report with code inputs hidden
qa_summary.json               # machine-readable aggregate QA record
SHA256SUMS                    # checksums for the three delivery artifacts
```

The HTML and executed notebook are scientific QA records, not accuracy
validation against spectroscopic truth. The notebook stops with an error if
the final schema, null pattern, interval ordering, grid support, row counts,
or persisted numerical-failure counters violate the documented contract.
