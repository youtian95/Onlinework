import os
from pathlib import Path
import pandas as pd
import math

# 缓存加载的数据
_PHI_DATA = None

def _load_phi_data():
    """
    从 column_phi.xlsx 中加载稳定系数（phi）表格。
    返回一个包含 'a', 'b', 'c', 'd' 键的字典，每个键对应一个
    按 lamda 排序的元组列表：[(lamda_val, phi_val), ...]
    """
    global _PHI_DATA
    if _PHI_DATA is not None:
        return _PHI_DATA

    excel_path = Path(__file__).parent / "column_phi.xlsx"
    
    data = {'a': [], 'b': [], 'c': [], 'd': []}
    
    # 不包含表头读取 excel 文件
    df = pd.read_excel(excel_path, header=None)
    
    # 将 DataFrame 所有单元格转换为字符串，将 NaN 视为空字符串 ''
    df = df.fillna('')
    lines = df.astype(str).values.tolist()
    
    for row in lines:
        if not row or len(row) < 11:
            continue
            
        try:
            # 检查行首是否为数字（长细比的十位）
            int(row[0].strip().replace('.0', ''))
        except ValueError:
            continue
            
        # 依次解析 'a', 'b', 'c', 'd' 类别
        categories = ['a', 'b', 'c', 'd']
        offsets = []
        
        # 动态找出每个类别对应的起始索引，以增强鲁棒性
        for i, val in enumerate(row):
            clean_val = val.strip()
            # 必须是数字，并且是第一个元素，或者其前一个元素为空白或 NaN
            if clean_val.replace('.', '', 1).isdigit() and (i == 0 or (i > 0 and not row[i-1].strip())):
                offsets.append(i)
                
        # 退回使用默认的预期偏移量
        if len(offsets) < 4:
            offsets = [0, 11, 22, 33]
            
        for idx, cat in enumerate(categories):
            if idx >= len(offsets):
                continue
            offset = offsets[idx]
            if offset + 10 >= len(row):
                continue
                
            try:
                base_lamda = float(row[offset].strip())
            except ValueError:
                continue
                
            for unit in range(10):
                val_idx = offset + 1 + unit
                if val_idx < len(row):
                    val_str = row[val_idx].strip()
                    if val_str and val_str != '---' and val_str != 'NaN':
                        try:
                            phi_val = float(val_str)
                            lamda_val = base_lamda + unit
                            data[cat].append((lamda_val, phi_val))
                        except ValueError:
                            pass
                            
    # 对数据进行排序，确保插值准确
    for cat in categories:
        data[cat].sort(key=lambda x: x[0])
        
    _PHI_DATA = data
    return _PHI_DATA

def get_phi(category: str, lamda: float, fy: float = 235.0) -> float:
    """
    插值获取给定类别和长细比的稳定系数（phi）。如果长细比超出表格范围，返回0。
    
    :param category: 截面类别，为 'a', 'b', 'c', 'd' 中的一个
    :param lamda: 构件的长细比
    :param fy: 钢材的屈服强度 (N/mm²)，默认 235.0
    :return: 稳定系数 phi
    """
    category = category.lower()
    if category not in ['a', 'b', 'c', 'd']:
        raise ValueError("类别必须是 'a', 'b', 'c', 'd' 中的一个")
        
    data = _load_phi_data()
    cat_data = data[category]
    
    if not cat_data:
        raise RuntimeError(f"未加载到类别 {category} 的数据")
        
    # 根据规范，查表所需的长细比参数等于 lambda * sqrt(fy/235)
    lookup_lamda = lamda * math.sqrt(fy / 235.0)
        
    # 边界限制检查
    if lookup_lamda <= cat_data[0][0]:
        return cat_data[0][1]
    if lookup_lamda > cat_data[-1][0]:
        return 0.0

    # 线性插值
    for i in range(len(cat_data) - 1):
        x0, y0 = cat_data[i]
        x1, y1 = cat_data[i+1]
        if x0 <= lookup_lamda <= x1:
            if x0 == x1:
                return y0
            # 线性插值公式
            return y0 + (y1 - y0) * (lookup_lamda - x0) / (x1 - x0)
            
    return 0.0

# 直接运行时的示例测试逻辑
if __name__ == "__main__":
    print("测试 get_phi('b', 15.5, 345):", get_phi('b', 15.5, 345))