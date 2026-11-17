import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from database.db import query_db

def generate_excel_leave_report(department_id=None, start_date=None, end_date=None):
    """
    Generates Excel report for leave requests.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Leave Report"

    # Theme colors
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=16, bold=True, color="0F172A")
    sub_font = Font(name="Calibri", size=10, italic=True, color="64748B")

    ws.merge_cells("A1:I1")
    ws["A1"] = "Smart HRMS - Enterprise Leave Report"
    ws["A1"].font = title_font

    ws.merge_cells("A2:I2")
    ws["A2"] = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws["A2"].font = sub_font

    headers = [
        "Req #", "Employee Name", "Emp ID", "Department", "Leave Type", 
        "Start Date", "End Date", "Days", "Status"
    ]
    
    ws.append([]) # Blank row 3
    ws.append(headers) # Row 4

    for col in range(1, 10):
        cell = ws.cell(row=4, column=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Fetch data
    query = """
        SELECT lr.request_number, u.full_name, u.emp_id, d.name as dept_name,
               lt.name as leave_type_name, lr.start_date, lr.end_date, lr.total_days, lr.status
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        LEFT JOIN departments d ON u.department_id = d.id
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE 1=1
    """
    args = []
    if department_id:
        query += " AND u.department_id = ?"
        args.append(department_id)
    if start_date:
        query += " AND lr.start_date >= ?"
        args.append(start_date)
    if end_date:
        query += " AND lr.end_date <= ?"
        args.append(end_date)

    query += " ORDER BY lr.id DESC"
    rows = query_db(query, tuple(args))

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    row_idx = 5
    for r in rows:
        ws.append([
            r['request_number'], r['full_name'], r['emp_id'], r['dept_name'] or 'N/A',
            r['leave_type_name'], r['start_date'], r['end_date'], r['total_days'], r['status']
        ])
        for col in range(1, 10):
            cell = ws.cell(row=row_idx, column=col)
            cell.border = thin_border
            if col in (6, 7, 8, 9):
                cell.alignment = Alignment(horizontal="center")
        row_idx += 1

    # Adjust column widths
    from openpyxl.utils import get_column_letter
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

def generate_pdf_leave_report(department_id=None, start_date=None, end_date=None):
    """
    Generates PDF report using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )

    elements = []
    elements.append(Paragraph("Smart HRMS - Enterprise Leave Report", title_style))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", meta_style))

    # Fetch data
    query = """
        SELECT lr.request_number, u.full_name, d.code as dept_code,
               lt.code as lt_code, lr.start_date, lr.end_date, lr.total_days, lr.status
        FROM leave_requests lr
        JOIN users u ON lr.user_id = u.id
        LEFT JOIN departments d ON u.department_id = d.id
        JOIN leave_types lt ON lr.leave_type_id = lt.id
        WHERE 1=1
    """
    args = []
    if department_id:
        query += " AND u.department_id = ?"
        args.append(department_id)
    if start_date:
        query += " AND lr.start_date >= ?"
        args.append(start_date)
    if end_date:
        query += " AND lr.end_date <= ?"
        args.append(end_date)

    query += " ORDER BY lr.id DESC LIMIT 100"
    rows = query_db(query, tuple(args))

    table_data = [[
        Paragraph('<b>Req #</b>', styles['Normal']),
        Paragraph('<b>Employee</b>', styles['Normal']),
        Paragraph('<b>Dept</b>', styles['Normal']),
        Paragraph('<b>Type</b>', styles['Normal']),
        Paragraph('<b>Start Date</b>', styles['Normal']),
        Paragraph('<b>End Date</b>', styles['Normal']),
        Paragraph('<b>Days</b>', styles['Normal']),
        Paragraph('<b>Status</b>', styles['Normal'])
    ]]

    for r in rows:
        table_data.append([
            r['request_number'],
            r['full_name'],
            r['dept_code'] or '-',
            r['lt_code'],
            r['start_date'],
            r['end_date'],
            str(r['total_days']),
            r['status']
        ])

    t = Table(table_data, colWidths=[80, 110, 45, 45, 70, 70, 40, 70])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))

    elements.append(t)
    doc.build(elements)

    buffer.seek(0)
    return buffer
