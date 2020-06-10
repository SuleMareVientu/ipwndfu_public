import sys

__all__ = ['AutoFinalizedObject']


class _AutoFinalizedObjectBase(object):
    """
    Base class for objects that get automatically
    finalized on delete or at exit.
    """

    def _finalize_object(self):
        """Actually finalizes the object (frees allocated resources etc.).

        Returns: None

        Derived classes should implement this.
        """
        pass

    def __new__(cls, *args, **kwargs):
        """Creates a new object instance and adds the private finalizer
        attributes to it.

        Returns: new object instance

        Arguments:
        * *args, **kwargs -- ignored
        """
        instance = super(_AutoFinalizedObjectBase, cls).__new__(cls)
        instance._finalize_called = False
        return instance

    def _do_finalize_object(self):
        """Helper method that finalizes the object if not already done.

        Returns: None
        """
        if not self._finalize_called: # race-free?
            self._finalize_called = True
            self._finalize_object()

    def finalize(self):
        """Finalizes the object if not already done.

        Returns: None
        """
        raise NotImplementedError(
            "finalize() must be implemented by AutoFinalizedObject."
        )

    def __del__(self):
        self.finalize()


if sys.hexversion >= 0x3040000:
    import weakref

    def _do_finalize_object_ref(obj_ref):
        """Helper function for weakref.finalize() that dereferences a weakref
        to an object and calls its _do_finalize_object() method if the object
        is still alive. Does nothing otherwise.

        Returns: None (implicit)

        Arguments:
        * obj_ref -- weakref to an object
        """
        obj = obj_ref()
        if obj is not None:
            # else object disappeared
            obj._do_finalize_object()


    class AutoFinalizedObject(_AutoFinalizedObjectBase):

        def __new__(cls, *args, **kwargs):
            """Creates a new object instance and adds the private finalizer
            attributes to it.

            Returns: new object instance

            Arguments:
            * *args, **kwargs -- passed to the parent instance creator
                                 (which ignores them)
            """
            instance = super(AutoFinalizedObject, cls).__new__(
                cls, *args, **kwargs
            )

            instance._finalizer = weakref.finalize(
                instance, _do_finalize_object_ref, weakref.ref(instance)
            )

            return instance

        def finalize(self):
            """Finalizes the object if not already done."""
            self._finalizer()


else:
    class AutoFinalizedObject(_AutoFinalizedObjectBase):

        def finalize(self):
            """Finalizes the object if not already done."""
            self._do_finalize_object()
