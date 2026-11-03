"""Scan-then-print: lookup rules (core) and the Qt ScanController."""
from labelapp.core.scan import INCREASE_QTY, ADD_ROW, ScanIndex, ScanQueue

HEADERS = ["Brand", "Model", "Barcode"]
ROWS = [{"Brand": "A", "Model": "m1", "Barcode": "111111111111"},
        {"Brand": "B", "Model": "m2", "Barcode": "222222222222"},
        {"Brand": "C", "Model": "m3", "Barcode": "333333333333"},
        {"Brand": "D", "Model": "m4", "Barcode": "333333333333"}]


def index():
    return ScanIndex(HEADERS, ROWS)


def test_resolve_exact_glued_duplicate_and_missing():
    ix = index()
    assert ix.resolve(" 111111111111\r\n") == ("ok", ["111111111111"])
    assert ix.resolve("111111111111222222222222") == ("ok", ["111111111111", "222222222222"])
    assert ix.resolve("333333333333")[0] == "duplicate"
    assert ix.resolve("999999999999")[0] == "not_found"
    assert ix.resolve("")[0] == "empty"
    assert ix.min_length == 12


def test_queue_increase_qty_vs_add_row_and_issues():
    ix, q = index(), ScanQueue()
    q.add_raw(ix, "111111111111, 111111111111;222222222222 999999999999 333333333333", INCREASE_QTY)
    st = [(i["code"], i["qty"], i["status"]) for i in q.items]
    assert st == [("111111111111", 2, "READY"), ("222222222222", 1, "READY"),
                  ("999999999999", 1, "NOT FOUND"), ("333333333333", 1, "DUPLICATE x2")]
    assert q.summary() == {"total": 4, "ready": 2, "checked": 2, "labels": 3, "issues": 2}
    q2 = ScanQueue()
    q2.add_raw(ix, "111111111111 111111111111", ADD_ROW)
    assert len(q2.items) == 2


def test_resolve_duplicate_and_edits():
    ix, q = index(), ScanQueue()
    q.add_raw(ix, "333333333333")
    assert not q.checked_ready()
    q.resolve(0, 3)
    assert q.items[0]["row_index"] == 3 and q.items[0]["checked"]
    q.set_qty(0, 5)
    q.toggle(0)
    assert not q.checked_ready()
    q.set_all_checked(True)
    assert q.summary()["labels"] == 5
    q.remove_ids([q.items[0]["id"]])
    assert not q.items


def test_suggest_matches_upc_sku_name_brand_and_ranks():
    from labelapp.core.suggest import SuggestIndex
    headers = ["Brand Name", "SKU", "Product Name", "UPC", "Price"]
    rows = [{"Brand Name": "Contoso", "SKU": "CT3025", "Product Name": "Aviator Large", "UPC": 405289026,"Price": "3.000"},
            {"Brand Name": "Fabrikam", "SKU": "FB9102", "Product Name": "Harbor", "UPC": "488392000111", "Price": "2.500"},
            {"Brand Name": "Northwind", "SKU": "NW0237", "Product Name": "Aviator Round", "UPC": "012345678905", "Price": "9.000"}]
    sx = SuggestIndex(headers, rows)
    assert sx.search("0123") == [2]                      # UPC prefix
    assert sx.search("ct30") == [0]                      # SKU prefix
    assert sx.search("harb") == [1]                      # name
    assert sx.search("fabrikam") == [1]                    # brand
    assert sx.search("aviator north") == [2]               # every word must match
    assert sorted(sx.search("aviator")) == [0, 2]
    assert sx.search("") == [] and sx.search("zzz") == []
    assert sx.search("CT3025")[0] == 0                   # case-insensitive
    d = sx.describe(2)
    assert (d["upc"], d["sku"], d["brand"], d["name"]) == ("012345678905", "NW0237", "Northwind", "Aviator Round")
