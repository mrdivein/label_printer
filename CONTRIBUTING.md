# Đóng góp · Contributing

## Chạy và kiểm thử · Run and test

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m labelapp
python -m pytest tests
```

Trên Windows có thể chạy `RUN.bat`. *On Windows you can also use `RUN.bat`.*

## Cấu trúc · Layout

- `labelapp/ui/qml`: giao diện QML · QML interface
- `labelapp/bridge`: cầu nối Qt ↔ Python · Qt bridge
- `labelapp/services`, `labelapp/core`: in ấn, dữ liệu, mẫu tem · printing, data, templates
- `labelapp/i18n_en.py`: bản dịch tiếng Anh · English translation
- `tools/make_icons.py`: vẽ logo và biểu tượng · draws the logo and symbols
- `tools/make_gallery.py`: tạo kho mẫu tem · builds the template gallery

## Phát hành · Release

1. Tăng `__version__` trong `labelapp/version.py`. *Raise `__version__` in `labelapp/version.py`.*
2. Merge vào `main`: GitHub Actions chạy kiểm thử, đóng gói bộ cài và phát hành `v<version>` cùng `latest.json`.
   Ứng dụng đã cài sẽ tự cập nhật. *Merge to `main`: GitHub Actions tests, builds the installer and publishes
   release `v<version>` with `latest.json`; installed apps update themselves.*
