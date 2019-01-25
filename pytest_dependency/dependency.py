import pytest
from _pytest.nodes import Item, Node
from _pytest.reports import TestReport
from typing import Optional

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


class Dependency(object):
    """
    Test item
    """

    __DEPENDENCIES = {}

    @classmethod
    def get(cls, item: Item) -> 'Dependency':
        return cls.__DEPENDENCIES.setdefault(item, cls(item))

    def __init__(self, item: Item):
        self.__item = item
        self.__status = Status()

    def add_report(self, report: TestReport):
        self.__status += report

    @property
    def item(self) -> Item:
        return self.__item

    @property
    def passed(self) -> bool:
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
        def __init__(self, name, dependency: Dependency):
            self.name = name
            self.dependency = dependency
            super().__init__(f"Name {name} has been used by a different dependency")

    @classmethod
    def get(cls, item: Item, scope=SCOPE_DEFAULT) -> Optional['DependencyManager']:
        """
        Get the DependencyManager object from the node at scope level.
        Create it, if not yet present.
        """
        node = item.getparent(cls.SCOPE_CLASSES[scope])
        if not node:
            return None
        if not hasattr(node, cls.NODE_ATTR):
            setattr(node, cls.NODE_ATTR, cls(node, scope))
        return getattr(node, cls.NODE_ATTR)

    def __init__(self, node: Node, scope):
        self.__node = node
        self.__scope = scope
        self.__items = {}

    def _gen_name(self, item: Item) -> str:
        if self.__scope == self.SCOPE_SESSION:
            return item.nodeid.replace("::()::", "::")
        if self.__scope == self.SCOPE_MODULE and item.cls:
            return f"{item.cls.__name__}::{item.name}"
        return item.name

    def __contains__(self, name):
        return name in self.__items

    def __iter__(self):
        return iter(self.__items)

    def __getitem__(self, name) -> Dependency:
        return self.__items[name]

    def __setitem__(self, name, dependency: Dependency):
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

    def _check_depend_all(self, item: Item):
        for name in self:
            if self[name].passed:
                continue
            pytest.skip(
                f"{item.name} depends on all previous tests passing ({name} failed)")

    def check_depend(self, names, item: Item):
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
