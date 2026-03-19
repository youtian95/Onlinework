from backend.services.problem_check_template import NumericCheckTemplate


meta = {
    "title": "团队作业 Demo 01",
    "teamwork": {
        "team_count": 10,
        "team_size": 3
    }
}


def generate(rng):
    x = rng.randint(10, 99)
    y = rng.randint(10, 99)
    m = rng.randint(2, 9)
    n = rng.randint(2, 9)
    p = rng.randint(1, 20)
    q = rng.randint(1, 20)

    return {
        "x": x,
        "y": y,
        "m": m,
        "n": n,
        "p": p,
        "q": q,
    }


class DemoTeam01Checker(NumericCheckTemplate):
    def alpha_answer(self):
        return self.is_int_equal("alpha_answer", self.params["x"] + self.params["y"])

    def beta_answer(self):
        return self.is_int_equal("beta_answer", self.params["m"] * self.params["n"])

    def gamma_answer(self):
        return self.is_int_equal("gamma_answer", self.params["p"] - self.params["q"])
