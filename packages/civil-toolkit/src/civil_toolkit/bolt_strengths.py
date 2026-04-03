# 使用说明：
# 1. 这个文件只负责螺栓强度指标查表，不负责承载力计算。
# 2. 普通螺栓、锚栓、承压型高强螺栓、螺栓球节点高强螺栓的强度指标都在这里查。
# 3. 如果要计算单栓抗拉承载力，请改用 bolt_capacity.py 中的函数。

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BoltStrengthIndex:
    """螺栓强度指标查表结果，统一承载各类强度设计值。"""

    source_group: str
    """数据来源分组标识"""
    
    grade: str
    """螺栓性能等级或钢材牌号 (例如 '4.6', '8.8', 'Q235')"""
    
    ft_mpa: Optional[float] = None
    """螺栓抗拉强度设计值 ft (MPa)"""
    
    fv_mpa: Optional[float] = None
    """螺栓抗剪强度设计值 fvb (MPa)"""
    
    fc_mpa: Optional[float] = None
    """承压强度设计值 fcb (MPa)"""
    
    fub_mpa: Optional[float] = None
    """螺栓最小抗拉强度 fub (MPa)"""
    
    standard: str = "GB50017-2017"
    """查询所依据的规范标准"""


# 按性能等级给出的抗拉强度后备值。
_MECHANICAL_GRADE_FUB_MPA = {
    "4.6": 400.0,
    "4.8": 400.0,
    "5.6": 500.0,
    "5.8": 500.0,
    "6.8": 600.0,
    "8.8": 800.0,
    "10.9": 1000.0,
    "12.9": 1200.0,
}


# 数据来源：用户提供的“附表5 螺栓连接的强度指标”图片。
# 普通螺栓：C级螺栓
_ORDINARY_BOLT_C_STRENGTH = {
    "4.6": {"ft": 170.0, "fv": 140.0},
    "4.8": {"ft": 170.0, "fv": 140.0},
}

# 普通螺栓：A、B级螺栓
_ORDINARY_BOLT_AB_STRENGTH = {
    "5.6": {"ft": 210.0, "fv": 190.0},
    "8.8": {"ft": 400.0, "fv": 320.0},
}

# 锚栓：按锚栓钢材牌号给出的抗拉设计值
_ANCHOR_BOLT_TENSION_STRENGTH = {
    "Q235": 140.0,
    "Q355": 180.0,
    "Q390": 185.0,
}

# 承压型高强度螺栓或网架用高强度螺栓
_BEARING_TYPE_HIGH_STRENGTH_BOLT = {
    "8.8": {"ft": 400.0, "fv": 250.0, "fub": 830.0},
    "10.9": {"ft": 500.0, "fv": 310.0, "fub": 1040.0},
}

# 螺栓球节点用高强度螺栓
_BOLT_SPHERE_NODE_HIGH_STRENGTH = {
    "9.8": {"ft": 385.0},
    "10.9": {"ft": 430.0},
}

# 按构件钢材牌号给出的承压设计值
_COMPONENT_STEEL_BEARING_STRENGTH = {
    "Q235": {"c": 305.0, "ab": 405.0, "hs": 470.0},
    "Q355": {"c": 385.0, "ab": 510.0, "hs": 590.0},
    "Q390": {"c": 400.0, "ab": 530.0, "hs": 615.0},
    "Q420": {"c": 425.0, "ab": 560.0, "hs": 655.0},
    "Q460": {"c": 450.0, "ab": 595.0, "hs": 695.0},
    "Q345GJ": {"c": 400.0, "ab": 530.0, "hs": 615.0},
}


def _normalize_grade(value: str) -> str:
    """将牌号或等级标准化为去空格后的大写字符串。"""
    return str(value or "").strip().upper()


def get_ordinary_bolt_strength(
    grade: str,
    bolt_class: str = "AB",
    standard: str = "GB50017-2017",
) -> BoltStrengthIndex:
    """按普通螺栓等级和类别查抗拉与抗剪强度设计值。"""
    key = _normalize_grade(grade)
    cls = _normalize_grade(bolt_class)

    if cls == "C":
        row = _ORDINARY_BOLT_C_STRENGTH.get(key)
        if not row:
            supported = ", ".join(sorted(_ORDINARY_BOLT_C_STRENGTH.keys()))
            raise ValueError(f"Unsupported C-class ordinary bolt grade: {grade}. Supported: {supported}")
        return BoltStrengthIndex(
            source_group="ordinary_bolt_c",
            grade=key,
            ft_mpa=row["ft"],
            fv_mpa=row["fv"],
            standard=standard,
        )

    if cls in {"AB", "A/B", "A_B"}:
        row = _ORDINARY_BOLT_AB_STRENGTH.get(key)
        if not row:
            supported = ", ".join(sorted(_ORDINARY_BOLT_AB_STRENGTH.keys()))
            raise ValueError(f"Unsupported A/B-class ordinary bolt grade: {grade}. Supported: {supported}")
        return BoltStrengthIndex(
            source_group="ordinary_bolt_ab",
            grade=key,
            ft_mpa=row["ft"],
            fv_mpa=row["fv"],
            standard=standard,
        )

    raise ValueError("bolt_class must be one of: C, AB")


