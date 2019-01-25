"""$DOC"""
import pytest
from _pytest.nodes import Item

from .config import conf
from .dependency import Dependency, DependencyManager

__version__ = "$VERSION"
__revision__ = "$REVISION"


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
        'markers',
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
    marker = item.get_closest_marker('dependency')
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
        if manager is None:
            continue
        manager[name] = dependency


def pytest_runtest_setup(item: Item):
    """
    Check dependencies if this item is marked "dependency".
    Skip if any of the dependencies has not been run successfully.
    """
    marker = item.get_closest_marker('dependency')
    if marker is None:
        return

    dependencies = marker.kwargs.get('depends')
    if not dependencies:
        return

    scope = marker.kwargs.get('scope', DependencyManager.SCOPE_DEFAULT)
    manager = DependencyManager.get(item, scope=scope)
    manager.check_depend(dependencies, item)
