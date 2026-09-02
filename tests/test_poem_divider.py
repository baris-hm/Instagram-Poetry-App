import unittest

from poetry_app.poem_divider import divide_bent_poem, divide_poem, poem_lines


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

    def test_poem_lines_ignores_blank_stanza_separators(self) -> None:
        self.assertEqual(poem_lines(" Bir \n\n İki\n  \nÜç "), ["Bir", "İki", "Üç"])

    def test_automatic_bent_mode_balances_extra_lines_at_the_end(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 45))

        slides = divide_bent_poem(poem)

        self.assertEqual([len(slide) for slide in slides], [4, 5, 5, 5, 5, 5, 5, 5, 5])
        self.assertEqual(slides[0][0], "Dize 1")
        self.assertEqual(slides[-1][-1], "Dize 44")

    def test_automatic_bent_mode_divides_37_lines_as_specified(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 38))

        self.assertEqual(
            [len(slide) for slide in divide_bent_poem(poem)],
            [4, 4, 4, 4, 4, 4, 4, 4, 5],
        )

    def test_fixed_bent_mode_keeps_a_remainder_on_the_last_slide(self) -> None:
        poem = "\n".join(f"Dize {number}" for number in range(1, 38))

        self.assertEqual(
            [len(slide) for slide in divide_bent_poem(poem, mode=5)],
            [5, 5, 5, 5, 5, 5, 5, 2],
        )

    def test_automatic_bent_mode_does_not_create_empty_slides_for_short_poems(self) -> None:
        self.assertEqual(divide_bent_poem("Bir\nİki\nÜç"), [["Bir"], ["İki"], ["Üç"]])


if __name__ == "__main__":
    unittest.main()
