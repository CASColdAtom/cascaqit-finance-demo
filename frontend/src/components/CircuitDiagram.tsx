import { CircuitBoard } from "lucide-react";
import type { QuantumPayload } from "../types";
import { useI18n } from "../i18n";

/** 展示后端返回的 QAOA 逻辑层，不在客户界面展开底层通用门分解。 */
export function CircuitDiagram({ quantum }: { quantum: QuantumPayload }) {
  const { t } = useI18n();
  return (
    <section className="circuit-workspace" aria-label={t("digitalCircuit")}>
      <div className="subsection-head">
        <div>
          <span className="section-kicker">
            <CircuitBoard size={14} aria-hidden="true" /> QAOA
          </span>
          <h3>{t("logicalLayers")}</h3>
        </div>
      </div>
      <div className="layer-rail" role="img" aria-label={`${quantum.mode} ${t("logicalLayers")}`}>
        {quantum.layers.map((layer, index) => (
          <div className={`layer-node layer-${layer.toLowerCase()}`} key={`${layer}-${index}`}>
            <small>{String(index + 1).padStart(2, "0")}</small>
            <strong>{layer}</strong>
            <span>
              {layer === "A" || layer === "AHS"
                ? "ANALOG"
                : layer === "M" || layer === "MEASURE"
                  ? "READOUT"
                  : "DIGITAL"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
