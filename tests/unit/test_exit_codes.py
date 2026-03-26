import unittest

from toolkit.core.exits import ExitCode


class ExitCodeContractTests(unittest.TestCase):
    def test_exit_code_contract_is_stable(self) -> None:
        self.assertEqual(ExitCode.SUCCESS, 0)
        self.assertEqual(ExitCode.FINDINGS_OR_FAILURE, 1)
        self.assertEqual(ExitCode.CONFIG_OR_RUNTIME_ERROR, 2)
