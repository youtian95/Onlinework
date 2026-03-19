from typing import Any, Dict, Optional


class NumericCheckTemplate:
    """Reusable helper for fill-in numeric problem checks.

    - Define one method per input id, e.g. `def ans_1(self): ...`
    - Use normal Python arithmetic in that method
    - Any parse/calculation error in that method is caught and that input is marked False
    """

    def __init__(self, params: Dict[str, Any], user_answers: Dict[str, Any], default_tol: float = 5e-2):
        self.params = params or {}
        self.user_answers = user_answers or {}
        self.default_tol = default_tol
        self.results: Dict[str, bool] = {}

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_close(user_value: Optional[float], correct_value: Optional[float], tol: float) -> bool:
        if user_value is None or correct_value is None:
            return False
        scale = max(abs(correct_value), 1.0)
        return abs(user_value - correct_value) <= tol * scale

    def parse_float(self, key: str) -> float:
        num = self._to_float(self.user_answers.get(key))
        if num is None:
            raise ValueError(f"Invalid float answer for {key}")
        return num

    def parse_int(self, key: str) -> int:
        num = self._to_float(self.user_answers.get(key))
        if num is None:
            raise ValueError(f"Invalid int answer for {key}")
        if abs(num - int(num)) > 1e-9:
            raise ValueError(f"Non-integer answer for {key}")
        return int(num)

    def text(self, key: str) -> str:
        value = self.user_answers.get(key)
        if value is None:
            raise ValueError(f"Missing text answer for {key}")
        text = str(value).strip()
        if text == "":
            raise ValueError(f"Empty text answer for {key}")
        return text

    def is_close(self, key: str, correct_value: float, tol: Optional[float] = None) -> bool:
        user_value = self.parse_float(key)
        use_tol = self.default_tol if tol is None else tol
        return self._is_close(user_value, correct_value, use_tol)

    def is_int_equal(self, key: str, expected: int) -> bool:
        return self.parse_int(key) == expected

    def is_int_range(self, key: str, low: int, high: int) -> bool:
        user_value = self.parse_int(key)
        return low <= user_value <= high

    def run(self) -> Dict[str, bool]:
        for name, attr in self.__class__.__dict__.items():
            if name.startswith("_") or name == "run":
                continue
            if not callable(attr):
                continue
            try:
                self.results[name] = bool(getattr(self, name)())
            except Exception:
                self.results[name] = False
        return dict(self.results)
