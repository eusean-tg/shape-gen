"""Check view labeling and image preparation without loading model weights."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from generate import prepare_views, source_views


class MultiViewInputsTest(unittest.TestCase):
    def test_named_views_reach_upstream_in_the_correct_orientation_order(self):
        from hy3dgen.shapegen.preprocessors import MVImageProcessorV2

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            colors = {"front": (255, 0, 0, 255), "left": (0, 255, 0, 255), "back": (0, 0, 255, 255)}
            for name, color in colors.items():
                image = Image.new("RGBA", (16, 16))
                image.paste(color, (4, 2, 12, 14))
                image.save(root / f"{name}.png")
            Image.new("RGBA", (16, 16), "white").save(root / "style-reference.png")
            paths = source_views(root, "mv")
            self.assertEqual(list(paths), ["front", "left", "back"])
            images, removed = prepare_views(paths, keep_background=False)
            self.assertFalse(any(removed.values()))
            # Deliberately scramble insertion order: validate the real upstream
            # camera-index mapping and image correspondence, not only our dict.
            batch = MVImageProcessorV2(size=32)({name: images[name] for name in ("back", "front", "left")})
            self.assertEqual(batch["view_idxs"], (0, 1, 2))
            self.assertEqual(batch["image"].shape[:3], (1, 3, 3))
            self.assertEqual(batch["image"][0, :, :, 16, 16].argmax(dim=1).tolist(), [0, 1, 2])

    def test_requires_front_and_another_named_view(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "front.png"):
                source_views(root, "mv")
            (root / "front.png").touch()
            with self.assertRaisesRegex(ValueError, "at least one"):
                source_views(root, "mv")
            with self.assertRaisesRegex(ValueError, "directory"):
                source_views(root / "front.png", "mv")

    def test_single_image_keeps_alpha_and_pixels(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "image.png"
            original = Image.new("RGBA", (16, 16), (10, 20, 30, 128))
            original.save(path)
            for model in ("full", "mini"):
                images, removed = prepare_views(source_views(path, model), keep_background=False)
                self.assertEqual(images["front"].tobytes(), original.tobytes())
                self.assertFalse(removed["front"])

    def test_empty_view_reports_its_name(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "back.png"
            Image.new("RGBA", (16, 16)).save(path)
            with self.assertRaisesRegex(ValueError, "back.*fully transparent"):
                prepare_views({"back": path}, keep_background=False)


if __name__ == "__main__":
    unittest.main()
