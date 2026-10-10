import unittest
from parser import parse_bool
class ParseTests(unittest.TestCase):
    def test_whitespace(self):
        self.assertIs(parse_bool(" True "), True)
        self.assertIs(parse_bool("\tFALSE\n"), False)
    def test_invalid(self):
        for text in ["yes", "", "1"]:
            with self.assertRaises(ValueError): parse_bool(text)
if __name__ == "__main__": unittest.main()
