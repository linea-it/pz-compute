#!/usr/bin/env bash

custom_dnf_variant_config() {
    local variant=${1:?variant is required}
    local scripts_dir project_dir dp2_doc_dir
    scripts_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    project_dir=$(cd "$scripts_dir/.." && pwd)
    dp2_doc_dir=$(cd "$project_dir/../.." && pwd)

    : "${PZ_DP2_CUSTOM_ROOT:?set PZ_DP2_CUSTOM_ROOT first}"

    case "$variant" in
        griz) PZ_CUSTOM_BANDS=griz ;;
        riz) PZ_CUSTOM_BANDS=riz ;;
        *)
            echo "Unsupported custom DNF variant: $variant (expected griz or riz)" >&2
            return 2
            ;;
    esac

    PZ_CUSTOM_VARIANT=$variant
    PZ_CUSTOM_PROJECT_DIR=$project_dir
    PZ_CUSTOM_DP2_DOC_DIR=$dp2_doc_dir
    PZ_CUSTOM_TRAIN_CONFIG=$project_dir/config/dnf-$variant-train.yaml
    PZ_CUSTOM_ESTIMATE_CONFIG=$project_dir/config/dnf-$variant-estimate.yaml
    PZ_CUSTOM_SFD_CONFIG=$dp2_doc_dir/config/dp2-v3-sfd-lsstcam.yaml
    PZ_CUSTOM_TRAINING_DATA=$PZ_DP2_CUSTOM_ROOT/common/training/train_clipped_v3_cmodel_$variant.hdf5
    PZ_CUSTOM_MODEL_BASENAME=model_dp2_v3p1_custom_dnf_cmodel_${variant}_gold.pickle
    PZ_CUSTOM_STAGE1=$PZ_DP2_CUSTOM_ROOT/$variant/stage1
    PZ_CUSTOM_MODEL=$PZ_CUSTOM_STAGE1/model/$PZ_CUSTOM_MODEL_BASENAME
    PZ_CUSTOM_STAGE2=$PZ_DP2_CUSTOM_ROOT/$variant/stage2
    PZ_CUSTOM_STAGE2_OUTPUT=$PZ_CUSTOM_STAGE2/output
    PZ_CUSTOM_STAGE3=$PZ_DP2_CUSTOM_ROOT/$variant/stage3
    PZ_CUSTOM_HATS_BASENAME=pz-dnf-cmodel-${variant}-scalar-hats
    PZ_CUSTOM_HATS_DIR=$PZ_CUSTOM_STAGE3/output/$PZ_CUSTOM_HATS_BASENAME

    export PZ_CUSTOM_VARIANT PZ_CUSTOM_BANDS PZ_CUSTOM_PROJECT_DIR
    export PZ_CUSTOM_DP2_DOC_DIR PZ_CUSTOM_TRAIN_CONFIG
    export PZ_CUSTOM_ESTIMATE_CONFIG PZ_CUSTOM_SFD_CONFIG
    export PZ_CUSTOM_TRAINING_DATA PZ_CUSTOM_MODEL_BASENAME
    export PZ_CUSTOM_STAGE1 PZ_CUSTOM_MODEL
    export PZ_CUSTOM_STAGE2 PZ_CUSTOM_STAGE2_OUTPUT
    export PZ_CUSTOM_STAGE3 PZ_CUSTOM_HATS_BASENAME PZ_CUSTOM_HATS_DIR
}
