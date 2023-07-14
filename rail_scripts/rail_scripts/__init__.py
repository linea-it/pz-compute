from os.path import isfile
from sys import stderr
import yaml
import ceci

from xdg.BaseDirectory import load_data_paths

VERSION_TEXT = "rail_scripts 0.1.0"
PROJECT_NAME = "rail_scripts"
ESTIMATOR_CONFIGURATION_TEMPLATE = "estimator_%s.pkl"
PARAMS_TEMPLATE = "%s_params.yaml"
DEFAULT_BANDS = ("u", "g", "r", "i", "z", "y")


def abort():
    raise SystemExit(1)


def error(msg, **kwargs):
    print(msg, file=stderr, **kwargs)


info = debug = warning = error


def find_data_file(file_name):
    if isfile(file_name):
        return file_name

    for data_file in load_data_paths(PROJECT_NAME, file_name):
        if isfile(data_file):
            return data_file

    # Non existent file just returns the original file name, so that it
    # can be tracked later.
    return file_name


def find_estimator_configuration(model_name):
    model_file = ESTIMATOR_CONFIGURATION_TEMPLATE % model_name

    return find_data_file(model_file)


def map_bands(template, bands):
    return [template.format(band=band) for band in bands]


def create_column_mapping_dict(column_template, column_template_error, def_maglimits):
    bands = DEFAULT_BANDS

    band_names = map_bands(column_template, bands)
    band_err_names = map_bands(column_template_error, bands)
    ref_band = column_template.format(band="i")

    mag_limits = {
        name: def_maglimits["mag_%s_lsst" % band]
        for (band, name) in zip(bands, band_names)
    }

    return {
        "bands": band_names,
        "band_names": band_names,
        "err_bands": band_err_names,
        "band_err_names": band_err_names,
        "ref_band": ref_band,
        "prior_band": ref_band,
        "mag_limits": mag_limits,
    }


def load_user_params(estimator, estimator_name):
    """_summary_

    Args:
        estimator (_type_): _description_
        estimator_name (_type_): _description_
    """

    user_params = find_user_params(estimator_name)
    default_params = dict(estimator.config_options)

    params = {}
    for name, value in user_params.items():
        if name in default_params:
            new_value = set_estimator_param(name, value, default_params)
            if not new_value:
                error(
                    (
                        "The configuration {} was not modified as it is not in the "
                        "same expected type or is not a valid configuration."
                    ).format(name)
                )
            params[name] = new_value

    return params


def set_estimator_param(name, value, default_params):
    param = default_params.get(name)
    if isinstance(param, ceci.config.StageParameter) and isinstance(value, param.dtype):
        return value
    return None


def find_user_params(estimator_name):
    filepath = PARAMS_TEMPLATE % estimator_name

    if not isfile(filepath):
        return {}

    with open(filepath, encoding="UTF-8") as estfile:
        data = yaml.load(estfile, Loader=yaml.loader.SafeLoader)
        return data
