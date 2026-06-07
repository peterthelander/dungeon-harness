import os
import sys
import unittest


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(root, "tests")
    suite = unittest.defaultTestLoader.discover(start_dir=tests_dir, pattern="test*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
