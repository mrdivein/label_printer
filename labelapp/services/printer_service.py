"""Printer discovery and job submission (Windows spooler via pywin32). ZPL raw-job construction.

Moved verbatim from the original app.py. win32 modules are imported lazily so the module imports everywhere.
"""
import os

def image_to_zpl_gfa(img):
    mono = img.convert("1")
    width, height = mono.size
    row_bytes = (width + 7) // 8
    data = bytearray()
    pix = mono.load()
    for y in range(height):
        row = bytearray(row_bytes)
        for x in range(width):
            if pix[x, y] == 0:
                row[x // 8] |= (1 << (7 - (x % 8)))
        data.extend(row)
    total = len(data)
    return f"^GFA,{total},{total},{row_bytes},{data.hex().upper()}"

def build_raw_gzpl(cfg, img):
    copies = max(1, int(cfg.get("copies", 1)))
    return (
        "^XA\r\n"
        "^LH0,0\r\n"
        f"^PW{img.width}\r\n"
        f"^LL{img.height}\r\n"
        "^FO0,0\r\n"
        f"{image_to_zpl_gfa(img)}\r\n"
        "^FS\r\n"
        f"^PQ{copies},0,1,N\r\n"
        "^XZ\r\n"
    ).encode("ascii")

def enum_printers():
    try:
        import win32print
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        return [p[2] for p in win32print.EnumPrinters(flags)]
    except Exception:
        return []

def preferred_printer(printers):
    for key in ("G530", "GoDEX", "Godex", "EZ530", "EZ530+"):
        for p in printers:
            if key.lower() in p.lower():
                return p
    return printers[0] if printers else ""

def raw_print(printer_name, raw_bytes):
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(h, 1, ("Label RAW", None, "RAW"))
        try:
            win32print.StartPagePrinter(h)
            win32print.WritePrinter(h, raw_bytes)
            win32print.EndPagePrinter(h)
        finally:
            win32print.EndDocPrinter(h)
    finally:
        win32print.ClosePrinter(h)


def printer_info(printer_name):
    import win32print
    h = win32print.OpenPrinter(printer_name)
    try:
        info = win32print.GetPrinter(h, 2)
        dm = info.get("pDevMode")
        out = {
            "name": printer_name,
            "driver": info.get("pDriverName", ""),
            "port": info.get("pPortName", ""),
            "status": info.get("Status", 0),
            "paper_width_mm": None,
            "paper_length_mm": None,
            "orientation": None,
            "print_quality": None,
        }
        if dm:
            try:
                pw = getattr(dm, "PaperWidth", 0)
                pl = getattr(dm, "PaperLength", 0)
                if pw: out["paper_width_mm"] = round(float(pw)/10.0, 2)
                if pl: out["paper_length_mm"] = round(float(pl)/10.0, 2)
                ori = getattr(dm, "Orientation", 0)
                out["orientation"] = "portrait" if ori == 1 else ("landscape" if ori == 2 else None)
                out["print_quality"] = getattr(dm, "PrintQuality", None)
            except Exception:
                pass
        return out
    finally:
        win32print.ClosePrinter(h)

def status_text(status):
    if status == 0:
        return "Ready / no Windows error reported"
    pairs = [
        (0x1,"Paused"), (0x2,"Error"), (0x8,"Paper jam"), (0x10,"Paper out"),
        (0x40,"Paper problem"), (0x80,"Offline"), (0x200,"Busy"),
        (0x400,"Printing"), (0x400000,"User intervention")
    ]
    names = [n for b,n in pairs if status & b]
    return ", ".join(names) if names else f"Windows status code: {status}"


def is_virtual_printer_name(name):
    low = str(name or "").lower()
    tokens = (
        "pdf", "xps", "onenote", "fax", "document writer",
        "adobe pdf", "foxit pdf", "nitro pdf", "cute pdf"
    )
    return any(t in low for t in tokens)


def print_pdf_via_windows_driver(pdf_path, printer_name):
    """
    Ask the installed Windows PDF handler to print the VECTOR PDF to a chosen
    Windows printer using the shell 'printto' verb. This is the correct route
    for virtual printers; sending ZPL RAW to a PDF/XPS printer is not.

    The selected PDF application/driver owns the final print dialog and may show
    a Save As prompt (e.g. Microsoft Print to PDF).
    """
    import win32api
    params = f'"{printer_name}"'
    result = win32api.ShellExecute(0, "printto", pdf_path, params, os.path.dirname(pdf_path) or ".", 1)
    if int(result) <= 32:
        raise RuntimeError(
            f"Windows PDF print handler returned error code {result}. "
            "Open the PDF Proof and print manually to this printer if its PDF app does not support PrintTo."
        )
    return result
