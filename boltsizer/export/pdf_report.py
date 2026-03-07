"""PDF calculation report generator using ReportLab.

Produces a structured calculation note with:
  - Cover page with project metadata
  - Input summary table
  - ECSS-compliant margin of safety table
  - Full calculation chain (per load case)
  - Assumptions and references
"""
from __future__ import annotations
import io
import datetime
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from boltsizer.models.results import AnalysisResults, BoltResults, MarginOfSafety

# ---------------------------------------------------------------------------
# Colour definitions
# ---------------------------------------------------------------------------
_GREEN = colors.Color(0.172, 0.627, 0.172)
_AMBER = colors.Color(1.0, 0.498, 0.055)
_RED = colors.Color(0.839, 0.153, 0.157)
_LIGHT_GREY = colors.Color(0.93, 0.93, 0.93)
_DARK_GREY = colors.Color(0.3, 0.3, 0.3)
_HEADER_BLUE = colors.Color(0.122, 0.467, 0.706)


def _ms_colour(ms: float) -> colors.Color:
    if ms < 0:
        return _RED
    if ms < 0.25:
        return _AMBER
    return _GREEN


def generate_pdf_report(
    results: AnalysisResults,
    bolt_cfg: Dict[str, Any],
    joint_cfg: Dict[str, Any],
    report_meta: Dict[str, Any],
) -> bytes:
    """Generate a PDF calculation report as bytes.

    Args:
        results: AnalysisResults from the VDI 2230 analysis.
        bolt_cfg: Bolt configuration dict from session state.
        joint_cfg: Joint configuration dict from session state.
        report_meta: Report metadata (project_name, revision, engineer_name).

    Returns:
        PDF content as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=25*mm,
        bottomMargin=20*mm,
        title=f"BoltSizer — {report_meta.get('project_name', 'Calculation Note')}",
        author=report_meta.get("engineer_name", ""),
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"],
                                  fontSize=20, spaceAfter=6, textColor=_HEADER_BLUE)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"],
                         fontSize=14, textColor=_HEADER_BLUE, spaceAfter=4, spaceBefore=12)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"],
                         fontSize=11, textColor=_DARK_GREY, spaceAfter=3, spaceBefore=8)
    body = styles["Normal"]
    body.fontSize = 9
    body.leading = 13
    caption = ParagraphStyle("Caption", parent=body, fontSize=8, textColor=_DARK_GREY, italic=True)
    mono = ParagraphStyle("Mono", parent=body, fontName="Courier", fontSize=8)

    story = []

    # -----------------------------------------------------------------------
    # Cover / title block
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("BoltSizer", title_style))
    story.append(Paragraph("Structural Flange Bolt Sizing — Calculation Note", styles["Heading2"]))
    story.append(Spacer(1, 5*mm))

    proj = report_meta.get("project_name") or "—"
    rev = report_meta.get("revision") or "A"
    eng = report_meta.get("engineer_name") or "—"
    date_str = datetime.date.today().strftime("%Y-%m-%d")

    meta_data = [
        ["Project:", proj, "Revision:", rev],
        ["Engineer:", eng, "Date:", date_str],
        ["Standard:", results.standard, "Bolt:", bolt_cfg.get("designation", "—")],
        ["Grade:", bolt_cfg.get("grade", "—"), "# Bolts:", str(joint_cfg.get("num_bolts", "—"))],
    ]
    meta_table = Table(meta_data, colWidths=[30*mm, 60*mm, 30*mm, 40*mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, _LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _LIGHT_GREY]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(meta_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=_HEADER_BLUE, spaceAfter=10))

    # -----------------------------------------------------------------------
    # Assumptions
    # -----------------------------------------------------------------------
    story.append(Paragraph("Assumptions & Scope", h1))
    assumptions = [
        "All calculations performed per VDI 2230 Part 1 (2014) unless stated otherwise.",
        "Internal units: SI (N, mm, MPa). Displayed values rounded for readability.",
        "Axial tension is positive (bolt in tension = opening the joint).",
        "Clamped-part compliance: Rotscher pressure cone model, half-angle φ_K = 30°.",
        "Bolt fatigue: infinite-life check only (no finite-life Miner's rule).",
        "Gasket flanges (ASME VIII / EN 1591) are out of scope.",
        "Thermal loading and differential expansion not included.",
    ]
    for a in assumptions:
        story.append(Paragraph(f"• {a}", body))
    story.append(Spacer(1, 4*mm))

    # -----------------------------------------------------------------------
    # Input summary
    # -----------------------------------------------------------------------
    story.append(Paragraph("1. Input Summary", h1))

    story.append(Paragraph("1.1 Bolt Specification", h2))
    bolt_rows = [
        ["Parameter", "Value", "Unit"],
        ["Designation", bolt_cfg.get("designation", "—"), "—"],
        ["Grade", bolt_cfg.get("grade", "—"), "—"],
        ["Coating / Lubrication", bolt_cfg.get("coating", "—"), "—"],
        ["K-factor", f"{bolt_cfg.get('nut_factor_K', 0):.3f}", "—"],
        ["Assembly torque", f"{bolt_cfg.get('assembly_torque_Nmm', 0):,.0f}", "N·mm"],
        ["Tightening method", bolt_cfg.get("tightening_method", "—"), "—"],
        ["Mating surfaces", str(bolt_cfg.get("num_mating_surfaces", 2)), "—"],
        ["Surface roughness Rz", f"{bolt_cfg.get('surface_roughness_Rz', 6.3):.1f}", "μm"],
    ]
    story.append(_make_table(bolt_rows))

    story.append(Paragraph("1.2 Joint Geometry", h2))
    grip = sum(l.get("thickness_mm", 0) for l in joint_cfg.get("layers", []))
    joint_rows = [
        ["Parameter", "Value", "Unit"],
        ["Number of bolts", str(joint_cfg.get("num_bolts", "—")), "—"],
        ["Bolt circle diameter (PCD)", f"{joint_cfg.get('bolt_circle_diameter_mm', 0):.1f}", "mm"],
        ["Total grip length l_K", f"{grip:.1f}", "mm"],
        ["Load intro factor n", f"{joint_cfg.get('load_intro_factor_n', 0.5):.2f}", "—"],
        ["Friction coefficient μ", f"{joint_cfg.get('friction_coefficient', 0):.2f}", "—"],
        ["Friction interfaces", str(joint_cfg.get("num_friction_interfaces", 1)), "—"],
        ["Plate thickness (bearing)", f"{joint_cfg.get('plate_thickness_mm', 0):.1f}", "mm"],
        ["Plate yield strength", f"{joint_cfg.get('plate_yield_strength_MPa', 0):.0f}", "MPa"],
    ]
    story.append(_make_table(joint_rows))

    story.append(Paragraph("1.3 Clamped Stack", h2))
    stack_header = [["Layer", "Material", "Thickness [mm]", "E [MPa]"]]
    stack_data = [
        [str(i+1), l.get("material", ""), f"{l.get('thickness_mm', 0):.1f}", f"{l.get('E', 0):,.0f}"]
        for i, l in enumerate(joint_cfg.get("layers", []))
    ]
    story.append(_make_table(stack_header + stack_data))

    # -----------------------------------------------------------------------
    # Results per load case
    # -----------------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("2. Analysis Results", h1))

    for case_result in results.case_results:
        _add_case_section(story, case_result, results.standard, h2, body, caption)

    # -----------------------------------------------------------------------
    # References
    # -----------------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("3. References", h1))
    refs = [
        "VDI 2230 Part 1 (2014): Systematic calculation of highly stressed bolted joints — "
        "Joints with one cylindrical bolt.",
        "ECSS-E-HB-32-23A (2010): Threaded fastener design manual.",
        "ISO 898-1:2013: Mechanical properties of fasteners — Bolts, screws and studs.",
        "ISO 724:1993: ISO general-purpose metric screw threads — Basic dimensions.",
        "Bickford, J.H. (2007): An Introduction to the Design and Behavior of Bolted Joints, "
        "4th ed. CRC Press.",
    ]
    for ref in refs:
        story.append(Paragraph(f"[{refs.index(ref)+1}] {ref}", body))
        story.append(Spacer(1, 2*mm))

    # Footer note
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_DARK_GREY))
    story.append(Paragraph(
        f"Generated by BoltSizer v0.1.0 on {date_str}. "
        "All results are engineering estimates. Verify against applicable project standards.",
        caption,
    ))

    doc.build(story)
    return buffer.getvalue()


def _make_table(data: list, col_widths: list = None) -> Table:
    """Make a standard styled data table."""
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _add_case_section(story, case_result: BoltResults, standard: str, h2, body, caption) -> None:
    """Add a full result section for one load case."""
    story.append(Paragraph(f"Load Case: {case_result.case_name}", h2))

    preload = case_result.preload
    stiffness = case_result.stiffness
    load_dist = case_result.load_dist

    # Preload summary
    pr_rows = [
        ["Parameter", "Value", "Unit"],
        ["Assembly preload F_M_max", f"{preload.F_M_max:,.0f}", "N"],
        ["Scatter factor α_A", f"{preload.alpha_A:.2f}", "—"],
        ["Min preload F_M_min (after scatter)", f"{preload.F_M_min:,.0f}", "N"],
        ["Embedding loss F_Z", f"{preload.F_Z:,.0f}", "N"],
        ["Net min preload F_V_min", f"{preload.F_preload_min:,.0f}", "N"],
        ["Bolt compliance δ_S", f"{stiffness.delta_S:.3e}", "mm/N"],
        ["Clamped-part compliance δ_P", f"{stiffness.delta_P:.3e}", "mm/N"],
        ["Force ratio φ_n", f"{stiffness.phi_n:.4f}", "—"],
        ["Critical bolt #", str(load_dist.critical_bolt_index + 1), "—"],
        ["Critical bolt axial load", f"{load_dist.F_total_axial:,.0f}", "N"],
        ["Critical bolt shear", f"{load_dist.V_shear_per_bolt:,.0f}", "N"],
        ["Max bolt load", f"{case_result.bolt_load_max:,.0f}", "N"],
        ["Min clamping force", f"{case_result.F_clamp_min:,.0f}", "N"],
    ]
    story.append(_make_table(pr_rows))
    story.append(Spacer(1, 4*mm))

    # Margin table
    ms_header = [["Check", "Allowable", "Applied", "Unit", "MS", "Status", "Binding"]]
    ms_rows = []
    for m in case_result.margins:
        v_str = "∞" if m.value == float("inf") else f"{m.value:.3f}"
        ms_rows.append([
            m.check_name,
            f"{m.allowable:.2f}",
            f"{m.applied:.2f}",
            m.unit,
            v_str,
            m.status,
            "★" if m.binding else "",
        ])

    ms_table_data = ms_header + ms_rows
    ms_table = Table(ms_table_data)
    col_styles = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
    ]
    # Colour rows by status
    for row_idx, m in enumerate(case_result.margins, 1):
        c = _ms_colour(m.value)
        col_styles.append(("BACKGROUND", (4, row_idx), (5, row_idx), c))
        col_styles.append(("TEXTCOLOR", (4, row_idx), (5, row_idx), colors.white))

    ms_table.setStyle(TableStyle(col_styles))
    story.append(ms_table)

    # Warnings
    if case_result.warnings:
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("Warnings:", body))
        for w in case_result.warnings:
            story.append(Paragraph(f"  {w}", caption))

    story.append(Spacer(1, 6*mm))
