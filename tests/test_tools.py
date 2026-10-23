"""Unit tests for the Claude Pets tooling (stdlib unittest + Pillow)."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import compose_atlas  # noqa: E402
import extract_strip_frames  # noqa: E402
import import_codex_pet  # noqa: E402
import make_sample_pet  # noqa: E402
import package_pet  # noqa: E402
import pet_spec  # noqa: E402
import pixelate  # noqa: E402
import validate_pet  # noqa: E402


def sprite(w=8, h=8, colors=3):
    """A small opaque asymmetric sprite with a few flat colours and a transparent corner."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if (x + y) % 5 == 0 and x < 2:
                continue
            c = (40 + 60 * ((x * 3 + y) % colors), 90, 200 - 50 * ((x + y * 2) % colors), 255)
            px[x, y] = c
    return img


def upscale(img, n):
    return img.resize((img.width * n, img.height * n), Image.NEAREST)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)


class PixelateTests(unittest.TestCase):
    def test_upscale_undone(self):
        base = sprite(12, 10)
        for n in (2, 3, 4):
            big = upscale(base, n)
            self.assertEqual(pixelate.detect_upscale(big), n)
            self.assertEqual(pixelate.reduce_nearest(big, n).tobytes(), pixelate.reduce_nearest(base, 1).tobytes())

    def test_native_art_not_reduced(self):
        self.assertEqual(pixelate.detect_upscale(sprite(12, 10)), 1)

    def test_palette_cap(self):
        img = Image.effect_noise((40, 40), 90).convert("RGB").convert("RGBA")
        out = pixelate.pixelate_image(img, 32, 32, max_colors=8, key=False)
        colors = {p[:3] for p in out.getdata() if p[3]}
        self.assertLessEqual(len(colors), 8)
        self.assertGreater(len(colors), 1)

    def test_binary_alpha(self):
        img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        for y in range(10, 30):
            for x in range(10, 30):
                img.putpixel((x, y), (200, 50, 50, 90 + (x * 7) % 160))
        out = pixelate.pixelate_image(img, 16, 16, key=False)
        self.assertTrue({p[3] for p in out.getdata()} <= {0, 255})

    def test_chroma_key_removed_and_fits(self):
        img = Image.new("RGBA", (200, 100), (0, 255, 0, 255))
        img.paste(Image.new("RGBA", (60, 60), (200, 40, 40, 255)), (70, 20))
        out = pixelate.pixelate_image(img, 16, 16)
        self.assertEqual(out.size, (16, 16))
        self.assertEqual(out.getpixel((0, 0))[3], 0)
        self.assertTrue(any(p[3] == 255 and p[0] > 150 for p in out.getdata()))
        self.assertFalse(any(p[3] == 255 and p[1] > 200 for p in out.getdata()))


class ExtractTests(unittest.TestCase):
    def test_gap_extraction_and_baseline(self):
        strip = Image.new("RGBA", (160, 40), (0, 255, 0, 255))
        for i in range(4):
            h = 20 + 4 * i
            strip.paste(Image.new("RGBA", (20, h), (200, 60 + 30 * i, 40, 255)), (10 + i * 40, 36 - h))
        frames, info = extract_strip_frames.extract_frames(strip, 4, 32, 32, key=None)
        self.assertEqual(info["method"], "gaps")
        self.assertEqual(len(frames), 4)
        bottoms = [im.getchannel("A").getbbox()[3] for im in frames]
        self.assertEqual(len(set(bottoms)), 1)
        self.assertTrue(all(im.size == (32, 32) for im in frames))

    def test_equal_slice_fallback(self):
        strip = Image.new("RGBA", (120, 20), (0, 0, 0, 0))
        strip.paste(Image.new("RGBA", (120, 20), (10, 200, 10, 255)), (0, 0))  # touching poses, no gaps
        frames, info = extract_strip_frames.extract_frames(strip, 6, 24, 24, key=False)
        self.assertEqual(info["method"], "equal")
        self.assertEqual(len(frames), 6)


