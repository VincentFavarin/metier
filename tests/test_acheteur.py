import unittest

from scripts.extraire import METIERS


class AcheteurROMEConfigTests(unittest.TestCase):
    def test_acheteur_uses_france_travail_rome_and_is_enabled_by_default(self):
        self.assertEqual(
            METIERS["M1101"],
            ("Acheteur / Acheteuse", "Achats", True),
        )


if __name__ == "__main__":
    unittest.main()
