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
