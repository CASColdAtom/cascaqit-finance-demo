# 生物医药演示数据来源清单

## 1. 清单结论

当前发布包包含 8 组生物医药 fixture：5 组小分子电子结构、1 组公开结构派生的离散构象匹配数据、1 组项目生成的有效自旋模型、1 组项目生成的小肽离散构象库。

只有构象匹配使用外部公开结构，来源为 RCSB Protein Data Bank 的 `1HSG`。其余数据由项目固定参数生成。仓库不包含患者、临床试验受试者、内部化合物或未公开研发项目数据。运行时不访问网络，也不需要 PySCF、OpenFermion、RDKit、AutoDock 或 PDB 服务。

## 2. 数据集明细

| 数据集 ID | 内容 | 来源与复核日期 | 许可证 | 原始输入标识 | 生成方法 |
|---|---|---|---|---|---|
| `electronic.h2.sto3g.0500` | H2，0.500 Å，STO-3G，2e/2o | 项目生成，2026-07-30 | `project_generated` | `3781ba55...7fe7cb` | PySCF 2.10.0 + OpenFermion 1.7.1 + OpenFermion-PySCF 0.5 |
| `electronic.h2.sto3g.0735` | H2，0.735 Å，STO-3G，2e/2o | 项目生成，2026-07-30 | `project_generated` | `2df612f9...8b69e7` | 同上 |
| `electronic.h2.sto3g.1500` | H2，1.500 Å，STO-3G，2e/2o | 项目生成，2026-07-30 | `project_generated` | `8961734c...85709` | 同上 |
| `electronic.lih.sto3g.1600.active-2e-3o` | LiH，1.600 Å，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `38c697dd...d7c72` | 同上，冻结占据轨道 0 |
| `electronic.h2o.sto3g.equilibrium.active-2e-3o` | H2O，0.9584 Å / 104.45°，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `855bb5d6...00b4` | 同上，冻结占据轨道 0–3 |
| `docking.1hsg.indinavir.discrete-match` | HIV-1 Protease/Indinavir 固定离散特征匹配 | RCSB PDB `1HSG`，2026-07-29 | CC0-1.0 | mmCIF `d2ba73b5...3c268`，DOI `10.2210/pdb1hsg/pdb` | `docking-fixture-v1`，2 个 pose、8 个候选匹配 |
| `active-center.bimetal-spin.effective-model` | 双位点各向异性 spin-1/2 Heisenberg 有效模型 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `active-center-fixture-v1`，单位 meV |
| `peptide.six-residue.square-lattice` | 6 残基、二维方格、D4 对称归一化的 10 个自回避构象 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `peptide-fixture-v1`，确定性枚举 |

电子结构表中的“原始输入标识”是规范化分子、几何、基组、活性空间和映射参数的 SHA-256，不是外部文件 checksum。每个 manifest 还保存完整参数，不依赖缩略值复核。

## 3. 电子结构生成与复核

生成脚本为 `scripts/generate_electronic_structure_fixtures.py`，当前 SHA-256 为 `252df6cc41998d8326e206bb925326bdbe8d1bf68df4c1f246ef7b55f993b632`。固定环境命令：

```bash
uv run --no-project --isolated --python 3.11 \
  --with 'pyscf==2.10.0' \
  --with 'openfermion==1.7.1' \
  --with 'openfermionpyscf==0.5' \
  python scripts/generate_electronic_structure_fixtures.py
```

生成流程执行 Hartree-Fock、活性空间裁剪、对称性守恒 Bravyi-Kitaev 映射和双量子位消去。manifest 分开记录：

- `spin_orbital_count`：映射前活性自旋轨道数；
- `tapered_qubit_count`：因对称性消去的量子位数，固定为 2；
- `final_qubit_count`：进入 CASCAQit 的逻辑量子位数，H2 为 2，LiH/H2O 为 4。

运行时加载器复核 artifact checksum、逻辑顺序、Pauli 项、有限系数和参考能量。精确参考值来自固化 Pauli Hamiltonian 的精确对角化；全空间 FCI 能量只作为生成信息，不与活性空间 VQE 结果混用。

## 4. 1HSG 派生数据

来源地址为 <https://files.rcsb.org/download/1HSG.cif>，RCSB 政策页为 <https://www.rcsb.org/pages/policies>。RCSB 声明 PDB archive 数据文件按 CC0 1.0 Universal Public Domain Dedication 提供；外部集成注释可能有独立条款。本项目只使用并打包最小派生特征，不打包原始 mmCIF。

派生 fixture 保存：

- PDB ID、配体 component ID `MK1`、名称 `INDINAVIR`；
- 原始 mmCIF SHA-256、初始发布日期和最新修订日期；
- 2 个固定 pose、8 个候选匹配、4 条冲突关系和最低覆盖数 2；
- `domain.json` 与 `reference.json` 的独立 checksum。

允许说明“基于 1HSG 共晶结构派生的离散特征匹配”。不得说明为任意配体对接、结合自由能计算或药效预测。

## 5. 项目生成模型

### 有效自旋模型

数据是为了演示 `XX/YY/ZZ` 交换项、局域场和 QWC 可观测量而固定的低能模型，没有引用具体金属酶文献参数。它只能称为“双金属语境下的两自旋有效模型”，不能称为从真实蛋白结构或电子轨道自动得到的 Hamiltonian。

`domain.json` SHA-256 为 `997632f18b2c5eccebf3e0465e642d681a4f929b9fc607da4f5ca9334e5fecd7`；`pauli.json` SHA-256 为 `72a25fdb54a7e3df582cb57a3df4ec4e53c0381b731548e5920627c6a6850476`。

### 小肽构象库

构象库由长度为 6 的二维方格自回避行走确定性枚举并按平移和 D4 对称去重。`domain.json` SHA-256 为 `6fc87e6f7feabc04907ed08541a7cac25cd43cd4c9f08068e5ea82a8cc8c3e56`。

接触分数是无量纲教学模型，不是分子自由能。数据没有溶剂、侧链几何、动力学或生物功能信息。

## 6. 发布包检查

Python wheel 必须包含以下目录及其中全部 JSON：

```text
cascaqit_biomedicine_demo/data/electronic_structure/
cascaqit_biomedicine_demo/data/docking_match/
cascaqit_biomedicine_demo/data/active_center/
cascaqit_biomedicine_demo/data/peptide_landscape/
```

发布检查应同时验证：

1. manifest 与 artifact checksum 一致；
2. 五组电子结构 fixture 的生成脚本 hash 一致；
3. 外部来源只有 `1HSG`，许可证状态为 CC0-1.0；
4. 项目生成数据明确标记为 `project_generated`；
5. 页面显示来源、许可证、允许说法和限制；
6. 标准运行不发起网络请求。
