const TERM_TITLES: Record<string, string> = {
  VQE: "变分量子本征求解器",
  QAOA: "量子近似优化算法",
  QWC: "逐量子比特可对易测量分组",
  QUBO: "二次无约束二元优化",
  "D-A-D": "数字-模拟-数字混合执行序列",
  HF: "Hartree-Fock 平均场参考",
  QAA: "量子绝热算法",
  AHS: "模拟 Hamiltonian 仿真",
};

const TERM_PATTERN = /(D-A-D|QAOA|QUBO|QWC|VQE|HF|QAA|AHS)/g;

export function QuantumText({ text }: { text: string }) {
  return text.split(TERM_PATTERN).map((fragment, index) =>
    TERM_TITLES[fragment] ? (
      <abbr className="quantum-term" title={TERM_TITLES[fragment]} key={`${fragment}-${index}`}>
        {fragment}
      </abbr>
    ) : (
      fragment
    ),
  );
}
