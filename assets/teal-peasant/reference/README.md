# Replacement character modelling references

The user's supplied front/back design is preserved as `style-reference.png`.
The target is a slender faceless medieval character with dark hair, a teal tunic
and knee breeches, pale sleeves/stockings, ankle shoes and small relaxed hands.

Three separate modelling images were made with the **built-in imagegen tool**:

- [Front](front.png) — [exact prompt](front-prompt.txt)
- [Back](back.png) — [exact prompt](back-prompt.txt)
- [Profile facing image-left](left.png) — [exact prompt](left-prompt.txt)

The front establishes the design; the other two reference that front. The back
also references the user's original design. PNG alpha was retained and each
image was copied into this workspace. No CLI/API fallback was used. These are
independently synthesized views, not exact camera projections of one mesh.

The images guide Hunyuan3D-2mv shape generation. Final color boundaries are
separately authored on the reconstructed mesh; the final face remains blank.
