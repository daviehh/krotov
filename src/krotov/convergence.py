r"""Routines for `check_convergence` in :func:`krotov.optimize.optimize_pulses`

A `check_convergence` function may be used to determine whether an optimization
is converged, and thus can be stopped before the maximum number of
iterations (`iter_stop`) is reached. A function suitable for
`check_convergence` must receive a :class:`.Result` object, and return a value
that evaluates as True or False in a Boolean context, indicating whether the
optimization has converged or not.

The :class:`.Result` object that the `check_convergence` function receives as
an argument will be up-to-date for the current iteration. That is, it will
already contain the current values from :func:`.optimize_pulses`'s `info_hook`
in :attr:`.Result.info_vals`, the current :attr:`~.Result.tau_vals`, etc.  The
:attr:`.Result.optimized_controls` attribute will contain the current optimized
pulses (defined on the intervals of :attr:`~.Result.tlist`). The
`check_convergence` function should not modify the :class:`.Result` object it
receives in any way. The proper place for custom modifications after each
iteration in :func:`.optimize_pulses` is through the `info_hook` routine.

It is recommended that a `check_convergence` function returns None (which is
False in a Boolean context) if the optimization has not yet converged. If the
optimization has converged, `check_convergence` should return a message string
(which is True in a Boolean context). The returned string will be included in
the final :attr:`.Result.message`.

A typical usage for `check_convergence` is ending the optimization when the
optimization functional falls below a specified limit. Such a
`check_convergence` function can be generated by :func:`value_below`.
By default, this assumes that the `info_hook` passed to
:func:`.optimize_pulses` returns the value of the functional,
which is then stored in :attr:`.Result.info_vals`. Alternatively,
:func:`value_below` could be told to look at the :attr:`.Result.tau_vals`.

Similarly, one might stop the optimization when there is an insufficient
improvement between iterations. The :func:`delta_below` function generates a
`check_convergence` function for this purpose.  Multiple convergence conditions
("stop optimization when :math:`J_T` reaches :math:`10^{-5}`, or if
:math:`\Delta J_T < 10^{-6}`") can be defined via :func:`Or`.

While Krotov's method is guaranteed to monotonically converge in the continuous
limit, this no longer strictly holds when time is discretized (in particular if
:attr:`~.PulseOptions.lambda_a` is too small). You can use
:func:`check_monotonic_error` or :func:`check_monotonic_fidelity` as a
`check_convergence` function that stops the optimization when monotonic
convergence is lost.
"""
from operator import xor
import glom

__all__ = [
    'Or',
    'value_below',
    'delta_below',
    'check_monotonic_error',
    'check_monotonic_fidelity',
]


def Or(*funcs):
    """Chain multiple `check_convergence` functions together in a logical Or.

    Each parameter must be a function suitable to pass to
    :func:`~krotov.optimize.optimize_pulses` as `check_convergence`. It
    must receive a :class:`.Result` object and should return None or a string
    message.

    Returns:
        callable: A function ``check_convergence(result)`` that returns the
        result of the first "non-passing" function in `*funcs`. A "non-passing"
        result is one that evaluates to True in a Boolean context (should be a
        string message)
    """

    def check_convergence(result):
        for func in funcs:
            msg = func(result)
            if bool(msg) is True:
                return msg
        return None

    return check_convergence


def value_below(limit, spec=('info_vals', glom.T[-1]), name=None, **kwargs):
    """Constructor for routine that checks if a value is below `limit`

    Args:
        limit (float or str): A float value (or str-representation of a float)
            against which to compare the value extracted from :class:`.Result`
        spec: A :func:`~glom.glom` specification of the :class:`.Result`
            attribute from which to extract the value to compare against
            `limit`. Defaults to a spec extracting the last value in
            :attr:`.Result.info_vals`.
        name (str or None): A name identifying the checked value, used for the
            message returned by the `check_convergence` routine. Defaults to
            ``str(spec)``.
        **kwargs: Keyword arguments to pass to :func:`~glom.glom`

    Returns:
        callable: A function ``check_convergence(result)`` that extracts the
        value specified by `spec` from the :class:`.Result` object, and checks
        it against `limit`. If the value is below the `limit`, it returns an
        appropriate message string. Otherwise, it returns None.

    Note:
        If you find :func:`~glom.glom`-specifications intimidating: A simple
        callable acting on :class:`.Result` is also a valid `spec`. However, if
        you use a callable `spec`, make sure to pass an appropriate `name`.

        The `spec` in the following example is equivalent to the default
        ``spec=('info_vals', glom.T[-1])``.

    Example:

        >>> check_convergence = value_below(
        ...     limit='1e-4',
        ...     spec=lambda r: r.info_vals[-1],
        ...     name='J_T'
        ... )
        >>> r = krotov.result.Result()
        >>> r.info_vals.append(1e-4)
        >>> check_convergence(r)  # returns None
        >>> r.info_vals.append(9e-5)
        >>> check_convergence(r)
        'J_T < 1e-4'
    """

    if name is None:
        name = str(spec)

    def check_convergence(result):
        v = glom.glom(result, spec, **kwargs)
        if v < float(limit):
            return "%s < %s" % (name, limit)
        else:
            return None

    return check_convergence


