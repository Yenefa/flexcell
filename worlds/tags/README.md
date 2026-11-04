Tag images 0–2 of family 36h11 are copied unchanged from
[AprilRobotics/apriltag-imgs](https://github.com/AprilRobotics/apriltag-imgs/tree/f3fd9a7add5bfd82a886fc65240fdb8e3c9ac5a1/tag36h11),
commit `f3fd9a7add5bfd82a886fc65240fdb8e3c9ac5a1`, under the adjacent BSD license.

The PNG is 10×10 pixels including a one-pixel white quiet border. The detector's
25 mm tag size is the **8-pixel black square**, so the textured visual is 31.25 mm
wide. The marker plane is 17.7 mm above the cube center (0.2 mm above its top).
For rendering, `*_texture.png` is an exact 32× nearest-neighbor expansion, using
the upstream README's `convert input.png -scale 3200% output.png` instruction.
The original 10×10 PNGs remain unchanged. This prevents the renderer from
blurring whole tag cells when magnifying a 10-pixel texture; physical size is
still 31.25 mm. These are visual-only additions; collision geometry and mass
are unchanged.
