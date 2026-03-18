# Chi Tiết Triển Khai – NCKH25-26

> **Đối tượng:** Sinh viên muốn hiểu sâu về code Python, không chỉ ý tưởng tổng quát.
> **Ngôn ngữ:** Tiếng Việt – giải thích đơn giản, từng dòng, từng hàm.

---

## Mục Lục

1. [Tư Duy Phát Triển Dự Án](#1-tư-duy-phát-triển-dự-án)
2. [Imports & Thư Viện](#2-imports--thư-viện)
3. [Giải Thích Từng File](#3-giải-thích-từng-file)
4. [Giải Thích Từng Hàm](#4-giải-thích-từng-hàm)
5. [Cách Các Hàm Kết Nối Nhau](#5-cách-các-hàm-kết-nối-nhau)
6. [Luồng Thực Thi Thực Tế](#6-luồng-thực-thi-thực-tế)
7. [Các Khái Niệm Python Quan Trọng](#7-các-khái-niệm-python-quan-trọng)
8. [Giải Thích Như Đang Dạy Sinh Viên](#8-giải-thích-như-đang-dạy-sinh-viên)

---

## 1. Tư Duy Phát Triển Dự Án

### Từ ý tưởng đến code

**Ý tưởng ban đầu:**
> "Làm sao để tự động sửa code Java bị lỗi mà không cần người dùng can thiệp?"

**Quá trình thiết kế:**

```
Ý tưởng
   ↓
Xác định bài toán:
  - Input: code Java có lỗi
  - Output: code Java đã sửa (pass test)
   ↓
Phân tích các bước cần thiết:
  1. Cần chạy test để biết lỗi gì  → Docker + Maven
  2. Cần đọc kết quả test           → LogProcessor
  3. Cần hiểu lỗi gì                → ErrorClassifier
  4. Cần sinh code mới              → LLM (Ollama/Llama 3.1)
  5. Cần làm sạch code LLM trả về  → CodeSanitizer
  6. Cần lặp lại cho đến khi đúng  → LoopOrchestrator
   ↓
Thiết kế module:
  - Mỗi bước = 1 module riêng biệt
  - Dễ thay thế, dễ test từng phần
   ↓
Viết code từng module
   ↓
Kết nối module qua LoopOrchestrator
   ↓
Tạo entry point (run_feedback_loop.py)
```

### Tại sao cấu trúc này?

| Thư mục | Lý do tách riêng |
|---------|-----------------|
| `core/` | Điều khiển trung tâm – thay đổi ít nhất |
| `llm/` | Logic LLM – dễ hoán đổi model khác |
| `execution/` | Tầng adapter – cách ly chi tiết kỹ thuật |
| `auto_grader/modules/` | Các module cụ thể – tái sử dụng độc lập |

**Nguyên tắc:** Mỗi file chỉ làm **một việc**. Ví dụ: `code_sanitizer.py` chỉ làm sạch code, không làm gì khác.

---

## 2. Imports & Thư Viện

### 2.1. `run_feedback_loop.py`

```python
from __future__ import annotations   # (1)
import argparse                       # (2)
import logging                        # (3)
import os                             # (4)
import re                             # (5)
import sys                            # (6)

from core.docker_manager import DockerManager        # (7)
from core.loop_orchestrator import LoopOrchestrator  # (8)
from execution.log_processor import LogProcessor     # (9)
from execution.error_classifier import ErrorClassifier  # (10)
from llm.llm_client import LLMClient                 # (11)
```

| # | Import | Loại | Tác dụng trong dự án |
|---|--------|------|----------------------|
| 1 | `from __future__ import annotations` | Built-in | Cho phép dùng type hint như `str \| None` trên Python < 3.10 |
| 2 | `argparse` | Built-in | Xử lý tham số dòng lệnh: `--workspace`, `--max-rounds` |
| 3 | `logging` | Built-in | Ghi log thông tin debug ra console/file |
| 4 | `os` | Built-in | Làm việc với đường dẫn file, thư mục |
| 5 | `re` | Built-in | Regex – tìm tên class trong code Java (`public class Xyz`) |
| 6 | `sys` | Built-in | Thao tác với `sys.path` để tìm module, và `sys.exit()` |
| 7–11 | Các module nội bộ | Internal | Các thành phần của hệ thống (xem chi tiết ở phần sau) |

---

### 2.2. `core/docker_manager.py`

```python
from __future__ import annotations
import logging
import os
import docker                                                    # (1) – EXTERNAL
from docker.errors import APIError, DockerException, ImageNotFound  # (2)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `docker` | **External** (`pip install docker`) | Python Docker SDK – tạo/chạy/xóa container bằng code Python, không cần gọi lệnh `docker run` trên terminal |
| 2 | `docker.errors.*` | External (cùng gói docker) | Các loại exception của Docker: `ImageNotFound` khi image chưa build, `DockerException` khi Docker daemon không chạy |

> **Tại sao dùng Python Docker SDK thay vì `subprocess.run("docker run ...")`?**
> Vì SDK cho phép kiểm soát chi tiết hơn: đặt giới hạn RAM/CPU, đọc log trực tiếp, xóa container tự động – tất cả trong cùng một đoạn code.

---

### 2.3. `core/loop_orchestrator.py`

```python
from __future__ import annotations
import json                           # (1)
import logging                        # (2)
from datetime import datetime         # (3)
from pathlib import Path              # (4)
from typing import TYPE_CHECKING      # (5)
from llm.code_sanitizer import sanitize_java_code  # (6)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `json` | Built-in | Lưu lịch sử vòng lặp ra file `.json` |
| 2 | `logging` | Built-in | Ghi log debug |
| 3 | `datetime` | Built-in | Lấy timestamp cho tên file output |
| 4 | `pathlib.Path` | Built-in | Làm việc với đường dẫn file theo kiểu hướng đối tượng (dễ hơn `os.path`) |
| 5 | `typing.TYPE_CHECKING` | Built-in | Chỉ import type annotation khi check type, không import lúc runtime (tránh circular import) |
| 6 | `sanitize_java_code` | Internal | Làm sạch code Java từ LLM trước khi lưu vào workspace |

---

### 2.4. `llm/llm_client.py`

```python
from __future__ import annotations
import json         # (1)
import logging      # (2)
import time         # (3)
import requests     # (4) – EXTERNAL
from llm.code_sanitizer import sanitize_java_code  # (5)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `json` | Built-in | Parse JSON response từ Ollama API |
| 2 | `logging` | Built-in | Ghi log các lần retry |
| 3 | `time` | Built-in | `time.sleep(backoff)` – dừng chờ trước khi retry |
| 4 | `requests` | **External** (`pip install requests`) | Gửi HTTP POST đến Ollama API (`http://localhost:11434/api/generate`) |
| 5 | `sanitize_java_code` | Internal | Làm sạch code mà LLM trả về |

> **`requests` là gì?** Giống như bạn dùng trình duyệt để gửi yêu cầu đến một website và nhận kết quả về. `requests.post(url, json=data)` làm điều đó trong code Python.

---

### 2.5. `llm/code_sanitizer.py`

```python
from __future__ import annotations
import logging   # (1)
import re        # (2)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `logging` | Built-in | Cảnh báo khi code sau khi làm sạch không còn từ khóa `class` |
| 2 | `re` | Built-in | Regex – tìm và xóa markdown fence (` ```java `), tìm `public class`, xóa text thừa |

---

### 2.6. `llm/patch_applier.py`

```python
from __future__ import annotations
import logging   # (1)
import re        # (2)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `logging` | Built-in | Cảnh báo khi patch không áp dụng được |
| 2 | `re` | Built-in | Parse hunk header (`@@ -1,3 +1,5 @@`) trong unified diff |

---

### 2.7. `execution/log_processor.py`

```python
from __future__ import annotations
import logging    # (1)
import os         # (2)
import tempfile   # (3)
from auto_grader.modules.log_processor import LogProcessor as _LogProcessor  # (4)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `logging` | Built-in | Ghi log |
| 2 | `os` | Built-in | `os.unlink()` – xóa file tạm sau khi xử lý xong |
| 3 | `tempfile` | Built-in | Tạo file tạm để lưu log string trước khi xử lý |
| 4 | `_LogProcessor` | Internal | LogProcessor gốc – logic thực sự nằm ở đây |

> **`tempfile` là gì?** Module tạo file tạm thời, tự động đặt tên ngẫu nhiên, thường dùng khi cần xử lý dữ liệu tạm mà không muốn giữ lại.

---

### 2.8. `auto_grader/modules/log_processor.py`

```python
import re                       # (1)
import json                     # (2)
from datetime import datetime   # (3)
from pathlib import Path        # (4)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `re` | Built-in | Regex – nhận diện các pattern lỗi trong log Maven |
| 2 | `json` | Built-in | Lưu kết quả phân tích log ra file JSON |
| 3 | `datetime` | Built-in | Tạo timestamp cho metadata |
| 4 | `pathlib.Path` | Built-in | Quản lý đường dẫn thư mục output |

---

### 2.9. `auto_grader/modules/error_classifier.py`

```python
import requests    # (1) – EXTERNAL
import json        # (2)
import re          # (3)
import time        # (4)
from pathlib import Path  # (5)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `requests` | External | Gọi Ollama API để LLM phân tích lỗi chi tiết |
| 2 | `json` | Built-in | Parse JSON từ LLM, lưu kết quả |
| 3 | `re` | Built-in | Regex quick-classify (nhanh hơn gọi LLM) |
| 4 | `time` | Built-in | `time.sleep()` cho exponential backoff khi retry |
| 5 | `pathlib.Path` | Built-in | Quản lý thư mục output |

---

### 2.10. `auto_grader/modules/feedback_generator.py`

```python
import requests                           # (1) – EXTERNAL
import json                               # (2)
import os                                 # (3)
import sys                                # (4)
import time                               # (5)
from pathlib import Path                  # (6)
from datetime import datetime             # (7)
from llm.code_sanitizer import sanitize_java_code  # (8)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 1 | `requests` | External | Gọi API Ollama để sinh gợi ý sửa lỗi |
| 2 | `json` | Built-in | Parse/lưu JSON |
| 3 | `os` | Built-in | Không dùng trực tiếp; giữ cho tương thích |
| 4 | `sys` | Built-in | Thêm thư mục gốc vào `sys.path` |
| 5 | `time` | Built-in | Exponential backoff khi retry |
| 6 | `pathlib.Path` | Built-in | Quản lý đường dẫn output |
| 7 | `datetime` | Built-in | Timestamp khi tạo feedback |
| 8 | `sanitize_java_code` | Internal | Làm sạch code từ LLM |

---

### 2.11. `auto_grader/modules/auto_fixer.py`

```python
import json                                               # (1)
import re                                                 # (2)
import sys                                                # (3)
import os                                                 # (4)
from datetime import datetime                             # (5)
from pathlib import Path                                  # (6)
from .log_processor import LogProcessor                   # (7)
from .error_classifier import ErrorClassifier             # (8)
from .feedback_generator import FeedbackGenerator         # (9)
from llm.code_sanitizer import sanitize_java_code         # (10)
```

| # | Import | Loại | Tác dụng |
|---|--------|------|----------|
| 7–9 | Module nội bộ (relative import) | Internal | Import tương đối trong cùng package `auto_grader/modules/` |
| 10 | `sanitize_java_code` | Internal | Làm sạch code sau khi LLM sửa |

---

### 2.12. `auto_grader/docker/run_in_docker.py`

```python
from __future__ import annotations
import logging
import os
import docker                                              # (1) – EXTERNAL
from docker.errors import DockerException, ImageNotFound  # (2)
```

Tương tự `docker_manager.py` – dùng Python Docker SDK để quản lý container.

---

### Tóm tắt thư viện External (cần `pip install`)

| Thư viện | Phiên bản | Tác dụng |
|----------|-----------|----------|
| `requests` | 2.31.0 | Gọi HTTP API (Ollama) |
| `docker` | 7.1.0 | Quản lý Docker container từ Python |
| `python-dotenv` | 1.0.0 | Đọc biến môi trường từ file `.env` (tùy chọn) |

---

## 3. Giải Thích Từng File

### `run_feedback_loop.py` – Điểm vào chính

**Mục đích:** File duy nhất người dùng cần gọi trực tiếp:

```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 3
```

**Cấu trúc:**
- 3 hàm tiện ích nhỏ (`_find_java_source`, `_load_code`, `_extract_class_name`)
- 1 hàm `main()` làm tất cả: đọc tham số → tìm file Java → khởi tạo các module → chạy orchestrator → in kết quả

---

### `core/loop_orchestrator.py` – Não bộ của hệ thống

**Mục đích:** Điều khiển vòng lặp sửa lỗi. Biết khi nào dừng, khi nào gọi LLM.

**Class:** `LoopOrchestrator`

- Nhận tất cả module khác qua constructor (Dependency Injection)
- Method `run()` là vòng lặp chính

---

### `core/docker_manager.py` – Quản lý Docker

**Mục đích:** Tạo container, chạy `mvn clean test`, lấy log, xóa container.

**Class:** `DockerManager`

- Dùng lazy initialization cho Docker client (chỉ kết nối Docker khi cần)

---

### `llm/llm_client.py` – Giao tiếp với AI

**Mục đích:** Gửi prompt đến Ollama API và nhận code đã sửa.

**Class:** `LLMClient`

- Tự động retry nếu Ollama chưa sẵn sàng
- Dùng `temperature=0.3` (ít ngẫu nhiên) để code ổn định hơn

---

### `llm/code_sanitizer.py` – Làm sạch code AI

**Mục đích:** LLM hay trả về code bị "bẩn" (có markdown, có text giải thích). File này dọn sạch trước khi compile.

**Pipeline hàm:** `strip_markdown_fences` → `strip_preamble` → `keep_only_first_class` → `enforce_class_name` → `sanitize_java_code` (gọi tất cả theo thứ tự)

---

### `llm/patch_applier.py` – Áp dụng patch

**Mục đích:** Nếu LLM trả về diff thay vì code đầy đủ, file này áp dụng patch đó.

**Lưu ý:** Không bắt buộc trong pipeline chính; là tính năng phụ trợ.

---

### `execution/log_processor.py` – Adapter layer

**Mục đích:** Cầu nối giữa `LoopOrchestrator` (dùng string) và `auto_grader.modules.LogProcessor` (đọc file).

**Cách hoạt động:** Lưu string vào file tạm → gọi LogProcessor gốc → xóa file tạm.

---

### `execution/error_classifier.py` – Re-export

**Mục đích:** Chỉ re-export `ErrorClassifier` từ `auto_grader.modules`. Không có logic riêng.

---

### `execution/runner.py` – Wrapper đơn giản

**Mục đích:** Hàm `run_tests()` gọi `docker_manager.compile_and_test()`. Đơn giản hóa code ở nơi gọi.

---

### `auto_grader/modules/log_processor.py` – Phân tích log

**Mục đích:** Đọc log Maven thô và chuyển thành dict Python có cấu trúc.

**Kết quả trả về:**

```python
{
  "metadata": {"timestamp": "...", "student_id": "...", ...},
  "execution": {"exit_code": 0, "error_type": "COMPILE_ERROR", "error_detail": [...]},
  "test_results": {"total_tests": 5, "passed": 3, "failed": 2, ...},
  "raw_logs": {"stdout": "...", "stderr": "..."}
}
```

---

### `auto_grader/modules/error_classifier.py` – Phân loại lỗi

**Mục đích:** Xác định lỗi cụ thể là gì và gợi ý sửa.

**2 chiến lược:**
- **Regex** (nhanh): So khớp keyword → độ tin cậy 85–95%
- **LLM** (chính xác): Gọi Llama 3.1 khi regex không đủ tin cậy (< 0.8)

---

### `auto_grader/modules/feedback_generator.py` – Sinh gợi ý

**Mục đích:** Gọi LLM sinh code đã sửa + giải thích lỗi + lý do sửa.

**Output:** Lưu ra cả `.json` và `.md` trong `auto_grader/output/feedback/`.

---

### `auto_grader/modules/auto_fixer.py` – Orchestrator cũ

**Mục đích:** Phiên bản orchestrator cũ hơn. Không phải pipeline chính; dùng `run_feedback_loop.py` thay thế. Có thể dùng độc lập để test.

---

### `auto_grader/modules/executor.py` – Tiện ích đơn giản

**Mục đích:** Chỉ có một hàm `extract_class_name()` – trích xuất tên class từ code Java.

---

### `auto_grader/modules/code_generator.py` – Sinh code từ đề bài

**Mục đích:** Dùng LLM để sinh code Java từ mô tả bài tập (để test hoặc tạo code mẫu).

---

### `auto_grader/docker/run_in_docker.py` – Docker runner thay thế

**Mục đích:** DockerRunner dành cho `auto_fixer.py`. Có thêm tính năng build image tự động nếu chưa có.

---

## 4. Giải Thích Từng Hàm

### 4.1. `run_feedback_loop.py`

#### `_find_java_source(workspace: str) -> str | None`

```python
def _find_java_source(workspace: str) -> str | None:
    src_root = os.path.join(workspace, "src", "main", "java")  # (1)
    if not os.path.isdir(src_root):                            # (2)
        return None
    for dirpath, _, filenames in os.walk(src_root):            # (3)
        for fname in filenames:                                 # (4)
            if fname.endswith(".java"):                         # (5)
                return os.path.join(dirpath, fname)            # (6)
    return None
```

- **Mục đích:** Tìm file `.java` đầu tiên trong cây thư mục `src/main/java/`
- **Input:** `workspace` – đường dẫn thư mục project
- **Output:** đường dẫn đầy đủ đến file `.java`, hoặc `None` nếu không tìm thấy
- **Giải thích từng dòng:**
  1. Ghép đường dẫn đến thư mục `src/main/java`
  2. Nếu thư mục không tồn tại → trả về `None`
  3. `os.walk()` duyệt đệ quy toàn bộ thư mục con (trả về `dirpath`, danh sách thư mục con `_`, danh sách file)
  4–5. Với mỗi file, kiểm tra có phần mở rộng `.java` không
  6. Trả về ngay file đầu tiên tìm được

---

#### `_extract_class_name(code: str) -> str`

```python
def _extract_class_name(code: str) -> str:
    m = re.search(r"public\s+class\s+(\w+)", code)  # (1)
    return m.group(1) if m else "Solution"           # (2)
```

- **Mục đích:** Tìm tên class public trong code Java
- **Input:** `code` – nội dung file Java dưới dạng string
- **Output:** tên class (ví dụ: `"Solution"`), hoặc `"Solution"` nếu không tìm thấy
- **Giải thích:**
  1. Regex `public\s+class\s+(\w+)` tìm pattern `public class TênGì`. `\s+` = một hoặc nhiều khoảng trắng. `(\w+)` = bắt nhóm tên class
  2. `m.group(1)` lấy phần bắt được trong ngoặc đơn `()`

---

#### `main(argv: list[str] | None = None) -> int`

```python
def main(argv=None):
    # Bước 1: Đọc tham số dòng lệnh
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--workspace", required=True, ...)
    parser.add_argument("--max-rounds", type=int, default=3, ...)
    args = parser.parse_args(argv)

    # Bước 2: Tìm và đọc file Java
    code_path = _find_java_source(args.workspace)
    initial_code = _load_code(code_path)
    class_name = _extract_class_name(initial_code)

    # Bước 3: Khởi tạo tất cả module
    docker_manager   = DockerManager()
    log_processor    = LogProcessor()
    error_classifier = ErrorClassifier(use_llm=True)
    llm_client       = LLMClient()

    # Bước 4: Tạo orchestrator, truyền tất cả module vào (Dependency Injection)
    orchestrator = LoopOrchestrator(
        docker_manager=docker_manager,
        log_processor=log_processor,
        error_classifier=error_classifier,
        llm_client=llm_client,
        workspace_path=args.workspace,
        max_rounds=args.max_rounds,
    )

    # Bước 5: Chạy vòng lặp và in kết quả
    result = orchestrator.run(initial_code=initial_code, class_name=class_name)
    return 0 if result["success"] else 1
```

- **Input:** `argv` – list tham số CLI (hoặc `None` để đọc từ `sys.argv`)
- **Output:** `0` (thành công) hoặc `1` (thất bại) – exit code cho shell
- **Mẫu khởi tạo:** Tất cả module được tạo ở đây và truyền vào `LoopOrchestrator`. Đây là **Dependency Injection**.

---

### 4.2. `core/loop_orchestrator.py`

#### `LoopOrchestrator.__init__(...)`

```python
def __init__(self, docker_manager, log_processor, error_classifier,
             llm_client, workspace_path="workspace", max_rounds=3,
             history_dir="auto_grader/output/auto_fix_history"):
    self.docker_manager  = docker_manager
    self.log_processor   = log_processor
    self.error_classifier = error_classifier
    self.llm_client      = llm_client
    self.workspace_path  = workspace_path
    self.max_rounds      = max_rounds
    self.history_dir     = Path(history_dir)
    self.history_dir.mkdir(parents=True, exist_ok=True)  # Tạo thư mục nếu chưa có
```

- `parents=True` – tạo cả thư mục cha nếu chưa tồn tại
- `exist_ok=True` – không báo lỗi nếu thư mục đã có

---

#### `LoopOrchestrator.run(initial_code, class_name, ...)`

**Đây là hàm quan trọng nhất của toàn bộ hệ thống.** Đây là vòng lặp chính:

```python
def run(self, initial_code, class_name="Solution", ...):
    current_code = initial_code   # Code hiện tại (thay đổi mỗi vòng)
    history = []                  # Lưu lịch sử từng vòng

    for round_num in range(1, self.max_rounds + 1):  # Vòng 1, 2, 3, ...

        # BƯỚC 1: Ghi code vào file .java trong workspace
        self._save_code(class_name, current_code)

        # BƯỚC 2: Chạy mvn clean test qua Docker → nhận log thô
        raw_log = self.docker_manager.compile_and_test(self.workspace_path)

        # BƯỚC 3: Phân tích log thô → dict có cấu trúc
        log_data = self.log_processor.process(raw_log, student_id)

        # BƯỚC 4: Phân loại lỗi → biết lỗi gì
        classification = self.error_classifier.classify(log_data)
        error_type = classification.get("loai_loi", "Unknown")

        history.append({...})

        # BƯỚC 5: Kiểm tra kết quả
        if error_type == "PASSED":
            return self._build_result(success=True, ...)  # DỪNG THÀNH CÔNG

        if round_num == self.max_rounds:
            break  # Hết số vòng

        # BƯỚC 6: Gọi LLM sinh code mới
        suggestion = self.llm_client.generate_fix(current_code, classification, ...)
        fixed_code = suggestion.get("fixed_code", "")

        # Làm sạch code từ LLM
        fixed_code   = sanitize_java_code(fixed_code, expected_class=class_name)
        current_code = fixed_code  # Cập nhật code cho vòng tiếp theo

    return self._build_result(success=False, ...)  # DỪNG THẤT BẠI
```

- **Input:** `initial_code` (string code Java), `class_name` (tên class)
- **Output:** dict `{"success": bool, "rounds": int, "final_code": str, "history": [...]}`

---

#### `LoopOrchestrator._save_code(class_name, code)`

```python
def _save_code(self, class_name: str, code: str) -> None:
    dest = (
        Path(self.workspace_path)
        / "src" / "main" / "java" / "com" / "example"
        / f"{class_name}.java"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(code, encoding="utf-8")
```

- **Mục đích:** Ghi code vào đúng vị trí Maven yêu cầu
- `Path / "folder"` là cách `pathlib` ghép đường dẫn (thay cho `os.path.join`)
- `dest.write_text()` viết string vào file, tự động mở và đóng file

---

### 4.3. `core/docker_manager.py`

#### `DockerManager.client` (property)

```python
@property
def client(self) -> docker.DockerClient:
    if self._client is None:              # Lần đầu gọi
        self._client = docker.from_env()  # Kết nối Docker daemon
    return self._client
```

- **Lazy initialization:** Chỉ kết nối Docker khi thực sự cần
- `docker.from_env()` tự động tìm Docker socket (Unix: `/var/run/docker.sock`)

---

#### `DockerManager.compile_and_test(workspace_path)`

```python
def compile_and_test(self, workspace_path: str) -> str:
    abs_path = os.path.abspath(workspace_path)     # (1) Đường dẫn tuyệt đối

    container = self.client.containers.create(     # (2) Tạo container (chưa chạy)
        self.image,
        command="mvn clean test --batch-mode",     # Lệnh sẽ chạy
        volumes={abs_path: {"bind": "/workspace", "mode": "rw"}},  # Mount thư mục
        working_dir="/workspace",
        mem_limit=self.memory_limit,               # Giới hạn RAM
        cpu_period=self.cpu_period,
        cpu_quota=self.cpu_quota,                  # Giới hạn CPU
        pids_limit=self.pids_limit,                # Giới hạn số process
    )
    try:
        container.start()                          # (3) Chạy container
        result = container.wait(timeout=180)       # (4) Đợi kết thúc
        logs = container.logs(stdout=True, stderr=True).decode("utf-8")  # (5) Lấy log
        exit_code = result.get("StatusCode", -1)
        return f"{logs}\n--- EXIT CODE: {exit_code} ---"  # (6) Trả về
    except Exception:
        logger.exception("Error while running container")
        raise
    finally:
        container.remove(force=True)               # (7) Luôn xóa container
```

- **`volumes`:** Ánh xạ thư mục trên máy host vào container.
- **`cpu_period/cpu_quota`:** Period=100 000µs, quota=100 000µs → 1 CPU; quota=50 000µs → 0.5 CPU.
- **`finally`:** Đảm bảo container luôn bị xóa dù có lỗi hay không.

---

### 4.4. `llm/llm_client.py`

#### `LLMClient.generate_fix(student_code, error_analysis, problem_description)`

```python
def generate_fix(self, student_code, error_analysis, problem_description=""):
    prompt = self._build_prompt(student_code, error_analysis, problem_description)

    for attempt in range(1, self.max_retries + 1):
        backoff = 2 ** (attempt - 1)   # 1s, 2s, 4s (exponential backoff)
        try:
            response = requests.post(
                self.generate_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "format": "json",    # Yêu cầu LLM trả về JSON
                    "stream": False,     # Không stream, đợi đến khi xong
                    "options": {"temperature": 0.3, "num_predict": 1500},
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            parsed  = json.loads(payload.get("response", "{}"))

            if parsed.get("fixed_code", "").strip():
                parsed["fixed_code"] = sanitize_java_code(parsed["fixed_code"])
                return parsed  # Thành công

        except requests.ConnectionError:
            logger.warning("Ollama not reachable, retry in %ds", backoff)
        except requests.Timeout:
            logger.warning("Ollama request timed out, retry in %ds", backoff)
        except json.JSONDecodeError as exc:
            logger.warning("Bad LLM response: %s, retry in %ds", exc, backoff)
        time.sleep(backoff)

    return {"fixed_code": "", "explanation": "LLM unavailable after retries"}
```

- **Input:** `student_code` (code Java có lỗi), `error_analysis` (dict từ ErrorClassifier)
- **Output:** dict `{"fixed_code": "...", "explanation": "...", "reasoning": "..."}`
- **Exponential backoff:** Lần 1 đợi 1s, lần 2 đợi 2s, lần 3 đợi 4s

---

#### `LLMClient._build_prompt(code, error_analysis, problem_description)`

```python
def _build_prompt(self, code, error_analysis, problem_description):
    loai_loi  = error_analysis.get("loai_loi", "Unknown")
    nguyen_nhan = error_analysis.get("nguyen_nhan", "Unknown")
    chi_tiet  = error_analysis.get("chi_tiet", "")

    # Cắt code nếu quá dài (tránh vượt ngữ cảnh LLM)
    code_snippet = code if len(code) <= 3000 else code[:3000]

    return (
        "You are a Java expert. A student's code has a bug. Fix it.\n\n"
        f"PROBLEM:\n{problem_description or 'Java exercise'}\n\n"
        f"STUDENT CODE:\n{code_snippet}\n\n"
        f"ERROR TYPE: {loai_loi}\n"
        f"REASON: {nguyen_nhan}\n"
        f"DETAILS: {str(chi_tiet)[:500]}\n\n"
        "IMPORTANT: Return the complete fixed Java source code. "
        "Do NOT wrap the code in markdown fences. "
        "Do NOT change the public class name.\n\n"
        'Return JSON only: {"fixed_code": "...", "explanation": "...", "reasoning": "..."}'
    )
```

---

### 4.5. `llm/code_sanitizer.py`

#### `sanitize_java_code(code, expected_class=None)`

```python
def sanitize_java_code(code: str, expected_class: str | None = None) -> str:
    if not code or not code.strip():
        return code

    cleaned = strip_markdown_fences(code)              # Bước 1
    cleaned = strip_preamble(cleaned)                  # Bước 2
    cleaned = keep_only_first_class(cleaned, expected_class)  # Bước 3
    cleaned = cleaned.strip()                          # Bước 4

    if expected_class:
        cleaned = enforce_class_name(cleaned, expected_class)  # Bước 5

    if not re.search(r'\bclass\s+', cleaned):
        logger.warning("Sanitized code has no 'class' keyword – returning original")
        return code  # An toàn: trả về code gốc nếu làm sạch sai

    return cleaned
```

---

#### `keep_only_first_class(code, expected_class=None)`

Hàm phức tạp nhất trong file – dùng thuật toán đếm dấu ngoặc:

```python
def keep_only_first_class(code, expected_class=None):
    match = re.search(r"(?:public\s+)?class\s+(\w+)", code)
    class_start = match.start()

    open_brace_pos = code.find("{", class_start)

    # Đếm cặp {} để tìm } đóng cuối cùng của class đầu tiên
    brace_count = 0
    i = open_brace_pos
    while i < len(code):
        char = code[i]
        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                last_close_brace = i
                break
        i += 1

    preamble         = code[:class_start]
    first_class_code = code[class_start:last_close_brace + 1]
    return preamble + first_class_code
```

**Ví dụ:**

```
Input:  "public class Solution { int x; }  class Helper { }"
Output: "public class Solution { int x; }"
```

---

### 4.6. `auto_grader/modules/log_processor.py`

#### `LogProcessor.extract_error_type(log_text)`

```python
def extract_error_type(self, log_text):
    # Kiểm tra BUILD SUCCESS trước (ưu tiên cao nhất)
    if re.search(self.patterns['build_success'], log_text):
        test_match = re.search(self.patterns['test_failed'], log_text)
        if test_match:
            failures = int(test_match.group(2))
            errors   = int(test_match.group(3))
            if failures + errors == 0:
                return 'PASSED', 'All tests passed'
            return 'TEST_FAILED', f'{failures} failures, {errors} errors'
        return 'PASSED', 'Build successful'

    for pattern in self.patterns['compile_error']:
        if re.search(pattern, log_text, re.IGNORECASE):
            return 'COMPILE_ERROR', self._extract_compile_error_detail(log_text)

    for pattern in self.patterns['runtime_error']:
        if re.search(pattern, log_text):
            return 'RUNTIME_ERROR', self._extract_runtime_error_detail(log_text)

    return 'UNKNOWN', 'Không xác định được loại lỗi'
```

- **Thứ tự ưu tiên:** PASSED > COMPILE_ERROR > RUNTIME_ERROR > TEST_FAILED > UNKNOWN

---

### 4.7. `auto_grader/modules/error_classifier.py`

#### `ErrorClassifier.classify(log_data)`

```python
def classify(self, log_data):
    # Bước 1: Thử regex trước (nhanh, không cần LLM)
    quick_result = self.quick_classify(log_data)

    # Bước 2: Nếu không đủ tin cậy VÀ có LLM → Dùng LLM
    if quick_result['confidence'] < 0.8 and self.use_llm:
        return self.llm_classify(log_data)

    return quick_result
```

**Logic hybrid:** Regex cho kết quả ngay lập tức (< 1ms) với độ tin cậy 85–95%. Chỉ khi không chắc (< 0.8) mới gọi LLM (tốn 5–30 giây).

---

#### `ErrorClassifier.llm_classify(log_data, max_retries=3)`

```python
def llm_classify(self, log_data, max_retries=3):
    # Cắt log để không quá dài
    stdout = log_data.get('raw_logs', {}).get('stdout', '')[-2000:]
    stderr = log_data.get('raw_logs', {}).get('stderr', '')[-1000:]

    prompt = prompt_template.format(...)

    for attempt in range(max_retries):
        backoff_time = 2 ** attempt  # 1s, 2s, 4s
        try:
            response = requests.post(self.ollama_url, json={...}, timeout=90)
            if response.status_code == 200:
                llm_result = json.loads(response.json()['response'])
                llm_result['method']     = 'llm'
                llm_result['confidence'] = 0.95
                return llm_result
        except ...:
            time.sleep(backoff_time)

    # Hết retry → Fallback về regex
    return self.quick_classify(log_data)
```

---

## 5. Cách Các Hàm Kết Nối Nhau

### Sơ đồ luồng gọi hàm (Call Chain)

```
run_feedback_loop.py
└── main()
    ├── _find_java_source()           # Tìm file .java
    ├── _load_code()                  # Đọc nội dung file
    ├── _extract_class_name()         # Lấy tên class
    ├── DockerManager()               # Khởi tạo object
    ├── LogProcessor()                # Khởi tạo object
    ├── ErrorClassifier()             # Khởi tạo object
    ├── LLMClient()                   # Khởi tạo object
    └── LoopOrchestrator.run()        # Bắt đầu vòng lặp chính
        │
        ├── [Mỗi vòng lặp]
        ├── LoopOrchestrator._save_code()
        │   └── Path.write_text()               # Ghi file .java
        │
        ├── DockerManager.compile_and_test()
        │   ├── docker.containers.create()
        │   ├── container.start()
        │   ├── container.wait()
        │   └── container.logs()                # Trả về string log
        │
        ├── execution.LogProcessor.process()    [ADAPTER]
        │   └── auto_grader.modules.LogProcessor.process_log()
        │       ├── read_log_file()
        │       ├── extract_error_type()
        │       │   ├── _extract_compile_error_detail()
        │       │   └── _extract_runtime_error_detail()
        │       └── _extract_test_details()     # Trả về dict
        │
        ├── ErrorClassifier.classify()
        │   ├── quick_classify()               # Regex nhanh
        │   └── llm_classify()                # LLM nếu cần
        │       └── requests.post(Ollama API)
        │
        └── LLMClient.generate_fix()           # Chỉ khi có lỗi
            ├── _build_prompt()
            ├── requests.post(Ollama API)
            └── sanitize_java_code()
                ├── strip_markdown_fences()
                ├── strip_preamble()
                ├── keep_only_first_class()
                └── enforce_class_name()
```

### Luồng dữ liệu qua các file

```
run_feedback_loop.py
     │  code Java (string)
     ▼
core/loop_orchestrator.py
     │  workspace path (string)
     ▼
core/docker_manager.py         → Docker container (mvn clean test)
     │  log thô (string)
     ▼
execution/log_processor.py     → auto_grader/modules/log_processor.py
     │  dict {error_type, test_results, raw_logs, ...}
     ▼
auto_grader/modules/error_classifier.py
     │  dict {loai_loi, nguyen_nhan, confidence, goi_y}
     ▼
llm/llm_client.py              → Ollama API (HTTP POST)
     │  dict {fixed_code, explanation, reasoning}
     ▼
llm/code_sanitizer.py
     │  code Java đã làm sạch (string)
     ▼
core/loop_orchestrator.py      → Vòng tiếp theo (hoặc dừng)
```

---

## 6. Luồng Thực Thi Thực Tế

Giả sử chạy lệnh:

```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 3
```

### Bước 1 – Python khởi động `main()`

```python
args.workspace  = "./workspace"
args.max_rounds = 3
```

### Bước 2 – Tìm và đọc file Java

```
os.walk("./workspace/src/main/java/")
→ Tìm thấy: "./workspace/src/main/java/com/example/Solution.java"
→ Nội dung:
    public class Solution {
        public int tinhTong(int a, int b) { return a - b; }
    }
→ Tên class: "Solution"
```

### Bước 3 – Tạo các module

```python
docker_manager   = DockerManager(image="nckh-build-env", memory_limit="512m")
log_processor    = LogProcessor()
error_classifier = ErrorClassifier(use_llm=True)
llm_client       = LLMClient(base_url="http://localhost:11434", model="llama3.1")
```

### Bước 4 – Vòng 1 bắt đầu

```
LoopOrchestrator.run() → Round 1/3
│
├── _save_code("Solution", code)
│   → Ghi: ./workspace/src/main/java/com/example/Solution.java
│
├── docker_manager.compile_and_test("./workspace")
│   → Tạo container từ image "nckh-build-env"
│   → Mount ./workspace → /workspace trong container
│   → Chạy: mvn clean test --batch-mode
│   → Log:
│       [INFO] BUILD FAILURE
│       Tests run: 3, Failures: 2, Errors: 0
│       expected:<5> but was:<-1>
│   → Exit code: 1
│   → Trả về: "[INFO] BUILD FAILURE\n...\n--- EXIT CODE: 1 ---"
│
├── log_processor.process(raw_log, "SV001")
│   → Lưu vào /tmp/tmpXYZ.txt
│   → Gọi LogProcessor.process_log("/tmp/tmpXYZ.txt")
│   → extract_error_type() → ('TEST_FAILED', '2 failures, 0 errors')
│   → _extract_test_details() → {total:3, passed:1, failed:2}
│   → Xóa file tạm
│   → Trả về dict có cấu trúc
│
├── error_classifier.classify(log_data)
│   → quick_classify(): pattern "expected:<.*> but was:<.*>" → confidence=0.9
│   → 0.9 >= 0.8 → KHÔNG gọi LLM
│   → Trả về: {
│       "loai_loi": "TEST_FAILED",
│       "nguyen_nhan": "Detected pattern: expected:<.*>",
│       "confidence": 0.9
│     }
│
├── error_type = "TEST_FAILED" → Chưa PASSED, tiếp tục
│
└── llm_client.generate_fix(current_code, classification, "")
    → _build_prompt() tạo prompt
    → requests.post("http://localhost:11434/api/generate", timeout=120)
    → Ollama / Llama 3.1 xử lý ~5–15 giây
    → Response: {"fixed_code": "public class Solution { return a + b; }", ...}
    → sanitize_java_code(fixed_code, "Solution")
        → strip_markdown_fences() → không có fence, giữ nguyên
        → strip_preamble()         → không có preamble, giữ nguyên
        → keep_only_first_class()  → chỉ 1 class, giữ nguyên
        → enforce_class_name()     → tên đúng, giữ nguyên
    → current_code = "public class Solution { return a + b; }"
```

### Bước 5 – Vòng 2

```
Round 2/3
│
├── _save_code("Solution", "...return a + b;...")
├── docker_manager.compile_and_test(...)
│   → Log: "BUILD SUCCESS\nTests run: 3, Failures: 0, Errors: 0"
│   → Exit code: 0
│
├── log_processor.process(...) → error_type: "PASSED"
├── error_classifier.classify(...) → {loai_loi: "PASSED", confidence: 0.95}
│
└── error_type == "PASSED" → DỪNG!
    → _build_result(success=True, rounds=2, ...)
    → _persist_history() → Lưu loop_20260318_120000.json
    → Trả về: {"success": True, "rounds": 2, ...}
```

### Bước 6 – In kết quả

```
======================================================================
SUMMARY
======================================================================
Status    : PASSED
Rounds    : 2
  Round 1: TEST_FAILED ❌
  Round 2: PASSED ✅
======================================================================
```

---

## 7. Các Khái Niệm Python Quan Trọng

### 7.1. Class và Object

```python
# Định nghĩa class (bản thiết kế)
class DockerManager:
    def __init__(self, image="nckh-build-env", memory_limit="512m"):
        self.image        = image           # Thuộc tính instance
        self.memory_limit = memory_limit

    def compile_and_test(self, path):       # Method
        ...

# Tạo object (thực thể cụ thể)
docker_manager = DockerManager(image="nckh-build-env", memory_limit="512m")
docker_manager.compile_and_test("./workspace")
```

> **Ví dụ thực tế:** Class như bản vẽ nhà. Object như ngôi nhà thực. Một bản vẽ có thể tạo nhiều ngôi nhà.

---

### 7.2. Property – Lazy initialization

```python
class DockerManager:
    def __init__(self):
        self._client = None  # Private, chưa kết nối

    @property                # Decorator biến method thành thuộc tính
    def client(self):
        if self._client is None:
            self._client = docker.from_env()  # Kết nối khi lần đầu truy cập
        return self._client

# Dùng như thuộc tính (không phải hàm)
dm = DockerManager()
dm.client.containers.create(...)  # Không phải dm.client().containers...
```

> Tránh kết nối Docker khi chưa cần, tiết kiệm tài nguyên.

---

### 7.3. Dependency Injection

```python
# KHÔNG tốt: tự tạo dependency bên trong
class LoopOrchestrator:
    def __init__(self):
        self.docker = DockerManager()  # Khó test, khó thay thế

# TỐT: nhận dependency từ bên ngoài
class LoopOrchestrator:
    def __init__(self, docker_manager, llm_client, ...):
        self.docker_manager = docker_manager  # Dễ thay bằng mock khi test
        self.llm_client     = llm_client
```

---

### 7.4. Exception Handling

```python
try:
    response = requests.post(url, timeout=120)
    response.raise_for_status()         # Raise nếu HTTP 4xx/5xx
    data = json.loads(response.text)

except requests.ConnectionError:        # Ollama chưa chạy
    logger.warning("Cannot connect to Ollama")

except requests.Timeout:                # Đợi quá 120 giây
    logger.warning("Request timed out")

except json.JSONDecodeError:            # LLM trả về không phải JSON
    logger.warning("Invalid JSON response")

finally:                                # Luôn chạy dù có lỗi hay không
    time.sleep(backoff)
```

> **`finally`:** Giống như "dọn dẹp trước khi ra khỏi phòng" – luôn thực hiện.

---

### 7.5. f-string

```python
round_num  = 2
max_rounds = 3
class_name = "Solution"

msg = f"[Round {round_num}/{max_rounds}]"              # "[Round 2/3]"
msg = f"Class: {class_name.upper()}, Len: {len(class_name)}"
```

---

### 7.6. `pathlib.Path` vs `os.path`

```python
from pathlib import Path

# Cách cũ
import os
path = os.path.join("workspace", "src", "main", "java", "Solution.java")

# Cách mới (dễ đọc hơn)
path = Path("workspace") / "src" / "main" / "java" / "Solution.java"

# Các method tiện lợi
path.exists()
path.mkdir(parents=True, exist_ok=True)
path.write_text("code", encoding="utf-8")
path.read_text(encoding="utf-8")
path.suffix   # ".java"
path.stem     # "Solution"
path.parent   # workspace/src/main/java
```

---

### 7.7. `re` – Regular Expression

```python
import re

code = "public class Solution implements Runnable {"

# re.search: Tìm ở bất kỳ vị trí nào
m = re.search(r"public\s+class\s+(\w+)", code)
# \s+ = một hoặc nhiều khoảng trắng
# (\w+) = bắt nhóm (chữ, số, _)
print(m.group(1))   # "Solution"

# re.findall: Tìm tất cả kết quả
errors = re.findall(r'\[ERROR\].*\.java:\[\d+,\d+\]', log_text)

# Pattern phân tích kết quả test Maven
pattern = r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)"
# Với "Tests run: 5, Failures: 2, Errors: 0":
#   group(1) = "5"   (total)
#   group(2) = "2"   (failures)
#   group(3) = "0"   (errors)
```

---

### 7.8. Context Manager (`with`)

```python
# Tự động đóng file sau khi xong
with open("log.txt", "r", encoding="utf-8") as f:
    content = f.read()
# f tự động đóng ở đây, dù có lỗi hay không

# Dùng với tempfile
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
    tmp.write(raw_log)
    tmp_path = tmp.name
# File tạm đã ghi xong; có thể đọc từ tmp_path
```

---

### 7.9. `TYPE_CHECKING` – Tránh circular import

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Chỉ True khi chạy mypy/pyright, False lúc runtime
    from core.docker_manager import DockerManager  # Chỉ dùng cho type hint

class LoopOrchestrator:
    def __init__(self, docker_manager: "DockerManager"):
        self.docker_manager = docker_manager
```

> Tránh lỗi "circular import" khi hai file import lẫn nhau.

---

### 7.10. Docker SDK – Container lifecycle

```python
import docker

client = docker.from_env()

# Tạo container (chưa chạy)
container = client.containers.create(
    "nckh-build-env",
    command="mvn clean test",
    volumes={"/host/path": {"bind": "/container/path", "mode": "rw"}},
    mem_limit="512m",
)

container.start()                           # Chạy
result   = container.wait(timeout=180)      # Đợi tối đa 180s
logs     = container.logs(stdout=True, stderr=True)
exit_code = result["StatusCode"]            # 0 = OK, khác 0 = lỗi
container.remove(force=True)               # Xóa
```

---

## 8. Giải Thích Như Đang Dạy Sinh Viên

### 8.1. `sys.path` là gì?

Khi viết `import requests`, Python tìm thư viện trong danh sách thư mục lưu trong `sys.path`.

```python
import sys
print(sys.path)
# ['/home/user/project', '/usr/lib/python3.11', ...]
```

Trong `run_feedback_loop.py`:

```python
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
```

**Giải thích đơn giản:** Nói với Python "khi tìm thư viện, hãy nhìn vào thư mục gốc của dự án trước". Nhờ đó `from core.docker_manager import DockerManager` hoạt động dù bạn chạy script từ thư mục nào.

---

### 8.2. Tại sao có 2 lớp xử lý log?

```
raw_log (string)
    ↓
execution/log_processor.py    ← Adapter: string → file tạm
    ↓
auto_grader/modules/log_processor.py  ← Logic thực sự (đọc file)
    ↓
dict {error_type, test_results, ...}
```

**Lý do:** `auto_grader/modules/log_processor.py` được viết trước, nhận **đường dẫn file**. `LoopOrchestrator` cần xử lý **string** trong bộ nhớ. Thay vì sửa code cũ, người phát triển viết thêm adapter: lưu string vào file tạm → gọi code cũ → xóa file tạm.

> **Nguyên tắc:** Không sửa code đang hoạt động tốt. Thêm wrapper ở ngoài.

---

### 8.3. Tại sao cần `sanitize_java_code`?

Khi hỏi Llama "sửa code này giúp tôi", AI thường trả lời như sau:

```
Đây là code đã sửa:

```java
public class Solution {
    public int tinhTong(int a, int b) {
        return a + b;
    }
}
```

Hy vọng điều này giúp ích cho bạn!
```

Nếu lưu nguyên văn vào file `.java` rồi compile → Java báo lỗi vì có "Đây là code đã sửa:", backtick markdown, và text cuối. `sanitize_java_code` tự động dọn sạch, chỉ giữ code Java thuần túy.

---

### 8.4. Exponential Backoff là gì?

Khi Ollama đang bận và không trả lời ngay:

```
Lần 1 thất bại → đợi 1 giây  → thử lại
Lần 2 thất bại → đợi 2 giây  → thử lại
Lần 3 thất bại → đợi 4 giây  → thử lại
Hết lần        → báo lỗi
```

```python
for attempt in range(1, max_retries + 1):
    backoff = 2 ** (attempt - 1)  # 2^0=1, 2^1=2, 2^2=4
    try:
        ...
        return result   # Thành công → thoát
    except:
        time.sleep(backoff)
```

> **Ví dụ thực tế:** Khi gõ cửa nhà ai đó và không thấy trả lời, bạn gõ lần 2 sau 1 phút, lần 3 sau 2 phút – không phải gõ liên tục.

---

### 8.5. Regex qua ví dụ thực tế

```python
# Tìm tên class Java
r"public\s+class\s+(\w+)"
# public  = khớp chính xác "public"
# \s+     = một hoặc nhiều khoảng trắng
# class   = khớp chính xác "class"
# (\w+)   = BẮT NHÓM: chữ, số, gạch dưới

# "public class Solution" → group(1) = "Solution"
# "public  class  MyClass" → group(1) = "MyClass" (nhiều space vẫn OK)
# "private class Helper"  → KHÔNG khớp (thiếu "public")
```

```python
# Tìm kết quả test Maven
r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
# Với "Tests run: 5, Failures: 2, Errors: 0, Skipped: 0":
#   group(1) = "5"  (total)
#   group(2) = "2"  (failures)
#   group(3) = "0"  (errors)
#   group(4) = "0"  (skipped)
```

---

*Tài liệu được tổng hợp từ phân tích toàn bộ mã nguồn Python của dự án NCKH25-26.*
*Phiên bản: tháng 3 năm 2026.*
