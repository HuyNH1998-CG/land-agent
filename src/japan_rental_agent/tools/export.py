from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from japan_rental_agent.config import AppConfig
from japan_rental_agent.tools.support import ensure_parent_dir, to_json_bytes


class ExportTool:
    """Exports listing results to CSV, JSON, or a lightweight PDF report."""

    name = "export"

    def __init__(self, config: AppConfig | None = None) -> None:
        self.config = config or AppConfig()

    def _timestamped_path(self, suffix: str) -> Path:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.config.export_dir / f"rental_results_{stamp}.{suffix}"

    def _write_csv(self, listings: list[dict[str, Any]]) -> Path:
        import csv

        path = self._timestamped_path("csv")
        ensure_parent_dir(path)
        normalized = [dict(listing) for listing in listings]
        fieldnames: list[str] = []
        for listing in normalized:
            for key in listing.keys():
                if key not in fieldnames:
                    fieldnames.append(key)

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(normalized)
        return path

    def _write_json(self, listings: list[dict[str, Any]]) -> Path:
        path = self._timestamped_path("json")
        ensure_parent_dir(path)
        payload = {"results": listings}
        path.write_bytes(to_json_bytes(payload))
        return path

    def _write_pdf(self, listings: list[dict[str, Any]]) -> Path:
        path = self._timestamped_path("pdf")
        ensure_parent_dir(path)
        lines = ["Rental Report", "Top Listings:"]
        for index, listing in enumerate(listings[:10], start=1):
            title = str(listing.get("title", "Listing"))
            rent = str(listing.get("rent_yen") or listing.get("rent") or "n/a")
            score = str(listing.get("score", "n/a"))
            lines.append(f"{index}. {title} - {rent} JPY - Score {score}")

        content_lines = ["BT", "/F1 12 Tf", "50 790 Td"]
        for index, line in enumerate(lines):
            safe_line = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            if index == 0:
                content_lines.append(f"({safe_line}) Tj")
            else:
                content_lines.append("0 -18 Td")
                content_lines.append(f"({safe_line}) Tj")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", errors="replace")

        objects = [
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj",
            b"4 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj",
            b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        ]

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(pdf))
            pdf.extend(obj)
            pdf.extend(b"\n")
        xref_start = len(pdf)
        pdf.extend(f"xref\n0 {len(objects)+1}\n".encode("ascii"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        pdf.extend(
            (
                f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\n"
                f"startxref\n{xref_start}\n%%EOF"
            ).encode("ascii")
        )
        path.write_bytes(bytes(pdf))
        return path

    def execute(self, listings: list[dict[str, Any]], output_format: str) -> dict[str, Any]:
        self.config.export_dir.mkdir(parents=True, exist_ok=True)
        normalized_format = output_format.lower().strip()
        if normalized_format == "csv":
            file_path = self._write_csv(listings)
        elif normalized_format == "json":
            file_path = self._write_json(listings)
        elif normalized_format == "pdf":
            file_path = self._write_pdf(listings)
        else:
            raise ValueError(f"Unsupported export format: {output_format}")

        return {
            "file_url": str(file_path),
            "file_type": normalized_format,
            "count": len(listings),
        }
