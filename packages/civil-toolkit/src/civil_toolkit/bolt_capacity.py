# 使用说明：
# 1. 这个文件包含普通螺栓与高强螺栓的单栓承载力计算。
# 2. 普通螺栓：支持单栓抗拉、单栓抗剪。
# 3. 高强螺栓：支持预紧力、摩擦型/承压型单栓抗拉抗剪与拉剪共同作用校核。

from dataclasses import dataclass
from math import pi, sqrt

from .bolt_strengths import (
    get_bearing_type_high_strength_bolt_strength,
    get_bolt_bearing_strength_by_component_steel,
    get_ordinary_bolt_strength,
)


@dataclass(frozen=True)
class BoltTensionCapacity:
    """普通螺栓单栓抗拉承载力结果。"""

    diameter_mm: int
    """螺栓公称直径 (mm)"""
    
    grade: str
    """螺栓性能等级，例如 4.6、4.8、5.6、8.8"""
    
    bolt_class: str
    """普通螺栓类别，通常为 C 或 AB"""
    
    ft_mpa: float
    """普通螺栓抗拉强度设计值 (MPa)"""
    
    effective_area_mm2: float
    """螺栓有效截面积 (mm2)"""
    
    design_kn: float
    """单栓抗拉承载力设计值 (kN)"""
    
    standard: str
    """采用的规范或数据来源标识"""


@dataclass(frozen=True)
class BoltShearCapacity:
    """普通螺栓单栓抗剪承载力结果。"""

    diameter_mm: int
    """螺栓公称直径 (mm)"""
    
    grade: str
    """螺栓性能等级，例如 4.6、4.8、5.6、8.8"""
    
    bolt_class: str
    """普通螺栓类别，通常为 C 或 AB"""
    
    shear_planes: int
    """受剪面数量，即公式中的 n_v"""
    
    fv_mpa: float
    """普通螺栓抗剪强度设计值 (MPa)"""
    
    gross_area_mm2: float
    """按螺栓公称直径计算得到的毛截面积 (mm2)"""
    
    shear_failure_kn: float
    """按抗剪破坏计算得到的承载力设计值 (kN)"""
    
    fc_mpa: float
    """连接板承压强度设计值 (MPa)"""
    
    total_bearing_thickness_mm: float
    """承压计算中各受压板件厚度之和 (mm)"""
    
    bearing_failure_kn: float
    """按承压破坏计算得到的承载力设计值 (kN)"""
    
    design_kn: float
    """最终单栓抗剪承载力设计值，取抗剪破坏和承压破坏中的较小值 (kN)"""
    
    standard: str
    """采用的规范或数据来源标识"""


@dataclass(frozen=True)
class BoltEffectiveSection:
    """螺栓有效截面参数。"""

    diameter_mm: int
    """螺栓公称直径 (mm)"""
    
    pitch_mm: float
    """螺距 (mm)"""
    
    effective_diameter_mm: float
    """螺栓有效直径 (mm)"""
    
    effective_area_mm2: float
    """螺栓有效截面积 (mm2)"""


@dataclass(frozen=True)
class HighStrengthBoltTensionCapacity:
    """高强螺栓单栓抗拉承载力结果。"""

    diameter_mm: int
    """螺栓公称直径 (mm)"""
    
    grade: str
    """高强螺栓性能等级，例如 8.8、10.9"""
    
    preload_kn: float
    """高强螺栓预紧力 P (kN)"""
    
    design_kn: float
    """单栓抗拉承载力设计值，按 0.8P 计算 (kN)"""
    
    standard: str
    """采用的规范或数据来源标识"""


@dataclass(frozen=True)
class HighStrengthFrictionShearCapacity:
    """高强螺栓摩擦型单栓抗剪承载力结果。"""

    diameter_mm: int
    """螺栓公称直径 (mm)"""
    
    grade: str
    """高强螺栓性能等级，例如 8.8、10.9"""
    
    preload_kn: float
    """高强螺栓预紧力 P (kN)"""
    
    friction_coefficient: float
    """摩擦面抗滑移系数 mu"""
    
    slip_surface_count: int
    """摩擦面数量 n_f"""
    
    design_kn: float
    """单栓抗剪承载力设计值，按 0.9*n_f*mu*P 计算 (kN)"""
    
    standard: str
    """采用的规范或数据来源标识"""


