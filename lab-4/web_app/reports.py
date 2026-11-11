"""Excel-звіти з явними типами комірок і захистом від формул у тексті."""

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def workbook_bytes(title, columns, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    sheet.append([label for _, label in columns])
    for record in rows:
        values = []
        for key, _ in columns:
            value = record.get(key)
            if isinstance(value, Decimal):
                value = float(value)
            elif isinstance(value, (datetime, date)):
                value = (
                    value.isoformat(sep=" ", timespec="seconds")
                    if isinstance(value, datetime)
                    else value.isoformat()
                )
            elif isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
                # Апостроф змушує Excel трактувати користувацьке значення як текст, а не формулу.
                value = "'" + value
            values.append(value)
        sheet.append(values)
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor="155E50")
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 28
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for index, (key, label) in enumerate(columns, 1):
        width = (
            max(len(label), *(len(str(record.get(key, "") or "")) for record in rows))
            if rows
            else len(label)
        )
        sheet.column_dimensions[get_column_letter(index)].width = min(55, max(14, width + 3))
        if key in ("price", "order_total", "revenue", "spent"):
            for cells in sheet.iter_rows(min_row=2, min_col=index, max_col=index):
                cells[0].number_format = "#,##0.00"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
