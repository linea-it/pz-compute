import numpy as np

from rail_scripts.integrity import row_id_fingerprint


def test_row_id_fingerprint_is_stable_and_order_sensitive():
    native = np.array([10, 20, 30], dtype=np.int64)
    big_endian = native.astype(">i8")

    assert row_id_fingerprint(native) == row_id_fingerprint(big_endian)
    assert row_id_fingerprint(native) != row_id_fingerprint(native[::-1])


def test_row_id_fingerprint_supports_strings():
    assert row_id_fingerprint(np.array(["a", "bc"])) == row_id_fingerprint(
        np.array(["a", "bc"])
    )
    assert row_id_fingerprint(np.array(["a", "bc"])) != row_id_fingerprint(
        np.array(["ab", "c"])
    )
