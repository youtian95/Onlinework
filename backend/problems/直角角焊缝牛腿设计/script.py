meta = {
    "title": "直角角焊缝牛腿连接设计"
}

def generate(rng):
    
    V = 225 + rng.randint(0, 50)*4
    return {
        "V": V
    }

def check(params, user_answers):

    tol = 5e-2

    # 弯矩计算
    correct_ans_M = params["V"] * 320
    user_val_M = float(user_answers.get("ans_M"))
    bool_M = abs(user_val_M - correct_ans_M) < tol * correct_ans_M

    # ans_h_min
    correct_ans_h_min = 8
    user_val_h_min = int(user_answers.get("ans_h_min"))
    bool_h_min = user_val_h_min == correct_ans_h_min

    # ans_h_max
    correct_ans_h_max = 12
    user_val_h_max = int(user_answers.get("ans_h_max"))
    bool_h_max = user_val_h_max == correct_ans_h_max

    # ans_f_fw
    correct_ans_f_fw = 200
    user_val_f_fw = int(user_answers.get("ans_f_fw"))
    bool_f_fw = user_val_f_fw == correct_ans_f_fw

    # ans_h
    user_val_h = int(user_answers.get("ans_h"))
    bool_h = user_val_h>=correct_ans_h_min and user_val_h<=correct_ans_h_max

    # ans_A_w
    correct_ans_A_w = 2 * 0.7 * 360 * user_val_h
    user_val_A_w = float(user_answers.get("ans_A_w"))
    bool_A_w = abs(user_val_A_w - correct_ans_A_w) < tol * correct_ans_A_w

    # ans_I_x
    # =2*0.7*A11*200*(200+0.7*A11/2)^2+4*0.7*A11*(200/2-10/2-0.7*A11)*(360/2-0.7*A11/2)^2+2*1/12*0.7*A11*360^3
    correct_ans_I_x = 2*0.7*200*user_val_h*(200+0.7*user_val_h/2)**2 + 4*0.7*user_val_h*(200/2-10/2-0.7*user_val_h)*(360/2-0.7*user_val_h/2)**2 + 2*(1/12)*0.7*user_val_h*360**3
    user_val_I_x = float(user_answers.get("ans_I_x"))
    bool_I_x = abs(user_val_I_x - correct_ans_I_x) < tol * correct_ans_I_x

    # ans_sigma_f =B5/B13*(360+20*2+2*0.7*A11)/2
    correct_ans_sigma_f = correct_ans_M / correct_ans_I_x * (360 + 20 * 2 + 2 * 0.7 * user_val_h) / 2
    user_val_sigma_f = float(user_answers.get("ans_sigma_f"))
    bool_sigma_f = abs(user_val_sigma_f - correct_ans_sigma_f) < tol * correct_ans_sigma_f

    # ans_tau_f =A5/A13
    correct_ans_tau_f = params["V"]*1000 / correct_ans_A_w
    user_val_tau_f = float(user_answers.get("ans_tau_f"))
    bool_tau_f = abs(user_val_tau_f - correct_ans_tau_f) < tol * correct_ans_tau_f

    # ans_sigma_f_prime=B5/B13*360/2
    correct_ans_sigma_f_prime = correct_ans_M / correct_ans_I_x * 360 / 2
    user_val_sigma_f_prime = float(user_answers.get("ans_sigma_f_prime"))
    bool_sigma_f_prime = abs(user_val_sigma_f_prime - correct_ans_sigma_f_prime) < tol * correct_ans_sigma_f_prime
    
    # ans_combined_stress = sqrt((sigma_f'/beta_f)^2 + tau_f^2)
    beta_f = 1.22
    correct_ans_combined_stress = ((correct_ans_sigma_f_prime / beta_f)**2 + correct_ans_tau_f**2)**0.5
    user_val_combined_stress = float(user_answers.get("ans_combined_stress"))
    bool_combined_stress = abs(user_val_combined_stress - correct_ans_combined_stress) < tol * correct_ans_combined_stress

    # 返回校验结果
    return {
        "ans_M": bool_M,
        "ans_h_min": bool_h_min,
        "ans_h_max": bool_h_max,
        "ans_f_fw": bool_f_fw,
        "ans_h": bool_h,
        "ans_A_w": bool_A_w,
        "ans_I_x": bool_I_x,
        "ans_sigma_f": bool_sigma_f,
        "ans_tau_f": bool_tau_f,
        "ans_sigma_f_prime": bool_sigma_f_prime,
        "ans_combined_stress": bool_combined_stress
    }
