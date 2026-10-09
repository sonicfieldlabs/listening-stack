"""Account for test failures and collection skips in installed boundary checks."""

class Results:
    def __init__(self):
        self.passed = self.skipped = self.failed = 0

    def pytest_runtest_logreport(self, report):
        if report.skipped:
            self.skipped += 1
        if report.failed:
            self.failed += 1
        if report.when == "call" and report.passed:
            self.passed += 1

    def pytest_collectreport(self, report):
        if report.skipped:
            self.skipped += 1
        if report.failed:
            self.failed += 1
