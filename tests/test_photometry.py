import numpy as np
import pandas as pd

from rail_scripts.photometry import (
    materialize_sfd_columns,
    parse_column_list,
    projected_input_columns,
    table_row_count,
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
