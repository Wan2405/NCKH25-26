# Hướng Dẫn Toàn Diện – NCKH25-26: Hệ Thống Gỡ Lỗi Java Tự Động với AI

> **Đối tượng đọc:** Sinh viên mới tiếp cận dự án, chưa có kinh nghiệm với các hệ thống AI-in-the-loop hay Docker.
> **Ngôn ngữ:** Tiếng Việt – giải thích đơn giản, có ví dụ minh hoạ cụ thể.

---

## Mục Lục

1. [Tổng Quan Dự Án](#1-tổng-quan-dự-án)
2. [Kiến Trúc Hệ Thống](#2-kiến-trúc-hệ-thống)
3. [Luồng Thực Thi Chi Tiết](#3-luồng-thực-thi-chi-tiết)
4. [Logic Vòng Lặp Phản Hồi](#4-logic-vòng-lặp-phản-hồi)
5. [Docker & Môi Trường Thực Thi](#5-docker--môi-trường-thực-thi)
6. [Luồng Dữ Liệu](#6-luồng-dữ-liệu)
7. [Giải Thích Từng File](#7-giải-thích-từng-file)
8. [Giải Thích Đơn Giản (ELI5)](#8-giải-thích-đơn-giản-eli5)
9. [Hướng Dẫn Mở Rộng và Chỉnh Sửa Hệ Thống](#9-hướng-dẫn-mở-rộng-và-chỉnh-sửa-hệ-thống)

---

## 1. Tổng Quan Dự Án

### Hệ thống này là gì?

**NCKH25-26** là một hệ thống **gỡ lỗi Java tự động** sử dụng trí tuệ nhân tạo. Hệ thống nhận vào một đoạn mã Java có lỗi (lỗi biên dịch, lỗi runtime, hoặc logic sai) và **tự động sửa lỗi** mà không cần can thiệp của con người.

Tên đầy đủ: **AI-in-the-loop Automated Java Debugging System** (Hệ thống Gỡ lỗi Java Tự động với AI trong vòng lặp).

### Hệ thống giải quyết vấn đề gì?

Hãy tưởng tượng bạn là một sinh viên đang học lập trình Java. Bạn viết một chương trình nhưng nó bị lỗi – có thể là lỗi cú pháp, lỗi logic, hoặc kết quả sai. Thông thường bạn phải:

1. Đọc thông báo lỗi (thường rất khó hiểu).
2. Tự tìm hiểu nguyên nhân.
3. Sửa lại code.
4. Chạy lại để kiểm tra.
5. Lặp lại cho đến khi đúng.

Hệ thống NCKH25-26 **tự động hoá toàn bộ quá trình này**: nó tự chạy code, đọc thông báo lỗi, hiểu nguyên nhân (bằng AI), sinh ra bản sửa lỗi, rồi chạy lại – lặp đi lặp lại cho đến khi code đúng hoặc đạt số vòng tối đa.

### Tóm tắt đơn giản

> **Giống như một gia sư AI không biết mệt:** bạn đưa code lỗi vào, hệ thống tự sửa, tự kiểm tra, báo lại kết quả từng bước.

---

## 2. Kiến Trúc Hệ Thống

### Cấu trúc thư mục

```
NCKH25-26/
│
├── run_feedback_loop.py          ← ★ ĐIỂM VÀO CHÍNH (Entry Point)
├── Dockerfile                    ← Định nghĩa image Docker (nckh-build-env)
├── requirements.txt              ← Thư viện Python cần thiết
├── README.md                     ← Tài liệu cài đặt & sử dụng nhanh
│
├── core/                         ← TẦNG ĐIỀU KHIỂN TRUNG TÂM
│   ├── loop_orchestrator.py      ← Não bộ: điều khiển vòng lặp sửa lỗi
│   └── docker_manager.py         ← Quản lý container Docker
│
├── execution/                    ← TẦNG XỬ LÝ KẾT QUẢ
│   ├── log_processor.py          ← Bộ chuyển đổi log thô → JSON
│   └── error_classifier.py       ← Bộ phân loại lỗi (re-export)
│
├── llm/                          ← TẦNG TRÍ TUỆ NHÂN TẠO
│   ├── llm_client.py             ← Giao tiếp với mô hình Llama 3.1
│   ├── code_sanitizer.py         ← Làm sạch code từ LLM
│   └── patch_applier.py          ← Áp dụng unified diff patch
│
├── auto_grader/                  ← MODULE ĐÁNH GIÁ VÀ PHÂN TÍCH
│   ├── modules/
│   │   ├── log_processor.py      ← Phân tích log Maven/JUnit (logic gốc)
│   │   ├── error_classifier.py   ← Phân loại lỗi (regex + LLM)
│   │   ├── feedback_generator.py ← Sinh gợi ý sửa lỗi từ LLM
│   │   ├── executor.py           ← Trích xuất tên class Java
│   │   ├── auto_fixer.py         ← Orchestrator thay thế (không phải chính)
│   │   └── code_generator.py     ← Sinh mã Java từ mô tả
│   ├── docker/
│   │   ├── Dockerfile            ← Dockerfile phụ
│   │   └── run_in_docker.py      ← Script chạy trong Docker
│   └── output/                   ← KẾT QUẢ ĐẦU RA (tự động tạo)
│       ├── logs/                 ← Log đã phân tích (JSON)
│       ├── classifications/      ← Kết quả phân loại lỗi (JSON)
│       ├── feedback/             ← Gợi ý sửa lỗi (JSON + Markdown)
│       └── auto_fix_history/     ← Lịch sử toàn bộ vòng lặp (JSON)
│
└── workspace/                    ← MÃ JAVA ĐẦU VÀO MẪU
    ├── pom.xml                   ← Cấu hình Maven (JUnit 5)
    └── src/
        ├── main/java/com/example/   ← Nơi đặt file .java cần sửa
        └── test/java/com/example/   ← Các bài test JUnit
```

### Vai trò của từng tầng (layer)

| Tầng | Thư mục | Vai trò |
|------|---------|---------|
| **Entry Point** | `run_feedback_loop.py` | Nhận lệnh từ người dùng, khởi động hệ thống |
| **Điều khiển** | `core/` | Điều phối toàn bộ vòng lặp sửa lỗi |
| **Thực thi** | `execution/` | Chạy test, xử lý kết quả |
| **AI** | `llm/` | Giao tiếp với mô hình ngôn ngữ, làm sạch code |
| **Phân tích** | `auto_grader/modules/` | Phân tích sâu log, phân loại lỗi, sinh gợi ý |
| **Lưu trữ** | `auto_grader/output/` | Lưu kết quả từng bước để theo dõi |

### Cách các thành phần tương tác

```
run_feedback_loop.py
    │  (khởi tạo & gọi)
    ▼
LoopOrchestrator  ─── DockerManager  ──────  Container Docker
    │                    (biên dịch/test)       (Maven + JDK 17)
    │
    ├──  LogProcessor  ───  auto_grader/modules/log_processor.py
    │        (phân tích log)
    │
    ├──  ErrorClassifier  ─  auto_grader/modules/error_classifier.py
    │        (phân loại lỗi)           │
    │                               Ollama LLM (nếu cần)
    │
    └──  LLMClient  ─────────  Ollama API (localhost:11434)
             (sửa code)              │
                              code_sanitizer.py
                              (làm sạch code trả về)
```

---

## 3. Luồng Thực Thi Chi Tiết

### Điểm vào (Entry Point): `run_feedback_loop.py`

Đây là **file chạy đầu tiên** khi bạn gõ lệnh:

```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 3
```

#### Bước 1: Đọc tham số dòng lệnh

Hàm `main(argv)` trong `run_feedback_loop.py` dùng `argparse` để đọc:
- `--workspace`: đường dẫn đến thư mục chứa code Java (bắt buộc)
- `--max-rounds`: số vòng sửa lỗi tối đa (mặc định: 3)

#### Bước 2: Tìm và đọc file Java

```
_find_java_source(workspace)
    → Duyệt qua workspace/src/main/java/**/*.java
    → Trả về đường dẫn file .java đầu tiên tìm thấy

_load_code(code_path)
    → Đọc nội dung file .java

_extract_class_name(code)
    → Dùng regex: r"public\s+class\s+(\w+)"
    → Lấy tên class Java (ví dụ: "Solution")
```

#### Bước 3: Khởi tạo các module

```python
docker_manager  = DockerManager()           # Quản lý Docker
log_processor   = LogProcessor()            # Phân tích log
error_classifier = ErrorClassifier(use_llm=True)  # Phân loại lỗi
llm_client      = LLMClient()               # Giao tiếp LLM
```

#### Bước 4: Tạo và chạy LoopOrchestrator

```python
orchestrator = LoopOrchestrator(
    docker_manager, log_processor,
    error_classifier, llm_client,
    workspace_path, max_rounds
)
result = orchestrator.run(initial_code, class_name)
```

#### Bước 5: In kết quả tổng hợp và thoát

Sau khi `orchestrator.run()` kết thúc, `main()` in tóm tắt (Status: PASSED/FAILED, số vòng lặp, lịch sử mỗi vòng) rồi trả về exit code `0` (thành công) hoặc `1` (thất bại).

---

### Bộ điều khiển chính: `core/loop_orchestrator.py`

Đây là **não bộ** của hệ thống. Phương thức `run(initial_code, class_name)` thực hiện vòng lặp:

```
FOR round_num = 1 đến max_rounds:

    ① Ghi code Java hiện tại vào:
       workspace/src/main/java/com/example/{ClassName}.java

    ② Gọi DockerManager.compile_and_test(workspace)
       → Kết quả: chuỗi log thô (stdout + stderr + exit code)

    ③ Gọi LogProcessor.process(raw_log)
       → Kết quả: JSON có cấu trúc {metadata, execution, test_results, raw_logs}

    ④ Gọi ErrorClassifier.classify(log_data)
       → Kết quả: {loai_loi, nguyen_nhan, confidence, chi_tiet, goi_y}

    ⑤ Kiểm tra kết quả:
       - Nếu loai_loi == "PASSED"  → Dừng vòng lặp, trả về thành công
       - Nếu round == max_rounds   → Dừng vòng lặp, trả về thất bại

    ⑥ Gọi LLMClient.generate_fix(code, classification)
       → Kết quả: {fixed_code, explanation, reasoning}

    ⑦ Làm sạch code: sanitize_java_code(fixed_code)
       → code hiện tại = code đã sửa và làm sạch

    ⑧ Lưu lịch sử vòng này vào history[]

LƯU lịch sử JSON vào: auto_grader/output/auto_fix_history/loop_YYYYMMDD_HHMMSS.json
TRẢ VỀ: {success, rounds, final_code, history[]}
```

---

### Sơ đồ luồng thực thi đầy đủ (cross-file)

```
[NGƯỜI DÙNG gõ lệnh]
         │
         ▼
run_feedback_loop.py :: main()
         │
         ├─ _find_java_source()   → tìm file .java
         ├─ _load_code()          → đọc code
         ├─ _extract_class_name() → lấy tên class
         │
         ├─ DockerManager()       ← core/docker_manager.py
         ├─ LogProcessor()        ← execution/log_processor.py
         ├─ ErrorClassifier()     ← execution/error_classifier.py
         ├─ LLMClient()           ← llm/llm_client.py
         │
         └─ LoopOrchestrator.run()  ← core/loop_orchestrator.py
                   │
         ┌─────────┴──────────┐
         │   FOR EACH ROUND   │
         └─────────┬──────────┘
                   │
          ① Ghi code vào file
                   │
          ② DockerManager.compile_and_test()
             └─ docker SDK: tạo container, mount workspace, chạy "mvn clean test"
             └─ Trả về: chuỗi log thô
                   │
          ③ LogProcessor.process()
             └─ execution/log_processor.py → auto_grader/modules/log_processor.py
             └─ Trả về: JSON phân tích log
                   │
          ④ ErrorClassifier.classify()
             └─ execution/error_classifier.py → auto_grader/modules/error_classifier.py
             └─ Regex classify (nhanh) → nếu cần → LLM classify (chính xác hơn)
             └─ Trả về: {loai_loi, nguyen_nhan, confidence}
                   │
          ⑤ PASSED? → Dừng (thành công)
          ⑤ Hết vòng? → Dừng (thất bại)
                   │
          ⑥ LLMClient.generate_fix()
             └─ llm/llm_client.py: POST đến Ollama API (localhost:11434)
             └─ Model: llama3.1, temperature: 0.3
             └─ Trả về: {fixed_code, explanation}
                   │
          ⑦ sanitize_java_code()
             └─ llm/code_sanitizer.py: xóa markdown, preamble, giữ 1 class, sửa tên class
             └─ Trả về: code Java sạch
                   │
          ⑧ Cập nhật current_code, lưu history
                   │
         [VỀ ĐẦU VÒNG LẶP TIẾP THEO]
```

---

## 4. Logic Vòng Lặp Phản Hồi

### Vòng lặp hoạt động như thế nào?

Hệ thống hoạt động theo mô hình **"thử – kiểm tra – sửa – thử lại"**:

```
Vòng 1:
  Code ban đầu (có lỗi) → Chạy test → Lỗi gì? → LLM sửa → Code mới

Vòng 2:
  Code mới → Chạy test → Còn lỗi không? → LLM sửa → Code mới nữa

Vòng 3:
  Code mới nữa → Chạy test → PASSED! → Dừng!
```

### Hệ thống phát hiện lỗi như thế nào?

**Module:** `auto_grader/modules/error_classifier.py` với 2 chiến lược:

#### Chiến lược 1: Regex (nhanh, ~0ms)

Hệ thống dùng các mẫu regex để quét log Maven/JUnit:

| Loại lỗi | Pattern nhận diện |
|----------|-------------------|
| `COMPILE_ERROR` | `"COMPILATION ERROR"`, `"cannot find symbol"`, `"illegal start of expression"` |
| `RUNTIME_ERROR` | `"Exception in thread"`, `"NullPointerException"`, stack trace |
| `TEST_FAILED` | `"Tests run: N, Failures: M"` (M > 0) |
| `PASSED` | `"BUILD SUCCESS"` + `"Failures: 0"` |

Nếu độ tin cậy (confidence) ≥ 0.8 → trả kết quả ngay, không cần hỏi LLM.

#### Chiến lược 2: LLM Classify (chính xác, ~30-90s)

Khi regex không đủ chắc chắn (confidence < 0.8), hệ thống gửi prompt đến Llama 3.1:

```
Bạn là AI chuyên phân tích lỗi Java.
Error Type: {error_type}, Exit Code: {exit_code}
Test Results: Total={N}, Passed={P}, Failed={F}
Chi tiết lỗi: {error_detail}
Maven Output: {stdout}

→ Trả về JSON: {loai_loi, nguyen_nhan, chi_tiet, goi_y}
```

### Gửi phản hồi cho LLM như thế nào?

**Module:** `llm/llm_client.py`

Sau khi phân loại lỗi, hệ thống tạo prompt cho LLM:

```
You are a Java expert. A student's code has a bug. Fix it.

PROBLEM: {problem_description}
STUDENT CODE: {code_snippet}  (tối đa 3000 ký tự)
ERROR TYPE: {loai_loi}
REASON: {nguyen_nhan}
DETAILS: {chi_tiet}

IMPORTANT:
- Trả về complete Java source code
- KHÔNG dùng markdown fences (không có ```java)
- KHÔNG đổi tên public class

Return JSON only: {"fixed_code": "...", "explanation": "...", "reasoning": "..."}
```

### Khi nào vòng lặp dừng?

Vòng lặp dừng khi gặp **một trong ba điều kiện**:

1. ✅ **Thành công:** Kết quả là `PASSED` (tất cả test JUnit đều pass).
2. ❌ **Hết vòng:** Đã chạy đủ `--max-rounds` lần mà vẫn chưa PASSED.
3. ❌ **LLM không trả về code:** `fixed_code` rỗng sau khi thử lại 3 lần.

### Chiến lược retry (thử lại)

Khi gọi LLM thất bại (mạng lỗi, timeout, JSON không hợp lệ), hệ thống thử lại với **exponential backoff**:

```
Lần thử 1: Ngay lập tức
Lần thử 2: Chờ 1 giây
Lần thử 3: Chờ 2 giây
Lần thử 4: Chờ 4 giây
→ Sau 3 lần thất bại: fallback về regex hoặc trả về rỗng
```

---

## 5. Docker & Môi Trường Thực Thi

### Tại sao dùng Docker?

Docker tạo ra một **môi trường cô lập hoàn toàn** để biên dịch và chạy code Java. Điều này đảm bảo:
- Code chạy trong môi trường nhất quán (không phụ thuộc máy người dùng).
- An toàn khi chạy code sinh ra bởi AI (code lạ không ảnh hưởng máy chủ).
- Phiên bản Java và Maven cố định (JDK 17, Maven 3.9).

### Image Docker: `nckh-build-env`

Được định nghĩa trong `Dockerfile` ở thư mục gốc:

```dockerfile
FROM maven:3.9-eclipse-temurin-17
# Pre-download JUnit 5 Jupiter dependencies
RUN mvn dependency:get -Dartifact=org.junit.jupiter:junit-jupiter-api:5.10.2
RUN mvn dependency:get -Dartifact=org.junit.jupiter:junit-jupiter-engine:5.10.2
WORKDIR /workspace
CMD ["mvn", "clean", "test", "--batch-mode"]
```

**Nội dung image:**
- **Base image:** `maven:3.9-eclipse-temurin-17` → Maven 3.9 + JDK 17.
- **Pre-downloaded:** JUnit 5 Jupiter (tăng tốc, tránh download mỗi lần chạy).
- **Working directory:** `/workspace` → đây là nơi code Java được mount vào.
- **Default command:** `mvn clean test --batch-mode` → compile và chạy test.

### Quá trình trong container (DockerManager)

**Module:** `core/docker_manager.py`

Khi `compile_and_test(workspace_path)` được gọi:

```
1. Chuyển workspace_path thành absolute path

2. Tạo container Docker:
   image    = "nckh-build-env"
   command  = "mvn clean test --batch-mode"
   volumes  = {abs_path: {bind: "/workspace", mode: "rw"}}
   mem_limit = "512m"       ← Giới hạn RAM
   cpu_quota = 100_000      ← Giới hạn CPU (1 core)
   pids_limit = 100         ← Giới hạn processes
   network_disabled = True  ← Không có mạng

3. Start container → Wait (timeout: 180 giây)

4. Lấy logs (stdout + stderr)

5. Xóa container (cleanup)

6. Trả về: "{logs}\n--- EXIT CODE: {exit_code} ---"
```

**Các giới hạn bảo mật:**

| Giới hạn | Giá trị | Mục đích |
|----------|---------|---------|
| RAM | 512 MB | Ngăn OOM bomb |
| CPU | 1 core | Ngăn CPU bomb |
| Processes | 100 PIDs | Ngăn fork bomb |
| Network | Disabled | Ngăn truy cập mạng |
| Timeout | 180 giây | Ngăn vòng lặp vô hạn |

### Java code được biên dịch và test như thế nào?

1. Code Java được ghi vào: `workspace/src/main/java/com/example/{ClassName}.java`
2. Container Docker mount thư mục `workspace/` vào `/workspace/`
3. Maven chạy: `mvn clean test --batch-mode`
   - `clean`: xóa build cũ
   - `test`: biên dịch source + biên dịch test + chạy test JUnit
   - `--batch-mode`: không hỏi user input
4. JUnit 5 chạy các `@Test` methods trong `SolutionTest.java`
5. Maven in kết quả (pass/fail) ra stdout
6. Hệ thống đọc log từ container

---

## 6. Luồng Dữ Liệu

### Sơ đồ luồng dữ liệu tổng thể

```
[ĐẦU VÀO]
Code Java có lỗi (file .java)
         │
         ▼
run_feedback_loop.py đọc code thành string
         │
         ▼
LoopOrchestrator.run(initial_code, class_name)
         │
         ▼ ① Ghi code vào workspace/src/main/java/com/example/Solution.java
         │
         ▼ ② DockerManager.compile_and_test()
┌─────────────────────────────────────────────┐
│ TRONG CONTAINER DOCKER:                      │
│   mvn clean test                             │
│     → Biên dịch .java → .class              │
│     → Chạy JUnit tests                      │
│     → In kết quả ra stdout                  │
└─────────────────────────────────────────────┘
         │
         ▼ Trả về: chuỗi log thô (stdout + stderr + exit code)
         │
         ▼ ③ LogProcessor.process(raw_log)
┌─────────────────────────────────────────────┐
│ Phân tích bằng Regex:                        │
│   - Xác định loại lỗi (compile/runtime/test) │
│   - Trích xuất chi tiết lỗi                  │
│   - Đếm tests passed/failed                  │
└─────────────────────────────────────────────┘
         │
         ▼ Trả về: JSON có cấu trúc
{
  "metadata": {timestamp, student_id, ...},
  "execution": {exit_code, error_type, error_detail},
  "test_results": {total, passed, failed, errors},
  "raw_logs": {stdout, stderr}
}
         │
         ▼ ④ ErrorClassifier.classify(log_data)
┌─────────────────────────────────────────────┐
│ Regex classify (nhanh):                      │
│   → confidence ≥ 0.8? → Dùng kết quả ngay  │
│                                              │
│ LLM classify (nếu regex không chắc):        │
│   → POST đến Ollama API                      │
│   → Nhận phân tích chi tiết từ Llama 3.1    │
└─────────────────────────────────────────────┘
         │
         ▼ Trả về: classification JSON
{
  "loai_loi": "TEST_FAILED",
  "nguyen_nhan": "Phép tính sai: dùng '-' thay vì '+'",
  "confidence": 0.85,
  "chi_tiet": "expected:<5> but was:<-1>",
  "goi_y": "Sửa toán tử từ '-' thành '+'"
}
         │
         ▼ ⑤ Nếu PASSED → DỪNG. Ngược lại, tiếp tục.
         │
         ▼ ⑥ LLMClient.generate_fix(code, classification)
┌─────────────────────────────────────────────┐
│ POST đến Ollama (localhost:11434):           │
│   Model: llama3.1                            │
│   Input: code lỗi + phân tích lỗi           │
│   Output: fixed_code + explanation           │
└─────────────────────────────────────────────┘
         │
         ▼ Trả về: {fixed_code, explanation, reasoning}
         │
         ▼ ⑦ code_sanitizer.sanitize_java_code(fixed_code)
┌─────────────────────────────────────────────┐
│ Làm sạch code từ LLM:                        │
│   1. Xóa markdown fences (```java ... ```)  │
│   2. Xóa preamble text ("Here's the fix:") │
│   3. Giữ lại chỉ class đầu tiên             │
│   4. Sửa tên class về đúng tên gốc          │
└─────────────────────────────────────────────┘
         │
         ▼ Trả về: code Java sạch
         │
         ▼ ⑧ current_code = fixed_code → Quay lại vòng lặp
         │
[ĐẦU RA]
Kết quả cuối: {success, rounds, final_code, history[]}
Lưu vào: auto_grader/output/auto_fix_history/loop_{timestamp}.json
```

### Cấu trúc file output

```
auto_grader/output/
├── logs/
│   └── log_YYYYMMDD_HHMMSS.json
│       → Log đã phân tích: {metadata, execution, test_results, raw_logs}
│
├── classifications/
│   └── classification_YYYYMMDD_HHMMSS.json
│       → Kết quả phân loại: {loai_loi, nguyen_nhan, confidence, chi_tiet}
│
├── feedback/
│   ├── feedback_YYYYMMDD.json     → Gợi ý sửa lỗi (JSON)
│   └── feedback_YYYYMMDD.md       → Gợi ý sửa lỗi (Markdown, dễ đọc)
│
└── auto_fix_history/
    └── loop_YYYYMMDD_HHMMSS.json
        → Lịch sử toàn bộ vòng lặp:
        {
          "success": true,
          "rounds": 2,
          "final_code": "public class Solution { ... }",
          "history": [
            {"round": 1, "error_type": "TEST_FAILED", "status": "FAILED", ...},
            {"round": 2, "error_type": "PASSED",      "status": "PASSED", ...}
          ]
        }
```

---

## 7. Giải Thích Từng File

### `run_feedback_loop.py` – Điểm vào chính

**Mục đích:** File duy nhất bạn cần chạy trực tiếp.

**Các hàm chính:**
| Hàm | Chức năng |
|-----|-----------|
| `main(argv)` | Phân tích tham số CLI, khởi tạo pipeline, in kết quả |
| `_find_java_source(workspace)` | Tìm file .java trong `workspace/src/main/java/` |
| `_load_code(code_path)` | Đọc nội dung file Java |
| `_extract_class_name(code)` | Trích xuất tên public class bằng regex |

**Kết nối với:** `core/loop_orchestrator.py`, `core/docker_manager.py`, `execution/log_processor.py`, `execution/error_classifier.py`, `llm/llm_client.py`

---

### `core/loop_orchestrator.py` – Não bộ vòng lặp

**Mục đích:** Điều phối toàn bộ quá trình: chạy → phân tích → sửa → lặp lại.

**Class:** `LoopOrchestrator`

**Phương thức quan trọng:**
| Phương thức | Chức năng |
|------------|-----------|
| `__init__(docker_manager, log_processor, error_classifier, llm_client, workspace_path, max_rounds)` | Khởi tạo với các module phụ thuộc |
| `run(initial_code, class_name, problem_description, student_id)` | Chạy vòng lặp, trả về `{success, rounds, final_code, history}` |

**Kết nối với:** tất cả module khác.

---

### `core/docker_manager.py` – Quản lý Docker

**Mục đích:** Tạo, chạy và dọn dẹp container Docker.

**Class:** `DockerManager`

**Phương thức quan trọng:**
| Phương thức | Chức năng |
|------------|-----------|
| `__init__(image, memory_limit, cpu_quota, pids_limit, timeout)` | Cấu hình Docker |
| `compile_and_test(workspace_path)` | Mount workspace, chạy `mvn test`, trả về log |

**Kết nối với:** Docker SDK (`import docker`), image `nckh-build-env`.

---

### `execution/log_processor.py` – Bộ xử lý log

**Mục đích:** Chuyển đổi log thô từ Maven/JUnit thành JSON có cấu trúc.

**Class:** `LogProcessor`

**Phương thức quan trọng:**
| Phương thức | Chức năng |
|------------|-----------|
| `process(raw_log, student_id)` | Phân tích log, trả về JSON dict |

**Nhận diện lỗi bằng regex:**
- `COMPILE_ERROR`: "COMPILATION ERROR", "cannot find symbol", v.v.
- `RUNTIME_ERROR`: "Exception in thread", "NullPointerException", v.v.
- `TEST_FAILED`: "Tests run: N, Failures: M" (M > 0)
- `PASSED`: "BUILD SUCCESS" + không có failures

**Kết nối với:** `auto_grader/modules/log_processor.py` (logic gốc).

---

### `execution/error_classifier.py` – Bộ phân loại lỗi

**Mục đích:** Tái xuất từ `auto_grader/modules/error_classifier.py`.

**Kết nối với:** `auto_grader/modules/error_classifier.py`.

---

### `auto_grader/modules/error_classifier.py` – Logic phân loại lỗi

**Mục đích:** Phân loại lỗi qua 2 chiến lược (regex nhanh + LLM chính xác).

**Class:** `ErrorClassifier`

**Phương thức quan trọng:**
| Phương thức | Chức năng |
|------------|-----------|
| `__init__(use_llm, ollama_url)` | Cấu hình (có dùng LLM không?) |
| `classify(log_data)` | Phân loại, trả về `{loai_loi, nguyen_nhan, confidence, chi_tiet, goi_y}` |
| `_quick_classify(log_data)` | Phân loại bằng regex (nhanh) |
| `_llm_classify(log_data)` | Phân loại bằng LLM (chính xác hơn) |

---

### `llm/llm_client.py` – Giao tiếp LLM

**Mục đích:** Gửi code lỗi + phân tích đến Llama 3.1 qua Ollama, nhận code đã sửa.

**Class:** `LLMClient`

**Phương thức quan trọng:**
| Phương thức | Chức năng |
|------------|-----------|
| `__init__(base_url, model, max_retries)` | Cấu hình Ollama URL và model |
| `generate_fix(student_code, error_analysis, problem_description)` | Sinh code sửa lỗi, trả về `{fixed_code, explanation, reasoning}` |

**Đặc điểm:**
- POST đến `http://localhost:11434/api/generate`
- Model: `llama3.1`, temperature: 0.3 (ít sáng tạo, code ổn định hơn)
- Retry tối đa 3 lần với exponential backoff

---

### `llm/code_sanitizer.py` – Làm sạch code từ LLM

**Mục đích:** LLM hay trả về code bị "bẩn" (có markdown, text thừa, nhiều class). Module này làm sạch code trước khi biên dịch.

**Hàm chính:** `sanitize_java_code(code, expected_class) → str`

**Quy trình làm sạch (theo thứ tự):**

1. **Xóa markdown fences:** Tìm ` ```java ... ``` ` và chỉ giữ phần bên trong.
2. **Xóa preamble text:** Xóa mọi text trước keyword Java đầu tiên (`package`, `import`, `public`, `//`).
3. **Giữ 1 class duy nhất:** Dùng thuật toán đếm ngoặc `{}` để trích xuất class đầu tiên.
4. **Sửa tên class:** Dùng regex thay tên class thành tên đúng (ví dụ: `Bug` → `Solution`).
5. **Safety check:** Nếu kết quả không có `class` → trả về code gốc (tránh mất dữ liệu).

**Ví dụ:**
```
INPUT (từ LLM):
  "Here's the corrected code:
   ```java
   public class Bug {
       public int add(int a, int b) { return a + b; }
   }
   ```"

OUTPUT (sau sanitize):
  "public class Solution {
       public int add(int a, int b) { return a + b; }
   }"
```

---

### `auto_grader/modules/log_processor.py` – Phân tích log (logic gốc)

**Mục đích:** Logic chi tiết để phân tích output của Maven/JUnit.

**Đặc điểm nổi bật:**
- Dùng nhiều regex pattern để nhận diện từng loại lỗi.
- Trích xuất số liệu test: total, passed, failed, errors, skipped.
- Giới hạn raw log: stdout (5000 ký tự cuối), stderr (3000 ký tự cuối).

---

### `auto_grader/modules/feedback_generator.py` – Sinh gợi ý sửa lỗi

**Mục đích:** Sinh ra gợi ý sửa lỗi (dạng text, không phải code đầy đủ) từ LLM.

**Đặc điểm:** Lưu kết quả ra cả file JSON và file Markdown trong `auto_grader/output/feedback/`.

---

### `auto_grader/modules/auto_fixer.py` – Orchestrator thay thế

**Mục đích:** Một phiên bản orchestrator cũ hơn, không phải pipeline chính.

**Lưu ý:** Không phải entry point chính. Sử dụng `run_feedback_loop.py` thay thế.

---

### `workspace/` – Workspace mẫu

**Cấu trúc:**
```
workspace/
├── pom.xml                          ← Cấu hình Maven (JUnit 5 Jupiter)
└── src/
    ├── main/java/com/example/       ← File .java cần sửa
    └── test/java/com/example/       ← Các test JUnit
```

**`workspace/pom.xml`:** Cấu hình Maven với JUnit 5 Jupiter 5.10.2 và Surefire plugin 3.2.5.

---

### `Dockerfile` – Định nghĩa môi trường Docker

**Mục đích:** Build image `nckh-build-env` dùng cho tất cả lần chạy test.

```dockerfile
FROM maven:3.9-eclipse-temurin-17
RUN mvn dependency:get -Dartifact=org.junit.jupiter:junit-jupiter-api:5.10.2
RUN mvn dependency:get -Dartifact=org.junit.jupiter:junit-jupiter-engine:5.10.2
WORKDIR /workspace
CMD ["mvn", "clean", "test", "--batch-mode"]
```

**Cách build:** `docker build -t nckh-build-env .`

---

### `requirements.txt` – Thư viện Python

```
requests==2.31.0    ← HTTP client (gọi Ollama API)
docker==7.1.0       ← Python Docker SDK (tạo/quản lý container)
python-dotenv==1.0.0 ← Đọc biến môi trường từ file .env
```

---

## 8. Giải Thích Đơn Giản (ELI5)

> **ELI5 = Explain Like I'm 5** – giải thích như đang nói chuyện với một đứa trẻ 5 tuổi (hoặc một sinh viên mới học lập trình).

### Ví dụ minh hoạ bằng câu chuyện

Tưởng tượng bạn có một **cái máy sửa bài tập lập trình tự động**. Cái máy đó hoạt động như thế này:

---

**Bước 1 – Bạn đưa bài tập vào:**

Bạn viết một đoạn code Java có lỗi:
```java
public class Solution {
    public int tinhTong(int a, int b) {
        return a - b;  // Sai rồi! Phải là + chứ không phải -
    }
}
```

---

**Bước 2 – Máy đưa vào "phòng thí nghiệm" (Docker):**

Máy đặt code vào một căn phòng sạch, cô lập (Docker container), rồi chạy thử:
```
"Bài test số 1: tinhTong(2, 3) = 5?  → Kết quả: -1  → SAI!"
```

---

**Bước 3 – Máy đọc kết quả:**

Máy đọc thông báo lỗi: *"Expected 5 but was -1"*. Máy hiểu đây là lỗi logic (TEST_FAILED).

---

**Bước 4 – Máy hỏi AI:**

Máy gửi cho AI (Llama 3.1) một tin nhắn:
> *"Này AI, code này bị lỗi: dùng '-' nhưng phải là '+'. Hãy sửa giúp tôi."*

AI trả lời code đã sửa.

---

**Bước 5 – Máy làm sạch câu trả lời của AI:**

AI đôi khi trả lời như thế này:
> *"Dưới đây là code đã sửa:*
> ```java
> public class Solution { ... }
> ```"*

Máy xóa phần "*Dưới đây là code đã sửa:*" và các dấu backtick, chỉ giữ lại code sạch.

---

**Bước 6 – Máy thử lại:**

Code đã sửa được đưa vào "phòng thí nghiệm" một lần nữa. Lần này:
```
"Bài test số 1: tinhTong(2, 3) = 5?  → Kết quả: 5  → ĐÚNG! ✅"
```

---

**Kết quả:** Máy báo: *"PASSED sau 2 vòng!"* và lưu lại toàn bộ lịch sử sửa lỗi.

---

### Tóm tắt bằng sơ đồ đơn giản

```
Code lỗi
   ↓
[Phòng thí nghiệm Docker]
   ↓ "Lỗi ở đây!"
[Máy đọc lỗi]
   ↓ "Đây là lỗi gì?"
[AI phân tích lỗi]
   ↓ "Hãy sửa lỗi này"
[AI sinh code mới]
   ↓ "Làm sạch code AI"
[Code đã sửa]
   ↓
[Phòng thí nghiệm Docker] (lần 2)
   ↓ "PASSED! ✅"
[Kết quả cuối]
```

---

## 9. Hướng Dẫn Mở Rộng và Chỉnh Sửa Hệ Thống

### Bắt đầu từ đâu?

Nếu bạn là sinh viên mới muốn hiểu hoặc chỉnh sửa hệ thống, hãy bắt đầu theo thứ tự:

1. **Đọc `run_feedback_loop.py`** – File ngắn (~157 dòng), dễ hiểu, là entry point.
2. **Đọc `core/loop_orchestrator.py`** – Hiểu vòng lặp chính.
3. **Đọc `core/docker_manager.py`** – Hiểu cách Docker được dùng.
4. **Đọc `llm/llm_client.py`** – Hiểu cách giao tiếp với LLM.
5. **Đọc `llm/code_sanitizer.py`** – Hiểu cách làm sạch code LLM.

### Các file quan trọng nhất

| File | Khi nào cần chỉnh? |
|------|--------------------|
| `run_feedback_loop.py` | Thêm tham số CLI mới, thay đổi output |
| `core/loop_orchestrator.py` | Thay đổi logic vòng lặp, điều kiện dừng |
| `core/docker_manager.py` | Thay đổi giới hạn Docker, timeout |
| `llm/llm_client.py` | Thay đổi model LLM, prompt template, API endpoint |
| `llm/code_sanitizer.py` | Sửa cách làm sạch code từ LLM |
| `auto_grader/modules/error_classifier.py` | Thêm pattern nhận diện lỗi mới |
| `auto_grader/modules/log_processor.py` | Thay đổi cách phân tích log Maven |
| `Dockerfile` | Cập nhật phiên bản Java/Maven, thêm dependency |
| `workspace/pom.xml` | Thêm thư viện Java, cập nhật phiên bản JUnit |

### Các ví dụ về tác vụ mở rộng thường gặp

#### Thêm hỗ trợ ngôn ngữ lập trình khác (ví dụ: Python)

1. Tạo Dockerfile mới cho Python (với `pytest`).
2. Chỉnh `core/docker_manager.py`: thêm tham số `language` và câu lệnh tương ứng.
3. Cập nhật `auto_grader/modules/log_processor.py`: thêm regex nhận diện output của pytest.
4. Cập nhật prompt trong `llm/llm_client.py` cho phù hợp với Python.

#### Thay đổi model LLM

Trong `llm/llm_client.py`, thay `"llama3.1"` thành model khác (ví dụ `"codellama"`, `"deepseek-coder"`):

```python
LLMClient(model="codellama")
# hoặc
LLMClient(base_url="http://localhost:11434", model="deepseek-coder:6.7b")
```

Lưu ý: Model phải được cài đặt trước trong Ollama (`ollama pull <tên_model>`).

#### Tăng số vòng lặp tối đa

```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 10
```

#### Thêm loại lỗi mới để nhận diện

Trong `auto_grader/modules/error_classifier.py`, thêm pattern regex vào `_COMPILE_PATTERNS`, `_RUNTIME_PATTERNS`, v.v.

#### Thêm output log chi tiết hơn

Trong `core/loop_orchestrator.py`, thêm các `print()` hoặc `logger.info()` vào từng bước của vòng lặp.

### Điều cần lưu ý

1. **Tên class Java phải khớp với tên file:** `Solution.java` phải chứa `public class Solution`. Nếu không, Maven sẽ báo lỗi biên dịch.

2. **Ollama phải đang chạy trước khi chạy hệ thống:**
   ```bash
   ollama serve
   # Trong terminal khác:
   python run_feedback_loop.py --workspace ./workspace
   ```

3. **Docker image phải được build trước:**
   ```bash
   docker build -t nckh-build-env .
   ```

4. **Tránh chỉnh sửa các file trong `auto_grader/output/`** – đây là dữ liệu tự động sinh ra, không phải code nguồn.

5. **`execution/error_classifier.py` chỉ là re-export** – logic thực sự ở `auto_grader/modules/error_classifier.py`. Nếu muốn chỉnh, hãy chỉnh file gốc.

6. **Khi thêm dependency Python mới**, hãy cập nhật `requirements.txt`:
   ```bash
   pip install <package>
   pip freeze | grep <package> >> requirements.txt
   ```

7. **Khi thêm dependency Java mới**, hãy cập nhật `workspace/pom.xml` và rebuild Docker image:
   ```bash
   docker build -t nckh-build-env . --no-cache
   ```

---

## Phụ Lục: Ví Dụ Chạy Hoàn Chỉnh

### Cài đặt môi trường

```bash
# 1. Clone dự án
git clone https://github.com/Wan2405/NCKH25-26.git
cd NCKH25-26

# 2. Cài Python dependencies
pip install -r requirements.txt

# 3. Build Docker image
docker build -t nckh-build-env .

# 4. Khởi động Ollama và tải model
ollama pull llama3.1
ollama serve &  # Chạy nền
```

### Chạy với workspace mẫu

```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 3
```

### Kết quả mong đợi

```
======================================================================
[*] NCKH25-26  AI-in-the-loop Automated Debugging Pipeline
======================================================================
Workspace : ./workspace
Code file : ./workspace/src/main/java/com/example/Solution.java
Class name: Solution
Max rounds: 3
======================================================================

[Round 1/3]
----------------------------------------------------------------------
[*] Code saved → Solution.java
[*] Running tests via Docker ...
[*] Result: TEST_FAILED
[*] Requesting fix from LLM ...
[+] Code updated from LLM suggestion

[Round 2/3]
----------------------------------------------------------------------
[*] Code saved → Solution.java
[*] Running tests via Docker ...
[*] Result: PASSED

[+] PASSED after 2 round(s)!
[+] History saved → auto_grader/output/auto_fix_history/loop_20250315_105015.json

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

*Tài liệu được tạo từ phân tích toàn bộ mã nguồn của dự án NCKH25-26.*
