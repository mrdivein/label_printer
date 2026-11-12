"""Builds the bundled template gallery: templates/gallery/<id>.json.

    python tools/make_gallery.py

Every gallery template is an ordinary label template plus a "gallery" block (category, bilingual name and
description, sample data for the preview). The designs are generic: placeholders such as {{Product}} are
filled from the user's Excel / Google Sheet columns, and the sample data is fictitious.
"""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "templates", "gallery")


# ------------------------------------------------------------------ element helpers (all sizes in mm)
def T(text, x, y, w, h, size, bold=False, align="left", wrap=False, fit=True, font="Arial"):
    e = {"type": "text", "text": text, "x": x, "y": y, "w": w, "h": h, "font": font, "font_size": size,
         "bold": bold, "align": align, "wrap": wrap}
    if fit:
        e.update(auto_fit=True, min_font_size=round(max(3.0, size * 0.6), 1))
    return e


def BC(value, x, y, w, h, sym="code128", text=False, text_size=6.0, mw=0.25):
    e = {"type": "barcode", "value": value, "x": x, "y": y, "w": w, "h": h, "symbology": sym,
         "barcode_height_mm": round(h - (3 if text else 0.5), 2), "module_width": mw, "quiet_zone": 1.0, "show_text": text}
    if text:
        e["text_size"] = text_size
    return e


def QR(value, x, y, s, ecc="M"):
    return {"type": "qr", "value": value, "x": x, "y": y, "w": s, "h": s, "ecc": ecc}


def BOX(x, y, w, h, t=0.2):
    return {"type": "box", "x": x, "y": y, "w": w, "h": h, "thickness": t}


def FILL(x, y, w, h):
    return {"type": "fill_box", "x": x, "y": y, "w": w, "h": h}


def ELL(x, y, w, h, t=0.25):
    return {"type": "ellipse", "x": x, "y": y, "w": w, "h": h, "thickness": t}


def LINE(x, y, x2, y2, t=0.2):
    return {"type": "line", "x": x, "y": y, "x2": x2, "y2": y2, "thickness": t}


def SYM(key, x, y, s):
    return {"type": "image", "path": "symbol:" + key, "x": x, "y": y, "w": s, "h": s, "fit": "contain", "dither": False}


def FRAME(w, h, inset=0.5, t=0.2):
    return BOX(inset, inset, w - 2 * inset, h - 2 * inset, t)


# ------------------------------------------------------------------ sample data (fictitious)
S_PRODUCT = {"Brand": "AURORA", "Product": "Bình giữ nhiệt inox 500ml", "Model": "AR-500", "Size": "500ml",
             "Color": "Xanh rêu", "Barcode": "8935001234567", "SKU": "SKU-001", "Price": "289.000 ₫",
             "Origin": "Việt Nam", "Description": "Giữ nóng 12h, giữ lạnh 24h"}

CATEGORIES = [
    ("product", "Tem sản phẩm", "Product labels", "▣"),
    ("price", "Tem giá", "Price tags", "₫"),
    ("barcode", "Tem mã vạch", "Barcode labels", "▥"),
    ("qr", "Tem mã QR", "QR code labels", "▦"),
    ("shipping", "Tem vận chuyển", "Shipping", "⛟"),
    ("eyewear", "Tem kính mắt", "Eyewear", "◎"),
    ("apparel", "Thời trang & hang tag", "Apparel & hang tags", "◇"),
    ("cosmetics", "Mỹ phẩm", "Cosmetics", "✿"),
    ("food", "Thực phẩm & đồ uống", "Food & drink", "☕"),
    ("jewelry", "Trang sức", "Jewelry", "◆"),
    ("warehouse", "Kho & tài sản", "Warehouse & assets", "▤"),
    ("electronics", "Điện tử & bảo hành", "Electronics & warranty", "⚡"),
    ("seal", "Niêm phong & QC", "Seal & QC", "✓"),
    ("office", "Địa chỉ & văn phòng", "Address & office", "✉"),
]

TEMPLATES = []


def tpl(tid, cat, w, h, name_vi, name_en, desc_vi, desc_en, elements, sample=None, popular=False, dpi=300, **extra):
    TEMPLATES.append(dict(id=tid, category=cat, w=w, h=h, name_vi=name_vi, name_en=name_en, desc_vi=desc_vi,
                          desc_en=desc_en, elements=elements, sample=sample or {}, popular=popular, dpi=dpi, extra=extra))


# ================================================================== product
tpl("product_60x40", "product", 60, 40, "Tem sản phẩm 60×40", "Product label 60×40",
    "Thương hiệu, tên hàng, giá và mã vạch Code 128 — khổ tem cuộn phổ biến nhất.",
    "Brand, product name, price and a Code 128 barcode — the most common roll size.", [
        FRAME(60, 40),
        T("{{Brand}}", 2.5, 2, 34, 5, 11, True),
        T("{{Price}}", 37, 2.4, 20.5, 4.4, 9, True, "right"),
        T("{{Product}}", 2.5, 8, 55, 3.6, 7, True),
        T("{{Model}} · {{Size}} · {{Color}}", 2.5, 12, 55, 3, 5.5),
        BC("{{Barcode}}", 5, 16.5, 50, 14),
        T("{{Barcode}}", 2, 31.5, 56, 2.8, 6, True, "center"),
        T("Xuất xứ: {{Origin}}", 2, 35.2, 56, 2.6, 4.8, align="center"),
    ], S_PRODUCT, popular=True)

tpl("product_50x30", "product", 50, 30, "Tem sản phẩm 50×30", "Product label 50×30",
    "Tên sản phẩm trên, mã vạch có số bên dưới — gọn cho hàng tạp hoá.",
    "Product name on top, barcode with digits below — compact for grocery items.", [
        T("{{Product}}", 2, 1.5, 46, 4.5, 8, True, "center"),
        T("{{Model}}  ·  {{Size}}", 2, 6.3, 46, 3, 5.5, align="center"),
        BC("{{Barcode}}", 3, 10, 44, 14, "ean13", True, 6),
        T("{{Price}}", 2, 25, 46, 4, 9, True, "center"),
    ], S_PRODUCT, popular=True)

tpl("product_70x50_detail", "product", 70, 50, "Tem thông tin sản phẩm 70×50", "Product info label 70×50",
    "Đủ thông tin theo quy định nhãn hàng hoá: tên, thành phần, xuất xứ, nhà phân phối, mã vạch.",
    "Full product-labelling details: name, composition, origin, distributor and barcode.", [
        FRAME(70, 50),
        T("{{Product}}", 3, 2.5, 64, 5, 10, True),
        LINE(3, 8.5, 67, 8.5),
        T("Mã hàng: {{Model}}", 3, 10, 40, 3, 6),
        T("Quy cách: {{Size}}", 3, 13.5, 40, 3, 6),
        T("Màu: {{Color}}", 3, 17, 40, 3, 6),
        T("Xuất xứ: {{Origin}}", 3, 20.5, 40, 3, 6),
        T("{{Description}}", 3, 24.5, 40, 7, 5.5, wrap=True),
        QR("{{SKU}}", 47, 10, 19),
        BC("{{Barcode}}", 3, 33, 46, 13, "ean13", True, 6),
        T("{{Price}}", 50, 36, 17, 6, 10, True, "right"),
    ], S_PRODUCT)

