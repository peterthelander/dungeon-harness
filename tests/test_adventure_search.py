import unittest

from app.adventure_search import filter_adventure_results


class AdventureSearchTests(unittest.TestCase):
    def test_filters_non_pdf_blocked_and_duplicate_results(self):
        items = [
            {"title": "Good", "url": "https://creator.example/adventure.pdf", "source": "Creator", "description": "A real adventure."},
            {"title": "Duplicate", "url": "https://creator.example/adventure.pdf", "source": "Creator", "description": "Duplicate."},
            {"title": "Landing", "url": "https://creator.example/adventure", "source": "Creator", "description": "Not direct."},
            {"title": "Mirror", "url": "https://www.scribd.com/file.pdf", "source": "Mirror", "description": "Blocked."},
        ]

        results = filter_adventure_results(items)

        self.assertEqual([item["title"] for item in results], ["Good"])

    def test_limits_and_sanitizes_results(self):
        items = [{
            "title": f"  Adventure   {index}  ",
            "url": f"https://publisher.example/{index}.pdf",
            "source": "Publisher",
            "description": "A   compact   dungeon.",
        } for index in range(14)]

        results = filter_adventure_results(items)

        self.assertEqual(len(results), 10)
        self.assertEqual(results[0]["title"], "Adventure 0")
        self.assertEqual(results[0]["description"], "A compact dungeon.")


if __name__ == "__main__":
    unittest.main()
