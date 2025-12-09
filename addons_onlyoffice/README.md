# 🚀 THG-ERP: HỆ THỐNG QUẢN LÝ TÀI NGUYÊN DOANH NGHIỆP

## 💡 Giới thiệu Chung

THG-ERP là hệ thống quản lý tài nguyên doanh nghiệp được xây dựng trên nền tảng **Odoo**, nhằm số hóa và tối ưu hóa các quy trình nghiệp vụ cốt lõi của công ty, đặc biệt là trong lĩnh vực Nhân sự và Quản lý Tài liệu.

Hệ thống được tùy chỉnh chuyên sâu, tích hợp với **OnlyOffice Document Server** để mang lại khả năng xem, tạo và chỉnh sửa tài liệu trực tuyến mạnh mẽ ngay trong Odoo mà không cần phần mềm bên ngoài.

---

## ✨ Tính năng Nổi bật (Core Features)

### 1. Quản lý Tài liệu Chuyên sâu với OnlyOffice

Tích hợp OnlyOffice giúp nâng cao khả năng xử lý tài liệu trên Odoo:

* **Xem & Chỉnh sửa Trực tuyến:** Xem, tạo mới, và chỉnh sửa các tệp tin Word, Excel, PowerPoint ngay trong Odoo thông qua **Module Tài liệu**.
* **Quản lý Thư mục & Phân quyền:** Phân quyền chi tiết cho từng tài liệu và thư mục (Folder) dựa trên vai trò người dùng Odoo.
* **Khóa Tài liệu (Document Locking):** Tự động khóa tài liệu khi một người dùng đang chỉnh sửa để ngăn chặn xung đột và bảo toàn dữ liệu.
* **Chỉnh sửa Tài liệu Liên kết:** Hỗ trợ xem và sửa tài liệu trực tiếp trên các bản ghi có liên kết với `ir.attachment` (ví dụ: Chỉnh sửa CV trong hồ sơ Nhân viên).

### 2. Tự động hóa với Template Mẫu biểu

Thiết lập các mẫu tài liệu tiêu chuẩn, giảm thiểu thao tác thủ công:

* **Cấu hình Template Đa dạng:** Thiết lập các mẫu sẵn có (Template) cho từng Model Odoo, bao gồm:
    * Template CV & Hồ sơ Nhân viên.
    * Template Thư Trúng Tuyển (Offer Letter).
    * Template Bảng Lương & Báo cáo.
    * Các mẫu Hợp đồng & Báo cáo khác.
* **Điền Dữ liệu Tự động:** Tự động điền thông tin từ bản ghi Odoo vào mẫu biểu (ví dụ: Lấy tên nhân viên, chức danh, lương từ hồ sơ nhân sự) chỉ bằng một cú nhấp chuột.

---

## 🛠️ Bắt đầu Sử dụng & Phát triển

### I. Dành cho Người dùng Mới

Để truy cập và sử dụng hệ thống, vui lòng làm theo các bước sau:

1.  Tru cập đường dẫn chính của hệ thống THG-ERP.
2.  Đăng nhập bằng tài khoản được cung cấp.
3.  Di chuyển đến Module **Tài liệu** hoặc các module nghiệp vụ liên quan (Nhân sự, Bán hàng) để bắt đầu công việc.

### II. Dành cho Nhà phát triển (DevOps)

#### A. Thêm mã nguồn

Sử dụng lệnh sau để đẩy kho lưu trữ Git hiện có của bạn lên GitLab:

```bash
cd existing_repo
git remote add origin [https://gitlab.com/edi-tech/erp/thg-erp.git](https://gitlab.com/edi-tech/erp/thg-erp.git)
git branch -M main
git push -uf origin main