def get_anchor_bolt_tension_strength(
    steel_grade: str,
    standard: str = "GB50017-2017",
) -> BoltStrengthIndex:
    """按锚栓钢材牌号查锚栓抗拉强度设计值。"""
    key = _normalize_grade(steel_grade)
    ft = _ANCHOR_BOLT_TENSION_STRENGTH.get(key)
    if ft is None:
        supported = ", ".join(sorted(_ANCHOR_BOLT_TENSION_STRENGTH.keys()))
        raise ValueError(f"Unsupported anchor steel grade: {steel_grade}. Supported: {supported}")

    return BoltStrengthIndex(
        source_group="anchor_bolt",
        grade=key,
        ft_mpa=ft,
        standard=standard,
    )


def get_bearing_type_high_strength_bolt_strength(
    grade: str,
    standard: str = "GB50017-2017",
) -> BoltStrengthIndex:
    """按承压型高强螺栓等级查强度设计值和抗拉强度。"""
    key = _normalize_grade(grade)
    row = _BEARING_TYPE_HIGH_STRENGTH_BOLT.get(key)
    if not row:
        supported = ", ".join(sorted(_BEARING_TYPE_HIGH_STRENGTH_BOLT.keys()))
        raise ValueError(f"Unsupported bearing-type high-strength bolt grade: {grade}. Supported: {supported}")

    return BoltStrengthIndex(
        source_group="bearing_type_high_strength_bolt",
        grade=key,
        ft_mpa=row["ft"],
        fv_mpa=row["fv"],
        fub_mpa=row["fub"],
        standard=standard,
    )


def get_bolt_sphere_node_high_strength_bolt_strength(
    grade: str,
    standard: str = "GB50017-2017",
) -> BoltStrengthIndex:
    """按螺栓球节点高强螺栓等级查抗拉强度设计值。"""
    key = _normalize_grade(grade)
    row = _BOLT_SPHERE_NODE_HIGH_STRENGTH.get(key)
    if not row:
        supported = ", ".join(sorted(_BOLT_SPHERE_NODE_HIGH_STRENGTH.keys()))
        raise ValueError(f"Unsupported bolt-sphere node high-strength grade: {grade}. Supported: {supported}")

    return BoltStrengthIndex(
        source_group="bolt_sphere_node_high_strength_bolt",
        grade=key,
        ft_mpa=row["ft"],
        standard=standard,
    )


def get_bolt_bearing_strength_by_component_steel(
    steel_grade: str,
    bolt_class: str = "AB",
    standard: str = "GB50017-2017",
) -> BoltStrengthIndex:
    """按构件钢材牌号和螺栓类别查连接承压强度设计值。
    - steel_grade: 构件钢材牌号，如 Q235、Q355 等。
    - bolt_class: 螺栓类别，C 代表普通螺栓C级，AB 代表普通螺栓A/B级，HS 代表承压型高强螺栓或网架用高强螺栓。默认 AB。
    """
    key = _normalize_grade(steel_grade)
    row = _COMPONENT_STEEL_BEARING_STRENGTH.get(key)
    if not row:
        supported = ", ".join(sorted(_COMPONENT_STEEL_BEARING_STRENGTH.keys()))
        raise ValueError(f"Unsupported component steel grade: {steel_grade}. Supported: {supported}")

    cls = _normalize_grade(bolt_class)
    if cls == "C":
        fc = row["c"]
    elif cls in {"AB", "A/B", "A_B"}:
        fc = row["ab"]
    elif cls in {"HS", "HIGH", "HIGH_STRENGTH", "BEARING_HS"}:
        fc = row["hs"]
    else:
        raise ValueError("bolt_class must be one of: C, AB, HS")

    return BoltStrengthIndex(
        source_group="component_steel_bearing",
        grade=key,
        fc_mpa=fc,
        standard=standard,
    )


def get_bolt_ultimate_strength_mpa(grade: str) -> float:
    """按等级获取螺栓抗拉强度，用于需要 fub 的计算。"""
    key = _normalize_grade(grade)

    row = _BEARING_TYPE_HIGH_STRENGTH_BOLT.get(key)
    if row:
        return row["fub"]

    fub = _MECHANICAL_GRADE_FUB_MPA.get(key)
    if fub is None:
        supported = ", ".join(sorted(_MECHANICAL_GRADE_FUB_MPA.keys()))
        raise ValueError(f"Unsupported bolt grade: {grade}. Supported: {supported}")
    return fub