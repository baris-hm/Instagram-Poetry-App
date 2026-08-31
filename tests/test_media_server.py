import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from poetry_app.media_server import create_media_server


class MediaServerTests(unittest.TestCase):
    def test_only_random_named_jpegs_are_public(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            media_dir = Path(directory)
            filename = f"{'a' * 32}.jpg"
            content = b"jpeg-placeholder"
            (media_dir / filename).write_bytes(content)
            (media_dir / "private.txt").write_text("not public", encoding="utf-8")

            server = create_media_server(media_dir, port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base_url = f"http://127.0.0.1:{server.server_port}"
            try:
                request = Request(f"{base_url}/media/{filename}", method="HEAD")
                with urlopen(request) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["Content-Type"], "image/jpeg")
                    self.assertEqual(response.read(), b"")

                with self.assertRaises(HTTPError) as error:
                    urlopen(f"{base_url}/media/private.txt")
                self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
