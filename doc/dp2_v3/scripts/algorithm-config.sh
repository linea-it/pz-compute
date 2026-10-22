#!/usr/bin/env bash

# Source this file, then call dp2_algorithm_config fzboost|bpz.
dp2_algorithm_config() {
    local algorithm=${1:?algorithm is required}
    local scripts_dir
    scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    PZ_DP2_DOC_DIR=$(cd "$scripts_dir/.." && pwd)

    case "$algorithm" in
        fzboost)
            PZ_MODEL_BASENAME=model_dp2_v3p1_fzboost_dp2_6band_gold.pickle
            PZ_ESTIMATE_CONFIG=$PZ_DP2_DOC_DIR/config/fzboost-estimate.yaml
            PZ_DEFAULT_MAX_CONCURRENT=82
            PZ_DEFAULT_MEMORY=40G
            PZ_DEFAULT_TIME=01:00:00
            ;;
        bpz)
            PZ_MODEL_BASENAME=model_dp2_v3p1_bpz_dp2_6band_gold.pickle
            PZ_ESTIMATE_CONFIG=$PZ_DP2_DOC_DIR/config/bpz-estimate.yaml
            PZ_DEFAULT_MAX_CONCURRENT=20
            PZ_DEFAULT_MEMORY=40G
            PZ_DEFAULT_TIME=24:00:00
            ;;
        *)
            echo "Unsupported algorithm: $algorithm (expected fzboost or bpz)" >&2
            return 2
            ;;
    esac

    PZ_ALGORITHM=$algorithm
    export PZ_ALGORITHM PZ_DP2_DOC_DIR PZ_MODEL_BASENAME PZ_ESTIMATE_CONFIG
    export PZ_DEFAULT_MAX_CONCURRENT PZ_DEFAULT_MEMORY PZ_DEFAULT_TIME
}