@dataclass(frozen=True)
class HighStrengthFrictionCombinedCheck:
    """高强螺栓摩擦型连接拉剪共同作用校核结果。"""

    shear_demand_kn: float
    """单栓剪力设计值 Nv (kN)"""
    
    tension_demand_kn: float
    """单栓拉力设计值 Nt (kN)"""
    
    shear_capacity_kn: float
    """摩擦型单栓抗剪承载力 N_v^b (kN)"""
    
    tension_capacity_kn: float
    """单栓抗拉承载力 N_t^b (kN)"""
    
    interaction_ratio: float
    """线性相关比值 Nv/N_v^b + Nt/N_t^b"""
    
    is_ok: bool
    """是否满足线性相关验算要求 (ratio <= 1)"""
    
    standard: str
    """采用的规范或数据来源标识"""


@dataclass(frozen=True)
class HighStrengthBearingShearCapacity:
    """高强螺栓承压型单栓抗剪承载力结果。

    参数说明：
    - diameter_mm：螺栓公称直径，单位为毫米。
    - grade：高强螺栓性能等级，例如 8.8、10.9。
    - shear_planes：受剪面数量 n_v。
    - fv_mpa：螺栓抗剪强度设计值 f_v^b，单位为 MPa。
    - gross_area_mm2：螺栓毛截面积，单位为平方毫米。
    - shear_failure_kn：按螺杆剪断破坏计算的抗剪承载力 N_v^b，单位为 kN。
    - fc_mpa：连接板承压强度设计值 f_c^b，单位为 MPa。
    - total_bearing_thickness_mm：承压计算厚度和 sum(t)，单位为毫米。
    - bearing_failure_kn：按承压破坏计算的承载力 N_v^c，单位为 kN。
    - design_kn：单栓抗剪承载力设计值，取两种破坏中的较小值，单位为 kN。
    - standard：采用的规范或数据来源标识。
    """

    diameter_mm: int
    grade: str
    shear_planes: int
    fv_mpa: float
    gross_area_mm2: float
    shear_failure_kn: float
    fc_mpa: float
    total_bearing_thickness_mm: float
    bearing_failure_kn: float
    design_kn: float
    standard: str


@dataclass(frozen=True)
class HighStrengthBearingCombinedCheck:
    """高强螺栓承压型连接拉剪共同作用校核结果。

    参数说明：
    - shear_demand_kn：单栓剪力设计值 Nv，单位为 kN。
    - tension_demand_kn：单栓拉力设计值 Nt，单位为 kN。
    - shear_bolt_failure_kn：按螺杆破坏计算的抗剪承载力 N_v^b，单位为 kN。
    - tension_capacity_kn：单栓抗拉承载力 N_t^b，单位为 kN。
    - interaction_ratio：平方和开方相关比值 sqrt((Nv/N_v^b)^2 + (Nt/N_t^b)^2)。
    - bearing_failure_kn：按承压破坏计算的承载力 N_v^c，单位为 kN。
    - bearing_limit_kn：承压破坏控制限值 N_v^c/1.2，单位为 kN。
    - bearing_ratio：承压校核比值 Nv/(N_v^c/1.2)。
    - is_interaction_ok：是否满足拉剪平方和开方相关验算。
    - is_bearing_ok：是否满足承压破坏附加验算。
    - is_ok：综合校核结论，等于前两项同时成立。
    - standard：采用的规范或数据来源标识。
    """

    shear_demand_kn: float
    tension_demand_kn: float
    shear_bolt_failure_kn: float
    tension_capacity_kn: float
    interaction_ratio: float
    bearing_failure_kn: float
    bearing_limit_kn: float
    bearing_ratio: float
    is_interaction_ok: bool
    is_bearing_ok: bool
    is_ok: bool
    standard: str


