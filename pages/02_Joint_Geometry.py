"""Page 2 — Joint Geometry.

User defines the bolt circle, clamped stack layers, interface friction,
and load introduction factor. Live compliance calculations shown.
"""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boltsizer.ui.session_state import init_session_state, mark_page_complete, render_sidebar_progress
from boltsizer.standards.material_library import FLANGE_MATERIAL_E

st.set_page_config(page_title="Joint Geometry — BoltSizer", page_icon="📐", layout="wide")
init_session_state()
render_sidebar_progress()

st.title("📐 Step 2: Joint Geometry")
st.caption("Define the bolt circle pattern, clamped stack, and interface friction.")

cfg = st.session_state["joint_config"]
bolt_cfg = st.session_state["bolt_config"]

col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.subheader("Bolt Circle")
    c1, c2 = st.columns(2)
    with c1:
        cfg["num_bolts"] = st.number_input(
            "Number of bolts", min_value=1, max_value=48,
            value=int(cfg.get("num_bolts", 8)),
            step=1,
            help="Total number of bolts in the pattern.",
        )
    with c2:
        cfg["bolt_circle_diameter_mm"] = st.number_input(
            "Bolt circle diameter PCD [mm]",
            min_value=1.0, max_value=5000.0,
            value=float(cfg.get("bolt_circle_diameter_mm", 100.0)),
            step=1.0,
        )

    st.subheader("Clamped Stack (Layers)")
    st.caption("Define each layer from bolt head to nut. Order does not affect the calculation.")

    material_options = list(FLANGE_MATERIAL_E.keys()) + ["Custom"]

    layers = cfg.get("layers", [{"material": "Steel (carbon)", "thickness_mm": 20.0}])

    # Add / remove layer buttons
    c_add, c_rem = st.columns(2)
    with c_add:
        if st.button("➕ Add Layer"):
            layers.append({"material": "Steel (carbon)", "thickness_mm": 10.0})
    with c_rem:
        if st.button("➖ Remove Last Layer") and len(layers) > 1:
            layers.pop()

    updated_layers = []
    for i, layer in enumerate(layers):
        with st.expander(f"Layer {i+1}: {layer['material']} ({layer['thickness_mm']:.0f} mm)", expanded=(i == 0)):
            lc1, lc2, lc3 = st.columns([2, 2, 2])
            with lc1:
                mat = st.selectbox(
                    "Material",
                    options=material_options,
                    index=material_options.index(layer["material"]) if layer["material"] in material_options else 0,
                    key=f"layer_mat_{i}",
                )
            with lc2:
                thk = st.number_input(
                    "Thickness [mm]",
                    min_value=0.1, max_value=500.0,
                    value=float(layer["thickness_mm"]),
                    step=0.5,
                    key=f"layer_thk_{i}",
                )
            with lc3:
                if mat == "Custom":
                    E = st.number_input(
                        "E [MPa]",
                        min_value=1000.0, max_value=500000.0,
                        value=float(layer.get("E_override", 210000.0)),
                        step=1000.0,
                        key=f"layer_E_{i}",
                    )
                else:
                    E = FLANGE_MATERIAL_E.get(mat, 210000.0)
                    st.metric("E [MPa]", f"{E:,.0f}")
            updated_layers.append({"material": mat, "thickness_mm": thk, "E": E})

    cfg["layers"] = updated_layers
    total_grip = sum(l["thickness_mm"] for l in updated_layers)
    st.info(f"Total grip length l_K = **{total_grip:.1f} mm**")

    st.subheader("Interface Treatment & Friction")
    interface_options = {
        "bare metal": 0.12,
        "anodised aluminium": 0.10,
        "painted": 0.08,
        "sandblasted": 0.35,
        "knurled": 0.25,
        "user-defined": None,
    }
    c1, c2 = st.columns(2)
    with c1:
        treatment = st.selectbox(
            "Interface treatment",
            list(interface_options.keys()),
            index=0,
            key="interface_treatment_sel",
        )
        cfg["interface_treatment"] = treatment
    with c2:
        default_mu = interface_options.get(treatment, 0.12) or cfg.get("friction_coefficient", 0.12)
        cfg["friction_coefficient"] = st.number_input(
            "Friction coefficient μ",
            min_value=0.01, max_value=1.0,
            value=float(cfg.get("friction_coefficient", default_mu)),
            step=0.01,
            format="%.2f",
            help="Friction coefficient at the shear interface.",
        )
    cfg["num_friction_interfaces"] = st.number_input(
        "Number of friction interfaces",
        min_value=1, max_value=8,
        value=int(cfg.get("num_friction_interfaces", 1)),
        help="n_i for slip check (number of surfaces where slip is resisted).",
    )

    st.subheader("Load Introduction")
    cfg["load_intro_factor_n"] = st.slider(
        "Load introduction factor n",
        min_value=0.0, max_value=1.0,
        value=float(cfg.get("load_intro_factor_n", 0.5)),
        step=0.05,
        help=(
            "0 = load introduced at the interface (most conservative for bolt). "
            "1 = load introduced at the bolt head/nut. "
            "VDI 2230 §5.3."
        ),
    )

    st.subheader("Plate Bearing Check")
    c1, c2 = st.columns(2)
    with c1:
        cfg["plate_thickness_mm"] = st.number_input(
            "Thinnest plate thickness [mm]",
            min_value=0.5, max_value=500.0,
            value=float(cfg.get("plate_thickness_mm", 20.0)),
            step=0.5,
        )
    with c2:
        cfg["plate_yield_strength_MPa"] = st.number_input(
            "Plate yield strength [MPa]",
            min_value=50.0, max_value=2000.0,
            value=float(cfg.get("plate_yield_strength_MPa", 240.0)),
            step=10.0,
        )

