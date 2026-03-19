from backend.services.problem_check_template import NumericCheckTemplate


meta = {
    "title": "综合能力测试 (Math/English/Logic)",
    "inputs": {
        "ans_math": {"max_attempts": 3, "score": 20},
        "ans_english": {"max_attempts": 5, "score": 20},
        "ans_logic": {"max_attempts": 3, "score": 30},
        "ans_history": {"max_attempts": 1, "score": 30},
    }
}

def generate(rng):
    return {
        "a": rng.randint(2, 9),
        "b": rng.randint(10, 20),
        "c": rng.randint(1, 100)
    }

class Demo03Checker(NumericCheckTemplate):
    def ans_math(self):
        correct_math = self.params["a"] * self.params["b"] + self.params["c"]
        return self.is_int_equal("ans_math", correct_math)

    def ans_english(self):
        return self.text("ans_english").lower() == "apples"

    def ans_logic(self):
        return self.text("ans_logic") == "13"

    def ans_history(self):
        return self.text("ans_history").upper() == "B"
