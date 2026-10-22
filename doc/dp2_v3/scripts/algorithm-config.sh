#!/usr/bin/env bash

# Source this file, then call dp2_algorithm_config fzboost|bpz|dnf|bpz_test.
# `bpz_test` is an independent workflow name even though it uses RAIL's BPZ
# implementation internally.
dp2_algorithm_config() {
    local algorithm=${1:?algorithm is required}
    local scripts_dir
    scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    PZ_DP2_DOC_DIR=$(cd "$scripts_dir/.." && pwd)
    PZ_SFD_CONFIG=$PZ_DP2_DOC_DIR/config/dp2-v3-sfd-lsstcam.yaml

    unset PZ_BPZ_DATA_ROOT PZ_BPZ_SPECTRA_FILE PZ_BPZ_EXPECTED_SEDS

    case "$algorithm" in
        fzboost)
            PZ_RAIL_ALGORITHM=fzboost
            PZ_MODEL_BASENAME=model_dp2_v3p1_fzboost_dp2_6band_gold.pickle
            PZ_TRAIN_CONFIG=$PZ_DP2_DOC_DIR/config/fzboost-train.yaml
            PZ_ESTIMATE_CONFIG=$PZ_DP2_DOC_DIR/config/fzboost-estimate.yaml
            PZ_DEFAULT_MAX_CONCURRENT=105
            PZ_DEFAULT_MEMORY=34G
            PZ_DEFAULT_TIME=01:00:00
            ;;
        bpz)
            PZ_RAIL_ALGORITHM=bpz
            PZ_MODEL_BASENAME=model_dp2_v3p1_bpz_dp2_6band_gold.pickle
            PZ_TRAIN_CONFIG=$PZ_DP2_DOC_DIR/config/bpz-train.yaml
            PZ_ESTIMATE_CONFIG=$PZ_DP2_DOC_DIR/config/bpz-estimate.yaml
            PZ_DEFAULT_MAX_CONCURRENT=20
            PZ_DEFAULT_MEMORY=40G
            PZ_DEFAULT_TIME=24:00:00
            PZ_BPZ_DATA_ROOT=${PZ_BPZ_OFFICIAL_DATA_ROOT:-${PZ_INSTALL_ROOT:?missing PZ_INSTALL_ROOT}/bpz_dp2_v3p1_data}
            PZ_BPZ_SPECTRA_FILE=cosmossedswdust136.list
            PZ_BPZ_EXPECTED_SEDS=136
            ;;
        dnf)
            PZ_RAIL_ALGORITHM=dnf
            PZ_MODEL_BASENAME=model_dp2_v3p1_dnf_dp2_6band_gold.pickle
            PZ_TRAIN_CONFIG=$PZ_DP2_DOC_DIR/config/dnf-train.yaml
            PZ_ESTIMATE_CONFIG=$PZ_DP2_DOC_DIR/config/dnf-estimate.yaml
            PZ_DEFAULT_MAX_CONCURRENT=105
            PZ_DEFAULT_MEMORY=34G
            PZ_DEFAULT_TIME=02:00:00
            ;;
        bpz_test)
            : "${PZ_PY:?missing PZ_PY}"
            PZ_RAIL_ALGORITHM=bpz
            PZ_MODEL_BASENAME=model_dp2_v3p1_bpz_test_cosmos31_gold.pickle
            PZ_TRAIN_CONFIG=$PZ_DP2_DOC_DIR/config/bpz-test-train.yaml
            PZ_ESTIMATE_CONFIG=$PZ_DP2_DOC_DIR/config/bpz-test-estimate.yaml
            PZ_DEFAULT_MAX_CONCURRENT=146
            PZ_DEFAULT_MEMORY=24G
            PZ_DEFAULT_TIME=02:00:00
            PZ_BPZ_DATA_ROOT=${PZ_BPZ_TEST_DATA_ROOT:-$(
                "$PZ_PY" - <<'PY'
import sysconfig
from pathlib import Path

print(Path(sysconfig.get_paths()["purelib"]) / "rail/examples_data/estimation_data/data")
PY
            )}
            PZ_BPZ_SPECTRA_FILE=COSMOS_seds.list
            PZ_BPZ_EXPECTED_SEDS=31
            echo "WARNING: bpz_test is non-production and must not be interpreted as official DP2 BPZ." >&2
            ;;
        *)
            echo "Unsupported algorithm: $algorithm (expected fzboost, bpz, dnf, or bpz_test)" >&2
            return 2
            ;;
    esac

    PZ_ALGORITHM=$algorithm
    export PZ_ALGORITHM PZ_RAIL_ALGORITHM PZ_DP2_DOC_DIR
    export PZ_SFD_CONFIG
    export PZ_MODEL_BASENAME PZ_TRAIN_CONFIG PZ_ESTIMATE_CONFIG
    export PZ_DEFAULT_MAX_CONCURRENT PZ_DEFAULT_MEMORY PZ_DEFAULT_TIME
    export PZ_BPZ_DATA_ROOT PZ_BPZ_SPECTRA_FILE PZ_BPZ_EXPECTED_SEDS
}