def delta_below(
    limit,
    spec1=('info_vals', glom.T[-1]),
    spec0=('info_vals', glom.T[-2]),
    absolute_value=True,
    name=None,
    **kwargs
):
    r"""Constructor for a routine that checks if
    $\Abs{v_1 - v_0} < \varepsilon$

    Args:
        limit (float or str): A float value (or str-representation of a float)
            for $\varepsilon$
        spec1: A :func:`~glom.glom` specification of the :class:`.Result`
            attribute from which to extract $v_1$. Defaults to a spec
            extracting the last value in :attr:`.Result.info_vals`.
        spec0: A :func:`~glom.glom` specification of the :class:`.Result`
            attribute from which to extract $v_0$.  Defaults to a spec
            extracting the last-but-one value in :attr:`.Result.info_vals`.
        absolute_value (bool): If False, check for $v_1 - v_0 < \varepsilon$,
            instead of the absolute value.
        name (str or None): A name identifying the delta, used for the
            message returned by the `check_convergence` routine. Defaults to
            ``"Δ({spec1},{spec0}"``.
        **kwargs: Keyword arguments to pass to :func:`~glom.glom`

    Note:
        You can use :func:`delta_below` to implement a check for strict
        monotonic convergence, e.g. when `info_hook` returns the optimization
        error, by flipping `spec0` and `spec1`, setting `limit` to zero, and
        setting `absolute_value` to False. See :func:`check_monotonic_error`.

    Example:

        >>> check_convergence = delta_below(limit='1e-4', name='ΔJ_T')
        >>> r = krotov.result.Result()
        >>> r.info_vals.append(9e-1)
        >>> check_convergence(r)  # None
        >>> r.info_vals.append(1e-1)
        >>> check_convergence(r)  # None
        >>> r.info_vals.append(4e-4)
        >>> check_convergence(r)  # None
        >>> r.info_vals.append(2e-4)
        >>> check_convergence(r)  # None
        >>> r.info_vals.append(1e-6)
        >>> check_convergence(r)  # None
        >>> r.info_vals.append(1e-7)
        >>> check_convergence(r)
        'ΔJ_T < 1e-4'
    """
    if name is None:
        name = "Δ(%s,%s)" % (spec1, spec0)

    def check_convergence(result):
        delayed_exc = None
        try:
            v1 = glom.glom(result, spec1, **kwargs)
        except (AttributeError, KeyError, IndexError, glom.GlomError) as exc:
            v1 = None
            delayed_exc = exc
        try:
            v0 = glom.glom(result, spec0, **kwargs)
        except (AttributeError, KeyError, IndexError, glom.GlomError) as exc:
            v0 = None
            delayed_exc = exc
        if xor((v1 is None), (v0 is None)):
            # After the first iteration, there may not be enough data to get
            # *both* v1 and v0. In this case, we just pass the check...
            return None
        else:
            # ... However, if we can access neither v1 nor v0, then something
            # is definitely wrong, and we should re-raise the original
            # exception
            if delayed_exc is not None:
                raise delayed_exc
        delta = v1 - v0
        if absolute_value:
            delta = abs(delta)
        if delta < float(limit):
            return "%s < %s" % (name, limit)
        else:
            return None

    return check_convergence


_monotonic_convergence = delta_below(
    limit=0,
    spec1=('info_vals', glom.T[-2]),
    spec0=('info_vals', glom.T[-1]),
    absolute_value=False,
    name="Loss of monotonic convergence; error decrease",
)


_monotonic_fidelity = delta_below(
    limit=0,
    spec1=('info_vals', glom.T[-1]),
    spec0=('info_vals', glom.T[-2]),
    absolute_value=False,
    name="Loss of monotonic convergence; fidelity increase",
)


def check_monotonic_error(result):
    """Check for monotonic convergence with respect to the error

    Check that the last value in :attr:`.Result.info_vals` is
    smaller than the last-but-one value. If yes, return None. If no, return an
    appropriate error message.

    This assumes that the `info_hook` passed to :func:`.optimize_pulses`
    returns the value of the functional, which is then available in
    :attr:`.Result.info_vals`.

    Example:

        >>> r = krotov.result.Result()
        >>> r.info_vals.append(9e-1)
        >>> check_monotonic_error(r)  # None
        >>> r.info_vals.append(1e-1)
        >>> check_monotonic_error(r)  # None
        >>> r.info_vals.append(2e-1)
        >>> check_monotonic_error(r)
        'Loss of monotonic convergence; error decrease < 0'

    See also:
        Use :func:`check_monotonic_fidelity` for when `info_hook` returns a
        "fidelity", that is, a measure that should *increase* in each
        iteration.
    """
    # This is a wrapper for `_monotonic_convergence` just so that we can have
    # `check_monotonic_convergence` with a nice docstring.
    return _monotonic_convergence(result)


def check_monotonic_fidelity(result):
    """Check for monotonic convergence with respect to the fidelity

    This is like :func:`check_monotonic_error`, but looking for a monotonic
    *increase* in the values in :attr:`.Result.info_vals`. Thus, it is assumed
    that the `info_hook` returns a fidelity, not an error.

    Example:
        >>> r = krotov.result.Result()
        >>> r.info_vals.append(0.0)
        >>> check_monotonic_fidelity(r)  # None
        >>> r.info_vals.append(0.2)
        >>> check_monotonic_fidelity(r)  # None
        >>> r.info_vals.append(0.15)
        >>> check_monotonic_fidelity(r)
        'Loss of monotonic convergence; fidelity increase < 0'
    """
    return _monotonic_fidelity(result)