tpl("product_40x30_mini", "product", 40, 30, "Tem sản phẩm mini 40×30", "Mini product label 40×30",
    "Tên + giá + mã vạch trên tem nhỏ, dán vừa hộp phụ kiện.",
    "Name + price + barcode on a small label that fits accessory boxes.", [
        T("{{Product}}", 1.5, 1.2, 37, 4, 7, True, "center"),
        BC("{{Barcode}}", 2, 6, 36, 13, "code128"),
        T("{{Barcode}}", 1.5, 19.3, 37, 2.6, 5, align="center"),
        LINE(4, 22.6, 36, 22.6, 0.15),
        T("{{Price}}", 1.5, 23.5, 37, 5, 10, True, "center"),
    ], S_PRODUCT)

# ================================================================== price
tpl("price_40x30_big", "price", 40, 30, "Tem giá to 40×30", "Big price tag 40×30",
    "Giá chữ lớn nhìn rõ từ xa, kèm tên hàng và mã vạch.",
    "Large price readable from afar, with item name and barcode.", [
        T("{{Product}}", 1.5, 1.2, 37, 3.6, 6.5, True),
        T("{{Price}}", 1.5, 5.5, 37, 10, 22, True, "center"),
        BC("{{Barcode}}", 4, 17, 32, 9.5),
        T("{{Barcode}}", 1.5, 26.6, 37, 2.5, 5, align="center"),
    ], S_PRODUCT, popular=True)

tpl("price_sale_50x30", "price", 50, 30, "Tem giảm giá 50×30", "Sale price tag 50×30",
    "Giá cũ, giá mới và % giảm nổi bật — dùng cho đợt khuyến mãi.",
    "Old price, new price and the discount — for promotions.", [
        LINE(0, 6.5, 50, 6.5, 0.4),
        SYM("sale", 1.5, 7.5, 10),
        T("{{Product}}", 2, 0.8, 46, 4.5, 7, True, "center"),
        T("Giá cũ: {{OldPrice}}", 13, 8, 35, 3.5, 6),
        T("{{Price}}", 13, 12, 35, 8, 16, True),
        T("Giảm {{Discount}}", 2, 21, 46, 3.5, 7, True, "center"),
        T("{{Barcode}}", 2, 25.5, 46, 3, 5, align="center"),
    ], dict(S_PRODUCT, OldPrice="359.000 ₫", Discount="20%"))

tpl("price_shelf_70x30", "price", 70, 30, "Tem giá kệ 70×30", "Shelf price tag 70×30",
    "Nẹp giá kệ siêu thị: tên, đơn vị tính, giá và mã vạch.",
    "Supermarket shelf edge label: name, unit, price and barcode.", [
        FRAME(70, 30),
        T("{{Product}}", 2.5, 2, 40, 6, 9, True, wrap=True),
        T("ĐVT: {{Unit}}", 2.5, 9, 40, 3, 6),
        BC("{{Barcode}}", 2.5, 14, 36, 13, "ean13", True, 5.5),
        LINE(42, 2, 42, 28),
        T("{{Price}}", 43, 6, 25, 9, 15, True, "center"),
        T("Ngày in: {{Date}}", 43, 24, 25, 3, 5, align="center"),
    ], dict(S_PRODUCT, Unit="Chai", Date="12/11/2026"))

tpl("price_jewelry_round_30", "price", 30, 30, "Tem giá tròn 30×30", "Round price sticker 30×30",
    "Tem tròn dán giá trên hộp quà, lọ, nắp hũ.",
    "Round price sticker for gift boxes, jars and lids.", [
        ELL(0.8, 0.8, 28.4, 28.4, 0.3),
        T("{{Brand}}", 4, 6, 22, 4, 7, True, "center"),
        T("{{Price}}", 3, 11.5, 24, 7, 12, True, "center"),
        T("{{Size}}", 4, 19.5, 22, 3.5, 6, align="center"),
    ], S_PRODUCT)

# ================================================================== barcode
tpl("barcode_30x20", "barcode", 30, 20, "Tem mã vạch 30×20", "Barcode label 30×20",
    "Chỉ mã vạch, phủ kín tem — quét nhanh nhất.",
    "Barcode only, edge to edge — fastest to scan.", [
        BC("{{SKU}}", 1, 1.5, 28, 13),
        T("{{SKU}}", 1, 15, 28, 4, 9, True, "center", font="Consolas"),
    ], S_PRODUCT, popular=True)

tpl("barcode_50x25", "barcode", 50, 25, "Tem mã vạch 50×25", "Barcode label 50×25",
    "Tên hàng phía trên, mã vạch phía dưới.",
    "Item name on top, barcode below.", [
        T("{{Product}}", 2, 1.2, 46, 4, 7, True, "center"),
        BC("{{SKU}}", 3, 6, 44, 13),
        T("{{SKU}}", 2, 19.5, 46, 4, 8, align="center", font="Consolas"),
    ], S_PRODUCT, popular=True)

tpl("barcode_ean13_40x25", "barcode", 40, 25, "Tem EAN-13 40×25", "EAN-13 label 40×25",
    "Mã EAN-13 chuẩn bán lẻ có số dưới vạch, kèm mã nội bộ.",
    "Retail EAN-13 with human-readable digits, plus an internal code.", [
        T("{{Brand}} · {{Model}}", 1.5, 1, 37, 3.5, 6, True, "center"),
        BC("{{Barcode}}", 2, 5, 36, 16, "ean13", True, 6.5),
        T("{{SKU}}", 1.5, 21.5, 37, 3, 5.5, align="center"),
    ], S_PRODUCT)

# ================================================================== qr
tpl("qr_asset_60x30", "qr", 60, 30, "Tem tài sản QR 60×30", "QR asset tag 60×30",
    "Tên tài sản, mã tài sản và QR tra cứu, có khung viền.",
    "Asset name, asset code and a lookup QR, framed.", [
        BOX(0.6, 0.6, 58.8, 28.8, 0.3),
        T("{{Owner}}", 2.5, 2, 34, 3, 5.5),
        T("{{AssetName}}", 2.5, 6, 34, 8, 9, True, wrap=True),
        T("Mã tài sản: {{AssetCode}}", 2.5, 16, 34, 3.5, 6.5, True),
        T("Ngày cấp: {{Date}}", 2.5, 21, 34, 3, 5.5),
        QR("{{AssetCode}}", 38, 3, 20),
        T("{{AssetCode}}", 36.5, 24, 23, 3, 5, align="center"),
    ], {"Owner": "PHÒNG HÀNH CHÍNH", "AssetName": "Laptop văn phòng 14 inch", "AssetCode": "TS-2026-0042",
        "Date": "12/11/2026"}, popular=True)

tpl("qr_menu_60x40", "qr", 60, 40, "Tem QR menu 60×40", "QR menu sticker 60×40",
    "Dán bàn quán: tên quán, lời mời quét QR xem menu / gọi món.",
    "Table sticker: shop name and a scan-for-menu QR.", [
        FRAME(60, 40, 0.6, 0.3),
        T("{{Shop}}", 3, 3, 30, 6, 11, True),
        T("Quét mã để xem menu & gọi món", 3, 11, 30, 8, 7, wrap=True),
        T("Bàn {{Table}}", 3, 22, 30, 8, 16, True),
        QR("{{MenuURL}}", 34, 5, 23, "Q"),
        T("Wi-Fi: {{Wifi}}", 3, 33, 54, 3.5, 6, align="center"),
    ], {"Shop": "CÀ PHÊ MẪU", "Table": "05", "MenuURL": "https://example.com/menu", "Wifi": "Mau_Guest"})