# 附表 6：螺栓的有效面积。
# 字段依次为：螺距 p、螺栓有效直径 d_e、螺栓有效截面积 A_e。
_BOLT_EFFECTIVE_SECTION_TABLE = {
    16: (2.0, 14.1236, 156.7),
    18: (2.5, 15.6545, 192.5),
    20: (2.5, 17.6545, 244.8),
    22: (2.5, 19.6545, 303.4),
    24: (3.0, 21.1854, 352.5),
    27: (3.0, 24.1854, 459.4),
    30: (3.5, 26.7163, 560.6),
}


# 高强螺栓预紧力 P（单位：kN），按螺栓等级与直径查表。
_HIGH_STRENGTH_BOLT_PRELOAD_KN = {
    "8.8": {16: 80.0, 20: 125.0, 22: 150.0, 24: 175.0, 27: 230.0, 30: 280.0},
    "10.9": {16: 100.0, 20: 155.0, 22: 190.0, 24: 225.0, 27: 290.0, 30: 355.0},
}


# 表 3.9：高强度螺栓连接的孔型尺寸匹配（单位：mm）。
_HIGH_STRENGTH_BOLT_HOLE_DIAMETER_MM = {
    "standard": {12: 13.5, 16: 17.5, 20: 22.0, 22: 24.0, 24: 26.0, 27: 30.0, 30: 33.0},
    "oversized": {12: 16.0, 16: 20.0, 20: 24.0, 22: 28.0, 24: 30.0, 27: 35.0, 30: 38.0},
    "slotted_short": {12: 13.5, 16: 17.5, 20: 22.0, 22: 24.0, 24: 26.0, 27: 30.0, 30: 33.0},
    "slotted_long": {12: 22.0, 16: 30.0, 20: 37.0, 22: 40.0, 24: 45.0, 27: 50.0, 30: 55.0},
}


def _normalize_grade(grade: str) -> str:
    """将螺栓等级标准化为去空格字符串。"""
    return str(grade or "").strip()

def get_available_bolt_diameters_mm() -> list[int]:
    """返回附表 6 中提供的螺栓公称直径列表，单位为毫米。"""
    return sorted(_BOLT_EFFECTIVE_SECTION_TABLE.keys())


def get_available_high_strength_bolt_diameters_mm() -> list[int]:
    """返回高强螺栓可选公称直径列表，按预紧力表汇总。"""
    diameters = {
        diameter_mm
        for row in _HIGH_STRENGTH_BOLT_PRELOAD_KN.values()
        for diameter_mm in row.keys()
    }
    return sorted(diameters)


def get_high_strength_bolt_hole_diameter_mm(diameter_mm: int, hole_type: str = "standard") -> float:
    """按公称直径与孔型获取高强螺栓孔径，默认返回标准孔直径。"""
    hole_key = str(hole_type or "standard").strip().lower()
    hole_table = _HIGH_STRENGTH_BOLT_HOLE_DIAMETER_MM.get(hole_key)
    if hole_table is None:
        supported_types = ", ".join(sorted(_HIGH_STRENGTH_BOLT_HOLE_DIAMETER_MM.keys()))
        raise ValueError(f"Unsupported hole_type: {hole_type}. Supported: {supported_types}")

    d = int(diameter_mm)
    hole_diameter_mm = hole_table.get(d)
    if hole_diameter_mm is None:
        supported_d = ", ".join(str(v) for v in sorted(hole_table.keys()))
        raise ValueError(
            f"Unsupported diameter M{d} for hole_type {hole_key}. Supported: M{supported_d}"
        )
    return float(hole_diameter_mm)


def get_high_strength_bolt_pretension_kn(diameter_mm: int, grade: str) -> float:
    """按高强螺栓等级与直径查预紧力 P，单位为 kN。"""
    key = _normalize_grade(grade)
    d = int(diameter_mm)
    row = _HIGH_STRENGTH_BOLT_PRELOAD_KN.get(key)
    if not row:
        supported = ", ".join(sorted(_HIGH_STRENGTH_BOLT_PRELOAD_KN.keys()))
        raise ValueError(f"Unsupported high-strength bolt grade: {grade}. Supported: {supported}")
    preload = row.get(d)
    if preload is None:
        supported_d = ", ".join(str(v) for v in sorted(row.keys()))
        raise ValueError(f"Unsupported diameter M{d} for grade {grade}. Supported: M{supported_d}")
    return preload

