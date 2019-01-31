"""$DOC"""
import pytest

from .config import conf
from .dependency import Dependency, Item, DependencyFinder

__version__ = "$VERSION"
__revision__ = "$REVISION"


def depends(request, other, scope=Dependency.SCOPE_DEFAULT):
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
    Item.get(item).check_skip(*Dependency.read_list(scope, *other))


def pytest_addoption(parser):
    return conf.pytest_addoption(parser)


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
    return Item.get(item).pytest_runtest_makereport()


def pytest_runtest_setup(item):
    """
    Check dependencies if this item is marked "dependency".
    Skip if any of the dependencies has not been run successfully.
    """
    return Item.get(item).check_skip()
