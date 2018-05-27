import numpy as np


def test_growfactor_start_year(growfactors):
    first_growfactors_year = growfactors.index.min()
    first_taxcalc_policy_year = 2013
    assert first_growfactors_year <= first_taxcalc_policy_year


def test_growfactor_values(growfactors):
    first_year = growfactors.index.min()
    for fname in growfactors:
        if fname != 'YEAR':
            assert growfactors[fname][first_year] == 1.0
    min_value = 0.50
    max_value = 1.60
    for fname in growfactors:
        if fname != 'YEAR':
            assert growfactors[fname].min() >= min_value
            assert growfactors[fname].max() <= max_value
