-- TAI LIEU THAM KHAO - KHONG CHAY TOAN BO FILE NAY TREN DATABASE DANG CO.
-- Schema va migration chinh thuc nam trong app/database.py.
-- Cac lenh CREATE/ALTER ben duoi co the bao loi neu bang/cot da ton tai.
-- ================================================================
-- HỆ THỐNG PHÂN QUYỀN - CẤU TRÚC CƠ SỞ DỮ LIỆU
-- ================================================================

-- 1. BẢNG ROLES (Vai trò)
-- Lưu trữ các vai trò trong hệ thống
CREATE TABLE roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- Tên vai trò (admin, user, moderator)
    description TEXT                      -- Mô tả vai trò
);

-- Thêm vai trò mặc định:
-- INSERT INTO roles (id, name, description) VALUES 
-- (1, 'admin', 'Quản trị viên hệ thống'),
-- (2, 'user', 'Người dùng thông thường');


-- 2. BẢNG PERMISSIONS (Quyền)
-- Lưu trữ các quyền có sẵn trong hệ thống
CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,           -- Tên quyền (view_documents, create_document)
    description TEXT                      -- Mô tả quyền
);

-- Thêm quyền mặc định:
-- INSERT INTO permissions (id, name, description) VALUES 
-- (1, 'view_documents', 'Xem tài liệu'),
-- (2, 'create_document', 'Tạo tài liệu'),
-- (3, 'edit_document', 'Chỉnh sửa tài liệu'),
-- (4, 'delete_document', 'Xóa tài liệu'),
-- (5, 'share_document', 'Chia sẻ tài liệu'),
-- (6, 'manage_users', 'Quản lý người dùng'),
-- (7, 'manage_roles', 'Quản lý vai trò'),
-- (8, 'view_reports', 'Xem báo cáo'),
-- (9, 'manage_system', 'Quản lý hệ thống');


-- 3. BẢNG ROLE_PERMISSIONS (Liên kết vai trò - quyền)
-- Định nghĩa những quyền nào thuộc về vai trò nào
CREATE TABLE role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
);

