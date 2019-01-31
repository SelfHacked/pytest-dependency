import pytest
from _pytest.nodes import Item as PytestItem, Node
from _pytest.reports import TestReport
from typing import Iterable, Optional

from .config import conf
from .constant import SCOPE_MODULE, SCOPE_CLASS, SCOPE_SESSION


class Marker(object):
    MARKER_NAME = 'dependency'

    NAME_FIELD = 'name'
    SCOPE_FIELD = 'scope'
    LIST_FIELD = 'depends'

    FIELDS = (
        NAME_FIELD,
        SCOPE_FIELD,
        LIST_FIELD,
    )

    @classmethod
    def get(cls, item: PytestItem) -> Optional['Marker']:
        marker = item.get_closest_marker(cls.MARKER_NAME)
        if marker is None:
            return None

        return cls(*(
            marker.kwargs.get(field)
            for field in cls.FIELDS
        ))

    def __init__(self, name, scope, depend_list):
        self.name = name
        self.scope = scope
        self.depend_list = depend_list


class Dependency(object):
    SCOPE_DEFAULT = SCOPE_MODULE

    MARKER = 'dependency'
    LIST_FIELD = 'depends'
    SCOPE_FIELD = 'scope'

    def __init__(self, scope, name):
        self.scope = scope
        self.name = name

    @classmethod
    def read_list(cls, scope, *dependencies) -> Iterable['Dependency']:
        for dependency in dependencies:
            if isinstance(dependency, str):
                yield cls(scope, dependency)
            else:
                yield cls(*dependency)

    @classmethod
    def read_marker(cls, marker: Marker) -> Iterable['Dependency']:
        scope = marker.scope or cls.SCOPE_DEFAULT

        if not marker.depend_list:
            return

        yield from cls.read_list(scope, *marker.depend_list)

    def __repr__(self):
        return f"{self.__class__.__name__} [{self.scope}] {self.name}"


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


class AbstractItem(object):
    def __init__(self, item: PytestItem):
        self.__item = item

    @property
    def pytest_item(self) -> PytestItem:
        return self.__item

    def pytest_runtest_makereport(self):
        raise NotImplementedError

    def check_skip(self, *dependencies: Dependency):
        raise NotImplementedError

    def __repr__(self):
        return repr(self.pytest_item)


class DummyItem(AbstractItem):
    def pytest_runtest_makereport(self):
        yield

    def check_skip(self, *dependencies: Dependency):
        pass


class Item(AbstractItem):
    """
    Test item
    """

    __ITEMS = {}

    class NotDependency(Exception):
        pass

    @classmethod
    def get(cls, item: PytestItem) -> AbstractItem:
        try:
            if item not in cls.__ITEMS:
                cls.__ITEMS[item] = cls(item)
            return cls.__ITEMS[item]
        except cls.NotDependency:
            return DummyItem(item)

    def __init__(self, item: PytestItem):
        super().__init__(item)
        self.__name = item.name
        self.__marker = Marker.get(item)
        if self.__marker is None:
            if not conf.auto_mark:
                raise self.NotDependency
        self.__status = Status()
        DependencyFinder.register(self)

    def add_report(self, report: TestReport):
        self.__status += report

    @property
    def item_name(self):
        return self.__name

    @property
    def marker_name(self):
        if self.marker is None:
            return None
        return self.marker.name

    @property
    def display_name(self):
        return self.marker_name or self.item_name

    def __repr__(self):
        return f"{self.display_name} {super().__repr__()}"

    def get_name(self, scope):
        if self.marker_name:
            return self.marker_name
        if scope == SCOPE_SESSION:
            return self.pytest_item.nodeid.replace("::()::", "::")
        if scope == SCOPE_MODULE and self.pytest_item.cls:
            return f"{self.pytest_item.cls.__name__}::{self.item_name}"
        return self.item_name

    @property
    def marker(self) -> Optional[Marker]:
        return self.__marker

    @property
    def passed(self) -> bool:
        return bool(self.__status)

    @property
    def dependencies(self) -> Iterable[Dependency]:
        if self.marker is None:
            return
        yield from Dependency.read_marker(self.marker)

    def depend_items(self, *dependencies: Dependency) -> Iterable['Item']:
        if not dependencies:
            dependencies = self.dependencies
        for dependency in dependencies:
            try:
                yield DependencyFinder.get(self, dependency.scope)[dependency.name]
            except DependencyFinder.DependencyNotFound:
                if not conf.ignore_unknown:
                    raise

    def check_skip(self, *dependencies: Dependency):
        try:
            for item in self.depend_items(*dependencies):
                if not item.passed:
                    pytest.skip(
                        f"{self.display_name} depends on {item.display_name}, "
                        f"which did not pass"
                    )
        except DependencyFinder.DependencyNotFound as e:
            pytest.skip(
                f"{self.display_name} depends on {e.name}, "
                f"which does not exist"
            )

    def pytest_runtest_makereport(self):
        outcome = yield
        report = outcome.get_result()
        self.add_report(report)


class DependencyFinder(object):
    SCOPE_CLASSES = {
        SCOPE_MODULE: pytest.Module,
        SCOPE_CLASS: pytest.Class,
        SCOPE_SESSION: pytest.Session,
    }

    NODE_ATTR = 'dependency_finder'

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

    class DependencyNotFound(Exception):
        def __init__(self, name):
            self.name = name

    @classmethod
    def register(cls, item: Item):
        for scope in cls.SCOPE_CLASSES:
            try:
                cls.get(item, scope)[item.get_name(scope)] = item
            except cls.InvalidNode:
                pass

    @classmethod
    def get(cls, item: Item, scope) -> 'DependencyFinder':
        pytest_item = item.pytest_item
        node = pytest_item.getparent(cls.SCOPE_CLASSES[scope])
        if not node:
            raise cls.InvalidNode(item, scope)
        if not hasattr(node, cls.NODE_ATTR):
            setattr(node, cls.NODE_ATTR, cls(node, scope))
        return getattr(node, cls.NODE_ATTR)

    def __init__(self, node: Node, scope):
        self.__node = node
        self.__scope = scope
        self.__items = {}

    @property
    def node(self) -> Node:
        return self.__node

    @property
    def scope(self):
        return self.__scope

    def __repr__(self):
        return f"{self.__class__.__name__} [{self.scope}] {self.node}"

    def __contains__(self, item):
        return item in self.__items

    def __len__(self):
        return len(self.__items)

    def __iter__(self):
        return iter(self.__items)

    def __getitem__(self, name) -> Item:
        try:
            return self.__items[name]
        except KeyError:
            raise self.DependencyNotFound(name) from None

    def keys(self):
        return self.__items.keys()

    def values(self):
        return self.__items.values()

    def __setitem__(self, name, item: Item):
        if name in self:
            if self[name] != item:
                raise self.DuplicateName(name, item)
        self.__items[name] = item
