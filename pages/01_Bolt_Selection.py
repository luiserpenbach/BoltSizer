"""Page 1 — Bolt Selection.

User selects bolt designation, grade, coating/lubrication,
tightening method, and assembly torque.
Live preload preview updates as inputs change.
"""
import streamlit as st
import math
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boltsizer.ui.session_state import init_session_state, mark_page_complete, render_sidebar_progress
from boltsizer.standards.bolt_library import BOLT_LIBRARY
from boltsizer.standards.material_library import MATERIAL_LIBRARY
from boltsizer.standards.nut_factors import NUT_FACTOR_TABLE, TIGHTENING_SCATTER, TIGHTENING_METHOD_LABELS, get_nut_factor

st.set_page_config(page_title="Bolt Selection — BoltSizer", page_icon="🔩", layout="wide")
init_session_state()
render_sidebar_progress()

st.title("🔩 Step 1: Bolt Selection")
st.caption("Select bolt size, material grade, surface condition, and tightening parameters.")

cfg = st.session_state["bolt_config"]

# ---------------------------------------------------------------------------
# Layout: two columns — selection | preview
# ---------------------------------------------------------------------------
col_sel, col_prev = st.columns([3, 2], gap="large")

with col_sel:
    st.subheader("Bolt Specification")

    # Filter bolt library by standard grouping
    iso_coarse = sorted([k for k, v in BOLT_LIBRARY.items() if v["standard"] == "ISO metric"])
    iso_fine = sorted([k for k, v in BOLT_LIBRARY.items() if v["standard"] == "ISO metric fine"])
    unified = sorted([k for k, v in BOLT_LIBRARY.items() if v["standard"] == "Unified"])

    standard_choice = st.selectbox(
        "Thread Standard",
        options=["ISO Metric (coarse)", "ISO Metric (fine)", "Unified (UNC/UNF)"],
        index=0,
        help="Select the bolt thread standard.",
    )
    if standard_choice == "ISO Metric (coarse)":
        desig_options = iso_coarse
    elif standard_choice == "ISO Metric (fine)":
        desig_options = iso_fine
    else:
        desig_options = unified

    desig_idx = desig_options.index(cfg["designation"]) if cfg["designation"] in desig_options else 0
    designation = st.selectbox("Bolt Designation", desig_options, index=desig_idx)
    cfg["designation"] = designation

    bdata = BOLT_LIBRARY[designation]
    st.caption(
        f"d = {bdata['nominal_diameter']:.1f} mm | "
        f"Pitch = {bdata['pitch']:.2f} mm | "
        f"A_s = {bdata['stress_area']:.1f} mm²"
    )

    # Grade
    grade_options = [k for k in MATERIAL_LIBRARY if k != "Custom"]
    grade_idx = grade_options.index(cfg["grade"]) if cfg["grade"] in grade_options else 0
    grade = st.selectbox(
        "Material Grade",
        grade_options + ["Custom"],
        index=grade_idx,
        help="Select material grade. Properties auto-populated from library.",
    )
    cfg["grade"] = grade

    mdata = MATERIAL_LIBRARY.get(grade, {})
    if grade != "Custom":
        st.caption(
            f"σ_y = {mdata.get('yield_strength', 0):.0f} MPa | "
            f"UTS = {mdata.get('uts', 0):.0f} MPa | "
            f"E = {mdata.get('youngs_modulus', 0)/1000:.0f} GPa"
        )
    else:
        st.info("Custom grade — material properties will be entered on the Joint Geometry page.")

    # Shank and thread lengths
    c1, c2 = st.columns(2)
    with c1:
        cfg["shank_length_mm"] = st.number_input(
            "Shank length [mm]", min_value=0.0, max_value=500.0,
            value=float(cfg.get("shank_length_mm", 20.0)), step=1.0,
        )
    with c2:
        cfg["threaded_length_mm"] = st.number_input(
            "Threaded engagement [mm]", min_value=1.0, max_value=500.0,
            value=float(cfg.get("threaded_length_mm", 15.0)), step=1.0,
        )

    st.subheader("Surface & Lubrication")
    coating_options = list(NUT_FACTOR_TABLE.keys())
    coat_idx = coating_options.index(cfg["coating"]) if cfg["coating"] in coating_options else 0
    coating = st.selectbox(
        "Coating / Lubrication",
        coating_options,
        index=coat_idx,
        help="Affects the K-factor (torque-to-preload relationship) and preload scatter.",
    )
    cfg["coating"] = coating
    k_nom = get_nut_factor(coating)
    k_row = NUT_FACTOR_TABLE[coating]
    st.caption(f"K = {k_nom:.2f} (range {k_row[1]:.2f}–{k_row[2]:.2f}) — {k_row[3]}")

    nut_factor = st.number_input(
        "Nut/K-factor (override)",
        min_value=0.01, max_value=0.50,
        value=float(cfg.get("nut_factor_K", k_nom)),
        step=0.01,
        format="%.3f",
        help="Edit to override the library K-factor.",
    )
    cfg["nut_factor_K"] = nut_factor

    st.subheader("Tightening Method")
    method_labels = list(TIGHTENING_METHOD_LABELS.values())
    method_keys = list(TIGHTENING_METHOD_LABELS.keys())
    m_idx = method_keys.index(cfg["tightening_method"]) if cfg["tightening_method"] in method_keys else 0
    method_choice = st.selectbox(
        "Tightening Method",
        method_labels,
        index=m_idx,
        help="Determines scatter factor α_A (F_max/F_min ratio).",
    )
    cfg["tightening_method"] = method_keys[method_labels.index(method_choice)]
    alpha_A = TIGHTENING_SCATTER[cfg["tightening_method"]][0]
    st.caption(f"Scatter factor α_A = {alpha_A:.2f} ({TIGHTENING_SCATTER[cfg['tightening_method']][1]})")

    st.subheader("Assembly Loading")
    use_target = st.toggle(
        "Enter target preload instead of torque",
        value=cfg.get("use_target_preload", False),
        help="Toggle between assembly torque entry mode and direct preload specification.",
    )
    cfg["use_target_preload"] = use_target

    if use_target:
        cfg["target_preload_N"] = st.number_input(
            "Target preload F_M [N]",
            min_value=0.0, max_value=1e7,
            value=float(cfg.get("target_preload_N", 30000.0)),
            step=100.0,
        )
        cfg["assembly_torque_Nmm"] = 0.0
    else:
        cfg["assembly_torque_Nmm"] = st.number_input(
            "Assembly torque M_A [N·mm]",
            min_value=0.0, max_value=1e8,
            value=float(cfg.get("assembly_torque_Nmm", 85000.0)),
            step=500.0,
            help="Enter torque in N·mm (1 N·m = 1000 N·mm).",
        )
        cfg["target_preload_N"] = 0.0

    c1, c2 = st.columns(2)
    with c1:
        cfg["num_mating_surfaces"] = st.number_input(
            "Number of mating surfaces", min_value=1, max_value=10,
            value=int(cfg.get("num_mating_surfaces", 2)),
            help="Number of contact interfaces (for embedding relaxation).",
        )
    with c2:
        cfg["surface_roughness_Rz"] = st.number_input(
            "Surface roughness Rz [μm]", min_value=0.5, max_value=100.0,
            value=float(cfg.get("surface_roughness_Rz", 6.3)),
            step=0.5,
            help="Mean surface roughness for embedding calculation.",
        )

