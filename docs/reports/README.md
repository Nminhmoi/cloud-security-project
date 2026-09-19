# Báo cáo môn An toàn thông tin

[ATTT1.pdf](ATTT1.pdf) là bản báo cáo để đọc và nộp. Nội dung được chỉnh sửa trong [ATTT1.tex](ATTT1.tex).

## Các file và thư mục

| Đường dẫn | Nội dung |
|---|---|
| `ATTT1.tex` | Mã nguồn LaTeX của báo cáo |
| `ATTT1.pdf` | Bản PDF hoàn chỉnh, được cập nhật sau khi biên dịch |
| `assets/` | Logo và hình dùng cho trình bày báo cáo |
| `evidence/` | Ảnh và dữ liệu kiểm thử dùng cho báo cáo; kết quả tạo tự động nằm trong `generated/` |
| `build/` | File tạm, log và PDF trung gian; Git bỏ qua thư mục này |
| `build.ps1` | Biên dịch hai lần rồi cập nhật PDF hoàn chỉnh |

## Cấu trúc theo quy định trình bày

Báo cáo được sắp theo tài liệu `Quy_dinh_ve_trinhbay_do_an_tot_nghiep-ban-moi.pdf` do người dùng cung cấp:

1. Bìa, bìa phụ và lời cảm ơn: không hiện số trang.
2. Mục lục, danh mục từ viết tắt, danh mục bảng, danh mục hình: số trang La Mã thường, bắt đầu từ i.
3. Mở đầu (gồm phần tóm tắt đề tài), năm chương nội dung, kết luận và hướng phát triển, tài liệu tham khảo: số trang Ả Rập, bắt đầu từ 1 ở Mở đầu.
4. Phụ lục A–F sau tài liệu tham khảo, tiếp tục số trang của nội dung.

Mục lục hiển thị tối đa ba mức. Tên đề tài nằm ở đầu trang bên phải từ Mục lục trở đi, kể cả trang đầu chương; số trang ở cuối trang bên phải. Giữ định dạng A4, Times New Roman 13 pt khi phông có sẵn, giãn dòng 1,2; lề trên/dưới 2,5 cm, trái 3,5 cm, phải 2 cm.

Giữ loại báo cáo là bài tập lớn và thông tin nhóm hiện có. Lời cảm ơn là nội dung dự thảo cần nhóm rà soát trước khi nộp. Việc sửa cấu trúc không rút gọn nội dung chuyên môn; báo cáo còn vượt mức 50–70 trang không kể phụ lục trong quy định.

Không để các tệp `ATTT1.aux`, `ATTT1.toc`, `ATTT1.lof`, `ATTT1.lot` cũ cạnh mã nguồn: MiKTeX có thể đọc chúng thay cho bản mới trong `build/`, làm mục lục và tham chiếu bị lỗi thời.

## Biên dịch trên Windows

Cài MiKTeX hoặc TeX Live có XeLaTeX, rồi chạy từ thư mục gốc dự án:

```powershell
powershell -ExecutionPolicy Bypass -File docs/reports/build.ps1
```

Script chạy trong đúng thư mục báo cáo để tìm được logo và ảnh bằng chứng. Khi cả hai lần biên dịch thành công, script chép PDF mới từ `build/` ra `ATTT1.pdf`. Nếu có lỗi, xem `build/ATTT1.log`; bản PDF hoàn chỉnh trước đó vẫn được giữ lại.

Trên Linux hoặc macOS, chạy từ thư mục gốc:

```bash
cd docs/reports
mkdir -p build
xelatex -interaction=nonstopmode -halt-on-error -no-shell-escape -output-directory=build ATTT1.tex &&
xelatex -interaction=nonstopmode -halt-on-error -no-shell-escape -output-directory=build ATTT1.tex &&
cp build/ATTT1.pdf ATTT1.pdf
```

## Bổ sung ảnh

Đặt ảnh và dữ liệu kiểm thử dùng trong báo cáo vào `evidence/`, đồng thời ghi chú trong [danh mục bằng chứng](evidence/README.md). Logo nằm tại `assets/logo.jpg`.

Script `scripts/capture_report_evidence.ps1` mặc định lưu kết quả chạy trên Windows vào `evidence/generated/windows/`, tránh ghi đè ảnh đang được báo cáo sử dụng. Có thể truyền `-OutputDirectory` để chọn một thư mục khác.

Sau khi sửa nội dung hoặc thay ảnh, biên dịch lại và lưu cả `ATTT1.tex`, ảnh liên quan và `ATTT1.pdf` trong cùng lần cập nhật. Không đưa file tạm trong `build/` vào Git.