tpl("qr_product_50x30", "qr", 50, 30, "Tem sản phẩm QR 50×30", "Product QR label 50×30",
    "QR dẫn tới trang sản phẩm / hướng dẫn sử dụng, kèm tên và mã hàng.",
    "QR linking to the product page / manual, with name and item code.", [
        QR("{{URL}}", 1.5, 2, 26),
        T("{{Product}}", 29, 2.5, 19.5, 12, 7, True, wrap=True),
        T("{{SKU}}", 29, 16, 19.5, 3.5, 6),
        T("Quét để xem hướng dẫn", 29, 21, 19.5, 6, 5, wrap=True),
    ], dict(S_PRODUCT, URL="https://example.com/p/sku-001"))

tpl("qr_wifi_50x50", "qr", 50, 50, "Tem QR Wi-Fi 50×50", "Wi-Fi QR sticker 50×50",
    "Quét để kết nối Wi-Fi — giá trị QR theo chuẩn WIFI:T:WPA;S:…;P:…;;",
    "Scan to join Wi-Fi — QR value in the WIFI:T:WPA;S:…;P:…;; format.", [
        FRAME(50, 50, 0.6, 0.3),
        T("Wi-Fi miễn phí", 2, 2.5, 46, 5, 11, True, "center"),
        QR("WIFI:T:WPA;S:{{Wifi}};P:{{Password}};;", 10, 9, 30, "Q"),
        T("Mạng: {{Wifi}}", 2, 40.5, 46, 3.5, 7, True, "center"),
        T("Mật khẩu: {{Password}}", 2, 44.5, 46, 3.5, 6.5, align="center"),
    ], {"Wifi": "Mau_Guest", "Password": "12345678"})

# ================================================================== shipping
tpl("ship_100x150", "shipping", 100, 150, "Phiếu giao hàng 100×150", "Shipping label 100×150",
    "Khổ A6 chuẩn sàn TMĐT: người gửi, người nhận, mã vận đơn, COD.",
    "Standard 4×6 e-commerce label: sender, recipient, tracking number, COD.", [
        FRAME(100, 150, 1, 0.4),
        T("{{Carrier}}", 4, 4, 50, 8, 16, True),
        T("{{Route}}", 56, 4, 40, 8, 16, True, "right"),
        LINE(1, 14, 99, 14, 0.4),
        BC("{{Tracking}}", 6, 17, 88, 22),
        T("{{Tracking}}", 4, 40, 92, 5, 10, True, "center", font="Consolas"),
        LINE(1, 47, 99, 47, 0.4),
        T("Từ:", 4, 49.5, 12, 4, 7, True),
        T("{{SenderName}} · {{SenderPhone}}", 16, 49.5, 80, 4, 7),
        T("{{SenderAddress}}", 16, 54, 80, 8, 6.5, wrap=True),
        LINE(1, 64, 99, 64, 0.2),
        T("Đến:", 4, 66.5, 12, 5, 9, True),
        T("{{ReceiverName}}", 16, 66.5, 80, 6, 12, True),
        T("{{ReceiverPhone}}", 16, 73.5, 80, 5, 10, True),
        T("{{ReceiverAddress}}", 16, 80, 80, 16, 9, wrap=True),
        LINE(1, 98, 99, 98, 0.4),
        T("Nội dung: {{Contents}}", 4, 100.5, 60, 10, 7, wrap=True),
        T("Khối lượng: {{Weight}}", 4, 112, 60, 4, 7),
        QR("{{Tracking}}", 70, 100, 26),
        LINE(1, 128, 99, 128, 0.4),
        T("Thu hộ (COD):", 4, 130.5, 40, 5, 9, True),
        T("{{COD}}", 40, 130, 56, 9, 18, True, "right"),
        T("Ngày gửi: {{Date}}", 4, 142, 92, 4, 6.5),
    ], {"Carrier": "GIAO NHANH", "Route": "HCM-Q1-03", "Tracking": "GN2026111200421",
        "SenderName": "Shop Mẫu", "SenderPhone": "0900 000 000", "SenderAddress": "12 Đường Mẫu, Phường 1, Quận 1, TP. HCM",
        "ReceiverName": "Nguyễn Văn A", "ReceiverPhone": "0911 111 111",
        "ReceiverAddress": "34 Đường Ví Dụ, Phường 2, Quận 3, TP. Hồ Chí Minh",
        "Contents": "Bình giữ nhiệt x2", "Weight": "1.2 kg", "COD": "578.000 ₫", "Date": "12/11/2026"}, popular=True)

tpl("ship_carton_100x50", "shipping", 100, 50, "Tem thùng carton 100×50", "Carton label 100×50",
    "Mã thùng, số lượng, PO và ký hiệu vận chuyển cho kho.",
    "Carton number, quantity, PO and handling symbols for the warehouse.", [
        FRAME(100, 50, 0.6, 0.3),
        T("{{Product}}", 3, 2.5, 66, 6, 11, True),
        T("PO: {{PO}}", 3, 9.5, 40, 4, 8, True),
        T("Thùng {{CartonNo}} / {{CartonTotal}}", 3, 14.5, 40, 4.5, 9, True),
        T("SL: {{Qty}} cái · {{Weight}}", 3, 20, 66, 4, 7.5),
        BC("{{CartonID}}", 3, 26, 66, 16),
        T("{{CartonID}}", 3, 43, 66, 4, 7, True, "center"),
        LINE(71, 2, 71, 48),
        SYM("fragile", 74, 3, 11), SYM("this_way_up", 86, 3, 11),
        SYM("keep_dry", 74, 16, 11), SYM("do_not_stack", 86, 16, 11),
        T("{{Destination}}", 72.5, 30, 26, 16, 10, True, "center", wrap=True),
    ], {"Product": "Bình giữ nhiệt inox 500ml", "PO": "PO-26-1108", "CartonNo": "3", "CartonTotal": "12",
        "Qty": "24", "Weight": "9.6 kg", "CartonID": "CTN-26-1108-003", "Destination": "KHO HÀ NỘI"})

tpl("ship_fragile_100x70", "shipping", 100, 70, "Tem hàng dễ vỡ 100×70", "Fragile handling label 100×70",
    "Cảnh báo HÀNG DỄ VỠ cỡ lớn với biểu tượng xử lý hàng.",
    "Large FRAGILE warning with handling symbols.", [
        BOX(1, 1, 98, 68, 0.8),
        T("HÀNG DỄ VỠ", 4, 4, 92, 14, 30, True, "center"),
        T("FRAGILE · HANDLE WITH CARE", 4, 19, 92, 6, 12, True, "center"),
        SYM("fragile", 8, 30, 24), SYM("this_way_up", 38, 30, 24), SYM("keep_dry", 68, 30, 24),
        T("Nhẹ tay · Không quăng ném · Đặt đúng chiều", 4, 58, 92, 6, 9, align="center"),
    ])

