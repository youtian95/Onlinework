from backend.services.problem_check_template import NumericCheckTemplate
from civil_toolkit import materials, phi_interpolation, hot_rolled_i, hot_rolled_h, section_category, local_stability
from typing import List, Optional

meta = {
    "title": "Demo - 轴心受压构件设计"
}

def generate(rng):
    
    H = 6000 + rng.randint(0, 80)*3*50
    N = 800 + rng.randint(0, 80)*3

    return {
        "H": H,
        "N": N
    }


class MyChecker(NumericCheckTemplate):
    tol = 2e-2

    def ans_3_H_sec(self):
        # H型钢型号是否存在
        correct_ans: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        return correct_ans
    
    def ans_3_Q(self):
        # 选择钢材牌号是否存在
        return self.text("ans_3_Q") in materials.get_supported_steel_grades()
    
    def _ans_3_f(self):
        # 钢材强度设计值
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        correct_ans = materials.get_steel_strength(self.text("ans_3_Q"), max(h_sec.t1, h_sec.t2)).f_mpa
        return correct_ans
    def ans_3_f(self):
        correct_ans = self._ans_3_f()
        return self.is_close("ans_3_f", correct_ans, tol=self.tol)
    
    def _ans_3_lambda_x(self):
        # =H/i_x
        l = self.params["H"]
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        i_x = h_sec.ix * 10  # ix为cm，需乘以10化为mm
        correct_ans = l/i_x
        return correct_ans
    def ans_3_lambda_x(self):
        correct_ans = self._ans_3_lambda_x()
        return self.is_close("ans_3_lambda_x", correct_ans, tol=self.tol) and correct_ans <= 150
    
    def _ans_3_lambda_y(self):
        # =H/i_y
        l = self.params["H"]/2
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        i_y = h_sec.iy * 10  # iy为cm，需乘以10化为mm
        correct_ans = l/i_y
        return correct_ans
    def ans_3_lambda_y(self):
        correct_ans = self._ans_3_lambda_y()
        return self.is_close("ans_3_lambda_y", correct_ans, tol=self.tol) and correct_ans <= 150
    
    def _ans_3_section_category_x(self):
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        b = h_sec.B
        h = h_sec.H
        tf = h_sec.t2
        cat_x, cat_y = section_category.get_hot_rolled_h_section_category(h, b, tf, self.text("ans_3_Q"))
        return cat_x
    def ans_3_section_category_x(self):
        correct_ans = self._ans_3_section_category_x()
        return correct_ans == self.text("ans_3_section_category_x")
    
    def _ans_3_section_category_y(self):
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        b = h_sec.B
        h = h_sec.H
        tf = h_sec.t2
        cat_x, cat_y = section_category.get_hot_rolled_h_section_category(h, b, tf, self.text("ans_3_Q"))
        return cat_y
    def ans_3_section_category_y(self):
        correct_ans = self._ans_3_section_category_y()
        return correct_ans == self.text("ans_3_section_category_y")
    
    def _ans_3_phi_x(self):
        # 稳定系数
        h_sec = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        fy = materials.get_steel_strength(self.text("ans_3_Q"), max(h_sec.t1, h_sec.t2)).fy_mpa
        phi_x = phi_interpolation.get_phi(self._ans_3_section_category_x(), self._ans_3_lambda_x(), fy=fy)
        correct_ans = phi_x
        return correct_ans
    def ans_3_phi_x(self):        
        correct_ans = self._ans_3_phi_x()
        return self.is_close("ans_3_phi_x", correct_ans, tol=self.tol)
    
    def _ans_3_phi_y(self):
        # 稳定系数
        h_sec = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        fy = materials.get_steel_strength(self.text("ans_3_Q"), max(h_sec.t1, h_sec.t2)).fy_mpa
        phi_y = phi_interpolation.get_phi(self._ans_3_section_category_y(), self._ans_3_lambda_y(), fy=fy)
        correct_ans = phi_y
        return correct_ans
    def ans_3_phi_y(self):
        correct_ans = self._ans_3_phi_y()
        return self.is_close("ans_3_phi_y", correct_ans, tol=self.tol)
    
    def _ans_3_stability_check_x(self):
        # 稳定验算
        f = self._ans_3_f()
        N = self.params["N"] * 1000  # N转换成牛顿
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        A = h_sec.area * 100  # area单位为cm2，转换成mm2
        phi_x = self._ans_3_phi_x()
        correct_ans = N / (phi_x * f * A)
        return correct_ans
    def ans_3_stability_check_x(self):
        correct_ans = self._ans_3_stability_check_x()
        return self.is_close("ans_3_stability_check_x", correct_ans, tol=self.tol) and correct_ans <= 1.0
    
    def _ans_3_stability_check_y(self):
        # 稳定验算
        f = self._ans_3_f()
        N = self.params["N"] * 1000  # N转换成牛顿
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        A = h_sec.area * 100  # area单位为cm2，转换成mm2
        phi_y = self._ans_3_phi_y()
        correct_ans = N / (phi_y * f * A)
        return correct_ans
    def ans_3_stability_check_y(self):
        correct_ans = self._ans_3_stability_check_y()
        return self.is_close("ans_3_stability_check_y", correct_ans, tol=self.tol) and correct_ans <= 1.0
    
    def ans_3_b1_to_t(self):
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        b1 = (h_sec.B - h_sec.t1) / 2
        tf = h_sec.t2
        correct_ans = b1/tf
        return self.is_close("ans_3_b1_to_t", correct_ans, tol=self.tol)
    
    def ans_3_b1_to_t_limit(self):
        lambda_max = max(self._ans_3_lambda_x(), self._ans_3_lambda_y())
        h_sec = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        fy = materials.get_steel_strength(self.text("ans_3_Q"), max(h_sec.t1, h_sec.t2)).fy_mpa
        correct_ans = local_stability.get_axial_comp_h_section_flange_limit(lambda_max, fy)
        print(f"lambda_max: {lambda_max}, fy: {fy}, limit: {correct_ans}")
        return self.is_close("ans_3_b1_to_t_limit", correct_ans, tol=self.tol)
    
    def ans_3_h_to_t(self):
        h_sec: Optional[hot_rolled_h.HSection] = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        h = h_sec.H
        tf = h_sec.t2
        tw = h_sec.t1
        r = h_sec.r
        correct_ans = (h - 2*tf - 2*r) / tw
        return self.is_close("ans_3_h_to_t", correct_ans, tol=self.tol)
    
    def ans_3_h_to_t_limit(self):
        lambda_max = max(self._ans_3_lambda_x(), self._ans_3_lambda_y())
        h_sec = hot_rolled_h.find_h_sections_by_model(self.text("ans_3_H_sec"))
        fy = materials.get_steel_strength(self.text("ans_3_Q"), max(h_sec.t1, h_sec.t2)).fy_mpa
        correct_ans = local_stability.get_axial_comp_h_section_web_limit(lambda_max, fy)
        return self.is_close("ans_3_h_to_t_limit", correct_ans, tol=self.tol)
    
