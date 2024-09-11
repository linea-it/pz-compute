import importlib.util
import sys

module_name = 'rail_scripts'
spec = importlib.util.spec_from_file_location(module_name, 'rail_scripts/rail-preprocess-parquet')

module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)

from module import dered

import pandas.testing as pd_testing

def test_dered():
    """ Unit test for dereddening function """

    A_EBV = {'u' : 4.81, 'g' : 3.64, 'r' : 2.70,
             'i' : 2.06, 'z' : 1.58, 'y' : 1.31}

    apply_dered = "sfd"

   
    input_table = pd.Dataframe({'mag_u': [75.121210, 26.671684, 30.535095],
                                'mag_g': [27.096551, 26.752316, 27.632894], 
                                'mag_r': [26.660967, 26.199939, 26.281313],
                                'mag_i': [26.277775, 26.492797, 26.080708], 
                                'mag_z': [25.930055, 26.032065, 25.856228],
                                'mag_y': [24.833418, 29.494424, 27.102938]}) 

    values = ['mag_u', 'mag_g', 'mag_r', 'mag_i', 'mag_z', 'mag_y']   

    ra_column = 'ra'
    dec_column = 'dec'


    output_table = pd.Dataframe({'mag_u': [74.956912, 26.511667, 30.368855],
                                 'mag_g': [26.972218, 26.631222, 27.507090], 
                                 'mag_r': [26.568742, 26.110116, 26.187997], 
                                 'mag_i': [26.207410, 26.424266, 26.009512], 
                                 'mag_z': [25.876086, 25.979502, 25.801621], 
                                 'mag_y': [24.788672, 29.450843, 27.057663]})


    # Compare DataFrames with a tolerance level
    pd_testing.assert_frame_equal(dered(apply_dered, input_table, 
                                        values, ra_column, dec_column),
                                  output_table, 
                                  atol=1e-2)  


