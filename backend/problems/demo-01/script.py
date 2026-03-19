from backend.services.problem_check_template import NumericCheckTemplate


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

class Demo01Checker(NumericCheckTemplate):
    def ans_1(self):
        correct_sum = self.params["a"] + self.params["b"]
        return self.is_int_equal("ans_1", correct_sum)

    def ans_2(self):
        correct_minus = self.params["a"] - self.params["b"]
        return self.is_int_equal("ans_2", correct_minus)
