"""One module per scene. Each defines LABEL, SCENE (markup), SCENE_TRANSFORM, LOOP (tracks) and LOOP_MS.

`productivity` is the top-level mark (production_logo.svg). Every other module is a crop scene keyed by
the Production Crop's crop_key with dashes as underscores (fruits_vegetables.py -> fruits-vegetables),
written to production_logo_<crop_key>.svg; the app shows it once that crop is open.
"""
