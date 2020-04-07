from unittest import TestCase

import abejacli.version


class VersionTest(TestCase):
    """this is a sample test case to make coverate report
    you can delete this when real unittests are ready
    """

    def test_version(self):
        self.assertIsInstance(abejacli.version.VERSION, str)