tpl("ship_return_100x75", "shipping", 100, 75, "Tem đổi trả hàng 100×75", "Return label 100×75",
    "Phiếu hoàn hàng: mã đơn, lý do, người nhận và mã vạch tra cứu.",
    "Return slip: order number, reason, recipient and lookup barcode.", [
        FRAME(100, 75, 0.6, 0.3),
        LINE(0.6, 9.6, 99.4, 9.6, 0.5),
        T("HÀNG HOÀN / RETURN", 3, 1.5, 94, 7, 12, True, "center"),
        T("Mã đơn: {{Order}}", 4, 13, 60, 5, 9, True),
        T("Lý do: {{Reason}}", 4, 19, 60, 9, 7, wrap=True),
        T("Gửi về: {{ReceiverName}}", 4, 30, 92, 5, 8, True),
        T("{{ReceiverAddress}}", 4, 35.5, 92, 9, 7, wrap=True),
        BC("{{Order}}", 4, 47, 70, 20),
        T("{{Order}}", 4, 67.5, 70, 4, 7, align="center"),
        QR("{{Order}}", 77, 47, 20),
    ], {"Order": "DH-26110042", "Reason": "Đổi size", "ReceiverName": "Kho hoàn hàng",
        "ReceiverAddress": "56 Đường Mẫu, KCN Ví Dụ, Bình Dương"})

# ================================================================== eyewear
tpl("eyewear_temple_tag", "eyewear", 22, 70, "Tem đuôi kính (gập) 22×70", "Eyewear temple tag 22×70",
    "Tem treo càng kính gập đôi: mặt trước thương hiệu + mẫu, mặt sau mã vạch + giá.",
    "Fold-over tag for the temple arm: brand + model on the front, barcode + price on the back.", [
        T("{{Brand}}", 1, 2, 20, 4.5, 8, True, "center"),
        T("{{Model}}", 1, 7.5, 20, 3.5, 6.5, True, "center"),
        T("{{Color}} · {{Size}}", 1, 11.5, 20, 3, 5, align="center"),
        T("{{Price}}", 1, 16, 20, 5, 9, True, "center"),
        BC("{{Barcode}}", 1, 50, 20, 11),
        T("{{Barcode}}", 1, 61.5, 20, 2.5, 4.5, align="center"),
        T("Xuất xứ: {{Origin}}", 1, 64.5, 20, 2.5, 4.2, align="center"),
    ], {"Brand": "LUMEN", "Model": "LM-1203", "Color": "C02 Đen", "Size": "52□18-145", "Price": "2.450.000 ₫",
        "Barcode": "8935001234567", "Origin": "Ý"}, popular=True,
    fold_regions=[{"name": "BACK", "x": 0, "y": 46, "w": 22, "h": 24, "angle": 180, "enabled": True}],
    preview_guides=[{"name": "Front", "type": "box", "x": 0, "y": 0, "w": 22, "h": 24, "color": "blue", "show": True},
                    {"name": "Back", "type": "box", "x": 0, "y": 46, "w": 22, "h": 24, "color": "green", "show": True}])

tpl("eyewear_box_60x30", "eyewear", 60, 30, "Tem hộp kính 60×30", "Eyewear box label 60×30",
    "Dán hộp kính: thương hiệu, mã mẫu, màu, cỡ mắt-cầu-càng và mã vạch.",
    "Glasses box label: brand, model, colour, eye-bridge-temple size and barcode.", [
        T("{{Brand}}", 2, 1.5, 36, 5, 10, True),
        T("{{Model}}", 2, 7, 36, 4, 8, True),
        T("Màu: {{Color}}", 2, 11.5, 36, 3, 6),
        T("Cỡ: {{Size}}", 2, 15, 36, 3, 6),
        T("{{Price}}", 2, 19, 36, 5, 9, True),
        BC("{{Barcode}}", 39, 2, 19.5, 20, "ean13", True, 5),
        T("{{Origin}}", 39, 24, 19.5, 3, 5, align="center"),
    ], {"Brand": "LUMEN", "Model": "LM-1203", "Color": "C02 Đen", "Size": "52□18-145", "Price": "2.450.000 ₫",
        "Barcode": "8935001234567", "Origin": "Made in Italy"})

tpl("eyewear_lens_50x30", "eyewear", 50, 30, "Tem tròng kính 50×30", "Lens envelope label 50×30",
    "Thông số tròng: độ cầu, độ loạn, trục, chiết suất, lớp phủ — cho bao tròng / phiếu cắt kính.",
    "Lens data: sphere, cylinder, axis, index and coating — for lens envelopes / job tickets.", [
        FRAME(50, 30),
        T("{{Customer}}", 2, 1.5, 46, 4, 7, True),
        LINE(2, 6, 48, 6, 0.15),
        T("MP  SPH {{R_SPH}}  CYL {{R_CYL}}  AX {{R_AX}}", 2, 7, 46, 3.5, 6, font="Consolas"),
        T("MT  SPH {{L_SPH}}  CYL {{L_CYL}}  AX {{L_AX}}", 2, 11, 46, 3.5, 6, font="Consolas"),
        T("PD {{PD}} · Chiết suất {{Index}} · {{Coating}}", 2, 15.5, 46, 3.2, 5.5),
        BC("{{Job}}", 2, 19.5, 30, 9),
        T("{{Job}}", 33, 21.5, 15, 5, 6, True, "center"),
    ], {"Customer": "Khách: Trần Thị B", "R_SPH": "-2.25", "R_CYL": "-0.50", "R_AX": "180",
        "L_SPH": "-2.00", "L_CYL": "-0.75", "L_AX": "175", "PD": "62", "Index": "1.60", "Coating": "Chống ánh sáng xanh",
        "Job": "JK-0421"})

tpl("eyewear_display_40x25", "eyewear", 40, 25, "Tem giá trưng bày kính 40×25", "Eyewear display price 40×25",
    "Tem nhỏ đặt trên kệ trưng bày gọng kính: mẫu, giá, chất liệu.",
    "Small display card for frames: model, price, material.", [
        T("{{Brand}}", 1.5, 1.2, 37, 4, 8, True, "center"),
        T("{{Model}} · {{Color}}", 1.5, 5.5, 37, 3, 5.5, align="center"),
        LINE(6, 9.5, 34, 9.5, 0.15),
        T("{{Price}}", 1.5, 10.5, 37, 7, 13, True, "center"),
        T("{{Material}}", 1.5, 18.5, 37, 3, 5.5, align="center"),
        T("{{Barcode}}", 1.5, 21.6, 37, 2.6, 4.5, align="center"),
    ], {"Brand": "LUMEN", "Model": "LM-1203", "Color": "C02", "Price": "2.450.000 ₫", "Material": "Gọng Titan",
        "Barcode": "8935001234567"})

