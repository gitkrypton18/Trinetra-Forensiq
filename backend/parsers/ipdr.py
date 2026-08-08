"""IPDR parsers for the formats found in the police dataset.

- jio_ipv6    Jio IPv6 session exports (24-column CSV)
- ipdr_xlsx   generic xlsx layouts: {IP, VALUE, F DATE, F TIME, T DATE, T TIME}
              and {No., IP Address, Date, Time(IST), username, ... mobile}
"""

from __future__ import annotations

import re
from datetime import datetime

from ..util import (
    clean_field, normalise_imei, normalise_imsi, normalise_ip, normalise_phone,
    parse_csv_robust, parse_time, to_epoch,
)

_EMPTY = {"-", "--", "", "NA", "N/A", "---"}


def _canon(row: dict, operator: str, source_file: str, source_format: str) -> dict:
    rec = {k: "" for k in (
        "ipdr_id", "operator", "msisdn", "imsi", "imei", "user_id", "mac",
        "source_ip", "public_ip", "dest_ip", "dest_port", "apn", "cell_id",
        "date", "start_time", "end_time", "start_ts", "end_ts", "duration_sec",
        "volume_up", "volume_down", "roaming_circle", "is_static",
        "source_file", "source_format")}
    rec.update(row)
    rec["operator"] = operator
    rec["source_file"] = source_file
    rec["source_format"] = source_format
    if rec.get("date") and rec.get("start_time"):
        rec["start_ts"] = to_epoch(rec["date"], rec["start_time"])
    if rec.get("date") and rec.get("end_time"):
        rec["end_ts"] = to_epoch(rec["date"], rec["end_time"])
    return rec


# ---------------------------------------------------------------------------
# Jio IPv6 24-column CSV
# ---------------------------------------------------------------------------
def parse_jio_ipv6(path: str) -> dict:
    rows = parse_csv_robust(path)
    header_idx = None
    for i, r in enumerate(rows):
        if r and "landline" in clean_field(r[0]).lower():
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("Jio IPv6: header not found")
    header = [clean_field(c).strip() for c in rows[header_idx]]
    records = []
    for r in rows[header_idx + 1:]:
        if not r or not any(clean_field(c) for c in r):
            continue
        m = {h: clean_field(v) for h, v in zip(header, r)}
        start_d = m.get("Start Date of Public IP Address allocation (dd/mm/yyyy)")
        if not start_d:
            start_d = m.get("Start Date of Public IP Address allocation")
        d = start_d
        if "/" in d:
            parts = d.split("/")
            if len(parts) == 3 and len(parts[2]) == 4:
                d = f"{parts[2]}-{parts[1]}-{parts[0]}"
        start_t = parse_time(m.get("IST Start Time of Public IP address allocation (hh:mm:ss)")
                             or m.get("IST Start Time"))
        end_t = parse_time(m.get("IST End Time of Public IP address allocation (hh:mm:ss)")
                           or m.get("IST End Time"))
        rec = _canon({
            "msisdn": m.get("Landline/MSISDN/MDN/Leased Circuit ID for Internet Access"),
            "source_ip": m.get("Source IP Address (IP Address Assigned/Translated)")
                         or m.get("Source IP Address"),
            "public_ip": m.get("Public IP Address"),
            "dest_ip": m.get("Destination IP Address"),
            "dest_port": m.get("Destination Port"),
            "user_id": m.get("User Id for internet Access based on authentication"),
            "mac": m.get("Source MAC-ID Address/Other device Identification number"),
            "imsi": m.get("IMSI"),
            "imei": m.get("IMEI"),
            "apn": m.get("Access Point Name"),
            "cell_id": m.get("CGI ID"),
            "date": d,
            "start_time": start_t,
            "end_time": end_t,
            "duration_sec": _int0(m.get("Session Duration")),
            "volume_up": _int0(m.get("Data Volume Up Link")),
            "volume_down": _int0(m.get("Data Volume Down Link")),
            "roaming_circle": m.get("Roaming Circle"),
            "is_static": m.get("Static/Dynamic IP Address Allocation"),
        }, "Jio", path, "jio_ipv6")
        records.append(rec)
    return {"records": records, "meta": {"operator": "Jio"}}


def _int0(v):
    s = clean_field(v)
    if not s or s in _EMPTY:
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Generic IPDR xlsx
# ---------------------------------------------------------------------------
def parse_ipdr_xlsx(path: str) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    records = []
    meta = {"operator": "Unknown"}
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = None
        for row in rows:
            if header is None:
                header = [clean_field(c).lower().strip() for c in row]
                continue
            if not any(c is not None and clean_field(c) for c in row):
                continue
            d = dict(zip(header, [clean_field(c) for c in row]))
            if not d.get("ip") and not d.get("ip address"):
                continue
            rec = _xlsx_row(d)
            if rec:
                rec["source_file"] = path
                rec["source_format"] = "ipdr_xlsx"
                records.append(rec)
    wb.close()
    return {"records": records, "meta": meta}


