# 本模块提供钢截面轴心受压稳定类别的查询和计算，供各类构件题目复用。
# 使用流程：按截面形式调用相应函数；输入为截面尺寸、加工方式或钢材牌号，输出为绕 x、y 轴的类别元组。


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


def get_welded_box_section_category(b: float, tf: float, h0: float, tw: float) -> tuple[str, str]:
    """按板件宽厚比计算焊接箱形截面绕 x、y 轴的稳定类别。

    :param b: 箱形截面外宽，与翼缘板宽度相同，单位 mm。
    :param tf: 翼缘板厚度，单位 mm。
    :param h0: 两翼缘内表面之间的腹板高度，单位 mm。
    :param tw: 腹板厚度，单位 mm。
    :return: (绕 x 轴的截面类别, 绕 y 轴的截面类别)。
    """
    # 分别计算翼缘和腹板宽厚比，以较大值判断；等于 20 时归入 c 类。
    plate_ratio = max(b / tf, h0 / tw)
    category = "b" if plate_ratio > 20 else "c"
    return category, category


def get_governing_section_category(categories: list[tuple[str, str]]) -> tuple[str, str]:
    """从多组截面类别中，分别选取两个方向的较不利类别。

    本函数只比较已经确定的类别，不负责推导格构截面绕虚轴的规范类别。

    :param categories: 待比较的非空类别列表，每项为 (绕 x 轴类别, 绕 y 轴类别)。
    :return: 两个方向分别按 a、b、c、d 顺序取较不利值的类别元组。
    """
    # 两个方向分别比较，避免较不利的 x、y 类别来自不同截面时遗漏其中一个。
    category_order = {"a": 0, "b": 1, "c": 2, "d": 3}
    category_x = max((item[0] for item in categories), key=category_order.__getitem__)
    category_y = max((item[1] for item in categories), key=category_order.__getitem__)
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


def get_lattice_section_category() -> tuple[str, str]:
    """获取格构式构件的整体稳定截面类别，无需尺寸、钢材牌号或强度输入。

    :return: (绕 x 轴的 b 类, 绕 y 轴的 b 类)。
    """
    # 整体格构截面与单肢截面分别分类，整体两个方向统一采用 b 类。
    return "b", "b"


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
