"""Small geometry helpers built on mathutils (available inside Blender and
as the standalone `mathutils` package). All lengths are millimetres."""

import math

from mathutils import Matrix, Vector

Z = Vector((0.0, 0.0, 1.0))
EPS = 1e-9


def v3(p):
    if len(p) == 2:
        return Vector((p[0], p[1], 0.0))
    return Vector(p)


def frame(origin, xdir, ydir):
    """Proper rigid frame: X along xdir, Y = ydir made orthogonal, Z = X x Y."""
    x = Vector(xdir).normalized()
    y = Vector(ydir)
    y = (y - x * y.dot(x)).normalized()
    z = x.cross(y)
    m = Matrix.Identity(4)
    for i, axis in enumerate((x, y, z)):
        m[0][i], m[1][i], m[2][i] = axis
    m[0][3], m[1][3], m[2][3] = v3(origin)
    return m


def hinge_frame_2d(origin2, dir2):
    """Frame in a flat pattern (z = 0 plane) whose Y axis runs along a fold
    line, Z is the printed-side normal and X = Y x Z."""
    d = Vector((dir2[0], dir2[1])).normalized()
    return frame((origin2[0], origin2[1], 0.0), (d.y, -d.x, 0.0), (d.x, d.y, 0.0))


def rot_y(a):
    return Matrix.Rotation(a, 4, "Y")


def angle_from_roty(m):
    """Angle of a matrix that should be a pure rotation about Y."""
    return math.atan2(m[0][2], m[0][0])


def is_roty(m, tol=1e-5):
    a = angle_from_roty(m)
    r = rot_y(a)
    return all(abs(m[i][j] - r[i][j]) < tol for i in range(4) for j in range(4))


def rot2(p, a):
    c, s = math.cos(a), math.sin(a)
    return (c * p[0] - s * p[1], s * p[0] + c * p[1])


def poly_area(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def clean(poly, eps=1e-7):
    """Drop repeated points and points lying on the line between their
    neighbours (Blender refuses faces with repeated vertices)."""
    pts = []
    for p in poly:
        p = (float(p[0]), float(p[1]))
        if not pts or abs(p[0] - pts[-1][0]) > eps or abs(p[1] - pts[-1][1]) > eps:
            pts.append(p)
    while len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) <= eps and abs(pts[0][1] - pts[-1][1]) <= eps:
        pts.pop()
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            cr = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            ln = math.hypot(c[0] - a[0], c[1] - a[1])
            if ln < eps or abs(cr) / ln < 1e-6:
                pts.pop(i)
                changed = True
                break
    return pts


def ccw(poly):
    poly = clean(poly)
    return poly if poly_area(poly) >= 0 else poly[::-1]


def clip_halfplane(poly, n, d):
    """Keep the part of a polygon where dot(p, n) >= d (Sutherland-Hodgman)."""
    out = []
    m = len(poly)
    for i in range(m):
        a, b = poly[i], poly[(i + 1) % m]
        da = a[0] * n[0] + a[1] * n[1] - d
        db = b[0] * n[0] + b[1] * n[1] - d
        if da >= 0:
            out.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return clean(out) if len(out) >= 3 else out


def xform2(m, p):
    """Apply a 4x4 matrix to a 2D pattern point, returning 3D."""
    return m @ v3(p)


def bbox2(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def scaled(m, s):
    """Rigid matrix in mm -> same matrix with translation scaled by s."""
    r = m.copy()
    for i in range(3):
        r[i][3] *= s
    return r
