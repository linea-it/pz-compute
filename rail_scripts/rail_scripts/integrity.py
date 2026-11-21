"""Integrity metadata shared by estimation and product-building stages."""

from __future__ import annotations

from hashlib import sha256
from struct import pack

import numpy as np


INTEGRITY_GROUP = "pz_compute"
FINGERPRINT_ALGORITHM = "sha256-canonical-v1"


def row_id_fingerprint(values) -> str:
    """Return an order-sensitive, platform-independent SHA-256 fingerprint."""
    array = np.asarray(values)
    if array.ndim != 1:
        raise ValueError("row identifier column must be one-dimensional")

    digest = sha256()
    digest.update(b"pz-compute-row-id-v1\0")
    digest.update(pack(">Q", len(array)))

    if np.issubdtype(array.dtype, np.signedinteger):
        digest.update(b"signed-int64\0")
        digest.update(np.ascontiguousarray(array, dtype="<i8").tobytes())
    elif np.issubdtype(array.dtype, np.unsignedinteger):
        digest.update(b"unsigned-int64\0")
        digest.update(np.ascontiguousarray(array, dtype="<u8").tobytes())
    elif array.dtype.kind in ("S", "U") or (
        array.dtype.kind == "O"
        and all(isinstance(value, (str, bytes)) for value in array)
    ):
        digest.update(b"utf8\0")
        for value in array:
            encoded = value if isinstance(value, bytes) else str(value).encode("utf-8")
            digest.update(pack(">Q", len(encoded)))
            digest.update(encoded)
    else:
        raise ValueError(
            "row identifier column must contain signed integers, unsigned integers, "
            "or strings"
        )

    return digest.hexdigest()
