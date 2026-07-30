# 生物医药演示数据来源清单

## 1. 清单结论

当前开发分支包含 17 组生物医药 fixture：9 组小分子电子结构、2 组公开结构派生的离散构象匹配数据、3 组项目生成的有效自旋模型、2 组项目生成的小肽离散构象库，以及 1 组短 RNA 候选配对基准。新增高级 fixture 在 V2 发布验收完成前仍属于开发资产，不表示高级入口已经正式发布。

构象匹配使用 RCSB Protein Data Bank 的 `1HSG` 派生数据；RNA 发卡预设引用 RCSB PDB `1ZIH` 的公开序列和二级结构元数据，其候选配对与教学评分由项目整理。其余数据由项目固定参数生成。仓库不包含患者、临床试验受试者、内部化合物或未公开研发项目数据。运行时不访问网络，也不需要 PySCF、OpenFermion、RDKit、AutoDock 或 PDB 服务。

十七组 manifest 均通过统一运行时契约校验，明确记录原始输入 checksum 状态、生成工具版本和参数、单位、坐标系、变量顺序、经典参考方法与软件版本、标准预设参考结果、允许说法和限制。项目生成且没有外部原始文件的数据以 `raw_file_sha256: null` 明确记录，不用缺失字段掩盖来源边界。

## 2. 数据集明细

| 数据集 ID | 内容 | 来源与复核日期 | 许可证 | 原始输入标识 | 生成方法 |
|---|---|---|---|---|---|
| `electronic.h2.sto3g.0500` | H2，0.500 Å，STO-3G，2e/2o | 项目生成，2026-07-30 | `project_generated` | `3781ba55...7fe7cb` | PySCF 2.10.0 + OpenFermion 1.7.1 + OpenFermion-PySCF 0.5 |
| `electronic.h2.sto3g.0735` | H2，0.735 Å，STO-3G，2e/2o | 项目生成，2026-07-30 | `project_generated` | `2df612f9...8b69e7` | 同上 |
| `electronic.h2.sto3g.1500` | H2，1.500 Å，STO-3G，2e/2o | 项目生成，2026-07-30 | `project_generated` | `8961734c...85709` | 同上 |
| `electronic.lih.sto3g.1200.active-2e-3o` | LiH，1.200 Å，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `ca16342e...9b988` | 同上，冻结占据轨道 0 |
| `electronic.lih.sto3g.1400.active-2e-3o` | LiH，1.400 Å，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `ce5cb222...288ca` | 同上，冻结占据轨道 0 |
| `electronic.lih.sto3g.1600.active-2e-3o` | LiH，1.600 Å，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `38c697dd...d7c72` | 同上，冻结占据轨道 0 |
| `electronic.lih.sto3g.1800.active-2e-3o` | LiH，1.800 Å，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `e02acc2f...26715f` | 同上，冻结占据轨道 0 |
| `electronic.lih.sto3g.2200.active-2e-3o` | LiH，2.200 Å，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `19dad269...e6a1e` | 同上，冻结占据轨道 0 |
| `electronic.h2o.sto3g.equilibrium.active-2e-3o` | H2O，0.9584 Å / 104.45°，STO-3G，2e/3o | 项目生成，2026-07-30 | `project_generated` | `855bb5d6...00b4` | 同上，冻结占据轨道 0–3 |
| `docking.1hsg.indinavir.discrete-match` | HIV-1 Protease/Indinavir 固定离散特征匹配 | RCSB PDB `1HSG`，2026-07-29 | CC0-1.0 | mmCIF `d2ba73b5...3c268`，DOI `10.2210/pdb1hsg/pdb` | `docking-fixture-v1`，2 个 pose、8 个候选匹配 |
| `docking.1hsg.indinavir.advanced-discrete-match` | 同一 1HSG 来源的三构象高级离散匹配图 | RCSB PDB `1HSG`，2026-07-30 | CC0-1.0 | 与标准数据共用 mmCIF 标识 | `docking-fixture-v2`，3 个 pose、24 个候选、12 条冲突，活动窗口 9 个匹配 |
| `active-center.bimetal-spin.effective-model` | 双位点各向异性 spin-1/2 Heisenberg 有效模型 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `active-center-fixture-v2`，单位 meV |
| `active-center.trinuclear-spin.effective-model` | 三位点三角受挫各向异性 Heisenberg 有效模型 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `active-center-fixture-v2`，单位 meV |
| `active-center.tetranuclear-spin.effective-model` | 四位点环形配体场各向异性 Heisenberg 有效模型 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `active-center-fixture-v2`，单位 meV |
| `peptide.six-residue.square-lattice` | 6 残基、二维方格、D4 对称归一化的 10 个自回避构象 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `peptide-fixture-v1`，确定性枚举 |
| `peptide.eight-residue.square-lattice` | 8 残基、二维方格、D4 对称归一化的 48 个自回避构象和 8 个盆地 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件 | `peptide-fixture-v2`，确定性枚举，活动窗口 12 个构象 |
| `rna.short-pairing-benchmarks` | 3 个短 RNA 预设、8–9 个候选配对、声明的假结策略 | RCSB PDB `1ZIH` 元数据 + 项目整理，2026-07-30 | RCSB PDB usage policy / project-generated candidate model | 不打包外部原始文件 | `rna-pairing-fixture-v1`，经典枚举和无假结动态规划参考 |
| `materials.surface-defect-adsorption.educational` | 3 个周期表面预设、3 个缺陷候选、8 个吸附构型候选 | 项目生成，2026-07-30 | `project_generated` | 无外部原始文件；domain SHA-256 `9c3c28d1...2c38c15` | `surface-config-fixture-v1`，完整枚举和独立默认控制参考 |

