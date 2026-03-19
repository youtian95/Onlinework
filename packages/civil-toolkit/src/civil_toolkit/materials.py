from dataclasses import dataclass


@dataclass(frozen=True)
class SteelStrength:
    """钢材强度查表结果，包含抗拉抗剪承压与屈服抗拉指标。"""

    grade: str
    thickness_mm: float
    f_mpa: float
    fv_mpa: float
    fce_mpa: float
    fy_mpa: float
    fu_mpa: float
    standard: str


# Data source: user-provided structural steel strength table image.
# Fields per row: (upper_thickness_mm, f, fv, fce, fy, fu)
_STEEL_TABLE_GB50017_2017 = {
    "Q235": [
        (16.0, 215.0, 125.0, 320.0, 235.0, 370.0),
        (40.0, 205.0, 120.0, 320.0, 225.0, 370.0),
        (100.0, 200.0, 115.0, 320.0, 215.0, 370.0),
    ],
    "Q355": [
        (16.0, 305.0, 175.0, 400.0, 355.0, 470.0),
        (40.0, 295.0, 170.0, 400.0, 345.0, 470.0),
        (63.0, 290.0, 165.0, 400.0, 335.0, 470.0),
        (80.0, 280.0, 160.0, 400.0, 325.0, 470.0),
        (100.0, 270.0, 155.0, 400.0, 315.0, 470.0),
    ],
    "Q390": [
        (16.0, 345.0, 200.0, 415.0, 390.0, 490.0),
        (40.0, 330.0, 190.0, 415.0, 370.0, 490.0),
        (63.0, 310.0, 180.0, 415.0, 350.0, 490.0),
        (100.0, 295.0, 170.0, 415.0, 330.0, 490.0),
    ],
    "Q420": [
        (16.0, 375.0, 215.0, 440.0, 420.0, 520.0),
        (40.0, 355.0, 205.0, 440.0, 400.0, 520.0),
        (63.0, 320.0, 185.0, 440.0, 380.0, 520.0),
        (100.0, 305.0, 175.0, 440.0, 360.0, 520.0),
    ],
    "Q460": [
        (16.0, 410.0, 235.0, 470.0, 460.0, 550.0),
        (40.0, 390.0, 225.0, 470.0, 440.0, 550.0),
        (63.0, 355.0, 205.0, 470.0, 420.0, 550.0),
        (100.0, 340.0, 195.0, 470.0, 400.0, 550.0),
    ],
}


def _normalize_grade(grade: str) -> str:
    """将钢材牌号标准化为去空格后的大写字符串。"""
    return str(grade or "").strip().upper()


def get_steel_strength(grade: str, thickness_mm: float, standard: str = "GB50017-2017") -> SteelStrength:
    """按钢材牌号与厚度查强度设计值并返回统一结果对象。"""
    if thickness_mm is None or float(thickness_mm) <= 0:
        raise ValueError("thickness_mm must be > 0")

    if standard != "GB50017-2017":
        raise ValueError(f"Unsupported standard: {standard}")

    normalized_grade = _normalize_grade(grade)
    rows = _STEEL_TABLE_GB50017_2017.get(normalized_grade)
    if not rows:
        supported = ", ".join(sorted(_STEEL_TABLE_GB50017_2017.keys()))
        raise ValueError(f"Unsupported steel grade: {grade}. Supported grades: {supported}")

    t = float(thickness_mm)
    for upper_limit, f, fv, fce, fy, fu in rows:
        if t <= upper_limit:
            return SteelStrength(
                grade=normalized_grade,
                thickness_mm=t,
                f_mpa=f,
                fv_mpa=fv,
                fce_mpa=fce,
                fy_mpa=fy,
                fu_mpa=fu,
                standard=standard,
            )

    raise ValueError(f"thickness_mm is out of supported range for {normalized_grade}: {t}")
