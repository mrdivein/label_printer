<div align="center">

<img src="docs/logo.svg" width="112" alt="Label Printer logo">

# Label Printer

**Thiết kế và in tem nhãn, hang tag trên máy in nhiệt hoặc máy in văn phòng.**<br>
**Design and print labels and hang tags on thermal or office printers.**

[![Release](https://img.shields.io/github/v/release/mrdivein/label_printer?style=flat-square&color=4f5bf0&label=release)](https://github.com/mrdivein/label_printer/releases/latest)
[![Build](https://img.shields.io/github/actions/workflow/status/mrdivein/label_printer/release.yml?style=flat-square&label=build)](https://github.com/mrdivein/label_printer/actions/workflows/release.yml)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078d4?style=flat-square&logo=windows&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)
![Qt](https://img.shields.io/badge/Qt%20Quick-PySide6-41cd52?style=flat-square&logo=qt&logoColor=white)

[**⬇ Tải bản cài đặt · Download**](https://github.com/mrdivein/label_printer/releases/latest) &nbsp;·&nbsp;
[Tính năng · Features](#tính-năng--features) &nbsp;·&nbsp;
[Biểu tượng · Symbols](#biểu-tượng--symbols) &nbsp;·&nbsp;
[Mã nguồn · Source](#chạy-từ-mã-nguồn--run-from-source)

<br>

<img src="docs/screenshot.png" width="900" alt="Label Printer designer">

</div>

---

## Tính năng · Features

<table>
<tr>
<td width="50%" valign="top">

### 🎨 Thiết kế tự do · Free-form design
Kéo thả chữ, mã vạch (Code 128, EAN-13, UPC…), mã QR, ảnh/logo, đường kẻ, khung và biểu tượng lên tem.
Kích thước tính bằng mm, có thước, lưới, căn chỉnh, xoay, nhóm phần tử và hoàn tác.

*Drag text, barcodes, QR codes, images, lines, boxes and symbols onto the label. Sizes in millimetres,
with rulers, grid, alignment, rotation, grouping and undo.*

</td>
<td width="50%" valign="top">

### 📊 Gắn dữ liệu · Data binding
Nối mẫu tem với cột của **Excel** hoặc **Google Sheet** bằng `{{TênCột}}`.
Quét mã vạch để tìm dòng, in một tem hay cả danh sách.

*Bind a template to Excel or Google Sheet columns with `{{Column}}`. Scan a barcode to find a row,
print one label or a whole list.*

</td>
</tr>
<tr>
<td valign="top">

### 🏷️ Tem gập hai mặt · Fold-over tags
Phần dưới đường gập được in lật 180° để gập thành hang tag hai mặt. Vùng in giúp canh nội dung.

*Everything below the fold line prints rotated 180° so the tag folds into a two-sided hang tag.*

</td>
<td valign="top">

### 🖨️ In chính xác · Accurate printing
In RAW ZPL cho máy in tem hoặc qua driver Windows; xuất PDF. In thử, bù tỉ lệ / độ lệch và hồ sơ máy in.

*RAW ZPL to label printers or the Windows driver; PDF export. Test prints, scale/offset
compensation and saved printer profiles.*

</td>
</tr>
<tr>
<td valign="top">

### 🔄 Tự cập nhật · Auto-update
Kiểm tra bản mới khi mở và mỗi 4 giờ, tải nền (kiểm tra dung lượng và SHA-256) rồi báo khởi động lại.

*Checks for a new version at start and every 4 hours, downloads it in the background (size and SHA-256
checked) and offers a restart.*

</td>
<td valign="top">

### 💾 Giữ dữ liệu của bạn · Your data stays
Mẫu tem, hồ sơ máy in và phiên làm việc nằm trong `%APPDATA%\LabelPrinter`, không bị đụng tới khi cập nhật hay gỡ.

*Templates, printer profiles and workspace live in `%APPDATA%\LabelPrinter` and survive updates
and uninstall. Templates are plain JSON.*

</td>
</tr>
</table>

## Biểu tượng · Symbols

Mục **Chèn → Biểu tượng** có sẵn ký hiệu vận chuyển, niêm phong và bán hàng, in đen trắng sắc nét.<br>
*The **Insert → Symbols** palette has shipping, seal and retail symbols, printed crisp black and white.*

<p align="center"><img src="docs/symbols.png" width="900" alt="Symbols: fragile, this way up, keep dry, seal, QC passed…"></p>

## Mẫu ví dụ · Example templates

Bốn mẫu kèm theo, dùng với `Example_Label_Data.xlsx` (dữ liệu giả lập). Chúng chỉ được chép vào thư viện ở lần
chạy đầu; mẫu bạn đã xoá sẽ không tự quay lại.<br>
*Four bundled templates for `Example_Label_Data.xlsx` (fictitious data). They are copied into the library on
first run only; templates you delete do not come back.*

<p align="center"><img src="docs/examples.png" width="900" alt="Carton label 100x50, fold hang tag 50x68, thermal hang tag 56x83, product label 60x40"></p>

## Cài đặt · Install (Windows)

1. Tải `Label-Printer-Setup-x.y.z.exe` ở [Releases](https://github.com/mrdivein/label_printer/releases/latest).
   *Download the installer from Releases.*
2. Chạy tệp cài đặt — không cần quyền quản trị. *Run it — no admin rights needed.*

## Chạy từ mã nguồn · Run from source

```bash
pip install -r requirements.txt
python -m labelapp
```

Trên Windows có thể chạy `RUN.bat`. Kiểm thử · Tests:

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

Kiến trúc · Architecture: [`MIGRATION_QT.md`](MIGRATION_QT.md).
Logo và biểu tượng được vẽ trong · Logo and symbols are drawn in [`tools/make_icons.py`](tools/make_icons.py).

## Phát hành · Release

1. Tăng `__version__` trong `labelapp/version.py`. *Raise `__version__` in `labelapp/version.py`.*
2. Merge vào nhánh mặc định: GitHub Actions chạy kiểm thử, đóng gói exe và bộ cài, rồi phát hành `v<version>`
   cùng `latest.json`. *Merge to the default branch: GitHub Actions tests, builds the exe and installer and
   publishes release `v<version>` with `latest.json`.*