-- Ví dụ: Gán quyền cho admin
-- INSERT INTO role_permissions (role_id, permission_id) VALUES 
-- (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (1, 6), (1, 7), (1, 8), (1, 9);

-- Ví dụ: Gán quyền cho user thông thường
-- INSERT INTO role_permissions (role_id, permission_id) VALUES 
-- (2, 1), (2, 2), (2, 3), (2, 4), (2, 5);


-- 4. BẢNG USERS (Người dùng) - CẬP NHẬT
-- Thêm trường role_id và is_active
ALTER TABLE users ADD role_id INTEGER DEFAULT 2;
ALTER TABLE users ADD is_active INTEGER DEFAULT 1;
-- ALTER TABLE users ADD FOREIGN KEY (role_id) REFERENCES roles(id);

-- Cấu trúc hoàn chỉnh của bảng users:
-- CREATE TABLE users (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     username TEXT UNIQUE NOT NULL,
--     email TEXT UNIQUE,
--     password TEXT NOT NULL,
--     role_id INTEGER DEFAULT 2,        -- Vai trò của user (mặc định là user)
--     is_active INTEGER DEFAULT 1,      -- Trạng thái hoạt động (1=active, 0=inactive)
--     FOREIGN KEY (role_id) REFERENCES roles(id)
-- );


-- ================================================================
-- CÁC QUERY THƯỜNG DÙNG
-- ================================================================

-- 1. LẤY THÔNG TIN NGƯỜI DÙNG + VAI TRÒ
SELECT u.id, u.username, u.email, r.name as role, r.description as role_description
FROM users u
LEFT JOIN roles r ON u.role_id = r.id;


-- 2. LẤY CÁC QUYỀN CỦA NGƯỜI DÙNG
SELECT DISTINCT p.id, p.name, p.description
FROM permissions p
JOIN role_permissions rp ON p.id = rp.permission_id
JOIN users u ON rp.role_id = u.role_id
WHERE u.id = 5;  -- Thay 5 bằng user_id


-- 3. LẤY CÁC QUYỀN CỦA MỘT VĂN TRÒ
SELECT p.id, p.name, p.description
FROM permissions p
JOIN role_permissions rp ON p.id = rp.permission_id
WHERE rp.role_id = 1;  -- Thay 1 bằng role_id


-- 4. KIỂM TRA NGƯỜI DÙNG CÓ QUYỀN CỤTHỂ KHÔNG
SELECT COUNT(*) as has_permission
FROM permissions p
JOIN role_permissions rp ON p.id = rp.permission_id
JOIN users u ON rp.role_id = u.role_id
WHERE u.id = 5 AND p.name = 'delete_document';  -- Thay user_id và quyền


-- 5. LẤY DANH SÁCH TẤT CẢ VAI TRÒ VÀ CÁC QUYỀN
SELECT r.id, r.name, r.description, GROUP_CONCAT(p.name, ', ') as permissions
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
GROUP BY r.id;


-- 6. KIỂM TRA NGƯỜI DÙNG CÓ PHẢI ADMIN KHÔNG
SELECT COUNT(*) as is_admin
FROM users u
JOIN roles r ON u.role_id = r.id
WHERE u.id = 5 AND r.name = 'admin';


-- 7. ĐẾM SỐ ADMIN VÀ USER
SELECT 
    COUNT(CASE WHEN r.name = 'admin' THEN 1 END) as admin_count,
    COUNT(CASE WHEN r.name = 'user' THEN 1 END) as user_count,
    COUNT(*) as total_users
FROM users u
LEFT JOIN roles r ON u.role_id = r.id;


-- 8. LẤY NHỮNG NGƯỜI KHÔNG HOẠT ĐỘNG
SELECT id, username, email, r.name as role
FROM users u
LEFT JOIN roles r ON u.role_id = r.id
WHERE u.is_active = 0;


-- ================================================================
-- CÁC HOẠT ĐỘNG QUẢN TRỊ
-- ================================================================

-- 1. THĂNG NGƯỜI DÙNG LÊN ADMIN
UPDATE users SET role_id = 1 WHERE id = 5;


-- 2. HẠ ADMIN XUỐNG USER
UPDATE users SET role_id = 2 WHERE id = 5;


-- 3. VÔ HIỆU HÓA NGƯỜI DÙNG
UPDATE users SET is_active = 0 WHERE id = 5;


-- 4. KÍCH HOẠT NGƯỜI DÙNG
UPDATE users SET is_active = 1 WHERE id = 5;


-- 5. XÓA NGƯỜI DÙNG
DELETE FROM users WHERE id = 5;


-- 6. TẠO ROLE MỚI
INSERT INTO roles (name, description) VALUES ('moderator', 'Người kiểm duyệt nội dung');


-- 7. GÁN QUYỀN CHO ROLE
INSERT INTO role_permissions (role_id, permission_id) VALUES (3, 1);  -- Gán quyền 1 cho role 3


-- 8. THU HỒI QUYỀN TỪ ROLE
DELETE FROM role_permissions WHERE role_id = 3 AND permission_id = 1;


-- 9. XÓA ROLE (và tất cả role_permissions liên kết)
-- (Được xóa tự động nhờ ON DELETE CASCADE)
DELETE FROM roles WHERE id = 3;


-- ================================================================
-- VÍ DỤ DATA
-- ================================================================

-- Thêm người dùng admin
-- INSERT INTO users (username, email, password, role_id, is_active) VALUES 
-- ('admin', 'admin@example.com', 'hashed_password', 1, 1);

-- Thêm người dùng thường
-- INSERT INTO users (username, email, password, role_id, is_active) VALUES 
-- ('john_doe', 'john@example.com', 'hashed_password', 2, 1),
-- ('jane_smith', 'jane@example.com', 'hashed_password', 2, 1);


-- ================================================================
-- THỐNG KÊ
-- ================================================================

-- Số lượng người dùng theo vai trò
SELECT r.name as role, COUNT(u.id) as user_count
FROM roles r
LEFT JOIN users u ON r.id = u.role_id
GROUP BY r.name;

-- Số lượng quyền theo vai trò
SELECT r.name as role, COUNT(p.id) as permission_count
FROM roles r
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
GROUP BY r.name;

-- Người dùng và quyền của họ (chi tiết)
SELECT 
    u.id,
    u.username,
    r.name as role,
    GROUP_CONCAT(p.name, ', ') as permissions
FROM users u
LEFT JOIN roles r ON u.role_id = r.id
LEFT JOIN role_permissions rp ON r.id = rp.role_id
LEFT JOIN permissions p ON rp.permission_id = p.id
GROUP BY u.id
ORDER BY u.id;