def get_bolt_effective_section(diameter_mm: int) -> BoltEffectiveSection:
    """按螺栓公称直径查附表 6，返回螺距、有效直径和有效面积。"""
    d = int(diameter_mm)
    row = _BOLT_EFFECTIVE_SECTION_TABLE.get(d)
    if row is None:
        supported = ", ".join(str(v) for v in sorted(_BOLT_EFFECTIVE_SECTION_TABLE.keys()))
        raise ValueError(f"Unsupported bolt diameter: M{d}. Supported: M{supported}")
    pitch_mm, effective_diameter_mm, effective_area_mm2 = row
    return BoltEffectiveSection(
        diameter_mm=d,
        pitch_mm=pitch_mm,
        effective_diameter_mm=effective_diameter_mm,
        effective_area_mm2=effective_area_mm2,
    )


def get_bolt_effective_area_mm2(diameter_mm: int) -> float:
    """按螺栓公称直径获取有效截面积，单位为平方毫米。"""
    return get_bolt_effective_section(diameter_mm).effective_area_mm2


def get_bolt_gross_area_mm2(diameter_mm: int) -> float:
    """按公称直径计算螺栓毛截面积，公式为 pi*d^2/4。"""
    d = float(diameter_mm)
    if d <= 0:
        raise ValueError("diameter_mm must be > 0")
    return pi * d * d / 4.0


def ordinary_bolt_single_tension_capacity(
    ft_mpa: float,
    effective_area_mm2: float,
    diameter_mm: int,
    grade: str,
    bolt_class: str,
    standard: str = "GB50017-2017",
) -> BoltTensionCapacity:
    """按普通螺栓抗拉公式计算单栓抗拉承载力设计值。"""
    if ft_mpa <= 0:
        raise ValueError("ft_mpa must be > 0")
    if effective_area_mm2 <= 0:
        raise ValueError("effective_area_mm2 must be > 0")

    design_kn = ft_mpa * effective_area_mm2 / 1000.0

    return BoltTensionCapacity(
        diameter_mm=int(diameter_mm),
        grade=str(grade),
        bolt_class=str(bolt_class),
        ft_mpa=float(ft_mpa),
        effective_area_mm2=float(effective_area_mm2),
        design_kn=design_kn,
        standard=standard,
    )


def ordinary_bolt_single_tension_capacity_by_grade(
    diameter_mm: int,
    grade: str,
    bolt_class: str = "AB",
    standard: str = "GB50017-2017",
) -> BoltTensionCapacity:
    """先按等级查普通螺栓抗拉指标，再计算单栓抗拉承载力。"""
    strength = get_ordinary_bolt_strength(grade=grade, bolt_class=bolt_class, standard=standard)
    effective_area_mm2 = get_bolt_effective_area_mm2(diameter_mm)
    return ordinary_bolt_single_tension_capacity(
        ft_mpa=strength.ft_mpa,
        effective_area_mm2=effective_area_mm2,
        diameter_mm=diameter_mm,
        grade=grade,
        bolt_class=bolt_class,
        standard=standard,
    )


def ordinary_bolt_single_shear_capacity(
    fv_mpa: float,
    fc_mpa: float,
    diameter_mm: int,
    grade: str,
    bolt_class: str,
    shear_planes: int,
    total_bearing_thickness_mm: float,
    standard: str = "GB50017-2017",
) -> BoltShearCapacity:
    """按抗剪破坏与承压破坏两条公式计算并取较小值作为单栓抗剪承载力。"""
    if fv_mpa <= 0:
        raise ValueError("fv_mpa must be > 0")
    if fc_mpa <= 0:
        raise ValueError("fc_mpa must be > 0")
    if shear_planes <= 0:
        raise ValueError("shear_planes must be > 0")
    if total_bearing_thickness_mm <= 0:
        raise ValueError("total_bearing_thickness_mm must be > 0")

    gross_area_mm2 = get_bolt_gross_area_mm2(diameter_mm)
    shear_failure_kn = shear_planes * gross_area_mm2 * fv_mpa / 1000.0
    bearing_failure_kn = float(diameter_mm) * total_bearing_thickness_mm * fc_mpa / 1000.0
    design_kn = min(shear_failure_kn, bearing_failure_kn)

    return BoltShearCapacity(
        diameter_mm=int(diameter_mm),
        grade=str(grade),
        bolt_class=str(bolt_class),
        shear_planes=int(shear_planes),
        fv_mpa=float(fv_mpa),
        gross_area_mm2=gross_area_mm2,
        shear_failure_kn=shear_failure_kn,
        fc_mpa=float(fc_mpa),
        total_bearing_thickness_mm=float(total_bearing_thickness_mm),
        bearing_failure_kn=bearing_failure_kn,
        design_kn=design_kn,
        standard=standard,
    )


