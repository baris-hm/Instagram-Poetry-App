import unittest

from poetry_app.poem_divider import divide_poem


class DividePoemTests(unittest.TestCase):
    def test_empty_poem_returns_no_slides(self) -> None:
        self.assertEqual(divide_poem("  \n\n  "), [])

    def test_long_stanza_is_chunked_at_four_lines(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 10))

        self.assertEqual(
            divide_poem(poem),
            [
                ["Dize 1", "Dize 2", "Dize 3", "Dize 4"],
                ["Dize 5", "Dize 6", "Dize 7", "Dize 8"],
                ["Dize 9"],
            ],
        )

    def test_stanzas_are_not_merged(self) -> None:
        poem = "İlk dize\nİkinci dize\n\nYeni kıta\nSon dize"

        self.assertEqual(
            divide_poem(poem),
            [["İlk dize", "İkinci dize"], ["Yeni kıta", "Son dize"]],
        )

    def test_windows_line_endings_and_whitespace_are_normalized(self) -> None:
        poem = "  Birinci  \r\n\tİkinci\r\n\r\n Üçüncü "

        self.assertEqual(
            divide_poem(poem),
            [["Birinci", "İkinci"], ["Üçüncü"]],
        )

    def test_custom_line_limit_is_supported(self) -> None:
        self.assertEqual(
            divide_poem("Bir\nİki\nÜç", lines_per_slide=2),
            [["Bir", "İki"], ["Üç"]],
        )

    def test_invalid_line_limit_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            divide_poem("Bir", lines_per_slide=0)


if __name__ == "__main__":
    unittest.main()

