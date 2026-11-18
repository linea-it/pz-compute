import numpy as np
import pandas as pd

from rail_scripts.photometry import (
    materialize_sfd_columns,
    normalize_sfd_coefficients,
    parse_column_list,
    projected_input_columns,
    replace_nondetections,
    selected_photometry_quality,
    table_row_count,
)
from rail_scripts import (
    DEFAULT_BANDS,
    create_column_mapping_dict,
    parse_bands,
    validate_column_mapping_overrides,
)


def test_materialize_sfd_columns_from_magnitudes():
    table = pd.DataFrame(
        {
            "i_psfMag": [22.0, 23.0],
            "i_psfMagErr": [0.1, 0.2],
            "ebv": [0.5, 0.1],
        }
    )

    materialize_sfd_columns(table, ["i_psfMag_sfd", "i_psfMagErr_sfd"])

    np.testing.assert_allclose(table["i_psfMag_sfd"], [20.97, 22.794])
    np.testing.assert_allclose(table["i_psfMagErr_sfd"], [0.1, 0.2])


def test_materialize_sfd_columns_from_njy_fluxes():
    table = pd.DataFrame(
        {
            "i_psfFlux": [1000.0, -1.0],
            "i_psfFluxErr": [10.0, 2.0],
            "ebv": [0.2, 0.1],
        }
    )

    materialize_sfd_columns(table, ["i_psfMag_sfd", "i_psfMagErr_sfd"])

    np.testing.assert_allclose(table.loc[0, "i_psfMag_sfd"], 23.488)
    np.testing.assert_allclose(
        table.loc[0, "i_psfMagErr_sfd"], 2.5 / np.log(10.0) * 0.01
    )
    assert np.isnan(table.loc[1, "i_psfMag_sfd"])
    assert np.isnan(table.loc[1, "i_psfMagErr_sfd"])


def test_materialize_sfd_columns_with_explicit_dp2_v3_coefficients():
    table = pd.DataFrame(
        {
            "u_psfMag": [22.0],
            "g_psfMag": [21.0],
            "ebv": [0.1],
        }
    )
    coefficients = {
        "u": 4.78,
        "g": 3.65,
        "r": 2.70,
        "i": 2.06,
        "z": 1.58,
        "y": 1.31,
    }

    materialize_sfd_columns(
        table,
        ["u_psfMag_sfd", "g_psfMag_sfd"],
        sfd_a_ebv=coefficients,
    )

    np.testing.assert_allclose(table["u_psfMag_sfd"], [21.522])
    np.testing.assert_allclose(table["g_psfMag_sfd"], [20.635])
    assert normalize_sfd_coefficients(coefficients) == coefficients


def test_sfd_coefficients_require_exactly_six_lsst_bands():
    with np.testing.assert_raises(ValueError):
        normalize_sfd_coefficients({"u": 4.78})


def test_projection_prefers_magnitudes_over_fluxes():
    schema = ["i_psfMag", "i_psfMagErr", "i_psfFlux", "i_psfFluxErr", "ebv"]
    required = ["i_psfMag_sfd", "i_psfMagErr_sfd"]

    assert projected_input_columns(schema, required, "ebv") == [
        "i_psfMag",
        "ebv",
        "i_psfMagErr",
    ]


def test_projection_and_output_column_parser_are_deduplicated():
    schema = ["i_psfFlux", "i_psfFluxErr", "ebv", "detect_isPrimary"]
    required = ["i_psfMag_sfd", "i_psfMagErr_sfd", "detect_isPrimary"]

    assert projected_input_columns(schema, required, "ebv") == [
        "i_psfFlux",
        "ebv",
        "i_psfFluxErr",
        "detect_isPrimary",
    ]
    assert parse_column_list("i_psfMagErr_sfd, detect_isPrimary, i_psfMagErr_sfd") == (
        "i_psfMagErr_sfd",
        "detect_isPrimary",
    )


def test_table_row_count_handles_empty_tables_and_column_order():
    empty = pd.DataFrame({"second": np.array([], dtype=float), "first": []})
    reordered = pd.DataFrame({"first": [1, 2], "second": [3, 4]})[["second", "first"]]

    assert table_row_count(empty) == 0
    assert table_row_count(reordered) == 2


def test_band_parser_defaults_are_explicit_at_call_site_and_preserve_order():
    assert parse_bands("ugrizy") == DEFAULT_BANDS
    assert parse_bands("griz") == ("g", "r", "i", "z")
    assert parse_bands("r,i,z") == ("r", "i", "z")
    with np.testing.assert_raises(ValueError):
        parse_bands("griq")
    with np.testing.assert_raises(ValueError):
        parse_bands("grig")


def test_column_mapping_uses_only_selected_bands_and_rejects_conflicts():
    limits = {f"mag_{band}_lsst": 20.0 + index for index, band in enumerate("ugrizy")}
    mapping = create_column_mapping_dict(
        "{band}_cModelMag",
        "{band}_cModelMagErr",
        limits,
        bands=parse_bands("riz"),
    )

    assert mapping["bands"] == ["r_cModelMag", "i_cModelMag", "z_cModelMag"]
    assert mapping["err_bands"] == [
        "r_cModelMagErr",
        "i_cModelMagErr",
        "z_cModelMagErr",
    ]
    validate_column_mapping_overrides(
        {"bands": mapping["bands"], "err_bands": mapping["err_bands"]}, mapping
    )
    with np.testing.assert_raises(ValueError):
        validate_column_mapping_overrides(
            {"bands": ["g_cModelMag", "r_cModelMag"]}, mapping
        )


def test_replace_nondetections_is_copy_on_write_safe_and_exact():
    table = pd.DataFrame(
        {
            "r_mag": [20.0, np.nan, 22.0],
            "r_err": [0.1, np.nan, np.nan],
            "i_mag": [np.nan, 21.0, 22.0],
            "i_err": [0.2, 0.3, 0.4],
        }
    )

    counts = replace_nondetections(
        table,
        ("r_mag", "i_mag"),
        ("r_err", "i_err"),
        {"r_mag": 27.1, "i_mag": 26.7},
        np.nan,
    )

    assert counts == {"r_mag": 1, "i_mag": 1}
    np.testing.assert_allclose(table["r_mag"], [20.0, 27.1, 22.0])
    np.testing.assert_allclose(table["i_mag"], [26.7, 21.0, 22.0])
    assert table.loc[1, "r_err"] == 1.0
    assert table.loc[0, "i_err"] == 1.0
    assert np.isnan(table.loc[2, "r_err"])


def test_selected_photometry_quality_distinguishes_missing_and_unusable_rows():
    table = pd.DataFrame(
        {
            "r_mag": [20.0, np.nan, 22.0, np.nan, 21.0],
            "r_err": [0.1, np.nan, np.nan, np.nan, np.nan],
            "i_mag": [np.nan, np.nan, 23.0, np.nan, np.nan],
            "i_err": [np.nan, np.nan, 0.2, np.nan, np.nan],
        }
    )

    quality = selected_photometry_quality(
        table,
        ("r", "i"),
        ("r_mag", "i_mag"),
        ("r_err", "i_err"),
        np.nan,
    )

    assert quality == {
        "method": "selected-photometry-v1",
        "rows": 5,
        "selected_bands": "ri",
        "missing_r_rows": 2,
        "unusable_r_rows": 4,
        "missing_i_rows": 4,
        "unusable_i_rows": 4,
        "complete_selected_band_nondetection_rows": 2,
        "no_usable_selected_band_rows": 3,
    }