def ordinary_bolt_single_shear_capacity_by_grade(
    diameter_mm: int,
    grade: str,
    bolt_class: str,
    shear_planes: int,
    total_bearing_thickness_mm: float,
    component_steel_grade: str,
    standard: str = "GB50017-2017",
) -> BoltShearCapacity:
    """先查普通螺栓抗剪指标和构件承压指标，再计算单栓抗剪承载力。"""
    strength = get_ordinary_bolt_strength(grade=grade, bolt_class=bolt_class, standard=standard)
    bearing_strength = get_bolt_bearing_strength_by_component_steel(
        steel_grade=component_steel_grade,
        bolt_class=bolt_class,
        standard=standard,
    )
    return ordinary_bolt_single_shear_capacity(
        fv_mpa=strength.fv_mpa,
        fc_mpa=bearing_strength.fc_mpa,
        diameter_mm=diameter_mm,
        grade=grade,
        bolt_class=bolt_class,
        shear_planes=shear_planes,
        total_bearing_thickness_mm=total_bearing_thickness_mm,
        standard=standard,
    )


def high_strength_single_tension_capacity(
    diameter_mm: int,
    grade: str,
    standard: str = "GB50017-2017",
) -> HighStrengthBoltTensionCapacity:
    """计算高强螺栓单栓抗拉承载力，摩擦型和承压型均取 N_t^b = 0.8P。"""
    preload_kn = get_high_strength_bolt_pretension_kn(diameter_mm=diameter_mm, grade=grade)
    design_kn = 0.8 * preload_kn
    return HighStrengthBoltTensionCapacity(
        diameter_mm=int(diameter_mm),
        grade=str(grade),
        preload_kn=preload_kn,
        design_kn=design_kn,
        standard=standard,
    )


def high_strength_friction_single_shear_capacity(
    diameter_mm: int,
    grade: str,
    friction_coefficient: float,
    slip_surface_count: int,
    standard: str = "GB50017-2017",
) -> HighStrengthFrictionShearCapacity:
    """计算高强螺栓摩擦型单栓抗剪承载力，公式为 N_v^b = 0.9*n_f*mu*P。"""

    if friction_coefficient <= 0:
        raise ValueError("friction_coefficient must be > 0")
    if slip_surface_count <= 0:
        raise ValueError("slip_surface_count must be > 0")

    preload_kn = get_high_strength_bolt_pretension_kn(diameter_mm=diameter_mm, grade=grade)
    design_kn = 0.9 * int(slip_surface_count) * float(friction_coefficient) * preload_kn
    return HighStrengthFrictionShearCapacity(
        diameter_mm=int(diameter_mm),
        grade=str(grade),
        preload_kn=preload_kn,
        friction_coefficient=float(friction_coefficient),
        slip_surface_count=int(slip_surface_count),
        design_kn=design_kn,
        standard=standard,
    )


def high_strength_friction_combined_check(
    shear_demand_kn: float,
    tension_demand_kn: float,
    shear_capacity_kn: float,
    tension_capacity_kn: float,
    standard: str = "GB50017-2017",
) -> HighStrengthFrictionCombinedCheck:
    """校核高强螺栓摩擦型连接拉剪共同作用，线性相关公式为 Nv/Nvb + Nt/Ntb <= 1。"""
    if shear_capacity_kn <= 0:
        raise ValueError("shear_capacity_kn must be > 0")
    if tension_capacity_kn <= 0:
        raise ValueError("tension_capacity_kn must be > 0")

    ratio = float(shear_demand_kn) / float(shear_capacity_kn) + float(tension_demand_kn) / float(tension_capacity_kn)
    is_ok = ratio <= 1.0
    return HighStrengthFrictionCombinedCheck(
        shear_demand_kn=float(shear_demand_kn),
        tension_demand_kn=float(tension_demand_kn),
        shear_capacity_kn=float(shear_capacity_kn),
        tension_capacity_kn=float(tension_capacity_kn),
        interaction_ratio=ratio,
        is_ok=is_ok,
        standard=standard,
    )


