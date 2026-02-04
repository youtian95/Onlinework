# 题目元数据
meta = {
    "title": "整数加法练习",
    "inputs": {
        "ans_1": {"max_attempts": 3, "score": 10},
        "ans_2": {"max_attempts": 3, "score": 10},
    }
}

def generate(rng):
    """
    根据传入的随机数生成器生成题目参数
    """
    a = rng.randint(10, 99)
    b = rng.randint(10, 99)
    
    return {
        "a": a,
        "b": b
    }

def check(params, user_answers):
    """
    检查答案
        params: 已经生成好的题目参数 {'a': 12, 'b': 34, ...}
        user_answers: 用户提交的答案字典 {'ans_1': 'answer', ...}

    return: 
        结果字典 {'ans_1': True/False, ...}
    """
    correct_sum = params['a'] + params['b']
    correct_minus = params['a'] - params['b']
    
    results = {}
    
    # 检查 ans_1
    val_1 = user_answers.get("ans_1", str(correct_sum + 1000)) # 默认错误
    val_2 = user_answers.get("ans_2", str(correct_minus + 1000))
    try:
        if int(val_1) == correct_sum:
            results["ans_1"] = True
        else:
            results["ans_1"] = False
        if int(val_2) == correct_minus:
            results["ans_2"] = True
        else: 
            results["ans_2"] = False
    except ValueError:
        results["ans_1"] = False
        results["ans_2"] = False
    return results