# ================================================================== apparel
tpl("apparel_hangtag_50x90", "apparel", 50, 90, "Hang tag quần áo 50×90", "Clothing hang tag 50×90",
    "Hang tag treo: thương hiệu, tên sản phẩm, size, màu, giá, mã vạch và lỗ xỏ dây.",
    "Swing tag: brand, product, size, colour, price, barcode and a string hole.", [
        ELL(22.5, 3, 5, 5, 0.3),
        T("{{Brand}}", 2, 11, 46, 8, 16, True, "center"),
        LINE(10, 21, 40, 21, 0.2),
        T("{{Product}}", 3, 24, 44, 9, 8, True, "center", wrap=True),
        T("Size", 3, 36, 20, 3, 6, align="center"),
        T("Màu", 27, 36, 20, 3, 6, align="center"),
        BOX(5, 39.5, 16, 10, 0.3),
        T("{{Size}}", 5, 41.5, 16, 6, 13, True, "center"),
        T("{{Color}}", 27, 41.5, 20, 6, 8, True, "center"),
        T("{{Price}}", 2, 54, 46, 8, 15, True, "center"),
        BC("{{Barcode}}", 4, 66, 42, 16, "ean13", True, 6.5),
        T("{{Model}} · {{Origin}}", 2, 84, 46, 3, 5.5, align="center"),
    ], {"Brand": "MAU STUDIO", "Product": "Áo sơ mi linen tay dài", "Size": "M", "Color": "Trắng kem",
        "Price": "690.000 ₫", "Barcode": "8935001234574", "Model": "SM-LN-02", "Origin": "Việt Nam"}, popular=True)

tpl("apparel_care_30x60", "apparel", 30, 60, "Nhãn may hướng dẫn giặt 30×60", "Care label 30×60",
    "Nhãn may vào đường may: thành phần vải, hướng dẫn giặt ủi, xuất xứ.",
    "Sewn-in care label: fabric composition, washing instructions, origin.", [
        T("{{Brand}}", 1.5, 3, 27, 4, 8, True, "center"),
        T("Size {{Size}}", 1.5, 8, 27, 4, 8, True, "center"),
        T("{{Fabric}}", 1.5, 13, 27, 8, 6, align="center", wrap=True),
        LINE(4, 22, 26, 22, 0.15),
        T("Giặt tay hoặc giặt máy nhẹ ≤ 30°C\nKhông tẩy\nỦi nhiệt độ thấp\nKhông sấy khô", 1.5, 23.5, 27, 20, 5.5,
          align="center", wrap=True),
        T("Sản xuất tại {{Origin}}", 1.5, 50, 27, 3, 5, align="center"),
        T("{{Model}}", 1.5, 54, 27, 3, 5, align="center"),
    ], {"Brand": "MAU STUDIO", "Size": "M", "Fabric": "100% Linen", "Origin": "Việt Nam", "Model": "SM-LN-02"})

tpl("apparel_size_sticker_30x20", "apparel", 30, 20, "Tem size dán túi 30×20", "Bag size sticker 30×20",
    "Size chữ to + mã hàng, dán ngoài túi bóng để soạn hàng nhanh.",
    "Big size letter + item code on the poly bag for fast picking.", [
        BOX(0.6, 0.6, 28.8, 18.8, 0.3),
        T("{{Size}}", 1, 1.5, 12, 11, 22, True, "center"),
        LINE(13.5, 2, 13.5, 13, 0.2),
        T("{{Color}}", 14.5, 2.5, 14, 5, 6, True, wrap=True),
        T("{{Model}}", 14.5, 8, 14, 4, 5.5),
        BC("{{Barcode}}", 2, 14, 26, 5),
    ], {"Size": "XL", "Color": "Đen", "Model": "AT-01", "Barcode": "8935001234581"})

# ================================================================== cosmetics
tpl("cosmetic_50x30", "cosmetics", 50, 30, "Tem mỹ phẩm 50×30", "Cosmetic label 50×30",
    "Thương hiệu, tên sản phẩm, dung tích, HSD và mã vạch.",
    "Brand, product name, volume, expiry and barcode.", [
        T("{{Brand}}", 2, 1.5, 46, 4, 7, True, "center"),
        T("{{Product}}", 2, 6, 46, 5, 9, True, "center"),
        T("{{Size}}  ·  HSD: {{Expiry}}", 2, 11.5, 46, 3, 5.5, align="center"),
        BC("{{Barcode}}", 4, 15.5, 42, 13, "ean13", True, 5.5),
    ], {"Brand": "LUNA SKIN", "Product": "Serum dưỡng ẩm B5", "Size": "30ml", "Expiry": "11/2028",
        "Barcode": "8935001234598"}, popular=True)

tpl("cosmetic_ingredients_60x40", "cosmetics", 60, 40, "Nhãn phụ mỹ phẩm 60×40", "Cosmetic sub-label 60×40",
    "Nhãn phụ tiếng Việt cho hàng nhập: thành phần, công dụng, số công bố, nhà nhập khẩu.",
    "Vietnamese sub-label for imports: ingredients, use, notification no., importer.", [
        FRAME(60, 40),
        T("{{Product}}", 2, 1.5, 56, 4, 7.5, True),
        T("Thành phần: {{Ingredients}}", 2, 6, 56, 9, 4.8, wrap=True),
        T("Công dụng: {{Usage}}", 2, 15.5, 56, 5, 4.8, wrap=True),
        T("Số CB: {{Notification}} · NSX: {{MFG}} · HSD: {{Expiry}}", 2, 21, 56, 3, 4.8),
        T("Nhập khẩu & phân phối: {{Importer}}", 2, 24.5, 56, 3, 4.8),
        BC("{{Barcode}}", 2, 28.5, 34, 10, "ean13", True, 4.5),
        T("{{Size}}", 38, 30, 20, 7, 11, True, "right"),
    ], {"Product": "Serum dưỡng ẩm B5", "Ingredients": "Aqua, Glycerin, Panthenol, Niacinamide, Sodium Hyaluronate…",
        "Usage": "Dưỡng ẩm, làm dịu da.", "Notification": "000123/26/CBMP-HCM", "MFG": "11/2026", "Expiry": "11/2029",
        "Importer": "Công ty Mẫu", "Barcode": "8935001234598", "Size": "30ml"})

tpl("cosmetic_round_40", "cosmetics", 40, 40, "Tem tròn nắp hũ 40×40", "Jar lid round label 40×40",
    "Tem tròn cho nắp hũ kem: thương hiệu, tên, khối lượng.",
    "Round lid label for cream jars: brand, name, weight.", [
        ELL(0.8, 0.8, 38.4, 38.4, 0.3),
        ELL(3, 3, 34, 34, 0.15),
        T("{{Brand}}", 6, 9, 28, 5, 9, True, "center"),
        T("{{Product}}", 6, 15, 28, 8, 7, align="center", wrap=True),
        T("{{Size}}", 6, 25, 28, 5, 9, True, "center"),
    ], {"Brand": "LUNA SKIN", "Product": "Kem dưỡng ban đêm", "Size": "50g"})

# ================================================================== food
tpl("food_coffee_cup_60x40", "food", 60, 40, "Tem ly cà phê 60×40", "Coffee cup label 60×40",
    "Tên món, tuỳ chọn, giá và QR menu — dán nắp ly.",
    "Drink name, options, price and menu QR — for cup lids.", [
        T("{{Shop}}", 2, 1.5, 40, 4, 7, True),
        T("{{Item}}", 2, 6, 40, 7, 12, True),
        T("{{Options}}", 2, 13.5, 40, 6, 6, wrap=True),
        T("{{Price}}", 2, 21, 40, 6, 11, True),
        T("Đơn {{Order}} · {{Time}}", 2, 29, 40, 3.5, 6),
        T("{{Customer}}", 2, 33.5, 40, 4.5, 8, True),
        QR("{{MenuURL}}", 43, 3, 15),
        T("Menu", 43, 18.5, 15, 3, 5, align="center"),
    ], {"Shop": "CÀ PHÊ MẪU", "Item": "Bạc xỉu đá", "Options": "Ít đường · Size L · Thêm shot",
        "Price": "45.000 ₫", "Order": "#0421", "Time": "08:15", "Customer": "Chị Lan",
        "MenuURL": "https://example.com/menu"}, popular=True)

