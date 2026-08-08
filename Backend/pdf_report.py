"""pdf_report.py — generates the Bottleneck Report PDF.
Uses fpdf2 (pure Python, no system dependencies) so it installs cleanly
on Render / any container without extra build steps.
"""

from fpdf import FPDF
from datetime import datetime

ACCENT = (91, 33, 182)      # deep violet
ACCENT_LIGHT = (237, 233, 254)
DANGER = (220, 38, 38)
OK = (22, 163, 74)
TEXT_DARK = (31, 41, 55)
TEXT_MUTED = (107, 114, 128)


_UNICODE_REPLACEMENTS = {
    "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
    "\u201c": '"', "\u201d": '"', "\u2026": "...", "\u00d7": "x",
}


def clean(text):
    """Strip characters outside the base Helvetica (latin-1) font range,
    since fpdf2's core fonts don't support arbitrary Unicode."""
    if text is None:
        return ""
    text = str(text)
    for uni, ascii_ in _UNICODE_REPLACEMENTS.items():
        text = text.replace(uni, ascii_)
    return text.encode("latin-1", "replace").decode("latin-1")


def fmt_seconds(s):
    if s is None:
        return "-"
    total_min = s / 60
    if total_min < 60:
        return f"{total_min:.1f} min"
    hrs = total_min / 60
    if hrs < 24:
        return f"{hrs:.1f} hrs"
    return f"{hrs / 24:.1f} days"


class ReportPDF(FPDF):
    def header(self):
        pass  # custom header drawn manually per page


def generate_report_pdf(dataset_name: str, analysis: dict, generated_by: str) -> bytes:
    pdf = ReportPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ---- Header banner ----
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_xy(10, 6)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "FlowLens - Bottleneck Report", ln=1)
    pdf.set_x(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        0, 6,
        f"Dataset: {clean(dataset_name)}  |  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  By: {clean(generated_by)}",
        ln=1,
    )
    pdf.ln(14)

    # ---- Executive summary ----
    pdf.set_text_color(*ACCENT)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Executive Summary", ln=1)
    pdf.set_text_color(*TEXT_DARK)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.multi_cell(0, 5.5, clean(analysis["summaryText"]))
    pdf.ln(2)

    # ---- Key numbers row ----
    stats = [
        ("Items analyzed", str(analysis["totalItems"])),
        ("Stages analyzed", str(analysis["totalStages"])),
        ("Bottleneck stages", str(len(analysis["bottleneckStages"]))),
        ("Stuck items flagged", str(analysis["stuckItemCount"])),
    ]
    box_w = (190) / 4
    x0, y0 = 10, pdf.get_y()
    for i, (label, value) in enumerate(stats):
        x = x0 + i * box_w
        pdf.set_fill_color(*ACCENT_LIGHT)
        pdf.rect(x, y0, box_w - 3, 20, "F")
        pdf.set_xy(x + 3, y0 + 2)
        pdf.set_text_color(*ACCENT)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(box_w - 8, 8, value, ln=2)
        pdf.set_x(x + 3)
        pdf.set_text_color(*TEXT_MUTED)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.multi_cell(box_w - 8, 3.5, label)
    pdf.set_y(y0 + 26)

    # ---- Stage-by-stage breakdown ----
    pdf.set_text_color(*ACCENT)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 9, "Stage-by-Stage Breakdown", ln=1)

    for idx, s in enumerate(analysis["stageReports"]):
        if pdf.get_y() > 250:
            pdf.add_page()

        pdf.set_text_color(*TEXT_DARK)
        pdf.set_font("Helvetica", "B", 12)
        badge = "BOTTLENECK" if s["isBottleneck"] else "Healthy"
        badge_color = DANGER if s["isBottleneck"] else OK
        pdf.cell(0, 7, f"{idx + 1}. {clean(s['stage'])}", ln=0)
        pdf.set_text_color(*badge_color)
        pdf.cell(0, 7, f"   [{badge}]", ln=1)

        pdf.set_text_color(*TEXT_MUTED)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(
            0, 4.5,
            f"Avg: {fmt_seconds(s['mean'])}   Median: {fmt_seconds(s['median'])}   "
            f"Std Dev: {fmt_seconds(s['stddev'])}   Items: {s['count']}   "
            f"Outliers: {s['outlierCount']}   Z-score: {s['zScore']:.2f}",
        )
        pdf.set_text_color(*TEXT_DARK)
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.write(4.5, "Cause: ")
        pdf.set_font("Helvetica", "", 9.5)
        pdf.write(4.5, clean(s["cause"]))
        pdf.ln(6)
        pdf.set_text_color(*TEXT_MUTED)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.3, clean(s["explanation"]))
        pdf.set_text_color(*ACCENT)
        pdf.set_font("Helvetica", "B", 9)
        pdf.write(4.3, "Recommendation: ")
        pdf.set_text_color(*TEXT_DARK)
        pdf.set_font("Helvetica", "", 9)
        pdf.write(4.3, clean(s["recommendation"]))
        pdf.ln(9)

    # ---- Stuck items table ----
    if analysis["stuckItems"]:
        pdf.add_page()
        pdf.set_text_color(*ACCENT)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 9, "Stuck Items (Top Outliers)", ln=1)
        pdf.set_text_color(*TEXT_MUTED)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(
            0, 4,
            "Items whose stage duration exceeded the statistical outlier ceiling "
            "(Q3 + 1.5x IQR) for that stage.",
        )
        pdf.ln(2)

        col_w = [40, 40, 35, 35, 40]
        headers = ["Item ID", "Stage", "Duration", "Expected Max", "Exceeded By"]
        pdf.set_fill_color(*ACCENT)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        for w, h in zip(col_w, headers):
            pdf.cell(w, 7, h, border=0, fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8.5)
        for i, item in enumerate(analysis["stuckItems"][:30]):
            if pdf.get_y() > 270:
                pdf.add_page()
            fill = i % 2 == 0
            pdf.set_fill_color(249, 250, 251)
            pdf.set_text_color(*TEXT_DARK)
            pdf.cell(col_w[0], 6, clean(str(item["item_id"]))[:20], fill=fill)
            pdf.cell(col_w[1], 6, clean(str(item["stage"]))[:20], fill=fill)
            pdf.cell(col_w[2], 6, fmt_seconds(item["duration_seconds"]), fill=fill)
            pdf.cell(col_w[3], 6, fmt_seconds(item["expected_ceiling_seconds"]), fill=fill)
            pdf.set_text_color(*DANGER)
            pdf.cell(col_w[4], 6, fmt_seconds(item["exceeded_by_seconds"]), fill=fill)
            pdf.ln()

    return bytes(pdf.output())
