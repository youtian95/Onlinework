import math
from typing import Tuple

def _get_epsilon_k(fy: float) -> float:
    """计算钢材强度的修正系数 epsilon_k"""
    return math.sqrt(235.0 / fy)

def get_axial_comp_h_section_flange_limit(lamda_max: float, fy: float) -> float:
    """
    计算实腹式轴心受压构件（H形截面）翼缘宽厚比 (b/t) 限值
    (依据 GB50017-2017 第7.3章 表7.3.1)
    
    :param lamda_max: 构件的最大长细比 (对H/I型钢取两主轴长细比中的最大值)
    :param fy: 钢材屈服强度 (MPa)
    :return: b/t 的最大容许值
    """
    # 当长细比小于30时，按30计算；当大于100时，按100计算
    lamda = max(30.0, min(lamda_max, 100.0))
    ek = _get_epsilon_k(fy)
    
    limit = (10.0 + 0.1 * lamda) * ek
    return limit

def get_axial_comp_h_section_web_limit(lamda_max: float, fy: float) -> float:
    """
    计算实腹式轴心受压构件（H形截面）腹板高厚比 (h0/tw) 限值
    (依据 GB50017-2017 第7.3章 表7.3.1)
    
    :param lamda_max: 构件的最大长细比 (对H/I型钢取两主轴长细比中的最大值)
    :param fy: 钢材屈服强度 (MPa)
    :return: h0/tw 的最大容许值
    """
    lamda = max(30.0, min(lamda_max, 100.0))
    ek = _get_epsilon_k(fy)
    
    limit = (25.0 + 0.5 * lamda) * ek
    return limit

def get_axial_comp_box_section_limit(fy: float) -> float:
    """
    计算实腹式轴心受压构件（箱形截面）壁板宽厚比 (b/t) 限值
    (依据 GB50017-2017 第7.3章 表7.3.1)
    
    :param fy: 钢材屈服强度 (MPa)
    :return: 最大容许值
    """
    ek = _get_epsilon_k(fy)
    return 40 * ek

def get_axial_comp_circular_tube_limit(fy: float) -> float:
    """
    计算实腹式轴心受压构件（圆管截面）外径与壁厚之比 (D/t) 限值
    (依据 GB50017-2017 第7.3章 表7.3.1)
    
    :param fy: 钢材屈服强度 (MPa)
    :return: D/t 的最大容许值
    """
    ek = _get_epsilon_k(fy)
    # 圆管的径厚比限值不随长细比变化，为 100 * ek^2
    return 100.0 * (ek ** 2)

def get_combined_comp_h_section_flange_class(b: float, t: float, fy: float) -> str:
    """
    计算压弯构件（框架柱）（H形截面）翼缘宽厚比等级 S1~S5
    
    :param b: 翼缘悬伸部分宽度 (mm)
    :param t: 翼缘厚度 (mm)
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 'S5'
    """
    ratio = b / t
    ek = _get_epsilon_k(fy)
    
    if ratio <= 9 * ek:
        return "S1"
    elif ratio <= 11 * ek:
        return "S2"
    elif ratio <= 13 * ek:
        return "S3"
    elif ratio <= 15 * ek:
        return "S4"
    else:
        return "S5"

def get_combined_comp_h_section_web_class(h0: float, tw: float, alpha0: float, fy: float) -> str:
    """
    计算压弯构件（框架柱）（H形截面）腹板高厚比等级 S1~S5
    
    :param h0: 腹板计算高度 (mm)
    :param tw: 腹板厚度 (mm)
    :param alpha0: 截面应力梯度，压弯构件根据 (sigma_max - sigma_min) / sigma_max 计算
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 'S5'
    """
    ratio = h0 / tw
    ek = _get_epsilon_k(fy)
    
    if alpha0 >= 1.05:
        # 部分受拉压弯构件 (1.0 < alpha0 < 2)
        # 需补充完整的压弯腹板公式
        pass
        
    raise NotImplementedError("目前仅实现了完整压弯腹板框架，需补充完整的压弯腹板公式。")

def get_combined_comp_box_section_flange_class(b0: float, t: float, fy: float) -> str:
    """
    计算压弯构件（框架柱）（箱形截面）壁板(腹板)间翼缘宽厚比等级 S1~S4
    
    :param b0: 壁板间的距离 (mm)
    :param t: 壁板厚度 (mm)
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 '超出S4'
    """
    ratio = b0 / t
    ek = _get_epsilon_k(fy)
    
    if ratio <= 30 * ek:
        return "S1"
    elif ratio <= 35 * ek:
        return "S2"
    elif ratio <= 40 * ek:
        return "S3"
    elif ratio <= 45 * ek:
        return "S4"
    else:
        return "超出S4"

def get_combined_comp_circular_tube_class(D: float, t: float, fy: float) -> str:
    """
    计算压弯构件（框架柱）（圆钢管截面）径厚比等级 S1~S4
    
    :param D: 圆钢管截面外径 (mm)
    :param t: 圆钢管截面壁厚 (mm)
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 '超出S4'
    """
    ratio = D / t
    ek = _get_epsilon_k(fy)
    
    if ratio <= 50 * (ek ** 2):
        return "S1"
    elif ratio <= 70 * (ek ** 2):
        return "S2"
    elif ratio <= 90 * (ek ** 2):
        return "S3"
    elif ratio <= 100 * (ek ** 2):
        return "S4"
    else:
        return "超出S4"

