# Official BPZ reference data

BPZ estimation needs a reference-data root with this structure:

```text
bpz_dp2_v3p1_data/
├── SED/
│   ├── cosmossedswdust136.list
│   └── <the 136 official .sed files named by the list>
├── FILTER/
│   └── lsstcam_{u,g,r,i,z,y}.res
└── AB/
```

On LineA, place the reviewed reference-data tree at:

```text
$PZ_INSTALL_ROOT/bpz_dp2_v3p1_data
```

An administrator or operator may instead export
`PZ_BPZ_OFFICIAL_DATA_ROOT=/absolute/path/to/bpz_dp2_v3p1_data`. The path must
contain the official `cosmossedswdust136.list`, every one of its 136 SED files,
and the six LSSTCam filters. Its `AB/` directory must be writable by the
mandatory smoke test and the subsequent Slurm tasks.

The launchers validate the list length, every referenced SED, and every filter
before running. The smoke-test `READY` marker records checksums for the model,
YAML, list, 136 SEDs, and six filters. A missing or changed official input
therefore prevents production submission.

These official data are not distributed by the current public RAIL wheels. Do
not replace `cosmossedswdust136.list` with `COSMOS_seds.list`: the published
DP2 HDFN prior contains `nt_array=[7,57,72]`, which requires 136 templates in
the reviewed order.
