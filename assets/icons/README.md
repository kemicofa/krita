# Pencil preset illustrations

`artwork/` contains eleven original full-size PNG illustrations generated with the
built-in `image_gen` tool on 2026-09-27. `prompts.json` records the exact prompt and
the matching source file for each preset. No default Krita artwork was used.
Soft Touch also records the follow-up edit prompt that darkened its pencil and
pigment stroke to near-black charcoal.

The generator loads the matching image by preset ID, resizes it to 200 × 200, and
adds the grade, number, and tilt/fixed-tip labels using Pillow's bundled font.
The finished image is both the `.kpp` thumbnail and the standalone PNG in
`dist/icons/`. `dist/Icon_Preview.png` shows the complete set at 200 and 64 pixels.

Builds use these checked-in assets and require no image-generation service or key.
The drawings of pigment marks are decorative; use `Brush_Preview.png` for actual
Krita-rendered stroke samples. Assets are distributed under the repository's MIT
license.
