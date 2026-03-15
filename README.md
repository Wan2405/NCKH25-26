# NCKH25-26 – Hệ thống Gỡ lỗi Java Tự động với AI-in-the-loop

Hệ thống này tự động phát hiện và sửa các lỗi trong mã nguồn Java (lỗi biên dịch, lỗi runtime, lỗi test) bằng cách sử dụng vòng lặp phản hồi có sự tham gia của mô hình ngôn ngữ lớn (LLM – Llama 3.1 qua Ollama).

---

## Mục lục

1. [Yêu cầu cài đặt (Prerequisites)](#yêu-cầu-cài-đặt-prerequisites)
2. [Cấu trúc thư mục workspace đầu vào](#cấu-trúc-thư-mục-workspace-đầu-vào)
3. [Cách sử dụng (CLI)](#cách-sử-dụng-cli)
4. [Cách pipeline hoạt động](#cách-pipeline-hoạt-động)
5. [Cấu trúc dự án](#cấu-trúc-dự-án)
6. [Ghi chú bổ sung](#ghi-chú-bổ-sung)

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

**Build Docker image cho hệ thống:**

Trước khi chạy lần đầu, bạn cần build Docker image chứa môi trường Java và Maven:

```bash
docker build -t nckh-build-env .
```

Image này chứa:
- JDK 17 (Eclipse Temurin)
- Maven 3.9
- JUnit 5 dependencies (pre-downloaded để chạy nhanh hơn)

Nếu không build thủ công, `DockerManager` sẽ tự động build image khi chạy lần đầu.

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

**Repository này đã bao gồm workspace mẫu** trong thư mục `./workspace/` với:
- File `pom.xml` đã được cấu hình sẵn với JUnit 5 và Java 17
- Mã nguồn mẫu `Solution.java` (đã đúng - để test hệ thống)
- Bài test JUnit 5 đầy đủ trong `SolutionTest.java`

Bạn có thể sử dụng workspace mẫu này để test hệ thống hoặc tạo workspace riêng theo cấu trúc bên dưới.

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
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>sample-problem</artifactId>
    <version>1.0-SNAPSHOT</version>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <!-- JUnit 5 (Jupiter) -->
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>5.10.2</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>5.10.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.2.5</version>
            </plugin>
        </plugins>
    </build>
</project>
```

**Ví dụ mã nguồn Java có lỗi (`Solution.java`):**

```java
package com.example;

public class Solution {
    public int tinhTong(int a, int b) {
        return a - b;  // Lỗi: phép trừ thay vì phép cộng
    }
}
```

**Ví dụ bài test JUnit 5 (`SolutionTest.java`):**

```java
package com.example;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class SolutionTest {

    private final Solution solution = new Solution();

    @Test
    void testSumPositive() {
        assertEquals(5, solution.tinhTong(2, 3));
    }

    @Test
    void testSumZero() {
        assertEquals(0, solution.tinhTong(0, 0));
    }

    @Test
    void testSumMixed() {
        assertEquals(1, solution.tinhTong(-2, 3));
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

**Chạy với workspace mẫu đi kèm (đã đúng - để test hệ thống):**
```bash
python run_feedback_loop.py --workspace ./workspace
```

**Chạy với workspace tự tạo chứa code lỗi:**
```bash
python run_feedback_loop.py --workspace ./my_buggy_code
```

**Chỉ định số vòng lặp tối đa:**
```bash
python run_feedback_loop.py --workspace ./workspace --max-rounds 5
```

**Dùng đường dẫn tuyệt đối:**
```bash
python run_feedback_loop.py --workspace /home/user/projects/my_java_project --max-rounds 3
```

### Test hệ thống với workspace mẫu

Để kiểm tra hệ thống hoạt động đúng, bạn có thể sửa file `workspace/src/main/java/com/example/Solution.java`, thêm lỗi vào code (ví dụ: đổi `+` thành `-`), sau đó chạy:

```bash
python run_feedback_loop.py --workspace ./workspace
```

Hệ thống sẽ tự động phát hiện lỗi test và yêu cầu LLM sửa code.

### Kết quả đầu ra mẫu

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
[*] Running tests via Docker …
[*] Result: TEST_FAILED
[*] Requesting fix from LLM …
[+] Code updated from LLM suggestion

[Round 2/3]
----------------------------------------------------------------------
[*] Code saved → Solution.java
[*] Running tests via Docker …
[*] Result: PASSED

[+] PASSED after 2 round(s)!
[+] History saved → auto_grader/output/auto_fix_history/loop_20260315_083000.json

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

---

## Cấu trúc dự án

```
NCKH25-26/
├── run_feedback_loop.py          # Entry point chính - CLI để chạy hệ thống
├── Dockerfile                     # Docker image cho môi trường build (JDK 17 + Maven)
├── requirements.txt               # Python dependencies
├── workspace/                     # Workspace mẫu đi kèm
│   ├── pom.xml                   # Maven config với JUnit 5
│   └── src/
│       ├── main/java/            # Mã nguồn Java
│       └── test/java/            # JUnit 5 tests
├── core/                         # Module điều khiển chính
│   ├── docker_manager.py         # Quản lý Docker container, chạy mvn test
│   └── loop_orchestrator.py     # Điều khiển vòng lặp sửa lỗi
├── execution/                    # Module thực thi và phân tích
│   ├── runner.py                 # Wrapper chạy test qua Docker
│   ├── log_processor.py         # Phân tích log Maven/JUnit thành JSON
│   └── error_classifier.py      # Phân loại lỗi (compile/runtime/test)
├── llm/                          # Module tương tác với LLM
│   ├── llm_client.py            # Gọi API Ollama (Llama 3.1)
│   ├── code_sanitizer.py        # Làm sạch code từ LLM
│   └── patch_applier.py         # Áp dụng diff patch
└── auto_grader/                  # Module chấm bài (legacy + mở rộng)
    ├── modules/                  # Các module xử lý bổ sung
    │   ├── log_processor.py     # Log processor gốc
    │   ├── error_classifier.py  # Error classifier gốc
    │   ├── feedback_generator.py # Sinh feedback từ LLM
    │   ├── code_generator.py    # Sinh code từ đề bài
    │   └── auto_fixer.py        # Vòng lặp auto-fix (module mở rộng)
    ├── docker/
    │   └── run_in_docker.py     # Docker runner (Python SDK)
    └── output/                   # Thư mục chứa kết quả
        ├── auto_fix_history/     # Lịch sử sửa lỗi (JSON)
        ├── logs/                 # Log đã xử lý
        ├── classifications/      # Kết quả phân loại lỗi
        └── feedback/             # Feedback từ LLM
```

### Module chính

- **`core/`**: Điều khiển chính - Docker và vòng lặp
- **`execution/`**: Chạy test và phân tích kết quả
- **`llm/`**: Tương tác với Ollama/Llama 3.1
- **`auto_grader/`**: Module mở rộng và legacy code

---

## Ghi chú bổ sung

### Python Version
Hệ thống yêu cầu **Python 3.10 trở lên** do sử dụng type hints hiện đại (`str | None`, `from __future__ import annotations`).

### JUnit Version
Hệ thống sử dụng **JUnit 5 (Jupiter)**, không phải JUnit 4. Đảm bảo:
- Import từ `org.junit.jupiter.api.*`
- Dùng `@Test` không có `public` modifier
- Dùng `assertEquals()` từ `org.junit.jupiter.api.Assertions`

### Docker Image
Image mặc định là `nckh-build-env`. Nếu chưa build, hệ thống sẽ tự động build hoặc fallback sang `maven:3.9-eclipse-temurin-17`.

### Ollama Model
Mô hình mặc định là `llama3.1`. Có thể thay đổi trong `llm/llm_client.py` nếu cần dùng model khác.
