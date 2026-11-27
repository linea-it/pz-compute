# Photo-z QA notebooks

Two independent notebook versions are retained:

- [`pz_compute_v1/`](pz_compute_v1/README.md) is the original, detailed QA.
  It remains unchanged and includes PDF and product-integrity diagnostics.
- [`pz_compute_v2/`](pz_compute_v2/README.md) is a deliberately simple HATS
  characterization. It reads scalar columns only and reports catalog size,
  schema, descriptive statistics, and redshift distributions.

Use the version whose scope matches the analysis. The implementations,
configurations, and documentation are isolated from one another.

For example:

```bash
# Original detailed QA
PZ_QA_CONFIG=doc/notebooks/pz_compute_v1/config/dp2-v3-fzboost.yaml jupyter lab

# Simple scalar-only QA
PZ_QA_CONFIG=doc/notebooks/pz_compute_v2/config/dp2-v3-fzboost.yaml jupyter lab
```
