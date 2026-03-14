# FEEDBACK - GỢI Ý SỬA LỖI

**Thời gian:** 2026-03-15T01:13:09.850823

**Model:** llama3.1

**Loại lỗi:** COMPILE_ERROR

## 📝 Giải thích lỗi

Lỗi này xảy ra vì tên lớp không đúng. Tên lớp phải được viết hoa và trùng với tên file Java. Trong trường hợp này, tên lớp là P001_TongHaiSo nhưng file Java được đặt tên là P001_Solution.java.

## 💡 Code đã sửa

```java
package com.example;

public class P001_TongHaiSo {
    public static int tinhTong(int a, int b) {
        return a + b;
    }
}
```

## 🤔 Giải thích cách sửa

Để sửa lỗi này, chúng ta cần đổi tên lớp và tên file Java để trùng nhau. Ngoài ra, trong phương thức tinhTong, chúng ta cần thay thế dấu trừ (-) bằng dấu cộng (+) để tính tổng hai số.