def get_flexural_h_section_flange_class(b: float, t: float, fy: float) -> str:
    """
    计算受弯构件（梁）（工字形截面）翼缘宽厚比等级 S1~S5
    
    :param b: 翼缘悬伸部分宽度 (mm)
    :param t: 翼缘厚度 (mm)
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 'S5'
    """
    ratio = b / t
    ek = _get_epsilon_k(fy)
    
    if ratio <= 9 * ek:
        return "S1"
    elif ratio <= 11 * ek:
        return "S2"
    elif ratio <= 13 * ek:
        return "S3"
    elif ratio <= 15 * ek:
        return "S4"
    else:
        return "S5"

def get_flexural_h_section_web_class(h0: float, tw: float, fy: float) -> str:
    """
    计算受弯构件（梁）（工字形截面）腹板高厚比等级 S1~S5
    
    :param h0: 腹板净高 (mm)
    :param tw: 腹板厚度 (mm)
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 'S5'
    """
    ratio = h0 / tw
    ek = _get_epsilon_k(fy)
    
    if ratio <= 65 * ek:
        return "S1"
    elif ratio <= 72 * ek:
        return "S2"
    elif ratio <= 105 * ek:
        return "S3"
    elif ratio <= 124 * ek:
        return "S4"
    else:
        return "S5"

def get_flexural_box_section_flange_class(b0: float, t: float, fy: float) -> str:
    """
    计算受弯构件（梁）（箱形截面）壁板(腹板)间翼缘宽厚比等级 S1~S4
    
    :param b0: 壁板间的距离 (mm)
    :param t: 壁板厚度 (mm)
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 '超出S4'
    """
    ratio = b0 / t
    ek = _get_epsilon_k(fy)
    
    if ratio <= 25 * ek:
        return "S1"
    elif ratio <= 32 * ek:
        return "S2"
    elif ratio <= 37 * ek:
        return "S3"
    elif ratio <= 42 * ek:
        return "S4"
    else:
        return "超出S4"

# ==============================================================================
# 根据等级查询宽厚比/径厚比限值的函数
# ==============================================================================

def get_combined_comp_h_section_flange_limit_by_class(cls: str, fy: float) -> float:
    """查询压弯构件（H形截面）翼缘在指定等级下的宽厚比限值"""
    ek = _get_epsilon_k(fy)
    if cls == "S1": return 9 * ek
    if cls == "S2": return 11 * ek
    if cls == "S3": return 13 * ek
    if cls == "S4": return 15 * ek
    return 20.0

def get_combined_comp_h_section_web_limit_by_class(cls: str, alpha0: float, fy: float) -> float:
    """查询压弯构件（H形截面）腹板在指定等级下的高厚比限值"""
    ek = _get_epsilon_k(fy)
    if cls == "S1": return (3 + 13 * (alpha0 ** 1.3)) * ek
    if cls == "S2": return (38 + 13 * (alpha0 ** 1.39)) * ek
    if cls == "S3": return (40 + 18 * (alpha0 ** 1.5)) * ek
    if cls == "S4": return (45 + 25 * (alpha0 ** 1.66)) * ek
    return 250.0

def get_combined_comp_box_section_flange_limit_by_class(cls: str, fy: float) -> float:
    """查询压弯构件（箱形截面）壁板在指定等级下的宽厚比限值"""
    ek = _get_epsilon_k(fy)
    if cls == "S1": return 30 * ek
    if cls == "S2": return 35 * ek
    if cls == "S3": return 40 * ek
    if cls == "S4": return 45 * ek
    raise ValueError(f"箱形截面压弯构件不支持等级 {cls}")

def get_combined_comp_circular_tube_limit_by_class(cls: str, fy: float) -> float:
    """查询压弯构件（圆钢管截面）在指定等级下的径厚比限值"""
    ek = _get_epsilon_k(fy)
    ek2 = ek ** 2
    if cls == "S1": return 50 * ek2
    if cls == "S2": return 70 * ek2
    if cls == "S3": return 90 * ek2
    if cls == "S4": return 100 * ek2
    raise ValueError(f"圆钢管截面压弯构件不支持等级 {cls}")

def get_flexural_h_section_flange_limit_by_class(cls: str, fy: float) -> float:
    """查询受弯构件（工字形截面）翼缘在指定等级下的宽厚比限值"""
    ek = _get_epsilon_k(fy)
    if cls == "S1": return 9 * ek
    if cls == "S2": return 11 * ek
    if cls == "S3": return 13 * ek
    if cls == "S4": return 15 * ek
    return 20.0

def get_flexural_h_section_web_limit_by_class(cls: str, fy: float) -> float:
    """查询受弯构件（工字形截面）腹板在指定等级下的高厚比限值"""
    ek = _get_epsilon_k(fy)
    if cls == "S1": return 65 * ek
    if cls == "S2": return 72 * ek
    if cls == "S3": return 93 * ek 
    if cls == "S4": return 124 * ek
    return 250.0

def get_flexural_box_section_flange_limit_by_class(cls: str, fy: float) -> float:
    """查询受弯构件（箱形截面）受压翼缘在指定等级下的宽厚比限值"""
    ek = _get_epsilon_k(fy)
    if cls == "S1": return 25 * ek
    if cls == "S2": return 32 * ek
    if cls == "S3": return 37 * ek
    if cls == "S4": return 42 * ek
    raise ValueError(f"箱形截面受弯构件不支持等级 {cls}")

