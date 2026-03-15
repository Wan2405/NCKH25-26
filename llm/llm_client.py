"""
llm_client.py

Mục đích:
    Giao tiếp với Ollama (chạy Llama 3.1 local) để sinh code Java sửa lỗi.

Cách hoạt động:
    1. Nhận code lỗi + thông tin phân tích lỗi
    2. Tạo prompt yêu cầu LLM sửa
    3. Gọi API Ollama và parse JSON response
    4. Trả về code đã sửa

Lưu ý:
    - Ollama phải đang chạy trên máy local (port 11434)
    - Cần pull model llama3.1 trước: ollama pull llama3.1
    - Có cơ chế retry nếu gọi API thất bại
"""

from __future__ import annotations

import json
import logging
import time

import requests

from llm.code_sanitizer import sanitize_java_code

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Gửi prompt đến Ollama và parse JSON response.
    
    Tham số:
        base_url: URL API Ollama, mặc định http://localhost:11434
        model: Tên model, mặc định llama3.1
        max_retries: Số lần thử lại nếu gọi API lỗi
    """

    _DEFAULT_BASE_URL = "http://localhost:11434"
    _DEFAULT_MODEL = "llama3.1"

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
        max_retries: int = 3,
    ) -> None:
        self.generate_url = base_url.rstrip("/") + "/api/generate"
        self.model = model
        self.max_retries = max_retries

    # === Hàm công khai ===

    def generate_fix(
        self,
        student_code: str,
        error_analysis: dict,
        problem_description: str = "",
    ) -> dict:
        """
        Yêu cầu LLM sinh code đã sửa từ code lỗi.
        
        Tham số:
            student_code: Code Java của sinh viên (có lỗi)
            error_analysis: Dict chứa loại lỗi và nguyên nhân
            problem_description: Đề bài (nếu có)
        
        Trả về:
            Dict với fixed_code và explanation.
            Nếu LLM không phản hồi, trả về dict rỗng.
        """
        prompt = self._build_prompt(student_code, error_analysis, problem_description)

        for attempt in range(1, self.max_retries + 1):
            backoff = 2 ** (attempt - 1)
            try:
                logger.info(
                    "LLM generate_fix attempt %d/%d", attempt, self.max_retries
                )
                response = requests.post(
                    self.generate_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "format": "json",
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 1500},
                    },
                    timeout=120,
                )
                response.raise_for_status()
                payload = response.json()
                parsed = json.loads(payload.get("response", "{}"))
                if parsed.get("fixed_code", "").strip():
                    parsed["fixed_code"] = sanitize_java_code(
                        parsed["fixed_code"]
                    )
                    return parsed
                logger.warning(
                    "LLM returned empty fixed_code, retrying in %ds", backoff
                )
            except requests.ConnectionError:
                logger.warning("Ollama not reachable, retry in %ds", backoff)
            except requests.Timeout:
                logger.warning("Ollama request timed out, retry in %ds", backoff)
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Bad LLM response: %s, retry in %ds", exc, backoff)
            except Exception as exc:
                logger.error("Unexpected LLM error: %s", exc)
            time.sleep(backoff)

        return {"fixed_code": "", "explanation": "LLM unavailable after retries"}

    # === Hàm nội bộ ===

    def _build_prompt(
        self, code: str, error_analysis: dict, problem_description: str
    ) -> str:
        loai_loi = error_analysis.get("loai_loi", "Unknown")
        nguyen_nhan = error_analysis.get("nguyen_nhan", "Unknown")
        chi_tiet = error_analysis.get("chi_tiet", "")
        if isinstance(chi_tiet, list):
            chi_tiet = "\n".join(chi_tiet)

        code_snippet = code if len(code) <= 3000 else code[:3000]

        return (
            "You are a Java expert. A student's code has a bug. Fix it.\n\n"
            f"PROBLEM:\n{problem_description or 'Java exercise'}\n\n"
            f"STUDENT CODE:\n{code_snippet}\n\n"
            f"ERROR TYPE: {loai_loi}\n"
            f"REASON: {nguyen_nhan}\n"
            f"DETAILS: {str(chi_tiet)[:500]}\n\n"
            "IMPORTANT: Return the complete fixed Java source code. "
            "Do NOT wrap the code in markdown fences (no ```java). "
            "Do NOT change the public class name.\n\n"
            'Return JSON only: {"fixed_code": "...", "explanation": "...", "reasoning": "..."}'
        )
