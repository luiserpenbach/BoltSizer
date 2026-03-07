"""Page 3 — Loading.

User enters load cases: axial force, bending moment, shear, torsion.
Bolt circle diagram highlights the critical bolt live as loads change.
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boltsizer.ui.session_state import init_session_state, mark_page_complete, render_sidebar_progress

st.set_page_config(page_title="Loading — BoltSizer", page_icon="⚡", layout="wide")
init_session_state()
render_sidebar_progress()

st.title("⚡ Step 3: Loading")
st.caption("Define load cases. Each case will be assessed independently.")

load_cases = st.session_state["load_cases"]
bolt_cfg = st.session_state["bolt_config"]
joint_cfg = st.session_state["joint_config"]

st.info(
    "💡 **Sign convention:** Axial tension is positive (opening the joint). "
    "Bending moment opens the joint on the bolt at θ = 0°."
)

# ---------------------------------------------------------------------------
# Load case management
# ---------------------------------------------------------------------------
col_add, col_rem, _ = st.columns([1, 1, 4])
with col_add:
    if st.button("➕ Add Load Case"):
        n = len(load_cases) + 1
        load_cases.append({
            "case_name": f"LC{n}",
            "axial_force_N": 0.0,
            "bending_moment_Nmm": 0.0,
            "shear_force_N": 0.0,
            "torsion_Nmm": 0.0,
            "load_plane": "interface",
            "load_factor": 1.0,
        })
with col_rem:
    if st.button("➖ Remove Last") and len(load_cases) > 1:
        load_cases.pop()

# ---------------------------------------------------------------------------
# Load case editors
# ---------------------------------------------------------------------------
updated_cases = []
for i, lc in enumerate(load_cases):
    with st.expander(f"Load Case {i+1}: {lc['case_name']}", expanded=True):
        c1, c2, c3 = st.columns([1, 2, 2])
        with c1:
            name = st.text_input("Case name", value=lc["case_name"], key=f"lc_name_{i}")
        with c2:
            lf = st.number_input(
                "Load factor",
                min_value=0.1, max_value=10.0,
                value=float(lc.get("load_factor", 1.0)),
                step=0.05,
                format="%.2f",
                key=f"lc_lf_{i}",
                help="Safety/load factor applied to all loads in this case.",
            )
        with c3:
            plane = st.selectbox(
                "Load plane",
                ["interface", "bolt_head"],
                index=0 if lc.get("load_plane", "interface") == "interface" else 1,
                key=f"lc_plane_{i}",
                help="Where the external load is applied (affects φ correction).",
            )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            Fa = st.number_input(
                "Axial force F_A [N]",
                value=float(lc.get("axial_force_N", 0.0)),
                step=100.0,
                key=f"lc_fa_{i}",
                help="Positive = tension (opening the joint).",
            )
        with c2:
            Mb = st.number_input(
                "Bending moment M_B [N·mm]",
                value=float(lc.get("bending_moment_Nmm", 0.0)),
                step=1000.0,
                key=f"lc_mb_{i}",
            )
        with c3:
            V = st.number_input(
                "Shear force V [N]",
                value=float(lc.get("shear_force_N", 0.0)),
                step=100.0,
                key=f"lc_v_{i}",
            )
        with c4:
            Mt = st.number_input(
                "Torsion M_T [N·mm]",
                value=float(lc.get("torsion_Nmm", 0.0)),
                step=1000.0,
                key=f"lc_mt_{i}",
                help="Usually friction-reacted; included for reference only.",
            )

        updated_cases.append({
            "case_name": name,
            "axial_force_N": Fa,
            "bending_moment_Nmm": Mb,
            "shear_force_N": V,
            "torsion_Nmm": Mt,
            "load_plane": plane,
            "load_factor": lf,
        })

st.session_state["load_cases"] = updated_cases

# ---------------------------------------------------------------------------
# Live bolt circle diagram
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Critical Bolt Preview")
col_chart, col_info = st.columns([2, 3])

try:
    from boltsizer.standards import get_bolt_geometry, get_material
    from boltsizer.models.bolt import Bolt
    from boltsizer.models.joint import BoltCircle, ExternalLoading
    from boltsizer.calculations.load_distribution import calculate_load_distribution
    from boltsizer.ui.components.bolt_circle_viz import make_bolt_circle_diagram

    geom = get_bolt_geometry(
        bolt_cfg["designation"],
        shank_length=bolt_cfg.get("shank_length_mm", 20.0),
        threaded_length=bolt_cfg.get("threaded_length_mm", 15.0),
    )
    mat = get_material(bolt_cfg["grade"]) if bolt_cfg["grade"] != "Custom" else get_material("ISO 8.8")
    bolt = Bolt(geometry=geom, material=mat, grade=bolt_cfg["grade"])
    bc = BoltCircle(
        num_bolts=int(joint_cfg["num_bolts"]),
        bolt_circle_diameter=float(joint_cfg["bolt_circle_diameter_mm"]),
        bolt=bolt,
        nut_factor_K=float(bolt_cfg.get("nut_factor_K", 0.16)),
        assembly_torque=float(bolt_cfg.get("assembly_torque_Nmm", 85000.0)),
    )

    # Use first load case for live preview
    if updated_cases:
        lc0 = updated_cases[0]
        lc = ExternalLoading(
            axial_force=lc0["axial_force_N"],
            bending_moment=lc0["bending_moment_Nmm"],
            shear_force=lc0["shear_force_N"],
            torsion=lc0["torsion_Nmm"],
            load_factor=lc0["load_factor"],
            case_name=lc0["case_name"],
        )
        dist = calculate_load_distribution(bc, lc)

        with col_chart:
            fig = make_bolt_circle_diagram(
                num_bolts=int(joint_cfg["num_bolts"]),
                bolt_circle_diameter_mm=float(joint_cfg["bolt_circle_diameter_mm"]),
                critical_bolt_index=dist.critical_bolt_index,
                bolt_axial_forces=dist.bolt_axial_forces,
                title=f"Load Case: {lc0['case_name']}",
            )
            st.plotly_chart(fig, use_container_width=False)

        with col_info:
            st.markdown(f"**Critical bolt:** #{dist.critical_bolt_index + 1} "
                        f"(θ = {dist.bolt_angles_deg[dist.critical_bolt_index]:.1f}°)")
            st.metric("Axial force on critical bolt", f"{dist.F_total_axial:,.0f} N")
            st.metric("  — Membrane contribution", f"{dist.F_axial_per_bolt:,.0f} N")
            st.metric("  — Bending contribution", f"{dist.F_bend_per_bolt:,.0f} N")
            st.metric("Shear per bolt", f"{dist.V_shear_per_bolt:,.0f} N")

except Exception as e:
    st.error(f"Preview error: {e}")

# ---------------------------------------------------------------------------
# Run analysis button
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Run Analysis")
if st.button("▶ Run Full Analysis", type="primary", use_container_width=True):
    try:
        from boltsizer.standards import get_bolt_geometry, get_material
        from boltsizer.models.bolt import Bolt
        from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer, ExternalLoading
        from boltsizer.calculations.vdi2230 import run_vdi2230_analysis

        geom = get_bolt_geometry(
            bolt_cfg["designation"],
            shank_length=bolt_cfg.get("shank_length_mm", 20.0),
            threaded_length=bolt_cfg.get("threaded_length_mm", 15.0),
        )
        mat = get_material(bolt_cfg["grade"]) if bolt_cfg["grade"] != "Custom" else get_material("ISO 8.8")
        bolt_obj = Bolt(geometry=geom, material=mat, grade=bolt_cfg["grade"])
        bc = BoltCircle(
            num_bolts=int(joint_cfg["num_bolts"]),
            bolt_circle_diameter=float(joint_cfg["bolt_circle_diameter_mm"]),
            bolt=bolt_obj,
            nut_factor_K=float(bolt_cfg.get("nut_factor_K", 0.16)),
            assembly_torque=float(bolt_cfg.get("assembly_torque_Nmm", 85000.0)),
            target_preload=float(bolt_cfg.get("target_preload_N", 0.0)),
            tightening_method=bolt_cfg.get("tightening_method", "torque_wrench"),
            num_mating_surfaces=int(bolt_cfg.get("num_mating_surfaces", 2)),
            surface_roughness_Rz=float(bolt_cfg.get("surface_roughness_Rz", 6.3)),
        )

        layers = [
            ClampedLayer(l["material"], l["thickness_mm"], l["E"])
            for l in joint_cfg["layers"]
        ]
        iface = ClampedInterface(
            total_clamped_length=sum(l["thickness_mm"] for l in joint_cfg["layers"]),
            layers=layers,
            interface_treatment=joint_cfg["interface_treatment"],
            friction_coefficient=float(joint_cfg["friction_coefficient"]),
            num_friction_interfaces=int(joint_cfg["num_friction_interfaces"]),
        )

        lcs = [
            ExternalLoading(
                axial_force=lc["axial_force_N"],
                bending_moment=lc["bending_moment_Nmm"],
                shear_force=lc["shear_force_N"],
                torsion=lc["torsion_Nmm"],
                load_plane=lc["load_plane"],
                load_factor=lc["load_factor"],
                case_name=lc["case_name"],
            )
            for lc in updated_cases
        ]

        results = run_vdi2230_analysis(
            bolt_circle=bc,
            interface=iface,
            load_cases=lcs,
            load_intro_factor_n=float(joint_cfg["load_intro_factor_n"]),
            plate_thickness=float(joint_cfg["plate_thickness_mm"]),
            plate_yield_strength=float(joint_cfg["plate_yield_strength_MPa"]),
            standard=st.session_state.get("standard", "VDI"),
        )

        st.session_state["analysis_results"] = results
        mark_page_complete("Loading", True)
        st.success("✅ Analysis complete! Go to Results page.")

    except Exception as e:
        st.error(f"Analysis error: {e}")
        import traceback
        st.code(traceback.format_exc())

st.divider()
col_back, col_fwd = st.columns(2)
with col_back:
    st.page_link("pages/02_Joint_Geometry.py", label="← Back: Joint Geometry", icon="📐")
with col_fwd:
    st.page_link("pages/04_Results.py", label="Next: Results →", icon="📊")
