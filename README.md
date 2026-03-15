# NCKH25-26 – Hệ thống Gỡ lỗi Java Tự động với AI-in-the-loop

Hệ thống này tự động phát hiện và sửa các lỗi trong mã nguồn Java (lỗi biên dịch, lỗi runtime, lỗi test) bằng cách sử dụng vòng lặp phản hồi có sự tham gia của mô hình ngôn ngữ lớn (LLM – Llama 3.1 qua Ollama).

---

## Mục lục

1. [Yêu cầu cài đặt (Prerequisites)](#yêu-cầu-cài-đặt-prerequisites)
2. [Cấu trúc thư mục workspace đầu vào](#cấu-trúc-thư-mục-workspace-đầu-vào)
3. [Cách sử dụng (CLI)](#cách-sử-dụng-cli)
4. [Cách pipeline hoạt động](#cách-pipeline-hoạt-động)

---

## Yêu cầu cài đặt (Prerequisites)

### 1. Docker Desktop

Pipeline biên dịch và chạy test Java bên trong container Docker để đảm bảo môi trường độc lập, không phụ thuộc vào máy của người dùng.

- Tải và cài đặt **Docker Desktop** từ: https://www.docker.com/products/docker-desktop/
- Sau khi cài đặt, đảm bảo Docker daemon đang chạy (icon Docker xuất hiện trên thanh taskbar).
- Kiểm tra cài đặt:
  ```bash
  docker --version
  ```

### 2. Ollama với mô hình Llama 3.1

LLM được sử dụng để sinh ra phiên bản sửa lỗi của mã nguồn Java.

- Tải và cài đặt **Ollama** từ: https://ollama.com/
- Sau khi cài đặt, tải mô hình Llama 3.1:
  ```bash
  ollama pull llama3.1
  ```
- Đảm bảo Ollama đang chạy trên cổng mặc định `11434`:
  ```bash
  ollama serve
  ```
- Kiểm tra mô hình đã được tải:
  ```bash
  ollama list
  ```

### 3. Python và các thư viện phụ thuộc

Hệ thống yêu cầu **Python 3.10** trở lên.

- Cài đặt các thư viện cần thiết:
  ```bash
  pip install -r requirements.txt
  ```

---

## Cấu trúc thư mục workspace đầu vào

Thư mục workspace là nơi chứa toàn bộ mã nguồn Java có lỗi cùng với file cấu hình Maven và các bài kiểm thử (JUnit tests).

**Cấu trúc bắt buộc:**

```
test_workspace/
├── pom.xml                          # File cấu hình Maven (bắt buộc)
└── src/
    ├── main/
    │   └── java/
    │       └── com/
    │           └── example/
    │               └── Solution.java    # Mã nguồn Java có lỗi cần sửa
    └── test/
        └── java/
            └── com/
                └── example/
                    └── SolutionTest.java  # Các bài test JUnit
```

**Ví dụ nội dung `pom.xml`:**

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>solution</artifactId>
  <version>1.0-SNAPSHOT</version>
  <dependencies>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

**Ví dụ mã nguồn Java có lỗi (`Solution.java`):**

```java
public class Solution {
    public int tinhTong(int a, int b) {
        return a - b;  // Lỗi: phép trừ thay vì phép cộng
    }
}
```

**Ví dụ bài test JUnit (`SolutionTest.java`):**

```java
import org.junit.Test;
import static org.junit.Assert.*;

public class SolutionTest {
    @Test
    public void testTinhTong() {
        Solution s = new Solution();
        assertEquals(5, s.tinhTong(2, 3));
        assertEquals(0, s.tinhTong(-1, 1));
    }
}
```

---

## Cách sử dụng (CLI)

Sau khi cài đặt đầy đủ các yêu cầu, chạy pipeline từ thư mục gốc của dự án:

```bash
python run_feedback_loop.py --workspace <đường_dẫn_đến_workspace> [--max-rounds N]
```

### Các tham số

| Tham số | Bắt buộc | Mô tả | Mặc định |
|---------|----------|-------|----------|
| `--workspace` | ✅ Có | Đường dẫn tuyệt đối hoặc tương đối đến thư mục workspace chứa mã Java và `pom.xml` | *(bắt buộc)* |
| `--max-rounds` | ❌ Không | Số vòng lặp sửa lỗi tối đa | `3` |

### Ví dụ lệnh

**Chạy với workspace mặc định, tối đa 3 vòng:**
```bash
python run_feedback_loop.py --workspace ./test_workspace
```

**Chỉ định số vòng lặp tối đa:**
```bash
python run_feedback_loop.py --workspace ./test_workspace --max-rounds 5
```

**Dùng đường dẫn tuyệt đối:**
```bash
python run_feedback_loop.py --workspace /home/user/projects/my_java_project --max-rounds 3
```

### Kết quả đầu ra mẫu

```
======================================================================
[*] NCKH25-26  AI-in-the-loop Automated Debugging Pipeline
======================================================================
Workspace : ./test_workspace
Code file : ./test_workspace/src/main/java/com/example/Solution.java
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
[+] History saved → auto_grader/output/auto_fix_history/loop_20250314_210740.json

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

## Cách pipeline hoạt động

Hệ thống hoạt động theo mô hình **AI-in-the-loop** – vòng lặp phản hồi tự động có sự tham gia của AI – gồm các bước sau:

```
┌─────────────────────────────────────────────────────────────────┐
│                     run_feedback_loop.py                        │
│  (Đọc mã nguồn Java từ workspace → Khởi động LoopOrchestrator) │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LoopOrchestrator                             │
│                                                                 │
│  Lặp tối đa N vòng:                                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Bước 1: Ghi mã Java hiện tại vào workspace              │   │
│  │ Bước 2: DockerManager biên dịch + chạy JUnit test       │   │
│  │ Bước 3: LogProcessor phân tích log thô thành JSON       │   │
│  │ Bước 4: ErrorClassifier phân loại loại lỗi              │   │
│  │ Bước 5a: Nếu PASSED → Dừng, trả về kết quả thành công  │   │
│  │ Bước 5b: Nếu FAILED → LLMClient sinh mã sửa lỗi mới    │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Chi tiết từng thành phần

**1. `DockerManager` (core/docker_manager.py)**

Chạy lệnh `mvn test` bên trong container Docker được cô lập. Điều này đảm bảo:
- Mã Java được biên dịch trong môi trường sạch, nhất quán.
- Kết quả test không bị ảnh hưởng bởi phiên bản Java hay Maven trên máy chủ.
- An toàn khi chạy mã sinh ra từ AI.

**2. `LogProcessor` (execution/log_processor.py)**

Phân tích log thô từ Maven/JUnit thành một cấu trúc JSON có tổ chức, bao gồm:
- Loại lỗi: `COMPILE_ERROR`, `RUNTIME_ERROR`, `TEST_FAILED`, `PASSED`
- Chi tiết lỗi: thông báo lỗi, dòng lỗi, stack trace
- Thống kê test: số test passed/failed/error

**3. `ErrorClassifier` (execution/error_classifier.py)**

Sử dụng các quy tắc regex kết hợp với LLM để phân loại chính xác nguyên nhân gốc rễ của lỗi, cung cấp ngữ cảnh cho bước sửa lỗi.

**4. `LLMClient` (llm/llm_client.py)**

Gửi mã Java có lỗi cùng với thông tin phân tích lỗi đến mô hình **Llama 3.1** đang chạy cục bộ qua Ollama. LLM trả về:
- `fixed_code`: Phiên bản mã đã được sửa.
- `explanation`: Giải thích ngắn gọn về lỗi và cách sửa.

**5. Vòng lặp kết thúc khi:**
- Tất cả các test JUnit **PASSED** ✅ → thành công.
- Đã đạt số vòng lặp tối đa (`--max-rounds`) → thất bại.
- LLM không trả về mã sửa hợp lệ → thất bại.

Lịch sử toàn bộ quá trình sửa lỗi (từng vòng lặp) được lưu tự động vào thư mục `auto_grader/output/auto_fix_history/` dưới dạng file JSON để tiện theo dõi và phân tích.
