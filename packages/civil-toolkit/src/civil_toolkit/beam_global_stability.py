import math
import os
from typing import Optional, Tuple

def _get_epsilon_k(fy: float) -> float:
    return math.sqrt(235.0 / fy)

def get_section_asymmetry_coeff_eta_b(
    is_doubly_symmetric: bool,
    strengthen_comp_flange: bool = False,
    strengthen_ten_flange: bool = False,
    I1: float = 0.0,
    I2: float = 0.0
) -> float:
    """
    计算截面不对称影响系数 eta_b
    
    :param is_doubly_symmetric: 是否为双轴对称截面
    :param strengthen_comp_flange: 单轴对称加强受压翼缘
    :param strengthen_ten_flange: 单轴对称加强受拉翼缘
    :param I1: 受压翼缘对y轴的惯性矩 (mm^4)
    :param I2: 受拉翼缘对y轴的惯性矩 (mm^4)
    """
    if is_doubly_symmetric:
        return 0.0
    
    try:
        alpha_b = I1 / (I1 + I2)
    except ZeroDivisionError:
        alpha_b = 0.5
        
    if strengthen_comp_flange:
        return 0.8 * (2 * alpha_b - 1)
    elif strengthen_ten_flange:
        return 2 * alpha_b - 1
    return 0.0

def get_equivalent_moment_coeff_beta_b(
    support_condition: str,
    load_type: str = "",
    load_position: str = "",
    xi: float = 0.0,
    M1: Optional[float] = None,
    M2: Optional[float] = None
) -> float:
    """
    计算梁整体稳定的等效弯矩系数 beta_b (依据表5.5)
    
    :param support_condition: 侧向支撑情况 (跨中无侧向支撑/跨度中点有一侧向支撑点/跨中有不少于两个等距离侧向支撑点/端部弯矩跨中无荷载)
    :param load_type: 荷载类型 (均布荷载/集中荷载/任意荷载)
    :param load_position: 荷载作用位置 (上翼缘/下翼缘/截面高度的任意位置)
    :param xi: 参数 xi = (L1*t1)/(b1*h)
    :param M1: 端部弯矩1 (绝对值大的一端)。仅在”梁端有弯矩，但跨中无荷载作用“时需要输入。
    :param M2: 端部弯矩2 (产生同向曲率取同号，反向曲率取异号)。仅在”梁端有弯矩，但跨中无荷载作用“时需要输入。
    """
    if support_condition == "跨中无侧向支撑":
        if load_type == "均布荷载":
            if load_position == "上翼缘":
                return min(0.69 + 0.13 * xi, 2.0) if xi <= 2.0 else 0.95
            elif load_position == "下翼缘":
                return min(1.73 - 0.20 * xi, 2.0) if xi <= 2.0 else 1.33
        elif load_type == "集中荷载":
            if load_position == "上翼缘":
                return min(0.73 + 0.18 * xi, 2.0) if xi <= 2.0 else 1.09
            elif load_position == "下翼缘":
                return min(2.23 - 0.28 * xi, 2.0) if xi <= 2.0 else 1.67
                
    elif support_condition == "跨度中点有一侧向支撑点":
        if load_type == "均布荷载" and load_position == "上翼缘":
            return 1.15
        elif load_type == "集中荷载" and load_position == "下翼缘":
            return 1.40
        elif load_type == "集中荷载" and load_position in ["任意位置", "截面高度的任意位置"]:
            return 1.75
            
    elif support_condition == "跨中有不少于两个等距离侧向支撑点":
        if load_position == "上翼缘":
            return 1.20
        elif load_position == "下翼缘":
            return 1.40

    elif support_condition in ["端部弯矩跨中无荷载", "梁端有弯矩，但跨中无荷载作用"]:
        if M1 is None or M2 is None:
            raise ValueError("支撑条件为”梁端有弯矩，但跨中无荷载作用“时，必须输入端部弯矩 M1 和 M2 的值。")
        ratio = (M2 / M1) if M1 != 0 else 0.0
        val = 1.75 - 1.05 * ratio + 0.3 * (ratio ** 2)
        return min(val, 2.3)

    return 1.0  # 默认降级或抛出异常： raise ValueError(f"不匹配的条件 {support_condition} {load_type} {load_position}")