def high_strength_bearing_single_shear_capacity(
    diameter_mm: int,
    grade: str,
    shear_planes: int,
    total_bearing_thickness_mm: float,
    component_steel_grade: str,
    standard: str = "GB50017-2017",
) -> HighStrengthBearingShearCapacity:
    """计算高强螺栓承压型单栓抗剪承载力，包含螺杆破坏与承压破坏并取较小值。"""
    if shear_planes <= 0:
        raise ValueError("shear_planes must be > 0")
    if total_bearing_thickness_mm <= 0:
        raise ValueError("total_bearing_thickness_mm must be > 0")

    hs_strength = get_bearing_type_high_strength_bolt_strength(grade=grade, standard=standard)
    bearing_strength = get_bolt_bearing_strength_by_component_steel(
        steel_grade=component_steel_grade,
        bolt_class="HS",
        standard=standard,
    )

    gross_area_mm2 = get_bolt_gross_area_mm2(diameter_mm)
    shear_failure_kn = int(shear_planes) * gross_area_mm2 * float(hs_strength.fv_mpa) / 1000.0
    bearing_failure_kn = float(diameter_mm) * float(total_bearing_thickness_mm) * float(bearing_strength.fc_mpa) / 1000.0
    design_kn = min(shear_failure_kn, bearing_failure_kn)

    return HighStrengthBearingShearCapacity(
        diameter_mm=int(diameter_mm),
        grade=str(grade),
        shear_planes=int(shear_planes),
        fv_mpa=float(hs_strength.fv_mpa),
        gross_area_mm2=gross_area_mm2,
        shear_failure_kn=shear_failure_kn,
        fc_mpa=float(bearing_strength.fc_mpa),
        total_bearing_thickness_mm=float(total_bearing_thickness_mm),
        bearing_failure_kn=bearing_failure_kn,
        design_kn=design_kn,
        standard=standard,
    )


def high_strength_bearing_combined_check(
    shear_demand_kn: float,
    tension_demand_kn: float,
    shear_bolt_failure_kn: float,
    tension_capacity_kn: float,
    bearing_failure_kn: float,
    standard: str = "GB50017-2017",
) -> HighStrengthBearingCombinedCheck:
    """校核高强螺栓承压型连接拉剪共同作用，并附加承压破坏验算。"""
    if shear_bolt_failure_kn <= 0:
        raise ValueError("shear_bolt_failure_kn must be > 0")
    if tension_capacity_kn <= 0:
        raise ValueError("tension_capacity_kn must be > 0")
    if bearing_failure_kn <= 0:
        raise ValueError("bearing_failure_kn must be > 0")

    interaction_ratio = sqrt(
        (float(shear_demand_kn) / float(shear_bolt_failure_kn)) ** 2
        + (float(tension_demand_kn) / float(tension_capacity_kn)) ** 2
    )
    bearing_limit_kn = float(bearing_failure_kn) / 1.2
    bearing_ratio = float(shear_demand_kn) / bearing_limit_kn

    is_interaction_ok = interaction_ratio <= 1.0
    is_bearing_ok = bearing_ratio <= 1.0
    return HighStrengthBearingCombinedCheck(
        shear_demand_kn=float(shear_demand_kn),
        tension_demand_kn=float(tension_demand_kn),
        shear_bolt_failure_kn=float(shear_bolt_failure_kn),
        tension_capacity_kn=float(tension_capacity_kn),
        interaction_ratio=interaction_ratio,
        bearing_failure_kn=float(bearing_failure_kn),
        bearing_limit_kn=bearing_limit_kn,
        bearing_ratio=bearing_ratio,
        is_interaction_ok=is_interaction_ok,
        is_bearing_ok=is_bearing_ok,
        is_ok=is_interaction_ok and is_bearing_ok,
        standard=standard,
    )