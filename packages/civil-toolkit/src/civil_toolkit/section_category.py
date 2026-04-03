def get_welded_h_section_category(tf: float, edge_type: str = "flame_cut") -> tuple[str, str]:
    """
    获取焊接组合 H 型钢的截面类别。

    根据 GB 50017-2017 中表 7.2.1，计算轴心受压构件稳定系数时所需的截面类别。

    :param tf: 翼缘厚度 (mm)
    :param edge_type: 边缘加工方式，可选 "flame_cut" (默认，焰切边) 或 "sheared_edge" (剪切边或轧成边)
    :return: (绕强轴的截面类别, 绕弱轴的截面类别)
    """
    if edge_type == "sheared_edge":
        if tf >= 40:
            category_x = "c"
            category_y = "d"
        else:
            category_x = "b"
            category_y = "c"
    else:
        # 默认作为焰切边处理
        if tf >= 40:
            category_x = "b"
            category_y = "b"
        else:
            category_x = "b"
            category_y = "b"
            
    return category_x, category_y


def get_hot_rolled_i_section_category(h: float, b: float, steel_grade: str) -> tuple[str, str]:
    """
    获取热轧普通工字钢的截面类别。

    根据 GB 50017-2017 中表 7.2.1，计算轴心受压构件稳定系数时所需的截面类别。

    :param h: 截面高度 (mm)
    :param b: 截面宽度 (mm)
    :param steel_grade: 钢材牌号 (如 'Q235', 'Q355')
    :return: (绕强轴的截面类别, 绕弱轴的截面类别)
    """
    if b / h <= 0.8:
        category_x = "a"
        category_y = "b"
    else:
        if steel_grade.upper() == "Q235":
            category_x = "b"
            category_y = "c"
        else:
            category_x = "a"
            category_y = "b"
    return category_x, category_y


def get_hot_rolled_h_section_category(h: float, b: float, tf: float, steel_grade: str) -> tuple[str, str]:
    """
    获取热轧 H 型钢的截面类别。

    根据 GB 50017-2017 中表 7.2.1，计算轴心受压构件稳定系数时所需的截面类别。

    :param h: 截面高度 (mm)
    :param b: 截面宽度 (mm)
    :param tf: 翼缘厚度 (mm)
    :param steel_grade: 钢材牌号 (如 'Q235', 'Q355')
    :return: (绕强轴的截面类别, 绕弱轴的截面类别)
    """
    if tf >= 40:
        if tf < 80:
            category_x = "b"
            category_y = "c"
        else:
            category_x = "c"
            category_y = "d"
    else:
        if b / h <= 0.8:
            category_x = "a"
            category_y = "b"
        else:
            if steel_grade.upper() == "Q235":
                category_x = "b"
                category_y = "c"
            else:
                category_x = "a"
                category_y = "b"
    return category_x, category_y
