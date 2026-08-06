"""The Node suite actually runs — the guard for a bug that has now bitten twice.

Both incidents were the same shape: `npm run test:js` executed **zero tests** and the
build stayed green, so real failures accumulated invisibly behind it.

  1. The script passed a glob STRING (`"tests/js/**/*.test.js"`). `node --test` only
     expands those from Node 21, and CI pinned 20 — it matched nothing. Nine real
     failures had piled up by the time anyone ran it.
  2. The fix was a directory (`tests/js/`). That works on Node 20 but not on Node 22,
     which resolves a bare positional path as a module and dies with MODULE_NOT_FOUND.
     Bumping CI to Node 22 broke it again, in the opposite direction.

Both were invisible to every existing test, because every existing test asserted things
*about* the code rather than that the suite covering it had run at all.

So this asserts the outcome, not the incantation: the command in package.json, whatever
it is, executes at least one test per test file and reports no failures. It is deliberately
version-agnostic — it would have caught both incidents on both Node versions.

The suite is now invoked with explicit file paths (`tests/js/*.test.js`), expanded by the
shell before Node sees them. Explicit paths are the oldest and most stable form the test
runner accepts; nothing about it depends on which Node is installed.
"""

import json
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
NPM = shutil.which("npm")
JS_TEST_DIR = ROOT / "tests" / "js"


def js_test_files():
    return sorted(JS_TEST_DIR.glob("*.test.js"))


class TestTheJsSuiteIsReachable(unittest.TestCase):
    def test_there_are_js_test_files_to_run(self):
        # If this ever hits zero the assertions below become vacuous, which is precisely
        # the failure mode being guarded against.
        self.assertGreater(len(js_test_files()), 0,
                           "no tests/js/*.test.js files — the guard below would pass vacuously")

    def test_the_script_is_defined(self):
        pkg = json.loads((ROOT / "package.json").read_text())
        self.assertIn("test:js", pkg.get("scripts", {}))

    def test_the_script_does_not_depend_on_node_version_specific_globbing(self):
        # A quoted glob pattern is expanded by `node --test` itself, which only supports it
        # from Node 21 — that is incident 1. A bare directory is resolved as a module on
        # Node 22 — incident 2. Explicit paths work everywhere.
        script = json.loads((ROOT / "package.json").read_text())["scripts"]["test:js"]
        self.assertNotIn('"', script,
                         "a quoted glob makes the script Node-version dependent (Node 21+ only)")
        self.assertNotRegex(script.strip(), r"--test\s+\S*/\s*$",
                            "a bare directory fails on Node 22 with MODULE_NOT_FOUND")


@unittest.skipUnless(NPM, "npm not installed — cannot verify the Node suite runs")
class TestTheJsSuiteActuallyExecutes(unittest.TestCase):
    """Runs the real command. Slower than the rest of the suite, and worth it: this is the
    only check that fails when the Node tests silently stop running."""

    @classmethod
    def setUpClass(cls):
        cls.proc = subprocess.run([NPM, "run", "--silent", "test:js"],
                                  capture_output=True, text=True, cwd=ROOT)
        cls.out = cls.proc.stdout + cls.proc.stderr

    def _count(self, label):
        m = re.search(rf"^# {label} (\d+)$", self.out, re.M)
        self.assertIsNotNone(m, f"no '# {label} N' line in the runner output:\n{self.out[-2000:]}")
        return int(m.group(1))

    def test_the_runner_did_not_fail_to_start(self):
        # MODULE_NOT_FOUND / "Could not find" mean the pattern matched nothing. That is the
        # bug, and it must never be mistaken for "the tests passed".
        for symptom in ("MODULE_NOT_FOUND", "Could not find", "Cannot find module"):
            self.assertNotIn(symptom, self.out,
                             f"the test command failed to resolve its files: {symptom}")

    def test_it_ran_at_least_one_test_per_file(self):
        self.assertGreaterEqual(
            self._count("tests"), len(js_test_files()),
            "fewer tests ran than there are test files — some files were not executed")

    def test_nothing_failed(self):
        self.assertEqual(self._count("fail"), 0, self.out[-3000:])

    def test_the_command_exits_non_zero_when_something_is_wrong(self):
        # A green exit code is what everyone actually trusts.
        self.assertEqual(self.proc.returncode, 0, self.out[-3000:])


if __name__ == "__main__":
    unittest.main()
