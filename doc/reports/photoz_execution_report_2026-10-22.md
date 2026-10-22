# Photo-z Processing Report: DP1 and DP2

**Status as of October 22, 2026**

## Executive summary

The FlexZBoost processing was completed successfully for both Rubin DP1 and DP2. The production outputs comprise point estimates in HATS format and full redshift probability distributions (PDFs) in Parquet format. The final catalogs contain approximately **2.30 million DP1 objects** and **786.42 million DP2 objects**.

The DP2 run provides the most representative production-scale measurement. Its 2,174 estimation tasks all completed successfully in **2 hours 13 minutes**, processing the full catalog across 25 compute nodes. The final HATS assembly took approximately **9 minutes**. Peak memory remained within the adopted 40 GiB allocation, reaching **33.85 GiB** during estimation and **37.99 GiB** during HATS construction.

The DP2 BPZ Test did not complete. Two full-catalog attempts exceeded their memory allocations, and a third attempt with a higher limit was interrupted when the cluster had to be released. Consequently, no BPZ Test products should yet be treated as complete or scientifically validated.

Scientific QA reports for the completed FlexZBoost products are temporarily available at [dev.linea.org.br/~luigi.silva/general_files/](https://dev.linea.org.br/~luigi.silva/general_files/). They will be presented separately.

## Production outputs

The complete HATS catalogs and PDF files remain in the processing environment; they were not copied into this repository because of their size. The status and object counts below are based on the retained execution logs and final catalog metadata.

| Dataset and method | Point estimates | Full PDFs | Objects | Status |
|---|---|---|---:|---|
| DP1 FlexZBoost | HATS | Parquet | 2,299,757 | Complete |
| DP2 FlexZBoost | HATS | Parquet | 786,420,720 | Complete |
| DP2 BPZ Test | Not delivered | Not delivered | — | Pending a successful rerun and validation |

## Inputs used

| Processing | Model/training input | Catalog processed |
|---|---|---|
| DP1 FlexZBoost | `training_v4 match_ecdfs`, retained locally as `dp1_matched_v4_train.hdf5`: 6,778 matched spectroscopic objects with six-band GAaP 1.0 photometry | Complete DP1 primary Object catalog at `/data/cl/lsst/dp1/primary/catalogs/object`: 29 Parquet shards and 2,299,757 objects |
| DP2 FlexZBoost | RTN-124 `CLIPPED_TRAIN`, file `train_clipped_v3.parquet`: 554,676 objects with six-band GAaP 1.0 photometry | Complete DP2 primary Object catalog at `/data/cl/lsst/dp2/primary/catalogs/object`: 2,174 Parquet shards and 786,420,720 objects |
| DP2 BPZ Test | The same RTN-124 `CLIPPED_TRAIN` catalog, converted to `train_clipped_v3_gaap1p0.hdf5`, together with the 31 public COSMOS spectral templates | Partitioned DP2 secondary Object catalog at `/data/cl/lsst/dp2/secondary/catalogs/object_collection/object/dataset`; the pilot used its five largest shards, and the interrupted attempts targeted the full catalog |

In every case, the estimation step used the six `ugrizy` GAaP 1.0 bands. The training magnitudes were already corrected for Galactic extinction. For the Object catalogs, the corresponding correction was applied during input preparation so that estimation matched the training convention. The original Object catalog was also reused during HATS construction to preserve object identifiers, coordinates, and row association with the photo-z outputs.

## Execution metrics

### DP1 FlexZBoost

DP1 is a much smaller dataset than DP2 and completed quickly.

| Stage | Scale | Elapsed time | Memory | CPU |
|---|---:|---:|---:|---:|
| Model training | 1 job | 1 min 37 s | 2.47 GiB peak | 21.4% allocation efficiency |
| Photo-z estimation | 29/29 tasks completed | 3 min 30 s overall | Not retained in the available accounting snapshot | Not retained in the available accounting snapshot |
| HATS construction | 2.30 million objects | 40 s | Driver-only measurement | Driver used 14.4 CPU-seconds |

The median estimation task took **38 seconds**; 95% finished within **3 minutes 14 seconds**, and the longest took **3 minutes 29 seconds**. The measured runtime of the three successful stages totals approximately **5 minutes 47 seconds**. From the beginning of training to the final product, including setup and the correction of one missing-command issue before the successful HATS build, the elapsed clock time was approximately **22 minutes**.

### DP2 FlexZBoost

| Stage | Scale | Elapsed time | Peak memory | CPU allocation efficiency |
|---|---:|---:|---:|---:|
| Model training | 1 job | 2 min 37 s | 15.33 GiB | 7.2% |
| Photo-z estimation | 2,174/2,174 tasks | 2 h 13 min 25 s | 33.85 GiB | 55.9% |
| HATS construction | 82 workers; 786.42 million objects | 8 min 36 s | 37.99 GiB | 21.8% |

The estimation stage sustained an average of **76.6 concurrent tasks**, with a peak of 82, and completed approximately **978 shards per hour**. A typical task took **4 minutes 56 seconds**; 95% finished within **10 minutes 26 seconds**, and the longest took **17 minutes 1 second**. Memory use varied substantially by input shard: the median was **2.67 GiB**, the 95th percentile was **16.75 GiB**, and the maximum was **33.85 GiB**.

The three successful DP2 stages account for approximately **2 hours 25 minutes of measured wall-clock processing**, excluding operator time and the earlier failed attempt caused by storage capacity.

The HATS workers are recorded by Slurm as `CANCELLED`. In this case that reflects the normal shutdown of the temporary Dask cluster: the controlling process exited successfully, the build logged completion, and the final HATS catalog contains all 786,420,720 expected objects.

> Memory figures are peak resident memory for an individual job or worker, not total cluster memory. CPU efficiency measures the fraction of allocated CPU time actually used; lower values in the short training and data-assembly stages mainly indicate that these stages are not uniformly CPU-bound.

## Main challenges and how they were addressed

### 1. Establishing scientific reproducibility for DP1

The model initially available through the PZ Server belonged to an earlier training run. The final model and its correct 6,778-object training set were recovered from USDF, and inconsistencies between an old resolved configuration and the effective public configuration were reconciled. The complete model—50 regressions, 5,000 trees, and 1,386,032 tree nodes—was reproduced without divergence using the confirmed feature order and data transformation.

This investigation also established that the input magnitudes had already been corrected for Galactic extinction and that the current implementation must explicitly include magnitude errors. These checks prevented both a duplicate extinction correction and a silent change in the model inputs.

### 2. Matching production inputs to the trained models

For both DP1 and DP2, the estimation workflow was aligned with the training convention: GAaP fluxes are converted to AB magnitudes, the correct SFD extinction correction is applied, and band order, limits, uncertainties, and redshift grids are kept consistent. The DP2 SFD coefficients were also pinned to the Rubin reference values.

### 3. Sizing memory from real workloads

Small pilots were run on the largest catalog shards before full production. This revealed that memory consumption varies strongly with shard size and that the original allocations were insufficient in some cases. FlexZBoost production was therefore run with 40 GiB per task and controlled concurrency, which completed successfully without memory failures.

### 4. Resolving the DP2 storage failure

An initial DP2 estimation run stopped because the scratch filesystem quota was exhausted, not because of a CPU or RAM failure. Measurements of the completed files showed that Stage 2 alone would require about 3.45 TiB, with the complete workflow requiring substantially more once PDFs, HATS products, staging space, and safety margin were included. An **8 TiB usable allocation** was recommended, the incomplete attempt was cleaned up, and Stage 2 was restarted successfully from the beginning.

### 5. Making runs observable and reproducible

A reusable Slurm profiling module was added to record elapsed time, queue time, throughput, concurrency, CPU efficiency, memory percentiles, node distribution, and available disk I/O accounting. Environments, configurations, source revisions, logs, and machine-readable summaries are retained with the runs. This work made the figures in this report auditable and provides a standard baseline for future photo-z processing.

### 6. Scaling scientific QA

A single configurable QA workflow was developed for the DP1 and DP2 products. It performs distributed checks of HATS and PDF schemas, object counts and identifiers, redshift grids, invalid or negative PDFs, point-estimate consistency, and global redshift distributions. Computation is reduced on the workers so that only compact statistics and samples reach the notebook, allowing the same workflow to operate on the 786-million-object DP2 catalog.

## BPZ Test: current status and remaining risk

The BPZ Test is a standalone test configuration based on the COSMOS31 templates. It is useful for exercising the workflow, but it is **not the official Rubin BPZ production configuration**, whose complete set of 136 SEDs was not available in the inspected environment.

The five-largest-shard pilot completed with a peak of **20.53 GiB** and approximately **50–54 minutes per task**. Full-catalog behavior was less favorable:

- The first production array used 24 GiB per task and produced at least 15 out-of-memory terminations.
- A second attempt at 26 GiB also exceeded memory; one documented task failed after 58 minutes 25 seconds.
- A third attempt was launched with 32 GiB per task, but it was cancelled before completion because the cluster machines had to be released. Therefore, 32 GiB remains a provisional setting rather than a demonstrated solution.
- Warnings about non-finite PDF values were also observed. This is separate from the memory issue and must be resolved or quantified before any BPZ Test output is accepted.

The appropriate next step is a new controlled run with the revised memory allocation, followed by the same structural and scientific QA applied to FlexZBoost. If memory pressure persists, the input shards should be separated into different memory classes rather than increasing the allocation for every task equally.

## Overall assessment

The principal production objective was achieved: complete and traceable FlexZBoost products now exist for DP1 and DP2, including scalable scientific QA. The largest successful run processed all **786.42 million DP2 objects** with no failed estimation tasks and with measured memory below the 40 GiB per-task limit.

The remaining work is clearly isolated to BPZ: demonstrate a stable full-catalog memory configuration, investigate the non-finite PDF warnings, rerun the complete test, and validate its products before release.

## Evidence used

This report is based on the logs and files retained from the processing runs, including Slurm accounting summaries, driver logs, execution configurations, and final HATS metadata. The complete scientific products were not copied into this repository. Their object counts and completion status are taken from the production metadata and logs rather than from a new local scan of the full catalogs. Where a metric was not retained—most notably DP1 Stage 2 memory and CPU—it is reported as unavailable rather than inferred.
