import unittest

from popurri import effective_steps, semitone_difference, target_name
from popurri_notion import validate_payload


def root_key(page):
    return page["root"], page["original"]


class PopurriTests(unittest.TestCase):
    def test_transpose_minor_to_bm(self):
        self.assertEqual(semitone_difference("D", "Bm"), -3)
        self.assertEqual(semitone_difference("A", "Bm"), 2)

    def test_global_modes(self):
        dm = {"root": "D", "original": "Dm"}
        am = {"root": "A", "original": "Am"}
        major = {"root": "D", "original": "D"}
        song = {"steps": -1}
        self.assertEqual(effective_steps(song, dm, "Originales", "Bm", root_key), 0)
        self.assertEqual(effective_steps(song, dm, "Unificar tono", "Bm", root_key), -3)
        self.assertEqual(effective_steps(song, am, "Unificar tono", "Bm", root_key), 2)
        self.assertEqual(effective_steps(song, major, "Unificar tono", "Bm", root_key), 0)
        self.assertEqual(effective_steps(song, dm, "Personalizado", "Bm", root_key), -1)

    def test_output_note(self):
        self.assertEqual(target_name({"root": "D", "original": "Dm"}, -3,
                                     root_key, "sostenidos"), "Bm")

    def test_storage_data_validation(self):
        doc = {"format": "cana-popurri-v1", "name": "Menores",
               "songs": [{"song_id": "a", "steps": -3},
                         {"song_id": "b", "steps": 2}]}
        clean = validate_payload(doc, {"a"})
        self.assertEqual(clean["songs"], [{"song_id": "a", "steps": -3}])
        self.assertEqual(clean["mode"], "Personalizado")


if __name__ == "__main__":
    unittest.main()
