ECG Label Tool v21 — Rotate • Compare • Saved Sheets
=====================================================
Nâng cấp trực tiếp trên v20.2 (cùng folder, cùng app.py). Dữ liệu cũ được giữ nguyên.

GIỮ LẠI NHỮNG GÌ ĐÃ SETUP
- Template/label cũ, Calibration Profiles, workspace: vẫn nằm trong %APPDATA%\ECG_Label_Tool\ (không bị đụng tới).
- Google Sheet đã liên kết trước đây tự động được chuyển vào danh sách "Saved Google Sheets".

1) XOAY CÁC TRƯỜNG THEO GÓC BẤT KỲ (Designer)
- Chọn 1 phần tử (chữ, mã vạch, đường kẻ, khung...). Có 3 cách xoay:
  a. Kéo núm tròn vàng ↻ phía trên phần tử (giữ Shift = nhảy 15°).
  b. Gõ góc vào ô "Angle (°)" rồi Enter.
  c. Bấm nhanh ↺90 ↺15 ↺1 ↻1 ↻15 ↻90 / 0°  (áp dụng cho tất cả phần tử đang chọn).
- Góc dương = xoay theo chiều kim đồng hồ, quanh tâm phần tử. Lưu trong template dưới khoá "angle".
- Xoay hoạt động ở cả preview, in raster và in PDF vector; hoạt động cả trong vùng gập (fold).
- Các handle co giãn vẫn dùng được khi phần tử đang xoay.

2) GOOGLE SHEETS ĐƯỢC NHỚ
- Nút Data ▾ ở thanh trên: chọn lại sheet đã dùng chỉ bằng 1 click, hoặc "Add / manage Google Sheets...".
- Danh sách lưu ở %APPDATA%\ECG_Label_Tool\data_sources.json (cùng với Excel gần đây).
- Mở app lại: tự nạp lại nguồn dữ liệu cuối cùng (Google Sheet hoặc Excel).

3) SO SÁNH APP VỚI MÁY IN THỰC TẾ (Test Print ▾)
- "Current label + ruler overlay": in tem hiện tại kèm thước mm 4 cạnh + dấu + mỗi 10 mm.
  Bật "Rulers (mm)" ở tab Preview để xem đúng cùng thước trên màn hình rồi đặt tem thật cạnh màn hình để so.
- "Compare Sheet — raw": tờ so sánh không bù trừ gì (khung, 2 đường chuẩn, ô vuông 10 mm, chữ 8pt/5pt, barcode).
  Dùng thước đo: chiều dài đường ngang, đường dọc, khoảng cách từ mép tem đến khung (trái / trên).
- "Measure & Apply Compensation...": nhập 4 số đo -> app tính Width/Height scale % và Offset X/Y,
  áp dụng cho mọi lần in (lưu theo template / Profile).
- "Compare Sheet — with current compensation": in lại để kiểm tra sau khi bù.
- Thước và các dấu test là phần tử "physical": không bị lật theo vùng gập.

4) GIAO DIỆN MỚI
- Theme sáng hiện đại, header hiển thị nguồn dữ liệu + template đang dùng, bảng dữ liệu kẻ sọc,
  nút PRINT CURRENT nổi bật, Designer gọn hơn (mở 1440x900).

Cài đặt/chạy: RUN.bat (hoặc SETUP_AND_RUN.bat lần đầu). Cần: pillow, python-barcode, pywin32, reportlab, openpyxl, pymupdf.


=====================================================
V21 — BỔ SUNG: TỐI ƯU + TÍNH NĂNG KIỂU PHẦN MỀM IN TEM
=====================================================
TỐI ƯU
- In nhanh hơn: bỏ lần render thừa trong mỗi lần ghi PDF; lịch sử in dùng lại ảnh vừa gửi máy in
  (trước đây mỗi tem bị render 3 lần). Cache font và barcode.
- Chọn dòng trong bảng không còn render lại liên tục khi giữ phím mũi tên.
- Phím tắt Designer (Delete, mũi tên, Ctrl+C/V/A) không còn kích hoạt khi bạn đang gõ trong ô nhập liệu.
- In nhiều tem chạy theo từng bước, có thanh tiến trình, nút Cancel, và hỏi bỏ qua/thử lại khi lỗi.
- Print Selected / Print All trước đây không có nút trên giao diện -> nay có ở thanh trên bảng dữ liệu.

TÍNH NĂNG MỚI
- Print Queue: xem danh sách dòng sắp in, sửa số lượng từng dòng (Qty), tổng số tem,
  "Export all as PDF" gom toàn bộ tem vào 1 file PDF vector để duyệt trước.
- Template Library (nút Library): xem thumbnail, New (preset 50x68, 40x30, 100x150... hoặc kích thước tùy ý),
  Duplicate, Rename, Delete (có backup), Export.
- Phần tử mới: QR code, Barcode có in số bên dưới, Image/Logo (đường dẫn có thể chứa {{Cột}} để mỗi dòng một ảnh).
- Designer có tab "Style / Data": font, đậm, căn lề, tự thu nhỏ chữ, wrap, IN HOA/thường/Title,
  Prefix/Suffix (bỏ qua khi trống), độ dày nét, loại barcode, mức sửa lỗi QR, và "Only print if {{Cột}}"
  (ẩn phần tử khi cột trống) — không cần sửa JSON nữa.
- Designer: Ctrl+C / Ctrl+V / Ctrl+A, Shift+mũi tên = dịch 10 bước, nút ⊕H / ⊕V căn giữa tem.
