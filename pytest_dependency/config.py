from .util import str_to_bool


class Config(object):
    AUTO_MARK = "automark_dependency"
    IGNORE_UNKNOWN = "--ignore-unknown-dependency"

    def __init__(self):
        self.auto_mark = False
        self.ignore_unknown = False

    @classmethod
    def pytest_addoption(cls, parser):
        parser.addini(
            cls.AUTO_MARK,
            "Add the dependency marker to all tests automatically",
            default=False,
        )
        parser.addoption(
            cls.IGNORE_UNKNOWN,
            action="store_true",
            default=False,
            help="ignore dependencies whose outcome is not known"
        )

    def pytest_configure(self, config):
        self.auto_mark = str_to_bool(config.getini(self.AUTO_MARK))
        self.ignore_unknown = config.getoption(self.IGNORE_UNKNOWN)


conf = Config()