tpl("food_expiry_50x30", "food", 50, 30, "Tem NSX / HSD 50×30", "Production / expiry label 50×30",
    "Ngày sản xuất, hạn sử dụng, số lô và khối lượng tịnh — cho thực phẩm đóng gói.",
    "Production date, expiry, lot and net weight — for packaged food.", [
        FRAME(50, 30),
        T("{{Product}}", 2, 1.5, 46, 4.5, 8, True, "center"),
        T("NSX: {{MFG}}", 2, 7, 23, 4, 7, True),
        T("HSD: {{Expiry}}", 25, 7, 23, 4, 7, True),
        T("Lô: {{Lot}}", 2, 11.5, 23, 3.5, 6),
        T("KLT: {{Weight}}", 25, 11.5, 23, 3.5, 6),
        T("Bảo quản nơi khô ráo, thoáng mát.", 2, 15.5, 46, 3, 5, align="center"),
        BC("{{Barcode}}", 4, 19, 42, 10),
    ], {"Product": "Bánh quy bơ hộp thiếc", "MFG": "01/11/2026", "Expiry": "01/11/2027", "Lot": "L2611",
        "Weight": "454g", "Barcode": "8935001234604"})

tpl("food_bottle_60x90", "food", 60, 90, "Tem chai nước 60×90", "Bottle label 60×90",
    "Nhãn thân chai dọc: thương hiệu, tên, dung tích, thành phần và mã vạch.",
    "Vertical bottle body label: brand, name, volume, ingredients and barcode.", [
        T("{{Brand}}", 3, 6, 54, 10, 18, True, "center"),
        LINE(15, 18, 45, 18, 0.3),
        T("{{Product}}", 3, 21, 54, 12, 11, True, "center", wrap=True),
        T("{{Size}}", 3, 35, 54, 7, 12, True, "center"),
        T("Thành phần: {{Ingredients}}", 4, 46, 52, 12, 6, align="center", wrap=True),
        T("NSX: {{MFG}} · HSD: {{Expiry}}", 3, 60, 54, 3.5, 6, align="center"),
        BC("{{Barcode}}", 10, 66, 40, 18, "ean13", True, 6.5),
    ], {"Brand": "SUỐI MẪU", "Product": "Nước khoáng thiên nhiên", "Size": "500ml",
        "Ingredients": "Nước khoáng thiên nhiên, khoáng chất tự nhiên.", "MFG": "11/2026", "Expiry": "11/2028",
        "Barcode": "8935001234611"})

tpl("food_nutrition_60x60", "food", 60, 60, "Bảng giá trị dinh dưỡng 60×60", "Nutrition facts 60×60",
    "Bảng thành phần dinh dưỡng trên 100g theo khung kẻ.",
    "Nutrition facts per 100 g in a ruled table.", [
        BOX(1, 1, 58, 58, 0.4),
        T("GIÁ TRỊ DINH DƯỠNG", 2.5, 2.5, 55, 5, 10, True),
        T("Trong 100g", 2.5, 8, 55, 3.5, 6.5),
        LINE(1, 12.5, 59, 12.5, 0.8),
        T("Năng lượng", 2.5, 14, 35, 4, 7, True), T("{{Energy}}", 38, 14, 19.5, 4, 7, True, "right"),
        LINE(1, 19, 59, 19),
        T("Chất đạm", 2.5, 20.5, 35, 4, 7), T("{{Protein}}", 38, 20.5, 19.5, 4, 7, align="right"),
        LINE(1, 25.5, 59, 25.5),
        T("Chất béo", 2.5, 27, 35, 4, 7), T("{{Fat}}", 38, 27, 19.5, 4, 7, align="right"),
        LINE(1, 32, 59, 32),
        T("Carbohydrate", 2.5, 33.5, 35, 4, 7), T("{{Carb}}", 38, 33.5, 19.5, 4, 7, align="right"),
        LINE(1, 38.5, 59, 38.5),
        T("Đường", 6, 40, 31, 4, 6.5), T("{{Sugar}}", 38, 40, 19.5, 4, 6.5, align="right"),
        LINE(1, 45, 59, 45),
        T("Natri", 2.5, 46.5, 35, 4, 7), T("{{Sodium}}", 38, 46.5, 19.5, 4, 7, align="right"),
        LINE(1, 51.5, 59, 51.5, 0.8),
        T("Giá trị trên dựa theo chế độ ăn 2000 kcal/ngày.", 2.5, 53, 55, 4.5, 5, wrap=True),
    ], {"Energy": "502 kcal", "Protein": "6.2 g", "Fat": "24 g", "Carb": "65 g", "Sugar": "22 g", "Sodium": "310 mg"})

# ================================================================== jewelry
tpl("jewelry_rattail_72x10", "jewelry", 72, 10, "Tem đuôi chuột trang sức 72×10", "Jewelry rat-tail tag 72×10",
    "Tem dài hẹp quấn quanh nhẫn / dây chuyền: mã, tuổi vàng, trọng lượng, giá — đuôi để dán.",
    "Long narrow tag that wraps a ring / chain: code, purity, weight, price — tail for sticking.", [
        T("{{Model}}", 1, 0.8, 14, 3.5, 6, True),
        T("{{Purity}}", 1, 5, 14, 3.5, 6),
        BC("{{SKU}}", 15.5, 1, 15, 8),
        T("TL: {{Weight}}", 32, 0.8, 18, 3.5, 5.5),
        T("{{Price}}", 32, 5, 18, 4, 6.5, True),
        LINE(51, 0.5, 51, 9.5, 0.15),
    ], {"Model": "N-0217", "Purity": "Vàng 18K", "SKU": "TS0217", "Weight": "1.25 chỉ", "Price": "8.800.000 ₫"},
    popular=True)

tpl("jewelry_box_40x20", "jewelry", 40, 20, "Tem hộp trang sức 40×20", "Jewelry box label 40×20",
    "Dán đáy hộp trang sức: tên, chất liệu, mã và giá.",
    "Under-box label: name, material, code and price.", [
        T("{{Product}}", 1.5, 1, 37, 4, 7, True, "center"),
        T("{{Purity}} · {{Weight}}", 1.5, 5.3, 37, 3, 5.5, align="center"),
        BC("{{SKU}}", 3, 9, 22, 9),
        T("{{Price}}", 26, 10, 12.5, 7, 7, True, "center", wrap=True),
    ], {"Product": "Nhẫn đính đá", "Purity": "Vàng 18K", "Weight": "1.25 chỉ", "SKU": "TS0217", "Price": "8.800.000 ₫"})

