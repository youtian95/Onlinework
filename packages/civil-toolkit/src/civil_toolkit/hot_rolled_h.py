import os
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class HSection:
    """热轧H型钢截面参数数据类"""
    
    category: str
    """类别 (例如: HW, HM, HN, HT)"""
    
    model: str
    """型号 (例如: 400×400)"""
    
    designation: str
    """准确截面名称 (例如: 414×405)"""
    
    H: float
    """高度 (mm)"""
    
    B: float
    """宽度 (mm)"""
    
    t1: float
    """腹板厚度 (mm)"""
    
    t2: float
    """翼缘厚度 (mm)"""
    
    r: float
    """圆角半径 (mm)"""
    
    area: float
    """截面面积 (cm2)"""
    
    weight: float
    """理论重量 (kg/m)"""
    
    Ix: float
    """强轴惯性矩 (cm4)"""
    
    Iy: float
    """弱轴惯性矩 (cm4)"""
    
    ix: float
    """强轴回转半径 (cm)"""
    
    iy: float
    """弱轴回转半径 (cm)"""
    
    Wx: float
    """强轴截面抵抗矩 (cm3)"""
    
    Wy: float
    """弱轴截面抵抗矩 (cm3)"""

_H_SECTION_DATA: Optional[List[HSection]] = None

def _load_h_section_data() -> List[HSection]:
    """
    从 Hot_rolled_H_shaped.xlsx 中加载热轧H型钢的参数表格。
    采用向前填充(ffill)处理合并单元格产生的数据缺失。
    返回 HSection 对象列表，每个对象包含H型钢的所有参数。
    """
    global _H_SECTION_DATA
    if _H_SECTION_DATA is not None:
        return _H_SECTION_DATA

    excel_path = Path(__file__).parent / "Hot_rolled_H_shaped.xlsx"
    
    # 检查 openpyxl 是否存在
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl 缺失，请使用 'pip install openpyxl' 来读取Excel文件。")

    # 读取Excel，跳过前4行作为无效表头，提取纯数据
    df = pd.read_excel(excel_path, header=None)
    
    # 前4行（索引0~3）分别是标题或合并表头，有效数据从第4行（索引4）开始
    data_df = df.iloc[4:].copy()
    
    # 列 0 和 列 1 存在合并单元格现象，需要使用向前填充(ffill)
    data_df[[0, 1]] = data_df[[0, 1]].ffill()
    
    # 重命名便于处理内部的列索引
    # 0: category, 1: model, 2: HxB, 3: t1, 4: t2, 5: r
    # 6: area, 7: weight, 8: Ix, 9: Iy, 10: ix, 11: iy, 12: Wx, 13: Wy
    
    sections = []
    for _, row in data_df.iterrows():
        # 如果尺寸列（2）为空或无效，则跳过
        if pd.isna(row[2]) or pd.isna(row[3]) or str(row[2]).strip() == '':
            continue
            
        raw_dim = str(row[2]).strip().lower().replace('×', 'x')
        if 'x' not in raw_dim:
            continue
            
        try:
            h_val = float(raw_dim.split('x')[0])
            b_val = float(raw_dim.split('x')[1])
        except ValueError:
            continue
            
        try:
            section_data = HSection(
                category=str(row[0]).strip(),
                model=str(row[1]).strip(),
                designation=str(row[2]).strip(),
                H=h_val,
                B=b_val,
                t1=float(row[3]),
                t2=float(row[4]),
                r=float(row[5]) if not pd.isna(row[5]) else 0.0,
                area=float(row[6]) if not pd.isna(row[6]) else 0.0,
                weight=float(row[7]) if not pd.isna(row[7]) else 0.0,
                Ix=float(row[8]) if not pd.isna(row[8]) else 0.0,
                Iy=float(row[9]) if not pd.isna(row[9]) else 0.0,
                ix=float(row[10]) if not pd.isna(row[10]) else 0.0,
                iy=float(row[11]) if not pd.isna(row[11]) else 0.0,
                Wx=float(row[12]) if not pd.isna(row[12]) else 0.0,
                Wy=float(row[13]) if not pd.isna(row[13]) else 0.0,
            )
            
            sections.append(section_data)
        except (ValueError, TypeError):
            continue
            
    _H_SECTION_DATA = sections
    return _H_SECTION_DATA

def get_all_h_sections() -> List[HSection]:
    """获取所有H型钢的参数列表"""
    return _load_h_section_data()

def get_h_section(category: str, h: float, b: float) -> Optional[HSection]:
    """
    根据给定的类别及截面尺寸严格寻找匹配的H型钢参数。
    (例如 HW, H, B)
    
    :param category: 钢材类别 (如 HW, HM, HN)
    :param h: 高度 (mm)
    :param b: 宽度 (mm)
    :return: 匹配的H型钢截面对象，找不到则返回None
    """
    sections = _load_h_section_data()
    # 容差范围
    tol = 1e-3
    cat_upper = category.upper()
    for sec in sections:
        if (sec.category.upper() == cat_upper and 
            abs(sec.H - h) < tol and 
            abs(sec.B - b) < tol):
            return sec
    return None

def find_h_sections_by_model(model: str) -> Optional[HSection]:
    """
    根据输入的型号字符串直接查找对应的H型钢，例如 'HW250×255', 'HM 300x200' 等。
    大小写不敏感，支持乘号 '×' 和字母 'x' 混用，空格会被忽略。
    
    :param model: 用户输入的型号字符串
    :return: 匹配的H型钢截面对象，未找到则返回 None
    """
    sections = _load_h_section_data()
    query = model.lower().replace('×', 'x').replace(' ', '')
    
    for sec in sections:
        # 拼接已有数据的 category 和 designation 并标准化对比，例如 'hw' + '414x405' = 'hw414x405'
        sec_str = (sec.category + sec.designation).lower().replace('×', 'x').replace(' ', '')
        if sec_str == query:
            return sec
            
    return None

if __name__ == "__main__":
    # 测试打印第一项数据
    sections = get_all_h_sections()
    if sections:
        print("找到型钢数据量:", len(sections))
        print("第一条记录:", sections[0])
        print("严格查询 HW, H=414, B=405:", get_h_section("HW", 414, 405))
        
        # 测试直接通过字符串查找
        test_model = "HW 414×405"
        res = find_h_sections_by_model(test_model)
        print(f"快捷查询 '{test_model}':", res.designation if res else "未找到")
