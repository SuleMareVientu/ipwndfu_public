import sys
import array

__all__ = ['_reduce', '_set', '_next', '_update_wrapper']

assert sys.hexversion >= 0x020400f0

try:
    import functools
    _reduce = functools.reduce
except (ImportError, AttributeError):
    _reduce = reduce

# all, introduced in Python 2.5
try:
    _all = all
except NameError:
    _all = lambda iter_ : _reduce( lambda x, y: x and y, iter_, True )

try:
    _set = set
except NameError:
    import sets
    _set = sets.Set

def _next(iter):
    try:
        return next(iter)
    except NameError:
        return iter.next()

try:
    import functools
    _update_wrapper = functools.update_wrapper
except (ImportError, AttributeError):
    def _update_wrapper(wrapper, wrapped):
        wrapper.__name__ = wrapped.__name__
        wrapper.__module__ = wrapped.__module__
        wrapper.__doc__ = wrapped.__doc__
        wrapper.__dict__ = wrapped.__dict__

def as_array(data=None):
    if data is None:
        return array.array('B')

    if isinstance(data, array.array):
        return data

    try:
        return array.array('B', data)
    except TypeError:
        a = array.array('B')
        a.fromstring(data) # deprecated since 3.2
        return a
