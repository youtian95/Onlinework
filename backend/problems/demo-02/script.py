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

def check(params, answers):
    results = {}
    
    # 1. Math
    try:
        user_math = int(answers.get('ans_math', '').strip())
        correct_math = params['a'] * params['b'] + params['c']
        results['ans_math'] = (user_math == correct_math)
    except:
        results['ans_math'] = False
        
    # 2. English
    user_eng = answers.get('ans_english', '').strip().lower()
    results['ans_english'] = (user_eng == 'apples')
    
    # 3. Logic (Fibonacci)
    # 1,1,2,3,5,8 -> 13
    user_logic = answers.get('ans_logic', '').strip()
    results['ans_logic'] = (user_logic == '13')
    
    # 4. History
    user_hist = answers.get('ans_history', '').strip().upper()
    results['ans_history'] = (user_hist == 'B')
    
    return results
