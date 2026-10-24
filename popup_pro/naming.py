"""Data-block names per scene. A plain card scene uses the plain names
("Pop-up Art", "Pop-up Rig", ...); each carousel stage scene adds its own
suffix so stages never share art, sketches, rigs or collections."""


def N(scene, base):
    sfx = getattr(scene.popup, "suffix", "") if scene is not None else ""
    return base + sfx