def _xlsx_row(d: dict) -> dict | None:
    rec = {k: "" for k in (
        "ipdr_id", "operator", "msisdn", "imsi", "imei", "user_id", "mac",
        "source_ip", "public_ip", "dest_ip", "dest_port", "apn", "cell_id",
        "date", "start_time", "end_time", "start_ts", "end_ts", "duration_sec",
        "volume_up", "volume_down", "roaming_circle", "is_static",
        "source_file", "source_format")}
    ip = d.get("ip") or d.get("ip address") or ""
    if ip.lower().strip() in ("ipv6", "ipv4"):
        ip = d.get("value") or ""
    rec["source_ip"] = normalise_ip(ip)
    msisdn = d.get("mobile") or d.get("msisdn") or ""
    rec["msisdn"] = normalise_phone(msisdn)
    rec["user_id"] = (d.get("username") or "").strip()
    fdate, ftime = d.get("f date") or d.get("date"), d.get("f time") or d.get("time(ist)") or d.get("time")
    tdate, ttime = d.get("t date"), d.get("t time")
    if fdate:
        rec["date"] = _xlsx_date(fdate)
    rec["start_time"] = parse_time(str(ftime)) if ftime else ""
    rec["end_time"] = parse_time(str(ttime)) if ttime else ""
    if isinstance(fdate, datetime):
        rec["start_ts"] = int(fdate.timestamp())
    return rec


def _xlsx_date(v) -> str:
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = clean_field(v)
    s = re.sub(r"^(\d{4})(\d{2})(\d{2})$", r"\1-\2-\3", s)  # yyyymmdd
    s = re.sub(r"^(\d{2})(\d{2})(\d{4})$", r"\3-\2-\1", s)  # ddmmyyyy
    s = re.sub(r"^(\d{4})-(\d{2})-(\d{2})$", r"\1-\2-\3", s)
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return s[:10]


PARSERS = {
    "jio_ipv6": parse_jio_ipv6,
    "ipdr_xlsx": parse_ipdr_xlsx,
}


"""IPDR parser plugins (Jio IPv6, generic xlsx, generic csv)."""


import re

from ..errors import SkipFileError
from ..util import parse_csv_robust, clean_field, to_epoch
from .base import BaseParser, ParseResult
from .registry import register


class _IpdrBase(BaseParser):
    dataset = "IPDR"


@register
class JioIpv6Parser(_IpdrBase):
    format_id = "jio_ipv6"
    description = "Jio IPv6 session export (CSV)"

    def parse(self, path, context=None):
        try:
            res = parse_jio_ipv6(path)
        except ValueError as e:
            raise SkipFileError("parse_error", str(e)[:160]) from e
        return ParseResult(res["records"], res.get("meta", {}),
                           self.format_id, self.dataset)


@register
class IpdrXLSXParser(_IpdrBase):
    format_id = "ipdr_xlsx"
    description = "Generic IPDR spreadsheet"

    def parse(self, path, context=None):
        res = parse_ipdr_xlsx(path)
        return ParseResult(res["records"], res.get("meta", {}),
                           self.format_id, self.dataset)


@register
class IpdrCSVParser(_IpdrBase):
    format_id = "ipdr_csv"
    description = "Generic IPDR text export"

    def parse(self, path, context=None):
        return ParseResult(*_generic_csv_records(path),
                           self.format_id, self.dataset)


def _generic_csv_records(path: str) -> tuple[list[dict], dict]:
    rows = parse_csv_robust(path)
    if not rows:
        return [], {"layout": "ipdr_csv", "row_count": 0}
    header = [clean_field(c).lower() for c in rows[0]]
    col = {h: i for i, h in enumerate(header)}
    src_ip = next((col[k] for k in ("source ip", "source ip address", "ip address",
                                    "ip", "public ip") if k in col), None)
    if src_ip is None:
        return [], {"layout": "ipdr_csv", "row_count": 0, "no_header": True}
    dst_ip = next((col[k] for k in ("destination ip", "dest ip") if k in col), None)
    date_c = next((col[k] for k in ("start date", "date", "f date", "start_date")
                   if k in col), None)
    time_c = next((col[k] for k in ("start time", "time", "f time", "start_time",
                                    "time(ist)") if k in col), None)
    recs: list[dict] = []
    for r in rows[1:]:
        if len(r) <= src_ip:
            continue
        src = clean_field(r[src_ip])
        if not src or not re.match(r"[\dA-Fa-f:.]+", src):
            continue
        d = clean_field(r[date_c]) if date_c is not None else ""
        t = clean_field(r[time_c]) if time_c is not None else ""
        recs.append({
            "txn_id": "", "msisdn": "", "source_ip": src,
            "destination_ip": clean_field(r[dst_ip]) if dst_ip is not None else "",
            "start_time": to_epoch(d, t) or 0,
            "end_time": 0, "duration": 0, "source_port": "", "destination_port": "",
            "source_file": path, "source_format": "ipdr_csv",
            "date": d, "time": t,
        })
    stem = path.rsplit("\\", 1)[-1].rsplit(".", 1)[0][:20]
    for i, rec in enumerate(recs):
        rec["txn_id"] = f"ipdr_{stem}_{i:06d}"
    return recs, {"layout": "ipdr_csv", "row_count": len(recs)}
