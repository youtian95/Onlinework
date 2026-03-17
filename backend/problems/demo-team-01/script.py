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


def check(params, answers):
    results = {}

    try:
        results["alpha_answer"] = int(answers.get("alpha_answer", "")) == (params["x"] + params["y"])
    except Exception:
        results["alpha_answer"] = False

    try:
        results["beta_answer"] = int(answers.get("beta_answer", "")) == (params["m"] * params["n"])
    except Exception:
        results["beta_answer"] = False

    try:
        results["gamma_answer"] = int(answers.get("gamma_answer", "")) == (params["p"] - params["q"])
    except Exception:
        results["gamma_answer"] = False

    return results
