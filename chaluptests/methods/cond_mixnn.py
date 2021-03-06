""" A conditional (and unconditional!) independence test
based on neural network regression. This implementation
uses Tensorflow and sklearn.

Reference:
Chalupka, Krzysztof and Perona, Pietro and Eberhardt, Frederick, 2017.
"""
import sys
import time
import numpy as np
from scipy.stats import ttest_ind
import tensorflow as tf
from neural_networks import nn
from ..utils import equalize_dimensions
from scipy.stats import ttest_1samp

# Define available test statistic functions.
FS = {'min': lambda x, y: np.min(x) / np.min(y), 
      'mean': lambda x, y: np.mean(x) - np.mean(y)}


def bootstrap_mindiv(d0s, d1s):
    f = lambda x, y: np.min(x) / np.min(y)
    t_obs = f(d0s, d1s)
    t_star = bootstrap(d0s, d1s, f=f)
    p_value = np.sum(t_star > t_obs) / float(t_star.size)
    return p_value


def bootstrap_ttest(d0s, d1s):
    tstat, p_value = ttest_1samp(d0s / d1s, 1)
    if np.mean(d0s / d1s) > 1:
        p_value /= 2.
    else:
        p_value = 1 - p_value / 2.
    return p_value


def bootstrap_mindiff(d0s, d1s):
    f = lambda x, y: np.min(x) - np.min(y)
    t_obs = f(d0s, d1s)
    t_star = bootstrap(d0s, d1s, f=f)
    p_value = np.sum(t_star > t_obs) / float(t_star.size)
    return p_value


def mse(y_pred, y):
    """ Compute the mean squared error.

    Args:
        y_pred (n_samples, x_dim): First variable.
        y (n_samples, y_dim): Second variable.

    Returns
        mse: The test statistic: mean-squared error on a validation set.
    """
    return np.mean((y - y_pred)**2)


def bootstrap(h0, h1, f, B=10000):
    """ Bootstrap the test statistic.

    Args:
        h0: Iterable of length m.
        h1: Iterable of length n.
        f: Function taking (h0, h1) to a test statistic.
        B (int): Number of bootstrap samples to create.

    Returns:
        t_star (B,): Bootstraped means of the two distributions.
    """
    t_star = np.zeros(B)
    m = len(h0)
    n = len(h1)
    all_h = np.concatenate([h0, h1])
    for b_id in range(B):
        b_data = np.random.choice(all_h, size=m + n, replace=True)
        t_star[b_id] = f(b_data[:m], b_data[m:])
    return t_star


def test(x, y, z=None, num_perm=10, prop_test=.1,
             max_time=60, discrete=(False, False),
             plot_return=False, test_type='min',
             verbose=False, fixed_arch=False, bootstrap_type='mindiv', **kwargs):
    """ The neural net probabilistic independence test.
    See Chalupka, Perona, Eberhardt 2017.

    Args:
        x (n_samples, x_dim): First variable.
        y (n_samples, y_dim): Second variable.
        z (n_samples, z_dim): Conditioning variable.
        num_perm: Number of data permutations to estimate
            the p-value from marginal stats.
        prop_test (int): Proportion of data to evaluate test stat on.
        max_time (float): Time limit for the test (approximate).
        discrete (bool, bool): Whether x or y are discrete.
        plot_return (bool): If True, return statistics useful for plotting.
        test_type (str): Test statistic type, can be 'min', 'mean'.
        verbose (bool): Print out progress messages (or not).
        fixed_arch (bool): If True, keep the NN training procedure constant.
            If False, draw training parameters randomly at each permutation.
        kwargs: Arguments to pass to the neural net constructor.

    Returns:
        p (float): The p-value for the null hypothesis
            that x is independent of y.
    """
    # If x xor y is discrete, use the continuous variable as input.
    if discrete[0] and not discrete[1]:
        x, y = y, x
    # Otherwise, predict the variable with fewer dimensions.
    elif x.shape[1] < y.shape[1]:
        x, y = y, x

    # Adjust the dimensionalities of x, y, z to be on the same
    # order, by simple data duplication.
    x, y, z = equalize_dimensions(x, y, z)

    # Use this many datapoints as a test set.
    n_samples = x.shape[0]
    n_test = int(n_samples * prop_test)

    # Attach the conditioning variable to the input.
    x_z = np.hstack([x, z])

    # Set up storage.
    d0_preds = []
    d1_preds = []
    d0_stats = np.zeros(num_perm)
    d1_stats = np.zeros(num_perm)

    kwargs['epochs'] = 1000
    kwargs['lr'] = 1e-2
    kwargs['nn_verbose'] = True
    kwargs['batch_size'] = 128
    kwargs['ntype'] = 'plain'

    # Construct the neural net.
    if fixed_arch:
        clf = nn.NN(x_dim=x_z.shape[1], y_dim=y.shape[1],
            arch=[128]*2, ntype='plain')

    for perm_id in range(num_perm):
        # Create the d0 (reshuffled-x) dataset.
        perm_ids = np.random.permutation(n_samples)
        x_z_bootstrap = np.hstack([x[perm_ids], z])

        # Sample NN training params.
        if not fixed_arch:
            kwargs['arch'] = [32] * (perm_id + 1)
            clf = nn.NN(x_dim=x_z.shape[1], y_dim=y.shape[1], **kwargs)
            print(('lr={lr:.2}, bs={batch_size}, '
                    'arch={arch}, ntype={ntype}').format(**kwargs))

        with tf.Session() as sess:
            # Train on the reshuffled data.
            sess.run(tf.global_variables_initializer())
            clf.saver.save(sess, './init_nn_save')
            clf.fit(x_z_bootstrap[n_test:], y[n_test:], sess=sess, **kwargs)
            y_pred0 = clf.predict(x_z_bootstrap[:n_test], sess=sess)

            # Train on the original data.
            sess.run(tf.global_variables_initializer())
            clf.saver.restore(sess, './init_nn_save')
            clf.fit(x_z[n_test:], y[n_test:], sess=sess, **kwargs)
            y_pred1 = clf.predict(x_z[:n_test], sess=sess)

        d0_preds.append(y_pred0)
        d0_stats[perm_id] = mse(y_pred0, y[:n_test])
        d1_preds.append(y_pred1)
        d1_stats[perm_id] = mse(y_pred1, y[:n_test])

        if verbose:
            print('D0 statistic, iter {}: {}'.format(
                perm_id, d0_stats[perm_id]))
            print('D1 statistic, iter {}: {}'.format(
                perm_id, d1_stats[perm_id]))

        print('Resetting Tensorflow graph...')
        tf.reset_default_graph()
        
    # Compute the p-value.
    p_value = globals()['bootstrap_' + bootstrap_type](d0_stats, d1_stats)

    if plot_return:
        return (p_value, d0_stats, d1_stats)
    else:
        return p_value
