import sys

from _pytest.nodes import Item as PytestItem
from typing import Iterator, Optional

from .config import conf
from .dependency import Item, DependencyFinder


class TestOrganizer(Iterator[PytestItem]):
    STATUS_NONE = 0
    STATUS_PUSHED = 1
    STATUS_WAITING = 2

    def __init__(self, *items: PytestItem):
        self.__items = list(items)
        self.__statuses = {
            item: self.STATUS_NONE
            for item in items
        }

    def __check_item_ready(self, item: PytestItem) -> bool:
        try:
            for depend in Item.get(item).depend_items_setup():
                if depend.pytest_item not in self.__statuses:
                    return False
                if self.__statuses[depend.pytest_item] != self.STATUS_PUSHED:
                    return False

        except DependencyFinder.DependencyNotFound:
            return False

        return True

    @staticmethod
    def __has_unknown_dependency(item: PytestItem) -> bool:
        try:
            tuple(Item.get(item).depend_items_setup())
        except DependencyFinder.DependencyNotFound:
            return True
        else:
            return False

    def __remaining(self) -> Iterator[PytestItem]:
        for item in self.__items:
            if self.__statuses[item] == self.STATUS_PUSHED:
                continue
            yield item

    @property
    def __has_remaining(self) -> bool:
        return bool(tuple(self.__remaining()))

    def __next_ready(self) -> Optional[PytestItem]:
        for item in self.__remaining():
            if not self.__check_item_ready(item):
                self.__statuses[item] = self.STATUS_WAITING
                continue

            return item

        return None

    def __next_unknown(self) -> Optional[PytestItem]:
        for item in self.__remaining():
            if not self.__has_unknown_dependency(item):
                continue

            return item

        return None

    @staticmethod
    def warn_unknown_dependency(item: PytestItem):
        if conf.ignore_unknown:
            return
        name = Item.get(item).display_name
        print(f"{name} has unknown dependencies", file=sys.stderr)

    @staticmethod
    def warn_circular_dependency(item: PytestItem):
        name = Item.get(item).display_name
        print(f"{name} has circular dependencies", file=sys.stderr)

    def __next(self):
        if not self.__has_remaining:
            raise StopIteration

        item = self.__next_ready()
        if item is not None:
            return item

        item = self.__next_unknown()
        if item is not None:
            self.warn_unknown_dependency(item)
            return item

        item = next(self.__remaining())
        self.warn_circular_dependency(item)
        return item

    def __next__(self) -> PytestItem:
        item = self.__next()
        self.__statuses[item] = self.STATUS_PUSHED
        return item
