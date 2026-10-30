import unittest

from buscador_cana import search_song_options


def title(page):
    return page["title"]


class SearchAccentTests(unittest.TestCase):
    def setUp(self):
        self.pages = [
            {"id": "a", "title": "Es un río"},
            {"id": "b", "title": "El Señor está aquí"},
            {"id": "c", "title": "Espíritu Santo"},
            {"id": "d", "title": "Bendigan al Señor"},
        ]

    def test_tildes_are_optional(self):
        self.assertEqual(search_song_options("es un ri", self.pages, title),
                         [("Es un río", "a")])
        self.assertEqual(search_song_options("es un río", self.pages, title),
                         [("Es un río", "a")])

    def test_case_accents_and_punctuation(self):
        self.assertEqual(search_song_options("espiritu santo", self.pages, title),
                         [("Espíritu Santo", "c")])
        self.assertEqual(search_song_options("SENOR", self.pages, title),
                         [("Bendigan al Señor", "d"), ("El Señor está aquí", "b")])

    def test_complete_list_uses_original_titles(self):
        expected = search_song_options("", self.pages, title)
        self.assertEqual(len(expected), 4)
        self.assertTrue(any(name == "Es un río" for name, _ in expected))

    def test_filtered_list_respects_category_candidates(self):
        self.assertEqual(search_song_options("rio", self.pages[1:], title), [])


if __name__ == "__main__":
    unittest.main()
