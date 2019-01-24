"""$DOC"""

__version__ = "$VERSION"
__revision__ = "$REVISION"

import pytest

_STR_FALSE = ["0", "no", "n", "false", "f", "off"]
_STR_TRUE = ["1", "yes", "y", "true", "t", "on"]

_automark = False
_ignore_unknown = False


def _get_bool(value):
    """
    Evaluate string representation of a boolean value.
    """
    if not value:
        return False
    if value.lower() in _STR_FALSE:
        return False
    if value.lower() in _STR_TRUE:
        return True
    raise ValueError("Invalid truth value '%s'" % value)


class DependencyItemStatus(object):
    """
    Status of a test item in a dependency manager.
    """

    PHASES = ('setup', 'call', 'teardown')

    def __init__(self):
        self.results = {w: None for w in self.PHASES}

    def __str__(self):
        return "Status(%s)" % ", ".join(
            "%s: %s" % (w, self.results[w])
            for w in self.PHASES
        )

    def add_result(self, rep):
        self.results[rep.when] = rep.outcome

    @property
    def is_success(self):
        return list(self.results.values()) == ['passed', 'passed', 'passed']


class DependencyManager(object):
    """
    Dependency manager, stores the results of tests.
    """

    SCOPE_CLASSES = {
        'class': pytest.Class,
        'module': pytest.Module,
        'session': pytest.Session,
    }

    @classmethod
    def get_manager(cls, item, scope='module'):
        """
        Get the DependencyManager object from the node at scope level.
        Create it, if not yet present.
        """
        node = item.getparent(cls.SCOPE_CLASSES[scope])
        if not node:
            return None
        if not hasattr(node, 'dependency_manager'):
            node.dependency_manager = cls(scope)
        return node.dependency_manager

    def __init__(self, scope):
        self.results = {}
        self.scope = scope

    def _gen_name(self, item):
        if self.scope == "session":
            return item.nodeid.replace("::()::", "::")
        if item.cls and self.scope == "module":
            return "%s::%s" % (item.cls.__name__, item.name)
        return item.name

    def add_result(self, item, name, rep):
        if not name:
            name = self._gen_name(item)
        status = self.results.setdefault(name, DependencyItemStatus())
        status.add_result(rep)

    def _check_depend_all(self, item):
        for key in self.results:
            if self.results[key].is_success:
                continue
            pytest.skip("%s depends on all previous tests passing (%s failed)" % (item.name, key))

    def check_depend(self, depends, item):
        if depends == "all":
            return self._check_depend_all(item)

        for i in depends:
            if i in self.results:
                if self.results[i].is_success:
                    continue
            else:
                if _ignore_unknown:
                    continue
            pytest.skip("%s depends on %s" % (item.name, i))


def depends(request, other):
    """
    Add dependency on other test.

    Call pytest.skip() unless a successful outcome of all of the tests in
    other has been registered previously.  This has the same effect as
    the `depends` keyword argument to the :func:`pytest.mark.dependency`
    marker.  In contrast to the marker, this function may be called at
    runtime during a test.

    :param request: the value of the `request` pytest fixture related
        to the current test.
    :param other: dependencies, a list of names of tests that this
        test depends on.
    :type other: iterable of :class:`str`

    .. versionadded:: 0.2
    """
    item = request.node
    manager = DependencyManager.get_manager(item)
    manager.check_depend(other, item)


def pytest_addoption(parser):
    parser.addini(
        "automark_dependency",
        "Add the dependency marker to all tests automatically",
        default=False,
    )
    parser.addoption(
        "--ignore-unknown-dependency",
        action="store_true",
        default=False,
        help="ignore dependencies whose outcome is not known"
    )


def pytest_configure(config):
    global _automark, _ignore_unknown
    _automark = _get_bool(config.getini("automark_dependency"))
    _ignore_unknown = config.getoption("--ignore-unknown-dependency")
    config.addinivalue_line(
        "markers",
        "dependency(name=None, depends=[]): "
        "mark a test to be used as a dependency for "
        "other tests or to depend on other tests.",
    )


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Store the test outcome if this item is marked "dependency".
    """
    outcome = yield
    marker = item.get_closest_marker("dependency")
    if marker is not None:
        name = marker.kwargs.get('name')
    elif _automark:
        name = None
    else:
        return

    rep = outcome.get_result()
    # Store the test outcome for each scope if it exists
    for scope in DependencyManager.SCOPE_CLASSES:
        manager = DependencyManager.get_manager(item, scope=scope)
        if not manager:
            continue
        manager.add_result(item, name, rep)


def pytest_runtest_setup(item):
    """
    Check dependencies if this item is marked "dependency".
    Skip if any of the dependencies has not been run successfully.
    """
    marker = item.get_closest_marker("dependency")
    if marker is None:
        return

    depends = marker.kwargs.get('depends')
    if not depends:
        return

    scope = marker.kwargs.get('scope', 'module')
    manager = DependencyManager.get_manager(item, scope=scope)
    manager.check_depend(depends, item)