# ================================================================== warehouse
tpl("wh_location_100x50", "warehouse", 100, 50, "Tem vị trí kệ kho 100×50", "Warehouse location 100×50",
    "Mã vị trí chữ lớn (dãy-kệ-tầng-ô) + mã vạch để quét khi cất / lấy hàng.",
    "Large location code (aisle-rack-level-bin) + barcode for put-away / picking scans.", [
        BOX(0.8, 0.8, 98.4, 48.4, 0.5),
        T("{{Location}}", 3, 3, 94, 16, 32, True, "center"),
        T("Dãy {{Aisle}} · Kệ {{Rack}} · Tầng {{Level}} · Ô {{Bin}}", 3, 20, 94, 5, 9, align="center"),
        BC("{{Location}}", 10, 27, 80, 20),
    ], {"Location": "A-03-2-05", "Aisle": "A", "Rack": "03", "Level": "2", "Bin": "05"}, popular=True)

tpl("wh_bin_60x40", "warehouse", 60, 40, "Tem ô hàng / thùng nhựa 60×40", "Bin label 60×40",
    "Mã SKU, tên hàng, số lượng tối thiểu và QR cho ô kệ hoặc thùng nhựa.",
    "SKU, item name, minimum stock and QR for a shelf bin or tote.", [
        FRAME(60, 40),
        T("{{SKU}}", 2.5, 2, 36, 7, 14, True),
        T("{{Product}}", 2.5, 10, 36, 8, 7, wrap=True),
        T("Tồn tối thiểu: {{MinQty}}", 2.5, 19, 36, 3.5, 6),
        T("Vị trí: {{Location}}", 2.5, 23, 36, 3.5, 6, True),
        QR("{{SKU}}", 40, 2.5, 17.5),
        BC("{{SKU}}", 2.5, 28, 55, 10),
    ], dict(S_PRODUCT, MinQty="20", Location="A-03-2-05"))

tpl("wh_asset_50x25", "warehouse", 50, 25, "Tem tài sản cố định 50×25", "Fixed asset tag 50×25",
    "Tem dán thiết bị văn phòng: đơn vị quản lý, mã tài sản, mã vạch, ngày kiểm kê.",
    "Office equipment tag: owner, asset code, barcode, audit date.", [
        BOX(0.6, 0.6, 48.8, 23.8, 0.3),
        T("TÀI SẢN · {{Owner}}", 2, 1.5, 46, 3.5, 5.5, True, "center"),
        LINE(2, 5.5, 48, 5.5, 0.15),
        BC("{{AssetCode}}", 3, 6.5, 44, 10),
        T("{{AssetCode}}", 2, 17, 46, 3.5, 7, True, "center"),
        T("Kiểm kê: {{Date}}", 2, 20.6, 46, 3, 5, align="center"),
    ], {"Owner": "PHÒNG HÀNH CHÍNH", "AssetCode": "TS-2026-0042", "Date": "12/11/2026"})

tpl("wh_pallet_100x150", "warehouse", 100, 150, "Tem pallet 100×150", "Pallet label 100×150",
    "Nhãn pallet nhập / xuất kho: SKU, lô, số lượng, ngày, mã vạch SSCC.",
    "Inbound / outbound pallet label: SKU, lot, quantity, dates, SSCC barcode.", [
        FRAME(100, 150, 1, 0.4),
        T("PALLET", 4, 4, 92, 10, 22, True, "center"),
        LINE(1, 16, 99, 16, 0.4),
        T("SKU", 4, 18, 30, 4, 7), T("{{SKU}}", 4, 22, 92, 9, 18, True),
        T("Tên hàng", 4, 33, 30, 4, 7), T("{{Product}}", 4, 37, 92, 8, 11, True, wrap=True),
        LINE(1, 47, 99, 47, 0.2),
        T("Lô", 4, 49, 44, 4, 7), T("{{Lot}}", 4, 53, 44, 7, 13, True),
        T("Số lượng", 52, 49, 44, 4, 7), T("{{Qty}}", 52, 53, 44, 7, 13, True),
        T("Ngày SX", 4, 62, 44, 4, 7), T("{{MFG}}", 4, 66, 44, 6, 11, True),
        T("Hạn dùng", 52, 62, 44, 4, 7), T("{{Expiry}}", 52, 66, 44, 6, 11, True),
        LINE(1, 75, 99, 75, 0.4),
        BC("{{SKU}}", 6, 78, 88, 26, "code128", True, 9),
        LINE(1, 108, 99, 108, 0.2),
        T("SSCC", 4, 110, 30, 4, 7),
        BC("{{SSCC}}", 6, 115, 88, 30, "code128", True, 9),
    ], dict(S_PRODUCT, Lot="L2611", Qty="480 cái", MFG="01/11/2026", Expiry="01/11/2028", SSCC="389350012340000017"))

# ================================================================== electronics
tpl("elec_warranty_40x20", "electronics", 40, 20, "Tem bảo hành 40×20", "Warranty sticker 40×20",
    "Tem bảo hành dán máy: hạn bảo hành, số serial, mã vạch.",
    "Warranty sticker on the device: warranty end, serial, barcode.", [
        BOX(0.5, 0.5, 39, 19, 0.3),
        T("BẢO HÀNH ĐẾN {{WarrantyEnd}}", 1.5, 1.2, 37, 3.6, 6.5, True, "center"),
        BC("{{Serial}}", 2, 5.3, 36, 9),
        T("S/N: {{Serial}}", 1.5, 14.6, 37, 2.8, 5.5, align="center"),
        T("Rách tem không bảo hành", 1.5, 17.2, 37, 2.2, 4.2, align="center"),
    ], {"WarrantyEnd": "12/11/2027", "Serial": "SN26A00421"}, popular=True)

tpl("elec_serial_50x15", "electronics", 50, 15, "Tem serial / IMEI 50×15", "Serial / IMEI label 50×15",
    "Tem dài hẹp cho số serial / IMEI kèm mẫu máy.",
    "Long narrow label for serial / IMEI with the model.", [
        T("{{Model}}", 1, 0.8, 48, 3, 5.5, True),
        BC("{{IMEI}}", 1, 4, 48, 7.5),
        T("IMEI: {{IMEI}}", 1, 11.7, 48, 2.8, 5, align="center"),
    ], {"Model": "Điện thoại MX-20 128GB", "IMEI": "356938035643809"})

tpl("elec_repair_60x40", "electronics", 60, 40, "Phiếu nhận máy sửa chữa 60×40", "Repair intake tag 60×40",
    "Dán máy khách gửi sửa: mã phiếu, khách, lỗi, ngày hẹn trả.",
    "Tag for devices left for repair: ticket, customer, fault, due date.", [
        FRAME(60, 40),
        T("PHIẾU SỬA CHỮA", 2.5, 2, 36, 4.5, 8, True),
        T("{{Ticket}}", 2.5, 7, 36, 6, 13, True),
        T("Khách: {{Customer}} · {{Phone}}", 2.5, 14, 55, 3.5, 6),
        T("Thiết bị: {{Device}}", 2.5, 18, 55, 3.5, 6),
        T("Lỗi: {{Fault}}", 2.5, 22, 55, 6, 6, wrap=True),
        T("Hẹn trả: {{Due}}", 2.5, 29, 36, 4, 7, True),
        QR("{{Ticket}}", 41, 2.5, 16.5),
        BC("{{Ticket}}", 2.5, 33.5, 55, 5),
    ], {"Ticket": "SC-0421", "Customer": "Lê Văn C", "Phone": "0922 222 222", "Device": "Laptop 14 inch",
        "Fault": "Không lên nguồn, kiểm tra sạc", "Due": "15/11/2026"})

