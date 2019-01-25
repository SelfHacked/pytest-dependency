import pytest
from _pytest.nodes import Item as PytestItem, Node
from _pytest.reports import TestReport
from typing import Mapping

from .config import conf


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
        return "Status({})".format(
            ", ".join(
                f"{phase}: {self.__results[phase]}"
                for phase in self.PHASES
            )
        )

    def __iadd__(self, report: TestReport):
        self.__results[report.when] = report.outcome
        return self

    def __bool__(self):
        return list(self.__results.values()) == self.SUCCESS


class Item(object):
    """
    Test item
    """

    __DEPENDENCIES = {}

    @classmethod
    def get(cls, item: PytestItem) -> 'Item':
        return cls.__DEPENDENCIES.setdefault(item, cls(item))

    def __init__(self, item: PytestItem):
        self.__item = item
        self.__status = Status()

    def add_report(self, report: TestReport):
        self.__status += report

    @property
    def item(self) -> PytestItem:
        return self.__item

    @property
    def passed(self) -> bool:
        return bool(self.__status)

    def pytest_runtest_setup(self):
        marker = self.item.get_closest_marker('dependency')
        if marker is None:
            return

        dependencies = marker.kwargs.get('depends')
        if not dependencies:
            return

        scope = marker.kwargs.get('scope', DependencyManager.SCOPE_DEFAULT)
        manager = DependencyManager.get(self.item, scope=scope)
        manager.check_depend(dependencies, self.item)

    def pytest_runtest_makereport(self):
        outcome = yield
        marker = self.item.get_closest_marker('dependency')
        if marker is not None:
            name = marker.kwargs.get('name')
        elif conf.auto_mark:
            name = None
        else:
            return

        report = outcome.get_result()
        self.add_report(report)
        # Store the test outcome for each scope if it exists
        for scope in DependencyManager.SCOPE_CLASSES:
            try:
                manager = DependencyManager.get(self.item, scope=scope)
            except DependencyManager.InvalidNode:
                continue
            manager[name] = self


class DependencyManager(Mapping[str, Item]):
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

    class InvalidNode(Exception):
        def __init__(self, item, scope):
            self.item = item
            self.scope = scope
            super().__init__(f"Item {item} has no scope {scope}")

    class DuplicateName(Exception):
        def __init__(self, name, dependency: Item):
            self.name = name
            self.dependency = dependency
            super().__init__(f"Name {name} has been used by a different dependency")

    @classmethod
    def get(cls, item: PytestItem, scope=SCOPE_DEFAULT) -> 'DependencyManager':
        """
        Get the DependencyManager object from the node at scope level.
        Create it, if not yet present.
        """
        node = item.getparent(cls.SCOPE_CLASSES[scope])
        if not node:
            raise cls.InvalidNode(item, scope)
        if not hasattr(node, cls.NODE_ATTR):
            setattr(node, cls.NODE_ATTR, cls(node, scope))
        return getattr(node, cls.NODE_ATTR)

    def __init__(self, node: Node, scope):
        self.__node = node
        self.__scope = scope
        self.__items = {}

    def _gen_name(self, item: PytestItem) -> str:
        if self.__scope == self.SCOPE_SESSION:
            return item.nodeid.replace("::()::", "::")
        if self.__scope == self.SCOPE_MODULE and item.cls:
            return f"{item.cls.__name__}::{item.name}"
        return item.name

    def __contains__(self, name):
        return name in self.__items

    def __len__(self):
        return len(self.__items)

    def __iter__(self):
        return iter(self.__items)

    def __getitem__(self, name) -> Item:
        return self.__items[name]

    def __setitem__(self, name, dependency: Item):
        if not name:
            name = self._gen_name(dependency.item)
        if name in self:
            if self[name] != dependency:
                raise self.DuplicateName(name, dependency)
        self.__items[name] = dependency

    def keys(self):
        return self.__items.keys()

    def values(self):
        return self.__items.values()

    def _check_depend_all(self, item: PytestItem):
        for name in self:
            if self[name].passed:
                continue
            pytest.skip(
                f"{item.name} depends on all previous tests passing ({name} failed)")

    def check_depend(self, names, item: PytestItem):
        if names == self.DEPEND_ALL:
            return self._check_depend_all(item)

        for name in names:
            if name in self:
                if self[name].passed:
                    continue
            else:
                if conf.ignore_unknown:
                    continue
            pytest.skip(f"{item.name} depends on {name}")

    @classmethod
    def dynamic_check(cls, item: PytestItem, names, scope=SCOPE_DEFAULT):
        manager = cls.get(item, scope=scope)
        manager.check_depend(names, item)
