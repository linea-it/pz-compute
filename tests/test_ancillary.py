import h5py
import numpy as np

from rail_scripts.ancillary import load_estimator_ancillary


def test_load_estimator_ancillary_uses_explicit_allow_list(tmp_path):
    path = tmp_path / "estimate.hdf5"
    with h5py.File(path, "w") as handle:
        source = handle.create_group("ancil")
        source.create_dataset("DNF_ZN", data=np.array([0.1, 0.2]))
        source.create_dataset("photozerr", data=np.array([0.3, 0.4]))

    with h5py.File(path, "r") as handle:
        result = load_estimator_ancillary(handle, ("DNF_ZN",), 2)

    assert list(result) == ["DNF_ZN"]
    np.testing.assert_allclose(result["DNF_ZN"], [0.1, 0.2])


def test_load_estimator_ancillary_validates_presence_shape_and_rows(tmp_path):
    path = tmp_path / "estimate.hdf5"
    with h5py.File(path, "w") as handle:
        source = handle.create_group("ancil")
        source.create_dataset("matrix", data=np.ones((2, 2)))
        source.create_dataset("short", data=np.ones(1))

    with h5py.File(path, "r") as handle:
        with np.testing.assert_raises(ValueError):
            load_estimator_ancillary(handle, ("missing",), 2)
        with np.testing.assert_raises(ValueError):
            load_estimator_ancillary(handle, ("matrix",), 2)
        with np.testing.assert_raises(ValueError):
            load_estimator_ancillary(handle, ("short",), 2)


def test_empty_estimator_ancillary_allow_list_needs_no_source_group(tmp_path):
    path = tmp_path / "estimate.hdf5"
    with h5py.File(path, "w") as handle:
        assert load_estimator_ancillary(handle, (), 0) == {}
