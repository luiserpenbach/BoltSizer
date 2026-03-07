import { Button, FormGroup, HTMLSelect, NumericInput } from "@blueprintjs/core";
import type { LayerConfig } from "../../types";

interface Props {
  layers: LayerConfig[];
  flangeMaterials: Record<string, number>;
  onChange: (layers: LayerConfig[]) => void;
}

export function LayerEditor({ layers, flangeMaterials, onChange }: Props) {
  const matOptions = Object.keys(flangeMaterials);

  const update = (i: number, patch: Partial<LayerConfig>) => {
    const next = layers.map((l, idx) => (idx === i ? { ...l, ...patch } : l));
    onChange(next);
  };

  const add = () =>
    onChange([
      ...layers,
      { material: "Steel (carbon)", thickness_mm: 10, E: 210000 },
    ]);

  const remove = (i: number) => {
    if (layers.length <= 1) return;
    onChange(layers.filter((_, idx) => idx !== i));
  };

  const totalGrip = layers.reduce((s, l) => s + l.thickness_mm, 0);

  return (
    <div>
      {layers.map((layer, i) => (
        <div key={i} className="layer-row">
          <div>
            <FormGroup label={`Layer ${i + 1} — Material`} style={{ marginBottom: 0 }}>
              <HTMLSelect
                value={layer.material}
                onChange={(e) => {
                  const mat = e.target.value;
                  const E = flangeMaterials[mat] ?? 210000;
                  update(i, { material: mat, E });
                }}
                options={matOptions}
                fill
              />
            </FormGroup>
          </div>
          <div>
            <FormGroup label="Thickness [mm]" style={{ marginBottom: 0 }}>
              <NumericInput
                value={layer.thickness_mm}
                min={0.1}
                max={500}
                stepSize={0.5}
                minorStepSize={0.1}
                onValueChange={(v) => update(i, { thickness_mm: v })}
                fill
              />
            </FormGroup>
          </div>
          <div>
            <FormGroup label="E [MPa]" style={{ marginBottom: 0 }}>
              <NumericInput
                value={layer.E}
                min={1000}
                max={500000}
                stepSize={1000}
                onValueChange={(v) => update(i, { E: v })}
                fill
              />
            </FormGroup>
          </div>
          <div style={{ paddingBottom: 2 }}>
            <Button
              icon="minus"
              minimal
              small
              intent="danger"
              onClick={() => remove(i)}
              disabled={layers.length <= 1}
            />
          </div>
        </div>
      ))}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 8 }}>
        <Button icon="plus" minimal small intent="primary" onClick={add}>
          Add Layer
        </Button>
        <span className="mono" style={{ fontSize: 12, color: "var(--text-secondary)", alignSelf: "center" }}>
          Total l_K = {totalGrip.toFixed(1)} mm
        </span>
      </div>
    </div>
  );
}
