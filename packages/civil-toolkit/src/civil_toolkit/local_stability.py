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

def get_bending_h_section_flange_class(b: float, t: float, fy: float) -> str:
    """
    计算压弯和受弯构件的（工字形或H形截面）翼缘宽厚比等级 S1~S5
    (依据 GB50017-2017 表3.5.1)
    
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

def get_bending_h_section_web_class(h0: float, tw: float, alpha0: float, fy: float) -> str:
    """
    计算压弯和受弯构件的（工字形或H形截面）腹板高厚比等级 S1~S5
    (依据 GB50017-2017 表3.5.1)
    
    :param h0: 腹板计算高度 (mm)
    :param tw: 腹板厚度 (mm)
    :param alpha0: 截面应力梯度，受弯构件通常为 2，压弯构件根据 (sigma_max - sigma_min) / sigma_max 计算
    :param fy: 钢材屈服强度 (MPa)
    :return: 'S1', 'S2', 'S3', 'S4' 或 'S5'
    """
    ratio = h0 / tw
    ek = _get_epsilon_k(fy)
    
    if alpha0 == 2.0:
        # 纯弯构件
        if ratio <= 72 * ek:
            return "S1"
        elif ratio <= 83 * ek:
            return "S2"
        elif ratio <= 105 * ek:
            return "S3"
        elif ratio <= 124 * ek:
            return "S4"
        else:
            return "S5"
    elif alpha0 >= 1.05:
        # 部分受拉压弯构件 (1.0 < alpha0 < 2)
        # S1: (36/alpha0 - 1)
        # S2: (41/alpha0 - 1)
        # S3: (48/alpha0 + 10.5) 或者是? Wait, formulas in 3.5.1: 
        # Actually it's complex to guess exactly without seeing the image properly.
        # But generally:
        # S1: (36/α0 - 1)
        # S2: (41/α0 - 1)
        # S3: (48/α0 + 0.5 α0^2?) wait, S3 for alpha0>1 is (48/alpha0 + 0.5 *?) No, it's (48/α0 + 10.5) - something?
        pass
        
    # 为了避免写错完整公式而引发错误，我会先返回一个保守或者通用的提示。
    raise NotImplementedError("目前仅实现了 alpha0=2 的受弯构件腹板分类。需补充完整的压弯腹板公式。")
