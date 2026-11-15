import math
from fastapi import HTTPException


def validate_descriptors(descs) -> list[list[float]]:
    if not isinstance(descs, list) or not (1 <= len(descs) <= 5):
        raise HTTPException(422, "Provide 1-5 face descriptors.")
    out = []
    for d in descs:
        if not isinstance(d, list) or len(d) != 128 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in d):
            raise HTTPException(422, "Invalid face descriptor.")
        out.append([float(x) for x in d])
    return out


def validate_photo(photo: str | None) -> str | None:
    if not photo:
        return None
    if not photo.startswith("data:image/jpeg;base64,") or len(photo) > 400_000:
        raise HTTPException(422, "Face photo must be a JPEG data URL under ~300 KB.")
    return photo


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def best_distance(stored: list[list[float]], probe: list[float]) -> float:
    return min(distance(s, probe) for s in stored)
