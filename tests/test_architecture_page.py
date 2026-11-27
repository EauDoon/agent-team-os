import re
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1] / 'docs/architecture.html').read_text(encoding='utf-8')


class ArchitecturePageTests(unittest.TestCase):
    def test_print_shows_the_reference_table_the_script_collapses(self):
        # The print stylesheet hides the map and the JSON view. The script
        # collapses the reference table on load, so it must reopen for print
        # or the printed page holds neither the map nor the table.
        self.assertRegex(PAGE, r'@media print\{[^}]*\}\.workbench,[^{]*\{display:none\}')
        self.assertIn("byId('reference').open=false", PAGE)
        self.assertRegex(PAGE, r"addEventListener\('beforeprint',\s*\(\)\s*=>\s*preparePrint\(true\)\)")
        self.assertRegex(PAGE, r"addEventListener\('afterprint',\s*\(\)\s*=>\s*preparePrint\(false\)\)")
        self.assertRegex(PAGE, r"matchMedia\('print'\)\.addEventListener\('change'")
        body = re.search(r'function preparePrint\(printing\) \{(.*?)\n\}', PAGE, re.S).group(1)
        self.assertIn('reference.open = true', body)
        self.assertIn('reference.open = openBeforePrint', body)


if __name__ == '__main__':
    unittest.main()
