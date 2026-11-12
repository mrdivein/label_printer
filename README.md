<div align="center">

<img src="docs/logo.svg" width="112" alt="Label Printer logo">

# Label Printer

**Thiết kế và in tem nhãn, hang tag trên máy in nhiệt hoặc máy in văn phòng.**<br>
Design and print labels and hang tags on thermal or office printers.

[![Release](https://img.shields.io/github/v/release/mrdivein/label_printer?style=flat-square&color=4f5bf0&label=phi%C3%AAn%20b%E1%BA%A3n)](https://github.com/mrdivein/label_printer/releases/latest)
[![Build](https://img.shields.io/github/actions/workflow/status/mrdivein/label_printer/release.yml?style=flat-square&label=build)](https://github.com/mrdivein/label_printer/actions/workflows/release.yml)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078d4?style=flat-square&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/Qt%20Quick-PySide6-41cd52?style=flat-square&logo=qt&logoColor=white)

[**⬇ Tải bản cài đặt**](https://github.com/mrdivein/label_printer/releases/latest) &nbsp;·&nbsp;
[Tính năng](#tính-năng) &nbsp;·&nbsp; [Biểu tượng](#biểu-tượng-có-sẵn) &nbsp;·&nbsp; [Chạy từ mã nguồn](#chạy-từ-mã-nguồn)

<br>

<img src="docs/screenshot.png" width="900" alt="Màn hình thiết kế tem của Label Printer">

</div>

---

## Tính năng

<table>
<tr>
<td width="50%" valign="top">

### 🎨 Thiết kế tự do
Kéo thả chữ, mã vạch (Code 128, EAN-13, UPC…), mã QR, ảnh/logo, đường kẻ, khung và **biểu tượng** lên tem.
Kích thước tính bằng mm, có thước, lưới, căn chỉnh, xoay, nhóm phần tử và hoàn tác.

</td>
<td width="50%" valign="top">

### 📊 Gắn dữ liệu
Nối mẫu tem với cột của **Excel** hoặc **Google Sheet** bằng `{{TênCột}}`.
Quét mã vạch để tìm dòng, in một tem hay cả danh sách, hoặc dùng hàng đợi in.

</td>
</tr>
<tr>
<td valign="top">

### 🏷️ Tem gập hai mặt
Đường gập: phần dưới được in lật 180° để gập thành hang tag hai mặt.
Vùng in giúp canh nội dung trong phần giấy thực sự in được.

</td>
<td valign="top">

### 🖨️ In chính xác
In RAW ZPL cho máy in tem, hoặc qua driver Windows; xuất PDF để duyệt.
Bản in thử, bù tỉ lệ / độ lệch đo được và hồ sơ máy in lưu sẵn.

</td>
</tr>
<tr>
<td valign="top">

### 🔄 Tự cập nhật
App kiểm tra bản mới khi mở và mỗi 4 giờ, tải nền (kiểm tra dung lượng và SHA-256)
rồi hiện “Khởi động lại để cập nhật”.

</td>
<td valign="top">

### 💾 Dữ liệu của bạn được giữ
Mẫu tem, hồ sơ máy in và trạng thái làm việc nằm trong `%APPDATA%\LabelPrinter`,
không bị đụng tới khi cập nhật hay gỡ cài đặt. Mẫu tem là tệp JSON thường.

</td>
</tr>
</table>

## Biểu tượng có sẵn

Mục **Chèn → Biểu tượng** có sẵn các ký hiệu đóng gói, niêm phong và bán hàng. Chúng được in đen trắng sắc nét
(không dither) và lưu trong mẫu dưới dạng `symbol:<tên>`, nên mẫu vẫn đúng khi mở trên máy khác.

<p align="center"><img src="docs/symbols.png" width="900" alt="Các biểu tượng: dễ vỡ, hướng lên, tránh ẩm, tem niêm phong, QC đạt…"></p>

## Cài đặt (Windows)

1. Tải `Label-Printer-Setup-x.y.z.exe` ở trang [Releases](https://github.com/mrdivein/label_printer/releases/latest).
2. Chạy tệp cài đặt — không cần quyền quản trị.

`Example_Label_Data.xlsx` và các mẫu trong `templates/` là ví dụ (dữ liệu giả lập); chúng chỉ được chép vào thư viện
ở lần chạy đầu tiên, nên mẫu nào bạn đã xoá sẽ không tự quay lại.

## Chạy từ mã nguồn

```bash
pip install -r requirements.txt
python -m labelapp
```

Trên Windows có thể chạy `RUN.bat`. Kiểm thử:

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

Kiến trúc được mô tả trong [`MIGRATION_QT.md`](MIGRATION_QT.md). Logo và biểu tượng được vẽ trong
[`tools/make_icons.py`](tools/make_icons.py); chạy lại script này sau khi sửa hình.

## Phát hành

1. Tăng `__version__` trong `labelapp/version.py`.
2. Merge vào nhánh mặc định. GitHub Actions chạy kiểm thử, đóng gói exe (PyInstaller) và bộ cài
   (Inno Setup, `installer/label_printer.iss`), rồi phát hành cùng `latest.json` thành release `v<version>`.
