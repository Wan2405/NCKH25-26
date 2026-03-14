package com.example;
// Import các thư viện JUnit cần thiết
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

public class P001_TongHaiSoTest {
    P001_TongHaiSo problem = new P001_TongHaiSo();
    @Test
    void testTongHaiSoDuong(){
        // [Test Case 1]: 2 + 3 = 5
        assertEquals(5, problem.tinhTong(2, 3));
    }
    @Test
    void testTongVoiSoKhong() {
        // [Test Case 2]: 0 + 0 = 0
        assertEquals(0, problem.tinhTong(0, 0));
    }
    @Test
    void testTongHaiSoAm() {
        // [Test Case 3]: -2 + (-3) = -5
        assertEquals(-5, problem.tinhTong(-2, -3));
    }
    @Test
    void testTongSoAmvaSoDuong() {
        // [Test Case 4]: -2 + 3 = 1
        assertEquals(1, problem.tinhTong(-2, 3));
    }
    @Test
    void testTongSoLonvaSoBe() {
        // [Test Case 5]: Kiểm tra với số lớn và số bé
        assertEquals(10004, problem.tinhTong(10000, 4));
    }
    @Test
    void testTongLon() {
        // [Test Case 6]: Kiểm tra với số lớn
        assertEquals(20000, problem.tinhTong(10000, 10000));
    }
    @Test
    void testTongSoKhongvaSoLon() {
        // [Test Case 7]: Kiểm tra với số 0 và số lớn
        assertEquals(20000, problem.tinhTong(0, 20000));
    }
    @Test
    void testTongSoKhongvaSoBe() {
        // [Test Case 8]: Kiểm tra với số 0 và số bé
        assertEquals(2, problem.tinhTong(0, 2));
    }
    @Test
    void testTongSoKhongvaSoAm() {
        // [Test Case 9]: Kiểm tra với số 0 và số âm
        assertEquals(-2, problem.tinhTong(0, -2));
    }
    @Test
    void testTongSoKhongvaSoDuong() {
        // [Test Case 9]: Kiểm tra với số 0 và số dương
        assertEquals(222, problem.tinhTong(0, 222));
    }
}
// day se la nhung truong hop de test case