# ---------------------------------------------------------------------------
# Right column: compliance preview
# ---------------------------------------------------------------------------
with col_right:
    st.subheader("Stiffness Preview")
    try:
        from boltsizer.standards import get_bolt_geometry, get_material
        from boltsizer.models.bolt import Bolt
        from boltsizer.models.joint import BoltCircle, ClampedInterface, ClampedLayer
        from boltsizer.calculations.joint_stiffness import calculate_joint_stiffness

        b_cfg = bolt_cfg
        geom = get_bolt_geometry(
            b_cfg["designation"],
            shank_length=b_cfg.get("shank_length_mm", 20.0),
            threaded_length=b_cfg.get("threaded_length_mm", 15.0),
        )
        mat = get_material(b_cfg["grade"]) if b_cfg["grade"] != "Custom" else get_material("ISO 8.8")
        bolt = Bolt(geometry=geom, material=mat, grade=b_cfg["grade"])
        bc = BoltCircle(
            num_bolts=int(cfg["num_bolts"]),
            bolt_circle_diameter=float(cfg["bolt_circle_diameter_mm"]),
            bolt=bolt,
            nut_factor_K=float(b_cfg.get("nut_factor_K", 0.16)),
            assembly_torque=float(b_cfg.get("assembly_torque_Nmm", 85000.0)),
        )

        cls = [
            ClampedLayer(l["material"], l["thickness_mm"], l["E"])
            for l in cfg["layers"]
        ]
        iface = ClampedInterface(
            total_clamped_length=total_grip,
            layers=cls,
            interface_treatment=cfg["interface_treatment"],
            friction_coefficient=float(cfg["friction_coefficient"]),
            num_friction_interfaces=int(cfg["num_friction_interfaces"]),
        )

        stiff = calculate_joint_stiffness(bc, iface, float(cfg["load_intro_factor_n"]))

        st.metric("Bolt compliance δ_S", f"{stiff.delta_S:.4e} mm/N")
        st.metric("Clamped-part compliance δ_P", f"{stiff.delta_P:.4e} mm/N")
        st.metric("Force ratio φ (basic)", f"{stiff.phi_basic:.4f}",
                  help="φ = δ_P / (δ_S + δ_P). Fraction of external load seen by bolt.")
        st.metric("Force ratio φ_n (with n)", f"{stiff.phi_n:.4f}",
                  delta=f"n = {stiff.load_intro_factor_n:.2f}",
                  delta_color="off")

        # Visual ratio bar
        st.markdown("**Load sharing: bolt vs. clamped plates**")
        st.progress(stiff.phi_basic, text=f"Bolt takes {stiff.phi_basic*100:.1f}% of external load")

        # Bolt circle preview
        from boltsizer.ui.components.bolt_circle_viz import make_bolt_circle_diagram
        fig = make_bolt_circle_diagram(
            num_bolts=int(cfg["num_bolts"]),
            bolt_circle_diameter_mm=float(cfg["bolt_circle_diameter_mm"]),
            title=f"{int(cfg['num_bolts'])}× {b_cfg['designation']} on PCD {cfg['bolt_circle_diameter_mm']:.0f} mm",
        )
        st.plotly_chart(fig, use_container_width=False)

    except Exception as e:
        st.error(f"Preview error: {e}")

st.session_state["joint_config"] = cfg
mark_page_complete("Joint Geometry", True)

st.divider()
col_back, col_fwd = st.columns(2)
with col_back:
    st.page_link("pages/01_Bolt_Selection.py", label="← Back: Bolt Selection", icon="🔩")
with col_fwd:
    st.page_link("pages/03_Loading.py", label="Next: Loading →", icon="⚡")