电子结构表中的“原始输入标识”是规范化分子、几何、基组、活性空间和映射参数的 SHA-256，不是外部文件 checksum。每个 manifest 还保存完整参数，不依赖缩略值复核。

## 3. 电子结构生成与复核

生成脚本为 `scripts/generate_electronic_structure_fixtures.py`，当前 SHA-256 为 `669253abba78ff95255d3c4b7430ab97479e694965aa06811f05b9bc7efd9f03`。固定环境命令：

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

高级 fixture 复用同一公开结构来源，扩展为 3 个固定 pose、24 个候选匹配和 12 条冲突关系。运行时按 `docking-active-subproblem-v1` 选择 9 个匹配；完整业务图没有送入 28 变量实时状态向量模拟。生成脚本为 `scripts/generate_advanced_docking_fixture.py`，SHA-256 为 `ea252ae8653c3cb587be8762281371f383f8567b4c1defb7d5e318a51db3a0da`。`domain.json` 与 `reference.json` 的 SHA-256 分别为 `760a017d...14298cc` 和 `d4c2c77b...3767a77`。

允许说明“基于 1HSG 共晶结构派生的离散特征匹配”。不得说明为任意配体对接、结合自由能计算或药效预测。

## 5. 项目生成模型

### 有效自旋模型

三组数据用于演示 `XX/YY/ZZ` 交换项、局域场和 QWC 可观测量，没有引用具体金属酶文献参数。双位点模型用于标准实验；三位点三角网络和四位点环形网络用于高级实验。它们只能称为“金属活性中心语境下的低能有效自旋模型”，不能称为从真实蛋白结构或电子轨道自动得到的 Hamiltonian。

生成脚本 `scripts/generate_active_center_fixtures.py` 的 SHA-256 为 `66e14e0a0fba02df27b2b1cd90873f3168c0daaff9d164c6dbe1fc06f0e9ad4b`。每组 manifest 分别登记 `domain.json`、`pauli.json` 和脚本 checksum，并保存经典精确基态能量与第一能隙；第一能隙只能标记为经典参考。

### 小肽构象库

标准构象库由长度为 6 的二维方格自回避行走确定性枚举并按平移和 D4 对称去重。`domain.json` SHA-256 为 `6fc87e6f7feabc04907ed08541a7cac25cd43cd4c9f08068e5ea82a8cc8c3e56`。

高级构象库使用同一套平移与 D4 归一化规则，保存 48 个八残基构象。接触图汉明距离阈值为 2，确定性生成 8 个盆地；运行时保留 12 个活动构象。生成脚本为 `scripts/generate_advanced_peptide_fixture.py`，SHA-256 为 `85fe49f93569bded0259b6b0ea75a7b91ec75fa85ff9dc5bda5f26aa0a683580`；`domain.json` SHA-256 为 `a822a571...5ed280`。

接触分数是无量纲教学模型，不是分子自由能。数据没有溶剂、侧链几何、动力学或生物功能信息。

### 短 RNA 候选配对基准

`hairpin_reference` 使用 `PDB:1ZIH` 的 `GGACUUCGGUCC` 序列和 `((((....))))` 参考二级结构元数据；`stem_competition` 与 `limited_pseudoknot` 是项目整理研究预设。所有候选只允许 A-U、C-G 和声明的 G-U 摆动配对，并保存一基位置、最小环长、允许交叉和参考配对 ID。

`canonical-pairing.educational.v1` 的配对收益、未配对代价和堆叠奖励均为无量纲教学分数。它不包含温度、溶剂、离子、三维坐标或动力学参数，不能解释为自由能模型。运行时只加载已固化预设，不联网查询 PDB，也不从 QAOA counts 推导配对概率。

### 周期表面缺陷与吸附教学模型

材料 fixture 固化 CeO2(111) / CO、TiO2(110) / H2O 和 MoS2 / H 三个预设，共用 12 个材料晶格显示位点、3 个缺陷候选和 8 个吸附构型候选。`domain.json` 明确记录二维周期单元、周期边界、对称操作、候选取向、局域互斥、禁配组合、形成能、吸附能、协同和近邻系数；`reference.json` 单独保存默认控制下的离线参考构型。

全部系数为无量纲项目生成教学值，没有引用或打包外部 DFT 数据。运行时不执行 DFT，不访问材料数据库。页面只能比较给定离散模型内的构型目标，不得把这些值解释为真实形成能、吸附自由能、催化活性、反应速率、选择性、稳定性或可合成性。

## 6. 发布包检查

Python wheel 必须包含以下目录及其中全部 JSON：

```text
cascaqit_biomedicine_demo/data/electronic_structure/
cascaqit_biomedicine_demo/data/docking_match/
cascaqit_biomedicine_demo/data/active_center/
cascaqit_biomedicine_demo/data/peptide_landscape/
cascaqit_biomedicine_demo/data/rna_structure/
cascaqit_materials_demo/data/defect_adsorption/
```

发布检查应同时验证：

1. manifest 与 artifact checksum 一致；
2. 九组电子结构 fixture 的生成脚本 hash 一致；
3. 外部引用限于 `1HSG` 派生数据和 `1ZIH` 公开元数据，并分别显示许可证/使用政策边界；
4. 项目生成数据明确标记为 `project_generated`；
5. 页面显示来源、许可证、允许说法和限制；
6. 标准运行不发起网络请求。
7. 坐标系、变量顺序和全部登记预设的经典参考值与运行时重算结果一致；
8. 三组有效自旋 fixture 的生成脚本 hash 一致，模板 hash 和参数实例 Hamiltonian hash 分开保存。
9. 两组高级组合优化 fixture 的生成脚本 hash、完整问题 hash、选择 hash 和活动 QUBO hash 分开复核。
