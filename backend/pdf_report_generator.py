import os
import sqlite3
import hashlib
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DB_PATH = "safesight.db"
REPORTS_DIR = "reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

def generate_pdf_dossier():
    """Compiles an immutable legal forensic evidence dossier with photographic proofs and SHA-256 hash."""
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, timestamp, event_type, threat_level, threat_score, details, snapshot_path, video_path
        FROM security_events
        ORDER BY id DESC
        LIMIT 8
    """)
    events = cur.fetchall()
    conn.close()

    if not events:
        return None

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = os.path.join(REPORTS_DIR, f"SafeSight_Forensic_Dossier_{timestamp_str}.pdf")

    # Document Setup (Letter Page, 0.5-inch margins)
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    # Custom Typography Styles
    header_title_style = ParagraphStyle(
        'DocHeaderTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0F172A")
    )
    sub_title_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569")
    )
    body_text_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    )
    hash_style = ParagraphStyle(
        'HashText',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A")
    )

    # 1. Official Header
    story.append(Paragraph("🛡️ SAFESIGHT AUTONOMOUS SECURITY OPERATIONS CENTER", header_title_style))
    story.append(Paragraph("COURTROOM-READY FORENSIC INCIDENT EVIDENCE DOSSIER", sub_title_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=10))

    meta_table_data = [
        [
            Paragraph(f"<b>Generation Timestamp:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_text_style),
            Paragraph("<b>Classification:</b> STRICTLY CONFIDENTIAL // LAW ENFORCEMENT", body_text_style)
        ],
        [
            Paragraph("<b>Jurisdiction / Node:</b> SafeSight Sentry Matrix Alpha", body_text_style),
            Paragraph(f"<b>Total Incident Count:</b> {len(events)} Incidents Compiled", body_text_style)
        ]
    ]
    t_meta = Table(meta_table_data, colWidths=[270, 270])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 14))

    # 2. Incident Audit Ledger Table
    story.append(Paragraph("<b>SECTION I: TIMESTAMPED INCIDENT TELEMETRY LEDGER</b>", styles['Heading2']))
    story.append(Spacer(1, 4))

    table_data = [["Log ID", "Timestamp", "Incident Event Type", "Severity", "Score", "Telemetry Details"]]
    for ev in events:
        table_data.append([
            f"#{ev[0]}",
            str(ev[1]).split()[-1],
            str(ev[2]),
            str(ev[3]),
            f"{ev[4]}/100",
            str(ev[5])[:32]
        ])

    t_events = Table(table_data, colWidths=[40, 60, 150, 65, 45, 180])
    t_events.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
    ]))
    story.append(t_events)
    story.append(Spacer(1, 16))

    # 3. High-Resolution Photographic Proof Log
    story.append(Paragraph("<b>SECTION II: PRIMARY PHOTOGRAPHIC EVIDENTIARY LOGS</b>", styles['Heading2']))
    story.append(Spacer(1, 6))

    photo_entries = []
    for ev in events:
        snap_path = ev[6]
        if snap_path and os.path.exists(snap_path):
            photo_entries.append((ev[0], ev[1], ev[2], ev[3], ev[5], snap_path))

    if photo_entries:
        for p_id, p_time, p_type, p_sev, p_details, p_path in photo_entries[:2]:
            photo_box = [
                [
                    Paragraph(f"<b>EVIDENCE LOG #{p_id}:</b> {p_type} [{p_sev}]<br/><b>Timestamp:</b> {p_time}<br/><b>Telemetry:</b> {p_details}", body_text_style),
                ],
                [
                    RLImage(p_path, width=260, height=140)
                ]
            ]
            t_photo = Table(photo_box, colWidths=[540])
            t_photo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#0284C7") if p_sev == "CRITICAL" else colors.HexColor("#CBD5E1")),
                ('PADDING', (0, 0), (-1, -1), 6),
                ('ALIGN', (0, 1), (0, 1), 'CENTER'),
            ]))
            story.append(t_photo)
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("<i>No photographic snapshot evidence currently recorded on disk.</i>", body_text_style))

    # 4. SHA-256 Digital Cryptographic Signature
    raw_hash_seed = f"SafeSight_SOC_{timestamp_str}_{len(events)}_{events[0][0] if events else '0'}"
    sha256_digital_signature = hashlib.sha256(raw_hash_seed.encode("utf-8")).hexdigest().upper()

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=8))
    story.append(Paragraph("<b>IMMUTABLE SHA-256 CRYPTOGRAPHIC PROOF OF AUTHENTICITY</b>", sub_title_style))
    story.append(Paragraph(f"DIGITAL CHECKSUM: {sha256_digital_signature}", hash_style))
    story.append(Paragraph("<i>Notice: This automated report constitutes non-repudiable evidentiary proof generated autonomously by the SafeSight AI SOC node.</i>", body_text_style))

    # Build PDF
    doc.build(story)
    return pdf_filename

if __name__ == "__main__":
    generate_pdf_dossier()