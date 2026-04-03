import os
from pathlib import Path
import pandas as pd
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

@dataclass
class ISection:
    """热轧普通工字钢截面参数数据类"""
    
    category: str
    """类别 (均为 'I' 或 '工字钢')"""
    
    model: str
    """型号 (例如: I 10, I 20a)"""
    
    designation: str
    """标准截面名称 (同型号)"""
    
    H: float
    """高度 (mm)"""
    
    B: float
    """宽度 (mm)"""
    
    t1: float
    """腹板厚度 (mm) [对应 tw]"""
    
    t2: float
    """翼缘平均厚度 (mm) [对应 tf]"""
    
    r: float
    """圆角半径 (mm) [对应 r1]"""
    
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

_I_SECTION_DATA: Optional[List[ISection]] = None

def _load_i_section_data() -> List[ISection]:
    """
    从 Hot_rolled_I_shaped.xlsx 中加载热轧普通工字钢的参数表格。
    返回 ISection 对象列表，每个对象包含工字钢的所有参数。
    """
    global _I_SECTION_DATA
    if _I_SECTION_DATA is not None:
        return _I_SECTION_DATA

    excel_path = Path(__file__).parent / "Hot_rolled_I_shaped.xlsx"
    
    # 检查 openpyxl 是否存在
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl 缺失，请使用 'pip install openpyxl' 来读取Excel文件。")

    # 读取Excel，不含表头读取以便完全控制索引
    df = pd.read_excel(excel_path, header=None)
    
    # 根据前面的试探，实际数据大概从索引为 2 的行开始（表格第一二是复合表头）
    data_df = df.iloc[2:].copy()
    
    # 列索引映射:
    # 1: model (型号)
    # 2: h (高度 mm)
    # 3: b (宽度 mm)
    # 4: tw (腹板 mm -> t1)
    # 5: tf (翼缘 mm -> t2)
    # 7: r1 (圆角 r mm)
    # 12: A (cm2) 截面面积
    # 13: Iy (强轴 cm4 -> Ix)
    # 14: Iz (弱轴 cm4 -> Iy)
    # 16: iy (强轴 mm -> ix 取 cm)
    # 17: iz (弱轴 mm -> iy 取 cm)
    # 21: Wy (强轴 cm3 -> Wx)
    # 22: Wz (弱轴 cm3 -> Wy)
    # 47: G (kg/m -> weight)
    
    sections = []
    category_name = "I"
    
    for _, row in data_df.iterrows():
        # 如果型号为空，或高度为空，则跳过
        if pd.isna(row[1]) or pd.isna(row[2]) or str(row[1]).strip() == '':
            continue
            
        try:
            h_val = float(row[2])
            b_val = float(row[3])
            t1_val = float(row[4])
            t2_val = float(row[5])
        except (ValueError, TypeError):
            continue
            
        try:
            # 读取其他相关字段，遇到空值或无法转换者置为0
            def safe_float(val, divisor=1.0):
                if pd.isna(val) or str(val).strip() == '':
                    return 0.0
                try:
                    return float(val) / divisor
                except ValueError:
                    return 0.0

            section = ISection(
                category=category_name,
                model=str(row[1]).strip(),
                designation=str(row[1]).strip(),
                H=h_val,
                B=b_val,
                t1=t1_val,
                t2=t2_val,
                r=safe_float(row[7]),
                area=safe_float(row[12]),
                weight=safe_float(row[47]),
                Ix=safe_float(row[13]),
                Iy=safe_float(row[14]),
                ix=safe_float(row[16], divisor=10.0),  # mm 转化为 cm
                iy=safe_float(row[17], divisor=10.0),  # mm 转化为 cm
                Wx=safe_float(row[21]),
                Wy=safe_float(row[22]),
            )
            sections.append(section)
        except Exception:
            continue
            
    _I_SECTION_DATA = sections
    return _I_SECTION_DATA

def get_all_i_sections() -> List[ISection]:
    """获取所有工字钢的参数列表"""
    return _load_i_section_data()

def find_i_sections_by_model(model: str) -> Optional[ISection]:
    """
    根据标称型号查找对应的工字钢，只返回一个准确匹配的截面。
    如 'I 20a', '20a', '20b' 等。会进行忽略大小写和空格的精确匹配。

    :param model: 用户输入的型号字符串
    :return: 匹配的工字钢截面对象，未找到则返回 None
    """
    sections = _load_i_section_data()
    # 去除空格并转小写
    model_query = model.lower().replace(' ', '')
    # 如果用户只输入 "20a"，而表格里叫 "i20a"，可以通过替换 'i' 统一处理
    if not model_query.startswith('i'):
        model_query = 'i' + model_query
        
    for sec in sections:
        sec_model = sec.model.lower().replace(' ', '')
        if sec_model == model_query:
            return sec
    return None

if __name__ == "__main__":
    # 测试打印数据
    sections = get_all_i_sections()
    if sections:
        print(f"找到工字钢数据量: {len(sections)}")
        print("第一条记录:", sections[0])
        res = find_i_sections_by_model("I20a")
        print("查询 I20a 型号:", res if res else "未找到")