class AtlasTests(TempDir):
    def test_geometry(self):
        for name, n in (("idle", 6), ("look", 16), ("celebrating", 8)):
            d = self.tmp / "frames" / name
            d.mkdir(parents=True)
            for i in range(n):
                Image.new("RGBA", (16, 16), (i * 10 + 5, 50, 50, 255)).save(d / f"{i:02d}.png")
        atlas, cell, drawn = compose_atlas.compose(self.tmp / "frames")
        self.assertEqual(cell, (16, 16))
        self.assertEqual(atlas.size, (8 * 16, 22 * 16))
        self.assertEqual(atlas.getpixel((5 * 16, 5))[:3], (55, 50, 50))  # idle frame 5
        self.assertEqual(atlas.getpixel((15 % 8 * 16, 10 * 16 + 3))[3], 255)  # look 15 on row 10
        self.assertEqual(atlas.getpixel((0, 9 * 16 + 3))[3], 255)  # look 0 on row 9
        self.assertEqual(atlas.getpixel((7 * 16, 14 * 16 + 3))[:3], (75, 50, 50))  # celebrating 7
        self.assertEqual(atlas.getpixel((6 * 16, 3))[3], 0)  # unused idle cell
        self.assertEqual(atlas.getpixel((0, 3 * 16 + 3))[3], 0)  # undrawn waving
        self.assertEqual(drawn, ["idle", "look", "celebrating"])

    def test_wrong_frame_count(self):
        d = self.tmp / "frames" / "idle"
        d.mkdir(parents=True)
        for i in range(3):
            Image.new("RGBA", (16, 16), (1, 2, 3, 255)).save(d / f"{i:02d}.png")
        with self.assertRaises(ValueError):
            compose_atlas.compose(self.tmp / "frames")