def get_beam_global_stability_coeff(
    beta_b: float,
    lambda_y: float,
    A: float,
    h: float,
    Wx: float,
    t1: float,
    eta_b: float,
    fy: float
) -> Tuple[float, float]:
    """
    计算等截面焊接工字型和轧制H型钢简支梁的整体稳定系数 phi_b (式5.37)
    返回修正前和修正后的梁整体稳定系统 (phi_b, phi_b_prime)
    
    :param beta_b: 等效弯矩系数
    :param lambda_y: 侧向支撑点间对弱轴y-y的长细比
    :param A: 毛截面积 (mm^2)
    :param h: 截面全高 (mm)
    :param Wx: 对x轴的截面模量 (mm^3)
    :param t1: 受压翼缘厚度 (mm)
    :param eta_b: 截面不对称影响系数
    :param fy: 钢材屈服强度 (MPa)
    """
    ek = _get_epsilon_k(fy)
    ek2 = ek ** 2
    
    part1 = beta_b * 4320.0 / (lambda_y ** 2)
    part2 = (A * h) / Wx
    part3_inner = 1.0 + ((lambda_y * t1) / (4.4 * h)) ** 2
    part3 = math.sqrt(part3_inner) + eta_b
    
    phi_b = part1 * part2 * part3 * ek2
    return phi_b, get_modified_global_stability_coeff(phi_b)

def get_modified_global_stability_coeff(phi_b: float) -> float:
    """
    当整体稳定系数原始计算值 phi_b > 0.6 时，其降低值 phi_b' (式5.38)
    """
    if phi_b <= 0.6:
        return phi_b
    
    phi_b_prime = 1.07 - (0.282 / phi_b)
    return min(phi_b_prime, 1.0)

_PHI_FLEXURAL_I_SHAPED_DATA: Optional["pd.DataFrame"] = None

def _load_phi_flexural_data():
    global _PHI_FLEXURAL_I_SHAPED_DATA
    if _PHI_FLEXURAL_I_SHAPED_DATA is not None:
        return _PHI_FLEXURAL_I_SHAPED_DATA
        
    import pandas as pd
    excel_path = os.path.join(os.path.dirname(__file__), "phi_flexual_I_shaped.xlsx")
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"未找到整体稳定系数表格: {excel_path}")
        
    _PHI_FLEXURAL_I_SHAPED_DATA = pd.read_excel(excel_path)
    return _PHI_FLEXURAL_I_SHAPED_DATA

def lookup_hot_rolled_I_section_phi_b(
    item_num: int,
    model_num: float,
    l1: float,
    fy: float = 235.0
) -> Tuple[float, float]:
    """
    读取附表8(热轧普通工字形简支梁的整体稳定系数)中的 phi_b，并自动处理 > 0.6的折减。
    数据已在内存中缓存，避免高频读取时的性能开销。
    返回修正前和修正后的整体稳定系数 (phi_b, phi_b_prime)。
    
    :param item_num: 梁加载类型和边界条件对应的表格项次 (1, 2, 3, 4, 或 5)。1-4为跨中无侧向支撑点的梁，1为集中荷载作用在上翼缘，2为集中荷载作用在下翼缘，3为均布荷载作用在上翼缘，4为均布荷载作用在下翼缘；5为跨中有侧向支撑点的梁（不论荷载作用点在截面高度上的位置）。
    :param model_num: 工字钢型号数值 (如 10, 12.6, 63 等)
    :param l1: 梁的自由长度 (m)
    :param fy: 钢材屈服强度 (MPa)，默认为 235.0 MPa。对于非 Q235 钢，自动对表中查得数值乘以 235/fy。
    """
    df = _load_phi_flexural_data()

    # 处理项次的合并单元格
    item_col = df.iloc[:, 0].copy()
    item_col = item_col.ffill()

    # 查找到对应项次的所有行
    target_rows = df[item_col == float(item_num)]
    if target_rows.empty:
        raise ValueError(f"未找到项次 {item_num}")

    # 在该项次内，找到符合 model_num 范围的行
    selected_row = None
    for idx, row in target_rows.iterrows():
        try:
            min_val = float(row.iloc[4])
            max_val = float(row.iloc[5])
            if min_val <= model_num <= max_val:
                selected_row = row
                break
        except (ValueError, TypeError):
            continue
            
    if selected_row is None:
        # 如果超出边界，取最近的型号边界
        min_model = target_rows.iloc[0, 4]
        max_model = target_rows.iloc[-1, 5]
        raise ValueError(f"型号 {model_num} 不在项次 {item_num} 支持的范围({min_model}-{max_model})内")

    # 提取 l1(m) 对应的 phi_b 数据列 (索引 6 到 14)
    # 表格的第0行(数据区第0引)包含了横向 l1 的坐标 [2.0, 3.0, ..., 10.0]
    l1_coords = [float(x) for x in df.iloc[0, 6:15]]
    phi_values = [float(x) for x in selected_row.iloc[6:15]]

    # 线性插值 l1
    import numpy as np
    raw_phi_b = float(np.interp(l1, l1_coords, phi_values))
    
    # 依据钢号修正：对其他钢号，表中数值应乘以 235/fy
    adjusted_phi_b = raw_phi_b * (235.0 / fy)
    
    return adjusted_phi_b, get_modified_global_stability_coeff(adjusted_phi_b)
