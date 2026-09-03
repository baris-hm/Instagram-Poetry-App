import base64
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from poetry_app.renderer import CANVAS_SIZE, CarouselRenderer, RenderError, decode_photo_data_url


LONG_PROSE_LINES = [
    "Bendeniz tarafından derlenip çevrilmiş ve Ankara’daki Bengü Yayınevi’nde 11 yıl önce, bugünkü tarihte, yayımlanmış olan Bulgar Şiiri Antolojisi Türk okurları tarafından öyle büyük bir ilgi ve sevgiyle karşılanmıştı ki,",
    "bugüne değin hâlâ duygularını paylaşmak için beni arayanlar bulunuyor.",
    "Издадената преди 11 години на днешна дата от издателство „Бенгю“ в Анкара беше издадена",
    "„Антология на българскака поезия“, съставена и преведена от моя милост, която се посрещна много радушно от турските читатели, които до ден днешен ми се обаждат и споделят своите прекрасни впечатления.",
]


def photo_data_url(size: tuple[int, int] = (640, 480)) -> str:
    image = Image.new("RGB", size, (198, 86, 57))
    output = io.BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class RendererTests(unittest.TestCase):
    def test_renders_poem_slides_then_uncropped_photo_as_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            renderer = CarouselRenderer(
                Path(directory),
                "https://media.example.test",
                "@hesap",
            )
            rendered = renderer.render(
                [["Birinci dize", "İkinci dize"], ["Üçüncü dize"]],
                title="Deneme",
                photo_data_url=photo_data_url(),
            )

            self.assertEqual(len(rendered), 3)
            self.assertTrue(rendered[-1].public_url.startswith("https://media.example.test/media/"))
            for item in rendered:
                with Image.open(item.path) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.mode, "RGB")
                    self.assertEqual(image.size, CANVAS_SIZE)
                    self.assertFalse(image.info.get("progressive", False))
                    self.assertFalse(image.info.get("progression", False))

            with Image.open(rendered[-1].path) as photo_slide:
                # The 4:3 source is contained, leaving dark bands instead of being cropped.
                corner = photo_slide.getpixel((10, 10))
                self.assertTrue(all(25 <= channel <= 36 for channel in corner))
                center = photo_slide.getpixel((CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] // 2))
                self.assertGreater(center[0], center[1])

    def test_rejects_unsupported_photo_data(self) -> None:
        with self.assertRaises(RenderError):
            decode_photo_data_url("data:image/gif;base64,R0lGODlh")

    def test_wraps_long_turkish_and_bulgarian_prose_instead_of_rejecting_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            renderer = CarouselRenderer(Path(directory), "", "@hesap")

            rendered = renderer.render([LONG_PROSE_LINES])

            self.assertEqual(len(rendered), 1)
            with Image.open(rendered[0].path) as image:
                self.assertEqual(image.size, CANVAS_SIZE)
                self.assertEqual(image.format, "JPEG")


if __name__ == "__main__":
    unittest.main()