# ---------------------------------------------------------------------------
# Live preload preview
# ---------------------------------------------------------------------------
with col_prev:
    st.subheader("Preload Preview")
    try:
        from boltsizer.standards import get_bolt_geometry, get_material
        from boltsizer.models.bolt import Bolt
        from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer
        from boltsizer.calculations.preload import calculate_preload
        from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness

        geom = get_bolt_geometry(
            cfg["designation"],
            shank_length=cfg.get("shank_length_mm", 20.0),
            threaded_length=cfg.get("threaded_length_mm", 15.0),
        )
        if cfg["grade"] == "Custom":
            st.warning("Grade 'Custom' requires explicit properties — preview unavailable.")
            st.stop()
        mat = get_material(cfg["grade"], geom.nominal_diameter)
        bolt = Bolt(geometry=geom, material=mat, grade=cfg["grade"])

        bc = BoltCircle(
            num_bolts=1,
            bolt_circle_diameter=0.0,
            bolt=bolt,
            nut_factor_K=cfg["nut_factor_K"],
            assembly_torque=cfg["assembly_torque_Nmm"],
            target_preload=cfg["target_preload_N"],
            tightening_method=cfg["tightening_method"],
            num_mating_surfaces=int(cfg["num_mating_surfaces"]),
            surface_roughness_Rz=float(cfg["surface_roughness_Rz"]),
        )

        # Preview grip: use the joint stack if already defined, else 40 mm
        joint_cfg = st.session_state.get("joint_config", {})
        layers_cfg = joint_cfg.get("layers") or [
            {"material": "Steel (carbon)", "thickness_mm": 40.0, "E": 210000.0}
        ]
        preview_iface = ClampedInterface(
            total_clamped_length=0.0,
            layers=[
                ClampedLayer(l["material"], float(l["thickness_mm"]), float(l.get("E", 210000.0)))
                for l in layers_cfg
            ],
            interface_treatment="bare metal",
            friction_coefficient=0.12,
        )
        stiff = calculate_joint_stiffness(bc, preview_iface)
        result = calculate_preload(
            bc,
            preview_iface.total_clamped_length,
            total_compliance=stiff.delta_S + stiff.delta_P,
            num_inner_interfaces=max(0, len(preview_iface.layers) - 1),
        )

        # Utilisation check
        A_s = geom.stress_area
        sigma_proof = mat.proof_load_stress
        util_pct = result.F_M_max / (A_s * sigma_proof) * 100 if sigma_proof > 0 else 0

        util_colour = "normal" if util_pct <= 90 else "off"
        st.metric("Assembly Preload F_M", f"{result.F_M_max:,.0f} N",
                  help="Maximum preload achieved with this torque.")
        st.metric("Scatter band α_A", f"{result.alpha_A:.2f}",
                  delta=f"F_M_min = {result.F_M_min:,.0f} N",
                  delta_color="off")
        st.metric("Embedding loss F_Z", f"{result.F_Z:,.0f} N",
                  delta=f"Net F_preload_min = {result.F_preload_min:,.0f} N",
                  delta_color="off")
        st.metric("Proof load utilisation", f"{util_pct:.1f}%",
                  delta="⚠ Exceeds 90% limit" if util_pct > 90 else "OK",
                  delta_color="inverse" if util_pct > 90 else "off")

        # Preload fraction of proof load bar
        st.progress(min(1.0, util_pct / 100), text=f"Assembly utilisation: {util_pct:.1f}%")

        if util_pct > 90:
            st.warning("⚠ Preload exceeds 90% of proof load. ECSS prohibits torque-to-yield tightening for space hardware.")

    except Exception as e:
        st.error(f"Preview error: {e}")

# Save and mark complete
st.session_state["bolt_config"] = cfg
mark_page_complete("Bolt Selection", True)

st.divider()
st.page_link("pages/02_Joint_Geometry.py", label="Next: Joint Geometry →", icon="📐")