# ================================================================== seal & QC
tpl("seal_void_40x20", "seal", 40, 20, "Tem niêm phong 40×20", "Tamper seal 40×20",
    "Tem niêm phong hộp có số seri — dán qua mép nắp.",
    "Box tamper seal with a serial — stick it across the lid edge.", [
        BOX(0.5, 0.5, 39, 19, 0.4),
        SYM("seal_lock", 1.5, 3, 12),
        T("NIÊM PHONG", 14, 2, 25, 5, 9, True, "center"),
        T("Không dùng nếu tem rách", 14, 7.5, 25, 3.5, 5, align="center"),
        T("No. {{SealNo}}", 14, 12, 25, 5, 8, True, "center", font="Consolas"),
    ], {"SealNo": "000421"}, popular=True)

tpl("seal_qc_30x20", "seal", 30, 20, "Tem QC đạt 30×20", "QC passed 30×20",
    "Tem kiểm tra chất lượng: QC PASS, ngày kiểm và người kiểm.",
    "Quality check sticker: QC PASS, inspection date and inspector.", [
        BOX(0.5, 0.5, 29, 19, 0.3),
        SYM("qc_pass", 1.5, 2.5, 11),
        T("QC PASS", 13.5, 2, 15, 5, 9, True, "center"),
        T("{{Date}}", 13.5, 7.5, 15, 3.5, 6, align="center"),
        T("KTV: {{Inspector}}", 13.5, 11.5, 15, 3.5, 5.5, align="center"),
        T("Lô {{Lot}}", 1.5, 15, 27, 3.5, 5.5, True, "center"),
    ], {"Date": "12/11/2026", "Inspector": "QC07", "Lot": "L2611"})

tpl("seal_genuine_40x40", "seal", 40, 40, "Tem chính hãng QR 40×40", "Genuine product QR 40×40",
    "Tem chống giả: QR xác thực + mã kiểm tra riêng cho từng sản phẩm.",
    "Anti-counterfeit tag: verification QR + unique check code per item.", [
        ELL(0.8, 0.8, 38.4, 38.4, 0.3),
        T("CHÍNH HÃNG", 6, 4, 28, 4, 7.5, True, "center"),
        QR("{{VerifyURL}}", 11, 9, 18, "Q"),
        T("Mã: {{Code}}", 6, 28, 28, 3.5, 6, True, "center", font="Consolas"),
        T("Quét để xác thực", 8, 32, 24, 3, 5, align="center"),
    ], {"VerifyURL": "https://example.com/v/7F3K9Q", "Code": "7F3K9Q"})

# ================================================================== office / address
tpl("office_address_70x36", "office", 70, 36, "Tem địa chỉ 70×36", "Address label 70×36",
    "Khổ tem địa chỉ thông dụng (24 tem / tờ A4): kính gửi, tên, địa chỉ, điện thoại.",
    "Common address label (24 per A4 sheet): to, name, address, phone.", [
        T("KÍNH GỬI", 3, 3, 40, 3, 5.5),
        T("{{ReceiverName}}", 3, 6.5, 64, 6, 11, True),
        T("{{ReceiverAddress}}", 3, 13.5, 64, 12, 8, wrap=True),
        LINE(3, 27, 67, 27, 0.15),
        T("ĐT: {{ReceiverPhone}}", 3, 28.5, 64, 4, 7),
    ], {"ReceiverName": "Nguyễn Văn A", "ReceiverAddress": "34 Đường Ví Dụ, Phường 2, Quận 3, TP. Hồ Chí Minh",
        "ReceiverPhone": "0911 111 111"}, popular=True)

tpl("office_file_folder_80x25", "office", 80, 25, "Tem gáy hồ sơ 80×25", "File folder label 80×25",
    "Gáy bìa hồ sơ / còng: phòng ban, tên hồ sơ, năm và mã lưu trữ.",
    "Folder / binder spine: department, file name, year and archive code.", [
        FILL(0, 0, 14, 25),
        T("{{Year}}", 15.5, 1.5, 20, 5, 9, True),
        T("{{Department}}", 36, 1.5, 42, 5, 7, align="right"),
        T("{{FileName}}", 15.5, 7.5, 62, 9, 12, True),
        BC("{{ArchiveCode}}", 15.5, 17, 40, 7),
        T("{{ArchiveCode}}", 57, 18, 21, 5, 7, True, "right"),
    ], {"Year": "2026", "Department": "KẾ TOÁN", "FileName": "Chứng từ chi Q4", "ArchiveCode": "KT-26-Q4-01"})

tpl("office_name_badge_86x54", "office", 86, 54, "Thẻ tên sự kiện 86×54", "Event name badge 86×54",
    "Thẻ tên khách mời / nhân viên: tên lớn, chức danh, đơn vị và QR check-in.",
    "Guest / staff badge: big name, title, organisation and check-in QR.", [
        BOX(1, 1, 84, 52, 0.4),
        LINE(1, 10, 85, 10, 0.5),
        T("{{Event}}", 4, 2, 78, 7, 11, True, "center"),
        T("{{Name}}", 4, 14, 56, 12, 20, True),
        T("{{Title}}", 4, 28, 56, 5, 9),
        T("{{Organization}}", 4, 34, 56, 5, 8, True),
        QR("{{GuestID}}", 63, 15, 20),
        T("{{GuestID}}", 61, 36, 24, 4, 6, align="center"),
        T("{{Role}}", 4, 44, 78, 7, 14, True, "center"),
    ], {"Event": "HỘI THẢO MẪU 2026", "Name": "Trần Thị B", "Title": "Trưởng nhóm", "Organization": "Đơn vị mẫu",
        "GuestID": "G-0421", "Role": "KHÁCH MỜI"})


# ------------------------------------------------------------------ write
def build():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    seen = set()
    for t in TEMPLATES:
        assert t["id"] not in seen, t["id"]
        seen.add(t["id"])
        cfg = {"width_mm": t["w"], "height_mm": t["h"], "dpi": t["dpi"], "orientation": "portrait", "copies": 1,
               "offset_x_mm": 0, "offset_y_mm": 0, "threshold": 160, "elements": t["elements"]}
        cfg.update(t["extra"])
        cfg["gallery"] = {"id": t["id"], "category": t["category"], "popular": t["popular"],
                          "name": {"vi": t["name_vi"], "en": t["name_en"]},
                          "description": {"vi": t["desc_vi"], "en": t["desc_en"]},
                          "sample": t["sample"]}
        with open(os.path.join(OUT, t["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
            f.write("\n")
    cats = [{"id": c, "name": {"vi": vi, "en": en}, "icon": icon} for c, vi, en, icon in CATEGORIES]
    with open(os.path.join(OUT, "_categories.json"), "w", encoding="utf-8") as f:
        json.dump(cats, f, ensure_ascii=False, indent=1)
        f.write("\n")
    used = {t["category"] for t in TEMPLATES}
    assert used <= {c[0] for c in CATEGORIES}, used
    print(f"{len(TEMPLATES)} templates in {len(used)} categories -> {OUT}")


if __name__ == "__main__":
    build()
