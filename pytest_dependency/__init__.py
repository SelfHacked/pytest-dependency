"""$DOC"""

__version__ = "$VERSION"
__revision__ = "$REVISION"

import pytest

from .config import Config

conf = Config()


class Status(object):
    """
    Status of a test item.
    """

    PHASES = ('setup', 'call', 'teardown')
    SUCCESS = ['passed', 'passed', 'passed']

    def __init__(self):
        self.__results = {
            phase: None
            for phase in self.PHASES
        }

    def __str__(self):
        return "Status(%s)" % ", ".join(
            "%s: %s" % (w, self.__results[w])
            for w in self.PHASES
        )

    def __iadd__(self, report):
        self.__results[report.when] = report.outcome
        return self

    def __bool__(self):
        return list(self.__results.values()) == self.SUCCESS


class Dependency(object):
    """
    Test item
    """

    __DEPENDENCIES = {}

    @classmethod
    def get(cls, item):
        return cls.__DEPENDENCIES.setdefault(item, cls(item))

    def __init__(self, item):
        self.__item = item
        self.__status = Status()

    def add_report(self, report):
        self.__status += report

    @property
    def item(self):
        return self.__item

    @property
    def passed(self):
        return bool(self.__status)


class DependencyManager(object):
    """
    Dependency manager, stores the results of tests.
    """

    SCOPE_MODULE = 'module'
    SCOPE_CLASS = 'class'
    SCOPE_SESSION = 'session'

    SCOPE_DEFAULT = SCOPE_MODULE

    SCOPE_CLASSES = {
        SCOPE_MODULE: pytest.Module,
        SCOPE_CLASS: pytest.Class,
        SCOPE_SESSION: pytest.Session,
    }

    DEPEND_ALL = 'all'

    NODE_ATTR = 'dependency_manager'

    class DuplicateName(Exception):
        def __init__(self, name, item):
            self.name = name
            self.item = item

    @classmethod
    def get(cls, item, scope=SCOPE_DEFAULT):
        """
        Get the DependencyManager object from the node at scope level.
        Create it, if not yet present.
        """
        node = item.getparent(cls.SCOPE_CLASSES[scope])
        if not node:
            return None
        if not hasattr(node, cls.NODE_ATTR):
            setattr(node, cls.NODE_ATTR, cls(node, scope))
        return node.dependency_manager

    def __init__(self, node, scope):
        self.__node = node
        self.__scope = scope
        self.__items = {}

    def _gen_name(self, item):
        item = item.item
        if self.__scope == self.SCOPE_SESSION:
            return item.nodeid.replace("::()::", "::")
        if item.cls and self.__scope == self.SCOPE_MODULE:
            return "%s::%s" % (item.cls.__name__, item.name)
        return item.name

    def __contains__(self, name):
        return name in self.__items

    def __iter__(self):
        return iter(self.__items)

    def __getitem__(self, name):
        return self.__items[name]

    def __setitem__(self, name, item):
        if not name:
            name = self._gen_name(item)
        if name in self:
            if self[name] != item:
                raise self.DuplicateName(name, item)
        self.__items[name] = item

    def _check_depend_all(self, item):
        for key in self:
            if self[key].passed:
                continue
            pytest.skip("%s depends on all previous tests passing (%s failed)" % (item.name, key))

    def check_depend(self, dependencies, item):
        if dependencies == self.DEPEND_ALL:
            return self._check_depend_all(item)

        for name in dependencies:
            if name in self:
                if self[name].passed:
                    continue
            else:
                if conf.ignore_unknown:
                    continue
            pytest.skip("%s depends on %s" % (item.name, name))


def depends(request, other, scope=DependencyManager.SCOPE_DEFAULT):
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
    :param scope:
    :type other: iterable of :class:`str`

    .. versionadded:: 0.2
    """
    item = request.node
    manager = DependencyManager.get(item, scope=scope)
    manager.check_depend(other, item)


def pytest_addoption(parser):
    conf.pytest_addoption(parser)


def pytest_configure(config):
    conf.pytest_configure(config)
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
    elif conf.auto_mark:
        name = None
    else:
        return

    dependency = Dependency.get(item)
    report = outcome.get_result()
    dependency.add_report(report)
    # Store the test outcome for each scope if it exists
    for scope in DependencyManager.SCOPE_CLASSES:
        manager = DependencyManager.get(item, scope=scope)
        if not manager:
            continue
        manager[name] = dependency


def pytest_runtest_setup(item):
    """
    Check dependencies if this item is marked "dependency".
    Skip if any of the dependencies has not been run successfully.
    """
    marker = item.get_closest_marker("dependency")
    if marker is None:
        return

    dependencies = marker.kwargs.get('depends')
    if not dependencies:
        return

    scope = marker.kwargs.get('scope', 'module')
    manager = DependencyManager.get(item, scope=scope)
    manager.check_depend(dependencies, item)
