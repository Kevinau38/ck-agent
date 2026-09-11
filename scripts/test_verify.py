"""Phase 3 acceptance test: verification must accept the right people and
refuse everyone else, including a verified user reaching for another's order.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agent"))

from verify import (  # noqa: E402
    get_shipment,
    list_orders,
    normalise_name,
    normalise_ssn,
    parse_dob,
    verify_user,
)

passed = failed = 0


def check(label: str, got, want) -> None:
    global passed, failed
    if got == want:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}\n        got={got!r}\n        want={want!r}")


print("\n1. SSN - lay 4 so cuoi du nhap du hay co dau phan cach")
check("4 chu so", normalise_ssn("4821"), "4821")
check("SSN day du", normalise_ssn("123-45-4821"), "4821")
check("co khoang trang", normalise_ssn("123 45 4821"), "4821")
check("qua ngan", normalise_ssn("21"), None)

print("\n2. DOB - moi dinh dang, ke ca cau tu nhien")
target = "1990-01-05"
for text in ["Jan 5 1990", "January 5th, 1990", "I was born on January 5th, 1990",
             "1990-01-05", "5 January 1990"]:
    check(f"{text!r}", any(str(d) == target for d in parse_dob(text)), True)
check("'05/01/1990' doc duoc ca hai kieu", len(parse_dob("05/01/1990")), 2)
check("rac", parse_dob("khong phai ngay thang"), [])

EMAIL = "jordan.reed@ck1.com"
NAME = "Jordan Reed"
NOBODY = "nobody@ck9.com"

print("\n3. Email - phai khop mau @ck<so>.com")
for bad in ["jordan.reed@gmail.com", "jordan.reed@ck.com", "jordan.reed@ckabc.com"]:
    check(f"tu choi {bad}", verify_user(bad, NAME, "4821", "Jan 5 1990")["verified"], False)

print("\n4. Ho ten - truong thu tu theo Level 100")
check("bo dau cau va khoang trang thua", normalise_name("Jordan  Reed."), "jordan reed")
check("sai ten", verify_user(EMAIL, "Someone Else", "4821", "1990-01-05")["verified"], False)
check("thieu ten", verify_user(EMAIL, "", "4821", "1990-01-05")["verified"], False)

print("\n5. Xac minh day du")
ok = verify_user(EMAIL, NAME, "4821", "I was born on January 5th, 1990")
check("dung ca bon truong", ok["verified"], True)
check("tra ve dung user", ok.get("user_id"), "U001")
upper = verify_user("JORDAN.REED@CK1.COM", "jordan  reed", "4821", "1990-01-05")
check("hoa thuong khong anh huong", upper["verified"], True)
check("sai SSN", verify_user(EMAIL, NAME, "0000", "1990-01-05")["verified"], False)
check("sai DOB", verify_user(EMAIL, NAME, "4821", "1991-01-05")["verified"], False)
check("email khong ton tai", verify_user(NOBODY, NAME, "4821", "1990-01-05")["verified"], False)

print("\n6. Khong ro ri du lieu khi that bai")
bad = verify_user(EMAIL, NAME, "0000", "1990-01-05")
check("khong tra ve user_id", "user_id" in bad, False)
check("cung mot thong bao cho email sai va SSN sai",
      verify_user(NOBODY, "Nobody", "1111", "1990-01-05")["reason"] == bad["reason"], True)

print("\n7. Don hang")
orders = list_orders("U001")
check("U001 co 3 don", len(orders), 3)
check("moi nhat truoc", orders[0]["order_id"], "ORD-10154")
check("U002 co 1 don", len(list_orders("U002")), 1)

print("\n8. Quyen so huu don hang")
check("chu don xem duoc", get_shipment("U001", "ORD-10021")["status"], "Delivered")
check("nguoi khac khong xem duoc", get_shipment("U002", "ORD-10021"), None)
check("ma don bia dat", get_shipment("U001", "ORD-99999"), None)

print("\n9. Khoa sau 3 lan xac minh sai")
sys.path.insert(0, str(ROOT / "agent"))
from tools import Session, run_tool  # noqa: E402

s = Session()
bad_args = {"email": "jordan.reed@ck1.com", "full_name": "Jordan Reed",
            "ssn_last4": "0000", "date_of_birth": "1990-01-05"}
run_tool(s, "verify_identity", bad_args)
run_tool(s, "verify_identity", bad_args)
check("dem du 2 lan sai", s.failed_attempts, 2)
third = run_tool(s, "verify_identity", bad_args)
check("lan thu 3 chuyen sang ho tro", "human support" in third, True)
check("van chua verify", s.verified_user_id, None)

print(f"\n{passed} pass, {failed} fail")
sys.exit(0 if failed == 0 else 1)
