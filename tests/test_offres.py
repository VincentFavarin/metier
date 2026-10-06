import unittest

from scripts.resumer import (
    est_alternance,
    est_stage,
    mots_cles_cibles,
    rome_principal_par_id,
)


class ClassificationOffresTests(unittest.TestCase):
    def test_stage_reconnu_dans_intitule_ou_nature(self):
        self.assertTrue(est_stage({"intitule": "Stage CRM de six mois"}))
        self.assertTrue(est_stage({"natureContrat": "Contrat de stage"}))
        self.assertTrue(est_stage({"typeContrat": "STG"}))
        self.assertTrue(est_stage({"intitule": "Stages en marketing"}))

    def test_mention_de_stage_dans_une_description_ne_suffit_pas(self):
        self.assertFalse(est_stage({
            "intitule": "Chargé de relation client",
            "description": "Une expérience en stage serait appréciée.",
            "natureContrat": "Contrat travail",
            "typeContrat": "CDI",
        }))

    def test_alternance_reconnue_par_nature_ou_indicateur_api(self):
        self.assertTrue(est_alternance({"natureContrat": "Contrat apprentissage"}))
        self.assertTrue(est_alternance({"natureContrat": "Cont. professionnalisation"}))
        self.assertTrue(est_alternance({"alternance": True}))
        self.assertFalse(est_alternance({"natureContrat": "Contrat travail"}))

    def test_reconnait_les_categories_cibles_dans_le_texte(self):
        offre = {
            "rome": "M1718",
            "intitule": "Chargé de marketing",
            "description": "Expérience en CRM et fidélisation client.",
        }
        self.assertEqual(
            mots_cles_cibles(offre),
            ["CRM", "Fidélisation"],
        )

    def test_d1415_relation_client_seul_est_ecarte(self):
        self.assertEqual(mots_cles_cibles({
            "rome": "D1415",
            "intitule": "Chargé de relation client",
            "description": "Répondre aux appels et traiter les demandes.",
        }), [])

    def test_d1415_est_applique_meme_si_annonce_partagee_avec_un_autre_rome(self):
        offre = {
            "intitule": "Chargé de relation client",
            "description": "Répondre aux appels et traiter les demandes.",
        }
        self.assertEqual(mots_cles_cibles(offre, {"M1718", "D1415"}), [])

    def test_un_identifiant_source_ne_garde_quun_rome_principal(self):
        self.assertEqual(
            rome_principal_par_id([
                ("D1415", "offre-partagee"),
                ("M1718", "offre-partagee"),
                ("D1415", "offre-crm"),
            ]),
            {"offre-partagee": "M1718", "offre-crm": "D1415"},
        )

    def test_d1415_crm_est_conserve(self):
        self.assertEqual(mots_cles_cibles({
            "rome": "D1415",
            "intitule": "Chargé de relation client",
            "description": "Améliorer le CRM et l'expérience client.",
        }), ["CRM", "Expérience client", "Relation client"])


if __name__ == "__main__":
    unittest.main()