class ValidatorTests(TempDir):
    @classmethod
    def setUpClass(cls):
        cls.frames = make_sample_pet.build_frames()

    def make(self, mutate_pet=None, mutate_atlas=None, strips=True):
        pet_dir = self.tmp / "tiny-pet"
        if pet_dir.exists():
            shutil.rmtree(pet_dir)
        pet_dir.mkdir()
        atlas = Image.new("RGBA", (8 * 32, 22 * 32), (0, 0, 0, 0))
        for name, imgs in self.frames.items():
            for i, im in enumerate(imgs):
                r, c = pet_spec.frame_cell(pet_spec.ANIMATIONS[name]["row"], i)
                atlas.paste(im, (c * 32, r * 32))
        if mutate_atlas:
            atlas = mutate_atlas(atlas) or atlas
        atlas.save(pet_dir / "spritesheet.png")
        pet = json.loads(json.dumps(make_sample_pet.PET))
        pet["id"] = "tiny-pet"
        if mutate_pet:
            mutate_pet(pet)
        (pet_dir / "pet.json").write_text(json.dumps(pet))
        if strips:
            package_pet.cut_strips(pet_dir)
        return pet_dir

    def test_cell_129_rejected(self):
        def m(p):
            p["cell"] = {"width": 129, "height": 129}
        rep = validate_pet.validate(self.make(mutate_pet=m, strips=False))
        self.assertIn("cell-invalid", self.codes(rep))

    def codes(self, rep, kind="errors"):
        return {e["code"] for e in getattr(rep, kind)}

    def test_valid(self):
        rep = validate_pet.validate(self.make())
        self.assertEqual(rep.errors, [])

    def test_id_folder_mismatch(self):
        self.assertIn("id-folder-mismatch", self.codes(validate_pet.validate(self.make(lambda p: p.update(id="other")))))

    def test_id_invalid(self):
        self.assertIn("id-invalid", self.codes(validate_pet.validate(self.make(lambda p: p.update(id="Bad_ID")))))

    def test_sprite_version(self):
        self.assertIn("sprite-version", self.codes(validate_pet.validate(self.make(lambda p: p.update(spriteVersionNumber=2)))))

    def test_cell_range(self):
        pd = self.make(lambda p: p.update(cell={"width": 300, "height": 32}))
        self.assertIn("cell-invalid", self.codes(validate_pet.validate(pd)))

    def test_atlas_size(self):
        pd = self.make(mutate_atlas=lambda a: a.crop((0, 0, 8 * 32, 21 * 32)))
        self.assertIn("atlas-size", self.codes(validate_pet.validate(pd)))

    def test_spritesheet_format(self):
        pd = self.make()
        Image.open(pd / "spritesheet.png").convert("RGB").save(pd / "spritesheet.png")
        self.assertIn("spritesheet-format", self.codes(validate_pet.validate(pd)))

    def test_alpha_not_binary(self):
        def m(a):
            a.putpixel((5, 5), (200, 100, 50, 128))
            a.putpixel((6, 5), (200, 100, 50, 128))

        self.assertIn("alpha-not-binary", self.codes(validate_pet.validate(self.make(mutate_atlas=m))))

    def test_too_many_colors(self):
        def m(a):
            for i in range(80):
                a.putpixel((i % 30, 2 + i // 30), (i * 3, 255 - i, i, 255))

        pd = self.make(mutate_atlas=m)
        self.assertIn("too-many-colors", self.codes(validate_pet.validate(pd)))

    def test_pre_upscaled(self):
        def m(a):
            cell = upscale(sprite(8, 8), 4).crop((0, 0, 32, 32))
            a.paste(Image.new("RGBA", (32, 32), (0, 0, 0, 0)), (0, 0))
            a.paste(cell, (0, 0))

        self.assertIn("pre-upscaled", self.codes(validate_pet.validate(self.make(mutate_atlas=m))))

    def test_unused_cell_not_empty(self):
        def m(a):
            a.paste(Image.new("RGBA", (32, 32), (9, 9, 9, 255)), (7 * 32, 3 * 32))  # waving has 4 frames

        self.assertIn("unused-cell-not-empty", self.codes(validate_pet.validate(self.make(mutate_atlas=m))))

    def test_idle_not_drawn(self):
        def m(a):
            a.paste(Image.new("RGBA", (8 * 32, 32), (0, 0, 0, 0)), (0, 0))

        rep = validate_pet.validate(self.make(mutate_atlas=m))
        self.assertIn("idle-not-drawn", self.codes(rep))

    def test_fallback_chain_broken(self):
        def p(pet):
            pet["animations"] = {"working": {"fallback": "review"}, "review": {"fallback": "working"}}

        def m(a):
            for row in (7, 8):
                a.paste(Image.new("RGBA", (8 * 32, 32), (0, 0, 0, 0)), (0, row * 32))

        rep = validate_pet.validate(self.make(p, m))
        self.assertIn("fallback-broken", self.codes(rep))

    def test_strip_missing(self):
        pd = self.make()
        (pd / "strips" / "idle.png").unlink()
        self.assertIn("strip-missing", self.codes(validate_pet.validate(pd)))

    def test_strip_mismatch(self):
        pd = self.make()
        Image.new("RGBA", (10, 10)).save(pd / "strips" / "idle.png")
        self.assertIn("strip-mismatch", self.codes(validate_pet.validate(pd)))

    def test_strip_too_large(self):
        pd = self.make()
        with open(pd / "strips" / "idle.png", "ab") as f:
            f.write(bytes(pet_spec.MAX_STRIP_BYTES + 1))  # trailing zero bytes: still a valid PNG, over the limit
        codes = self.codes(validate_pet.validate(pd))
        self.assertIn("strip-too-large", codes)

    def test_custom_animation_requires_fields(self):
        pd = self.make(lambda p: p.update(animations={"dance": {"row": 22}}))
        self.assertIn("animation-invalid", self.codes(validate_pet.validate(pd)))

    def test_custom_animation_row_must_extend_atlas(self):
        pd = self.make(lambda p: p.update(animations={"dance": {"row": 5, "frames": 2, "durations": 100, "fallback": "idle"}}))
        self.assertIn("animation-invalid", self.codes(validate_pet.validate(pd)))

    def test_custom_animation_valid_and_undrawn_falls_back(self):
        def grow(a):
            big = Image.new("RGBA", (a.width, a.height + 32), (0, 0, 0, 0))
            big.paste(a, (0, 0))
            return big

        pd = self.make(lambda p: p.update(animations={"dance": {"row": 22, "frames": 2, "durations": 100, "fallback": "idle"}}), grow)
        self.assertEqual(validate_pet.validate(pd).errors, [])

    def test_bad_fallback_name(self):
        pd = self.make(lambda p: p.update(animations={"waving": {"fallback": "nope"}}))
        self.assertIn("animation-invalid", self.codes(validate_pet.validate(pd)))

    def test_pixelart_false_warns(self):
        def m(a):
            a.putpixel((5, 5), (200, 100, 50, 128))

        pd = self.make(lambda p: p.update(pixelArt=False), m)
        rep = validate_pet.validate(pd)
        self.assertEqual(rep.errors, [])
        self.assertIn("not-pixel-art", self.codes(rep, "warnings"))
        self.assertIn("alpha-not-binary", self.codes(rep, "warnings"))


class PackagerTests(TempDir):
    def test_strip_cutting(self):
        out = self.tmp / "pixel-clawd"
        self.assertEqual(make_sample_pet.main(["--out", str(out)]), 0)
        atlas = Image.open(out / "spritesheet.png")
        strip = Image.open(out / "strips" / "celebrating.png")
        self.assertEqual(strip.size, (8 * 32, 32))
        self.assertEqual(strip.crop((7 * 32, 0, 8 * 32, 32)).tobytes(), atlas.crop((7 * 32, 14 * 32, 8 * 32, 15 * 32)).tobytes())
        look = Image.open(out / "strips" / "look.png")
        self.assertEqual(look.size, (16 * 32, 32))
        self.assertEqual(look.crop((9 * 32, 0, 10 * 32, 32)).tobytes(), atlas.crop((32, 10 * 32, 64, 11 * 32)).tobytes())

    def test_only_drawn_animations_get_strips_and_stale_removed(self):
        out = self.tmp / "pixel-clawd"
        make_sample_pet.main(["--out", str(out)])
        (out / "strips" / "stale.png").write_bytes(b"x")
        atlas = Image.open(out / "spritesheet.png")
        atlas.paste(Image.new("RGBA", (6 * 32, 32), (0, 0, 0, 0)), (0, 11 * 32))  # erase sleeping
        atlas.save(out / "spritesheet.png")
        names = package_pet.cut_strips(out)
        self.assertNotIn("sleeping", names)
        self.assertFalse((out / "strips" / "sleeping.png").exists())
        self.assertFalse((out / "strips" / "stale.png").exists())

    def test_install_dir(self):
        out = self.tmp / "pixel-clawd"
        make_sample_pet.main(["--out", str(out)])
        dest = package_pet.install(out, self.tmp / "installed")
        self.assertTrue((dest / "pet.json").is_file())
        self.assertTrue((dest / "strips" / "idle.png").is_file())


class SampleTests(unittest.TestCase):
    def test_look_directions_distinct(self):
        frames = make_sample_pet.build_frames()["look"]
        self.assertEqual(len({f.tobytes() for f in frames}), 16)

    def test_every_animation_distinct_motion(self):
        for name, imgs in make_sample_pet.build_frames().items():
            if name == "idle":
                continue
            self.assertGreater(len({f.tobytes() for f in imgs}), 1, name)


class CodexImportTests(TempDir):
    def make_codex(self, rows=11, manifest=None, sheet_name="spritesheet.png", extra_files=()):
        src = self.tmp / "codex-pet"
        shutil.rmtree(src, True)
        src.mkdir()
        sheet = Image.new("RGBA", (8 * 48, rows * 52), (0, 0, 0, 0))
        counts = {"idle": 6, "running-right": 8, "running-left": 8, "waving": 4, "jumping": 5, "failed": 8, "waiting": 6, "running": 6, "review": 6}
        for a in pet_spec.ANIMATIONS.values():
            if a["codex"]:
                for i in range(counts[a["codex"]]):
                    sheet.paste(Image.new("RGBA", (20, 30), (a["row"] * 20, i * 20, 120, 255)), (i * 48 + 10, a["row"] * 52 + 10))
        if rows == 11:
            for i in range(16):
                sheet.paste(Image.new("RGBA", (20, 30), (200, i * 10, 10, 255)), ((i % 8) * 48 + 10, (9 + i // 8) * 52 + 10))
        sheet.save(src / sheet_name)
        for extra in extra_files:
            sheet.save(src / extra)
        if manifest is None:
            manifest = {"id": "Codex Pet", "displayName": "Codex Pet", "description": "d", "spriteVersionNumber": 2, "spritesheetPath": "spritesheet.png"}
        (src / "pet.json").write_text(json.dumps(manifest))
        return src

    def test_row_mapping_without_pixelate(self):
        pkg = import_codex_pet.import_pet(self.make_codex(), self.tmp / "out")
        pet = json.loads((pkg / "pet.json").read_text())
        self.assertEqual(pet["id"], "codex-pet")
        self.assertEqual(pet["spriteVersionNumber"], 3)
        self.assertIs(pet["pixelArt"], False)
        self.assertEqual(pet["cell"], {"width": 48, "height": 52})
        atlas = Image.open(pkg / "spritesheet.png")
        self.assertEqual(atlas.size, (8 * 48, 22 * 52))
        # waving (row 3, frame 2) came from the Codex waving row
        self.assertEqual(atlas.getpixel((2 * 48 + 12, 3 * 52 + 12))[:3], (60, 40, 120))
        # look 12 on row 10 col 4
        self.assertEqual(atlas.getpixel((4 * 48 + 12, 10 * 52 + 12))[:3], (200, 120, 10))
        for row in range(11, 22):
            self.assertIsNone(atlas.crop((0, row * 52, atlas.width, (row + 1) * 52)).getchannel("A").getbbox())
        self.assertTrue((pkg / "strips" / "idle.png").is_file())
        self.assertFalse((pkg / "strips" / "sleeping.png").exists())
        rep = validate_pet.validate(pkg)
        self.assertEqual(rep.errors, [])
        self.assertIn("not-pixel-art", {w["code"] for w in rep.warnings})

    def test_pixelate_option(self):
        pkg = import_codex_pet.import_pet(self.make_codex(), self.tmp / "out", pixelate=True, cell=24, max_colors=16)
        pet = json.loads((pkg / "pet.json").read_text())
        self.assertEqual(pet["pixelArt"], {"maxColors": 16})
        self.assertEqual(pet["cell"], {"width": 24, "height": 24})
        rep = validate_pet.validate(pkg)
        self.assertEqual([e for e in rep.errors if e["code"] not in ("pre-upscaled",)], [])

    def test_alternate_manifest_keys(self):
        m = {"id": "pet_6abd0cfcb4a4819195fe7b7747962618", "name": "Kitsune", "description": "d", "sprite_version": 2, "spritesheet": "sheet-x.png"}
        pkg = import_codex_pet.import_pet(self.make_codex(manifest=m, sheet_name="sheet-x.png"), self.tmp / "out")
        pet = json.loads((pkg / "pet.json").read_text())
        self.assertEqual((pet["id"], pet["displayName"]), ("kitsune", "Kitsune"))
        self.assertEqual(validate_pet.validate(pkg).errors, [])

    def test_id_override_and_sanitising(self):
        m = {"id": "My Pet_v2!", "spriteVersionNumber": 2, "spritesheetPath": "spritesheet.png"}
        pkg = import_codex_pet.import_pet(self.make_codex(manifest=m), self.tmp / "out")
        self.assertEqual(pkg.name, "my-pet-v2")
        shutil.rmtree(self.tmp / "out")
        pkg = import_codex_pet.import_pet(self.make_codex(manifest=m), self.tmp / "out", pet_id="Chosen One")
        self.assertEqual(pkg.name, "chosen-one")

    def test_version_inferred_from_atlas_size(self):
        m = {"id": "plain", "spritesheet_file": "spritesheet.png"}
        self.assertEqual(import_codex_pet.infer_version((1536, 2288)), 2)
        self.assertEqual(import_codex_pet.infer_version((1536, 1872)), 1)
        pkg = import_codex_pet.import_pet(self.make_codex(manifest=m), self.tmp / "out")
        self.assertEqual(json.loads((pkg / "pet.json").read_text())["importedFrom"], "codex-v2")

    def test_v1_nine_row_sheet(self):
        m = {"id": "old", "name": "Old", "sprite_version": 1}
        pkg = import_codex_pet.import_pet(self.make_codex(rows=9, manifest=m), self.tmp / "out")
        atlas = Image.open(pkg / "spritesheet.png")
        self.assertEqual(atlas.size, (8 * 48, 22 * 52))
        self.assertEqual(atlas.getpixel((12, 12))[3], 255)  # idle drawn
        self.assertFalse((pkg / "strips" / "look.png").exists())
        rep = validate_pet.validate(pkg)
        self.assertEqual(rep.errors, [])
        shutil.rmtree(self.tmp / "out")
        m.pop("sprite_version")  # inferred as v1 from the 8 x 9 shape
        pkg = import_codex_pet.import_pet(self.make_codex(rows=9, manifest=m), self.tmp / "out")
        self.assertEqual(json.loads((pkg / "pet.json").read_text())["importedFrom"], "codex-v1")

    def test_sheet_fallback_single_and_ambiguous(self):
        m = {"id": "x1", "name": "Fallback", "spriteVersionNumber": 2, "spritesheetPath": "missing.png"}
        pkg = import_codex_pet.import_pet(self.make_codex(manifest=m, sheet_name="spritesheet-extended.png"), self.tmp / "out")
        self.assertTrue((pkg / "spritesheet.png").is_file())
        shutil.rmtree(self.tmp / "codex-pet")
        src = self.make_codex(manifest=m, sheet_name="spritesheet-a.png", extra_files=("spritesheet-b.webp",))
        with self.assertRaises(ValueError) as cm:
            import_codex_pet.import_pet(src, self.tmp / "out2")
        self.assertIn("several", str(cm.exception))

    def test_unsupported_version(self):
        m = {"id": "x", "sprite_version": 7, "spritesheetPath": "spritesheet.png"}
        with self.assertRaises(ValueError):
            import_codex_pet.import_pet(self.make_codex(manifest=m), self.tmp / "out")


class CellLimitTests(TempDir):
    def test_spec_limit(self):
        self.assertEqual(pet_spec.CELL_MAX, 128)
        pet_spec.check_cell(128, 128)
        with self.assertRaises(ValueError):
            pet_spec.check_cell(129, 128)

    def test_parse_cell(self):
        self.assertEqual(pixelate.parse_cell("128"), (128, 128))
        with self.assertRaises(ValueError):
            pixelate.parse_cell("129")
        with self.assertRaises(ValueError):
            pixelate.parse_cell("64x200")

    def test_clis_reject_129(self):
        img = self.tmp / "a.png"
        Image.new("RGBA", (8, 8)).save(img)
        for mod, argv in (
            (pixelate, [str(img), "-o", str(self.tmp / "o.png"), "--cell", "129"]),
            (extract_strip_frames, [str(img), "--animation", "idle", "--cell", "129", "--frames", "1"]),
            (compose_atlas, [str(self.tmp), "--cell", "129"]),
            (import_codex_pet, [str(self.tmp), "--pixelate", "--cell", "129"]),
        ):
            with self.subTest(mod=mod.__name__), self.assertRaises(SystemExit) as cm:
                mod.main(argv)
            self.assertEqual(cm.exception.code, 2)


class SpecTests(unittest.TestCase):
    def test_table_shape(self):
        self.assertEqual(len(pet_spec.ANIMATIONS), 21)
        self.assertEqual(pet_spec.atlas_rows(pet_spec.ANIMATIONS), 22)
        for a in pet_spec.ANIMATIONS.values():
            if not a["pose"]:
                self.assertEqual(len(a["durations"]), a["frames"] if len(a["durations"]) > 1 else 1)


if __name__ == "__main__":
    unittest.main()
