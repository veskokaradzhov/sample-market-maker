from decimal import Decimal
from typing import List


def to_nearest(num, tick_size):
    """Given a number, round it to the nearest tick. Very useful for sussing float error
       out of numbers: e.g. toNearest(401.46, 0.01) -> 401.46, whereas processing is
       normally with floats would give you 401.46000000000004.
       Use this after adding/subtracting/multiplying numbers."""
    tick_dec = Decimal(str(tick_size))
    return float((Decimal(round(num / tick_size, 0)) * tick_dec))


def estimate_exponential_lambda(values: List[float]) -> float:
    """
    Estimates the intensity parameter (lambda) of an exponential distribution
    p(x) = lambda * exp (- lambda * x)
    The mean of the exponential distribution is 1 / lambda
    The variance is 1 / (lambda ^ 2)

    :param values: list of floats (must be non-negative)
    :return: estimate of the lambda parameter
    """
    num_samples = len(values)
    sum_samples = sum(values)

    if num_samples > 2:
        if abs(sum_samples) < 1e-5:
            lambda_estimate = 0
        else:
            # calculate unbiased estimate
            lambda_estimate = (num_samples - 2) / sum_samples
    else:
        lambda_estimate = 0

    return lambda_estimate
