""" Evaluate available methods' power and size.
argv[1] should be the name of the dataset to use (see
experiment_settings.py).

The results are saved to SAVE_DIR/{argv[1]}_results.pkl.
"""
import os
import sys
import time
from collections import defaultdict
import joblib
import numpy as np

# Import all the conditional independence methods we have implemented.
from independence_test.methods import cond_cci
from independence_test.methods import cond_hsic
from independence_test.methods import cond_kcit
from independence_test.methods import cond_rcit
from independence_test.methods import cond_kcipt

# Import all the datasets we have implemented
from independence_test.data import make_chaos_data
from independence_test.data import make_pnl_data
from independence_test.data import make_discrete_data
from independence_test.data import make_chain_data

# Import DTIT.
from dtit import dtit, dtit_parallel

# Choose the sample numbers we will iterate over.
SAMPLE_NUMS = np.logspace(np.log10(100), np.log10(10000), 20).astype(int)
# Set a limit (in seconds) on each trial. Methods that go over
# will be forcefully terminated and will return -1 as p-value.
MAX_TIME = 60

# Make a dict of methods.
COND_METHODS = {'dtit': dtit_parallel,
                'rcit': cond_rcit,
                'cci': cond_cci,
                'chsic': cond_hsic,
                'kcit': cond_kcit,
                'kcipt': cond_kcipt}

# Make a dict of the datasets, as well as the values of the dataset 
# 'complexity' parameter we want to consider, and the dataset dimen-
# sionalities we want to consider (see documentation for each data-
# set for permissible complexity and dimensionality values).
DSETS = {'chaos': (make_chaos_data, [.01, .04, .16, .32, .5, .68, .84, .96, .99], [1]),
        'pnl': (make_pnl_data, [0], [1, 2, 4, 8, 16, 32, 64, 128, 256]),
         'discrete': (make_discrete_data, [8, 32], [8, 32]),#[2, 8, 32], [2, 8, 32]),
         'chain': (make_chain_data, [1], [1, 2, 4, 8, 16, 32, 64, 128, 256])}

def check_if_too_slow(res, method, dset, n_samples, dim, param):
    # If this method failed with the same param, but smaller n_samples
    # or same dim, but smaller n_samples, return True.

    for ns in SAMPLE_NUMS:
        if ns > n_samples:
            break
        key_prev = '{}_{}_{}mt_{}samples_{}dim_{}complexity'.format(
            method, dset, MAX_TIME, ns, dim, param)
        if res[key_prev] == []:
            break
        if (res[key_prev][-1][0] < 0 or res[key_prev][-1][1] < 0
            or res[key_prev][-1][2] > MAX_TIME):
            return True

    for d in DSETS[dset][2]:
        if ns > n_samples:
            break
        key_prev = '{}_{}_{}mt_{}samples_{}dim_{}complexity'.format(
            method, dset, MAX_TIME, n_samples, d, param)
        if res[key_prev] == []:
            break
        if (res[key_prev][-1][0] < 0 or res[key_prev][-1][1] < 0
            or res[key_prev][-1][2] > MAX_TIME):
            return True
    return False

if __name__ == "__main__":
    dset = sys.argv[1]
    dataset = DSETS[dset]
    method_name = sys.argv[2]
    RESULTS = defaultdict(list)

    SAVE_FNAME = os.path.join(
            'independence_test', 'saved_data', dset + '_parallel',
                '{}.pkl'.format(method_name))

    for dim in dataset[2]:
        for param in dataset[1]:
            for n_samples in SAMPLE_NUMS:
                # Create a conditionally dependent and a conditionally
                # independent version of the dataset.
                np.random.seed(n_samples)
                xd, yd, zd = dataset[0](type='dep', n_samples=n_samples,
                                        dim=dim, complexity=param)
                xi, yi, zi = dataset[0](type='indep', n_samples=n_samples,
                                        dim=dim, complexity=param)

                key = '{}_{}_{}mt_{}samples_{}dim_{}complexity'.format(
                    method_name, dset, MAX_TIME, n_samples, dim, param)
                print('=' * 70)
                print(key)
                print('=' * 70)

                if check_if_too_slow(RESULTS, method_name, dset,
                        n_samples, dim, param):
                    # If the method has been too slow for less
                    # time-consuming settings, assume it'd be too
                    # slow now too, and don't run it.
                    pval_d = (-3., np.array([-3.]), np.array([-3.]))
                    pval_i = (-3., np.array([-3.]), np.array([-3.]))
                    toc = -3.
                else:
                    # Run the test on ceonditionally-dependent and
                    # independent data.
                    method = COND_METHODS[method_name]
                    tic = time.time()
                    pval_d = method.test(xd, yd, zd, max_time=MAX_TIME,
                        verbose=False, plot_return=True, max_dim=100)
                    pval_i = method.test(xi, yi, zi, max_time=MAX_TIME,
                        verbose=False, plot_return=True, max_dim=100)
                    toc = time.time() - tic

                RESULTS[key].append((pval_d, pval_i, toc))
                joblib.dump(RESULTS, SAVE_FNAME)
                print('time {:.4}s, p_d {}, p_i {}.'.format(
                    toc, pval_d[0] if method_name in ['nn', 'dtit'] else pval_d,
                    pval_i[0] if method_name in ['nn', 'dtit'] else pval_i))
