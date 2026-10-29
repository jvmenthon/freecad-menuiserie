# SPDX-License-Identifier: LGPL-2.1-or-later
"""Formes d'essai de ``core/shaped`` : boîtes et cylindres échantillonnés, parfois tournés."""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from typing import TypeVar

from freecad.menuiserie.core.geometry import Vec3
from freecad.menuiserie.core.shaped import ShapeSample

_T = TypeVar("_T")
Rotation = Callable[[Vec3], Vec3]

X, Y, Z = Vec3(1, 0, 0), Vec3(0, 1, 0), Vec3(0, 0, 1)


def same(v: Vec3) -> Vec3:
    return v


def unit_vector(x: float, y: float, z: float) -> Vec3:
    length = math.sqrt(x * x + y * y + z * z)
    return Vec3(x / length, y / length, z / length)


def cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x)


def about_axis(axis: Vec3, degrees: float) -> Rotation:
    """Rotation directe d'un angle autour d'un axe unitaire (formule de Rodrigues)."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))

    def rotate(v: Vec3) -> Vec3:
        dot = axis.x * v.x + axis.y * v.y + axis.z * v.z
        side = cross(axis, v)
        return Vec3(
            v.x * c + side.x * s + axis.x * dot * (1 - c),
            v.y * c + side.y * s + axis.y * dot * (1 - c),
            v.z * c + side.z * s + axis.z * dot * (1 - c),
        )

    return rotate


def about_z(degrees: float) -> Rotation:
    return about_axis(Z, degrees)


def _permuted(items: list[_T], seed: int) -> list[_T]:
    """Permutation déterministe (multiplication modulo 97, premier) sans générateur aléatoire."""
    return [items[i] for i in sorted(range(len(items)), key=lambda i: (i * (2 * seed + 3)) % 97)]


def box_sample(
    lx: float, ly: float, lz: float, rotation: Rotation = same, shuffle_seed: int | None = None
) -> ShapeSample:
    """Boîte [0, lx] x [0, ly] x [0, lz] : 8 sommets, 6 faces planes, 12 arêtes droites."""
    corners = [Vec3(x, y, z) for x, y, z in itertools.product((0, lx), (0, ly), (0, lz))]
    faces = [
        (X, ly * lz),
        (Vec3(-1, 0, 0), ly * lz),
        (Y, lx * lz),
        (Vec3(0, -1, 0), lx * lz),
        (Z, lx * ly),
        (Vec3(0, 0, -1), lx * ly),
    ]
    edges = [(X, lx), (Y, ly), (Z, lz)] * 4
    if shuffle_seed is not None:
        faces, edges, corners = (
            _permuted(items, shuffle_seed) for items in (faces, edges, corners)
        )
    return ShapeSample(
        tuple(rotation(p) for p in corners),
        tuple((rotation(n), area) for n, area in faces),
        tuple((rotation(d), length) for d, length in edges),
    )


def cylinder_sample(radius: float, length: float, rotation: Rotation = same) -> ShapeSample:
    """Cylindre d'axe X (révolution) : deux disques, une génératrice."""
    angles = [k * math.pi / 8 for k in range(16)]
    ring = [(math.cos(a) * radius, math.sin(a) * radius) for a in angles]
    points = [Vec3(x, y, z) for x in (0.0, length) for y, z in ring]
    disc = math.pi * radius**2
    return ShapeSample(
        tuple(rotation(p) for p in points),
        ((rotation(X), disc), (rotation(Vec3(-1, 0, 0)), disc)),
        ((rotation(X), length),),
    )


def close(a: Vec3, b: Vec3, tolerance: float = 1e-9) -> bool:
    return max(abs(a.x - b.x), abs(a.y - b.y), abs(a.z - b.z)) <= tolerance


def parallel(a: Vec3, b: Vec3, tolerance: float = 1e-9) -> bool:
    """Colinéaires (au signe près)."""
    return close(a, b, tolerance) or close(a, Vec3(-b.x, -b.y, -b.z), tolerance)
