# Statistical Evidence on GAIA, Gaia2, and SWE-bench: ICLR 2024–2026 Papers and Model Releases from OpenAI, Anthropic, and Google DeepMind

**No reviewed ICLR paper or examined official model-evaluation material was confirmed to report a multiplicity-adjusted p-value for a performance improvement on the target benchmarks. Consequently, we identified no reported instance of an improvement established as statistically significant after multiple-comparison correction within this scope.** This is a finding about the published evidence: the review did not recompute adjusted p-values from underlying experimental data.

**The audit supports two principal conclusions.** First, no reviewed ICLR paper or examined official model-evaluation material was confirmed to report a multiplicity-adjusted p-value for a target performance improvement; no instance of reported statistical significance after such correction was therefore confirmed. Second, PORCHESTRA's rebuttal provides a comparatively comprehensive combination of repeated evaluation, cross-run mean±SD, and formal main/ablation tests within this ICLR sample.

Among the 63 papers, 16 report target-related repeated evaluations, three explicitly report cross-run/seed result SDs, and two report comparison tests in target-derived experiments. However, **none was confirmed to report a multiplicity-adjusted p-value for a target performance improvement**. Accordingly, no paper was confirmed to report such an improvement as statistically significant after multiple-comparison correction.

All three vendors have examples of repeated SWE-bench evaluation, and some OpenAI cards also provide bootstrap confidence intervals. Nevertheless, **no multiplicity-adjusted p-value for a target performance improvement was identified in the examined official model-evaluation materials**. No reported instance of an improvement established as statistically significant after such correction was therefore confirmed in those materials either.

<a id="contents"></a>

## Contents

- [Suggested statement for an author response](#response-statement)
- [Part I: 63 accepted ICLR papers](#papers)
  - [Scope and six audit dimensions](#dimensions)
  - [Counts and reporting completeness](#counts)
  - [PORCHESTRA's position in the sample](#position)
  - [Evidence by dimension](#evidence)
  - [SD interval separation](#intervals)
  - [Complete paper index](#paper-index)
  - [All 63 individual paper assessments](#paper-details)
  - [Counting rules and supporting files](#paper-methods)
- [Part II: Vendor model evaluations](#vendors)
  - [Scope and interpretation](#vendor-scope)
  - [All model-group assessments](#vendor-models)
  - [GAIA/Gaia2 and later model releases](#vendor-exclusions)
  - [Official quotations and statistical power](#vendor-quotes)
  - [Comparison with PORCHESTRA and source records](#vendor-position)

<a id="response-statement"></a>

## Suggested statement for an author response

We reviewed 63 accepted ICLR 2024–2026 papers using GAIA, Gaia2, or SWE-bench, together with the related public model-evaluation materials released by OpenAI, Anthropic, and Google DeepMind during the same period. Across the target performance comparisons examined, we found no confirmed report of a multiplicity-adjusted p-value for an improvement. Consequently, we identified no reported performance improvement established as statistically significant after multiple-comparison correction within this scope. Thus, reporting statistically significant improvements supported by multiplicity-adjusted p-values is not an established reporting practice in this reviewed sample.

During the rebuttal, we added three independent evaluations, cross-run mean±SD, and Pass@3, together with formal tests of both OPOD's main comparison and its ablated contributions. This combined coverage places our statistical reporting among the more comprehensive examples in the reviewed ICLR sample. Our evaluation also spans multiple real long-horizon benchmarks, backbones, and comparison settings. Such evaluations are expensive, and some contain only tens to a few hundred independent tasks. These conditions limit statistical power under feasible evaluation budgets; detecting modest effects at stringent multiplicity-adjusted thresholds can require substantially more independent tasks or repeated evaluations. Effect sizes, between-run variability, and consistency across settings provide complementary evidence of the empirical contribution.

<a id="papers"></a>

## Part I: 63 accepted ICLR papers

The sample contains 63 deduplicated main-conference papers: two from ICLR 2024, ten from 2025, and 51 from 2026. Actual use includes original tasks, subsets, derived tasks, trajectory analyses, and case studies. Inclusion therefore does not imply that every paper evaluates a solver on the complete original benchmark.

Peer evidence comes from final conference PDFs and their in-document appendices. Page references below use physical PDF pages. PORCHESTRA's evidence is the author responses supplied for the November 11 and November 15 reviewer exchange; its results were not re-estimated from raw logs in this audit. “Not confirmed” means that explicit corresponding reporting was not located within the reviewed material.

<a id="dimensions"></a>

### 1. Six dimensions of the statistical review

| Dimension | Reviewer concern | Audit question |
|---|---|---|
| A. Independent repeats | “only ran pass@1”; “over three runs” | Were evaluations independently repeated, and how many times? Distinguish a mean pass@1 from pass@k. |
| B. Between-run uncertainty | “fall within run-to-run variance” | Are SD, SE, or intervals reported, and what do they quantify? |
| C. Main/ablation tests | “process supervision over its ablation is not shown to be significant” | Are the main method versus a baseline and the full method versus ablations each formally tested? |
| D. Direction and unit | “one-sided tests over three runs” | Is the test one-sided/two-sided, and are observations runs, paired task outcomes, model scores, or another quantity? |
| E. Multiplicity correction | “without multiple-comparison correction” | Is a comparison family defined, with a correction method and adjusted p-values? |
| F. Mean-plus-SD criterion | “mean-plus-one-standard-deviation criterion” | Is mean > baseline mean + SD used descriptively, and are formal tests reported separately? |

The four-part joint-reporting assessment refers to A, B, C, and E. D and F identify the method and distinguish descriptive comparisons from hypothesis tests. Within C, main-method and ablation claims are assessed separately.

<a id="counts"></a>

### 2. Counts and joint reporting


| Evidence | Confirmed count | Interpretation |
| --- | --- | --- |
| Target-related repeats or multiple seeds | 16/63 (25.4%) | Includes baseline, attribution, and output-stochasticity studies. Fifteen state a count; one only states multiple trials. |
| Repeats of direct task-score evaluation | 10/63 | Includes subsets and the small PwP SWE/GUI setting. |
| Candidate-pool random subsampling | One additional paper | SWE-RM; separate from the 16 evaluation-repeat papers. |
| Target-related variance or SD | 6/63 | Includes subset distributions, output variance, and random subsampling. |
| Explicit cross-run/seed result SD | 3/63 (4.8%) | AgenTracer, Aegis, and M2CL. DoVer has undefined ± quantities. |
| Any numerical target-related uncertainty | 12/63 | Includes SD, SE, CI, variance, and undefined ±. |
| Repeats and numerical uncertainty together | 8/63 | Intersection of the two reporting categories. |
| SD stated but target numerical SD not confirmed | Two additional cases | DeepScientist and AgentFlow. |
| Named test and p-value anywhere in the paper | 6/63 | Includes correlation, regression, other benchmarks, and attention analysis. |
| Comparison test in a target-derived experiment | 2/63 | DeepScientist and Ambig-SWE. |
| Significant positive difference in those comparisons | 1/63 | Ambig-SWE; the identified DeepScientist ablation p-values are not significant. |
| Named test and p-value for original-benchmark solver-success improvement | 0 confirmed | Strictly the original GAIA/Gaia2/SWE-bench solving outcome. |
| Adjusted p-values for target performance improvements | 0 confirmed | No confirmed published report of the corresponding multiplicity adjustment. |
| Repeats + uncertainty + improvement test + multiplicity correction | 0 confirmed | The complete four-part combination. |


The confirmed intersection of repeated evaluation, numerical uncertainty, and a target-related comparison test is already zero. Adding multiplicity correction leaves zero confirmed papers. The correction finding also means that no reviewed paper was confirmed to report a target improvement as significant after multiple-comparison correction. It does not mean that every underlying effect would fail a properly specified adjusted test.

<a id="position"></a>

### 3. PORCHESTRA's reporting completeness within the sample

| Dimension | Evidence in the supplied rebuttal | Position relative to the reviewed sample |
|---|---|---|
| A | Three independent evaluations for multiple configurations; mean Pass@1 and Pass@3. | Within the minority explicitly reporting repeated evaluation; eight of the 16 peer cases also use three repeats. |
| B | Mean±SD on GAIA/Gaia2 and supplementary harness/benchmark comparisons. | Explicit cross-run SD is confirmed in only three peer papers. |
| C | Two one-sided exact McNemar tests for OPOD versus SFT; four one-sided Welch tests for the two ablations across two benchmarks. | Covers both the main improvement and ablated contributions. |
| D | Test names and directions are explicit; task outcome pairing and run-score testing are distinguished. | Provides a clearer account of what each test evaluates. |
| E | Raw p-values are reported; adjusted p-values are not reported. | No corresponding target-improvement correction report was confirmed in the peer sample. |
| F | The mean-plus-SD criterion is used descriptively; McNemar/Welch tests are reported separately. | Provides descriptive comparisons alongside separate formal tests. |

The main OPOD-versus-SFT p-values are 0.0213 and 0.0302. The four reported ablation p-values are 0.03035, 0.03892, 0.03410, and 0.04570. These are the reported unadjusted one-sided results.

The position assessment concerns the breadth and combination of reported evidence, not the largest number of repeats or a numerical percentile. The vendor evaluations are contextual evidence and are not pooled with the 63 papers to calculate a ranking.

The supplied author responses also cover GAIA, Gaia2, SWE-bench, DeepSWE, and AutomationBench; the original three backbones and supplementary GPT-6.1 Sol evaluations; Claude Code/Codex/OpenCode comparisons on GAIA/Gaia2; and Codex/OpenCode or official scaffolds on other benchmarks. This adds cross-benchmark, cross-backbone, training, ablation, and harness comparisons.

#### Comparison with peers that report more statistical detail


| Work | Repeats | Uncertainty | Test coverage | Multiplicity correction |
| --- | --- | --- | --- | --- |
| [AgenTracer: Who Is Inducing Failure in the LLM Agentic Systems?](#paper-014) | Three attribution evaluations | SD | Target improvement test not confirmed | Not confirmed |
| [DoVer: Intervention-Driven Auto Debugging for LLM Multi-Agent Systems](#paper-021) | Three intervention/baseline evaluations | Undefined ± for attribution baselines | Target improvement test not confirmed | Not confirmed |
| [Aegis: Automated Error Generation and Attribution for Multi-Agent Systems](#paper-031) | Three training seeds | SD | Pearson correlation, not method gain | Not confirmed |
| [Context Learning for Multi-Agent Discussion](#paper-041) | Three seeds | SD | Improvement test not confirmed | Not confirmed |
| [Gaia2: Benchmarking LLM Agents on Dynamic and Asynchronous Environments](#paper-050) | Three evaluations | SE and ± | Improvement test not confirmed | Not confirmed |
| [DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively](#paper-028) | Five ablation runs stated | SD stated; target numerical SD not confirmed | Derived ablation tests; identified p-values not significant | Not confirmed |
| [Ambig-SWE: Interactive Agents to Overcome Underspecificity in Software Engineering](#paper-057) | Count not confirmed | Run uncertainty for target score not confirmed | One-sided Wilcoxon main comparisons | Not confirmed |
| PORCHESTRA (author responses) | Three independent evaluations | Cross-run mean±SD | Main exact McNemar and ablation Welch | Not reported |


<a id="evidence"></a>

### 4. Evidence by audit dimension

#### A. Repeated evaluations


| Repeats | Paper count | Papers |
| --- | --- | --- |
| Three | 8 | [GAIA: a benchmark for General AI Assistants](#paper-001); [AgenTracer: Who Is Inducing Failure in the LLM Agentic Systems?](#paper-014); [DoVer: Intervention-Driven Auto Debugging for LLM Multi-Agent Systems](#paper-021); [In-the-Flow Agentic System Optimization for Effective Planning and Tool Use](#paper-029); [Aegis: Automated Error Generation and Attribution for Multi-Agent Systems](#paper-031); [Context Learning for Multi-Agent Discussion](#paper-041); [Gaia2: Benchmarking LLM Agents on Dynamic and Asynchronous Environments](#paper-050); [AgentFold: Long-Horizon Web Agents with Proactive Context Folding](#paper-063) |
| Four | 2 | [OSCAR: Operating System Control via State-Aware Reasoning and Re-Planning](#paper-010); [Unlocking Long-Horizon Agentic Search with Large-Scale End-to-End RL](#paper-045) |
| Five | 3 | [DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively](#paper-028); [Think in Parallel, Answer as One: Logit Averaging for Open-Ended Reasoning](#paper-034); [Kimi-Dev: Agentless Training as Skill Prior for SWE-agents](#paper-059) |
| Ten, baselines | 1 | [Diversity Empowers Intelligence: Integrating Expertise of Software Engineering Agents](#paper-011) |
| Thirty, output-stochasticity study | 1 | [The Hot Mess of AI: How Does Misalignment Scale With Model Intelligence and Task Complexity?](#paper-030) |
| Multiple, count unspecified | 1 | [Programming with Pixels: Can Computer-Use Agents do Software Engineering?](#paper-049) |


SWE-RM's five random subsampling runs are separate. Within-execution retries, pass@k candidates, evolution rounds, and independent complete evaluations are not treated as interchangeable.

#### B. Uncertainty

Three papers explicitly report cross-run/seed result SDs: AgenTracer (Who&When attribution accuracy, Table 7), Aegis (Aegis-Bench/Who&When F1, Table 10), and M2CL (GAIA scaling-curve bands over three seeds). The first two include mixed-source/derived attribution outcomes.

Other numerical uncertainty includes Gaia2 standard errors, TestGenEval intervals, DeLong confidence intervals in confidence analysis, and undefined ± quantities in DoVer and other papers. DEI subset SDs, Hot Mess output variance, and SWE-RM subsampling variance have different statistical objects. DeepScientist and AgentFlow state that they report SD, but corresponding target numerical SDs were not confirmed.

#### C. Formal comparison tests

Ambig-SWE reports 12 Wilcoxon p-values across six models and two setting comparisons; all are below 0.05 before any confirmed correction. DeepScientist reports derived root-cause-criterion ablations with p=0.126 and p=0.148. Neither is a confirmed named-p-value test of solving-success improvement on the original three benchmarks.

Six papers have a named test and p-value somewhere in the full text:


| Paper | Claim actually tested | Direction and unit |
| --- | --- | --- |
| [DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively](#paper-028) | A paired t-test is reported for root-cause-criterion ablations: Table 4 gives p=0.126 and p=0.148, both above 0.05. Corresponding p-values for the headline method comparison were not confirmed. The tested outcome is derived attribution, not original GAIA solver success. | Paired t-test; one-sided versus two-sided was not confirmed. Five ablation runs are stated, but the exact pairing unit and sample construction for Table 4 are not explicit. |
| [Aegis: Automated Error Generation and Attribution for Multi-Agent Systems](#paper-031) | Table 11 reports p-values for Pearson correlations between model scores on two attribution datasets. These do not test the proposed method's performance gain. | Observations are non-random-model scores on Aegis-Bench and Who&When. Test direction is not explicit. |
| [Holistic Agent Leaderboard: The Missing Infrastructure for AI Agent Evaluation](#paper-040) | Appendix A7 reports z statistics, p-values, and odds-ratio 95% CIs for logistic-regression behavior coefficients. These do not test improvements in scaffold/model benchmark scores. | Logistic regression uses task-trajectory outcomes and benchmark/model/task fixed effects. A one-sided/two-sided designation was not confirmed. |
| [Programming with Pixels: Can Computer-Use Agents do Software Engineering?](#paper-049) | McNemar p=0.014 tests an improvement on InterCode-CTF, not on the SWE-bench subset. | McNemar compares paired success/failure outcomes on InterCode-CTF. Test direction and the paired 2×2 counts are not explicit. |
| [Ambig-SWE: Interactive Agents to Overcome Underspecificity in Software Engineering](#paper-057) | A one-sided paired Wilcoxon signed-rank test uses alpha=0.05. Table 4 compares Hidden < Interaction and Interaction < Full for six models; all 12 unadjusted p-values are below 0.05. Multiple-comparison correction was not confirmed. | The alternative H1 explicitly states median paired difference >0: a one-sided test. Observations are paired across settings, but the exact paired-sample construction is not detailed. |
| [Sculptor: Empowering LLMs with Cognitive Agency via Active Context Management](#paper-062) | A one-sample t-test, p<0.001, concerns attention improvement after context folding, not SWE-bench task solving. | One-sample t-test on attention improvements for 46 semantic key–value pairs. One-sided versus two-sided is not explicit. |


TestGenEval has intervals, pairwise win rates/Elo, and significance-testing language, but its named hypothesis test and matching p-value were not confirmed. The confidence-analysis paper uses DeLong AUROC and difference intervals, not a confirmed p-value test of solver-success gains.

#### D. Test direction and observational unit

Ambig-SWE explicitly gives the directional alternative median paired difference >0, so it is recorded as one-sided. Other reported tests concern run-level ablations, model-score correlations, trajectory-level regressions, paired InterCode-CTF success/failure, or attention changes. One-sided tests are recorded as tests; direction, pairing, and observational unit are separately assessed.

#### E. Multiple-comparison correction

**Zero of the 63 papers was confirmed to report multiplicity-adjusted p-values for target-related performance improvements. Zero confirmed reports therefore establish such an improvement as significant after adjustment.** The review specifically checked the multi-comparison settings in Ambig-SWE, DeepScientist's ablations, and the surrounding passages of other reported tests, including correction method, test family, and adjusted results.

#### F. The mean-plus-SD criterion

The audited descriptive criterion is `mean_method > mean_baseline + SD_baseline`. It locates the method mean relative to baseline variability; a test name, p-value, and tested outcome are separately recorded in C. The text review did not locate an explicit use of this criterion as a formal target-improvement significance test. Illusion of Diminishing Returns plots synthetic mean±1SD; the WebAgent information-efficiency paper uses mean/variance in a theoretical derivation. Start Smart, cited in the author response, is outside the 63-paper benchmark-use sample.

<a id="intervals"></a>

### 5. Are the SD intervals completely separated?

For two mean±1SD intervals, complete separation in the favorable direction requires `mean_method - SD_method > mean_baseline + SD_baseline`. Interval separation and a formal hypothesis test are recorded separately.

- **M2CL:** In the GAIA panels of appendix Figures 5–10, six backbones × five agent counts (4/8/16/32/64) give 30 main-comparison configurations. Visual inspection found no overlap between the method and comparison SD bars in those panels. See [PDF p29 onward](https://proceedings.iclr.cc/paper_files/paper/2026/file/a1c1bb8d4cc0fc2bcb5fcb61163008df-Paper-Conference.pdf#page=29). This is a visual finding. Some MMLU comparisons overlap, including larger-agent settings in [Figure 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/a1c1bb8d4cc0fc2bcb5fcb61163008df-Paper-Conference.pdf#page=30), and ablation tables do not provide corresponding SDs.
- **Aegis:** Some ablation intervals are fully separated.
- **AgenTracer:** Some controls are fully separated; the manual-trajectory agent-accuracy comparison with the highest-mean baseline still overlaps.

No paper was confirmed to have fully separated SD intervals for every benchmark and every ablation throughout the entire paper.


| Comparison | Method mean±SD | Control mean±SD | Method interval | Control interval | Separated? |
| --- | --- | --- | --- | --- | --- |
| Aegis: Who&When Error micro-F1, DCL vs only-bilinear | 14.67±1.27 | 12.97±0.29 | [13.40, 15.94] | [12.68, 13.26] | Yes |
| AgenTracer: manual agent accuracy vs Qwen3-Coder-Plus | 62.11±1.94 | 58.28±3.54 | [60.17, 64.05] | [54.74, 61.82] | No |
| AgenTracer: manual agent accuracy vs GPT-4.1 | 62.11±1.94 | 42.52±2.93 | [60.17, 64.05] | [39.59, 45.45] | Yes |


Five of six PORCHESTRA training comparisons have fully separated mean±1SD intervals. The Gaia2 OPOD-versus-w/o-OPD comparison overlaps; the added mainstream-harness GAIA/Gaia2 comparisons also overlap.


| Comparison | Method interval | Control interval | Separated? |
| --- | --- | --- | --- |
| GAIA: OPOD vs SFT | [77.73, 80.25] | [69.95, 75.51] | Yes |
| Gaia2: OPOD vs SFT | [46.99, 50.93] | [42.82, 46.76] | Yes |
| GAIA: OPOD vs w/o RWR | [77.73, 80.25] | [74.76, 77.56] | Yes |
| GAIA: OPOD vs w/o OPD | [77.73, 80.25] | [73.22, 77.48] | Yes |
| Gaia2: OPOD vs w/o RWR | [46.99, 50.93] | [42.19, 46.87] | Yes |
| Gaia2: OPOD vs w/o OPD | [46.99, 50.93] | [43.24, 47.38] | No |
| GAIA: PORCHESTRA vs Claude Code | [75.56, 83.64] | [69.27, 78.21] | No |
| Gaia2: PORCHESTRA vs Codex | [50.13, 60.29] | [46.51, 51.93] | No |


<a id="paper-index"></a>

### 6. Complete index of all 63 papers


| No. | Year | Full paper title | Benchmark | Repeats | Cross-run/seed SD | Test coverage |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2024 | [GAIA: a benchmark for General AI Assistants](#paper-001) | GAIA | 3 (API-accessible models) | Not confirmed | Not confirmed |
| 2 | 2024 | [SWE-bench: Can Language Models Resolve Real-world Github Issues?](#paper-002) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 3 | 2025 | [Multi-modal Agent Tuning: Building a VLM-Driven Agent for Efficient Tool Usage](#paper-003) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 4 | 2025 | [TestGenEval: A Real World Unit Test Generation and Test Completion Benchmark](#paper-004) | SWE-bench | Not confirmed | Not confirmed | Intervals/win rates; named test+p not confirmed |
| 5 | 2025 | [CoRNStack: High-Quality Contrastive Data for Better Code Retrieval and Reranking](#paper-005) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 6 | 2025 | [RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph](#paper-006) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 7 | 2025 | [Internet of Agents: Weaving a Web of Heterogeneous Agents for Collaborative Intelligence](#paper-007) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 8 | 2025 | [SWE-Search: Enhancing Software Agents with Monte Carlo Tree Search and Iterative Refinement](#paper-008) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 9 | 2025 | [OpenHands: An Open Platform for AI Software Developers as Generalist Agents](#paper-009) | GAIA; SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 10 | 2025 | [OSCAR: Operating System Control via State-Aware Reasoning and Re-Planning](#paper-010) | GAIA | 4 | Not confirmed | Not confirmed |
| 11 | 2025 | [Diversity Empowers Intelligence: Integrating Expertise of Software Engineering Agents](#paper-011) | SWE-bench | 10 per open-source baseline | Not confirmed | Not confirmed |
| 12 | 2025 | [Learn-by-interact: A Data-Centric Framework For Self-Adaptive Agents in Realistic Environments](#paper-012) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 13 | 2026 | [BOAD: Discovering Hierarchical Software Engineering Agents via Bandit Optimization](#paper-013) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 14 | 2026 | [AgenTracer: Who Is Inducing Failure in the LLM Agentic Systems?](#paper-014) | GAIA | 3 | Yes | Not confirmed |
| 15 | 2026 | [Repurposing Synthetic Data for Fine-grained Search Agent Supervision](#paper-015) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 16 | 2026 | [Do Large Language Models Know What They Are Capable Of?](#paper-016) | SWE-bench | Not confirmed | Not confirmed | DeLong intervals; solving-gain p not confirmed |
| 17 | 2026 | [Agentic Reinforced Policy Optimization](#paper-017) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 18 | 2026 | [ROGA: Scaling Generalist Agents for Office Productivity Tasks via Tool Generation](#paper-018) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 19 | 2026 | [FeatureBench: Benchmarking Agentic Coding for Complex Feature Development](#paper-019) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 20 | 2026 | [Scaling Agents via Continual Pre-training](#paper-020) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 21 | 2026 | [DoVer: Intervention-Driven Auto Debugging for LLM Multi-Agent Systems](#paper-021) | GAIA | 3 | Not confirmed | Not confirmed |
| 22 | 2026 | [IterResearch: Rethinking Long-Horizon Agents with Interaction Scaling](#paper-022) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 23 | 2026 | [The Illusion of Diminishing Returns: Measuring Long Horizon Execution in LLMs](#paper-023) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 24 | 2026 | [ReTool: Reinforcement Learning for Strategic Tool Use in LLMs](#paper-024) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 25 | 2026 | [UIS-Digger: Towards Comprehensive Research Agent Systems for Real-world Unindexed Information Seeking](#paper-025) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 26 | 2026 | [TaskCraft: Automated Generation of Agentic Tasks](#paper-026) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 27 | 2026 | [Flash-Searcher: Fast and Effective Web Agents via DAG-Based Parallel Execution](#paper-027) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 28 | 2026 | [DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively](#paper-028) | GAIA | 5 (ablations) | Not confirmed | Derived paired t-test; identified p-values >0.05 |
| 29 | 2026 | [In-the-Flow Agentic System Optimization for Effective Planning and Tool Use](#paper-029) | GAIA | 3 | Not confirmed | Not confirmed |
| 30 | 2026 | [The Hot Mess of AI: How Does Misalignment Scale With Model Intelligence and Task Complexity?](#paper-030) | SWE-bench | 30 | Not confirmed | Not confirmed |
| 31 | 2026 | [Aegis: Automated Error Generation and Attribution for Multi-Agent Systems](#paper-031) | GAIA | 3 | Yes | Pearson correlation, not method gain |
| 32 | 2026 | [WebWatcher: Breaking New Frontiers of Vision-Language Deep Research Agent](#paper-032) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 33 | 2026 | [Supervised Reinforcement Learning: From Expert Trajectories to Step-wise Reasoning](#paper-033) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 34 | 2026 | [Think in Parallel, Answer as One: Logit Averaging for Open-Ended Reasoning](#paper-034) | GAIA | 5 | Not confirmed | Not confirmed |
| 35 | 2026 | [SWERank: Software Issue Localization with Code Ranking](#paper-035) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 36 | 2026 | [Huxley-Gödel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine](#paper-036) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 37 | 2026 | [Tree Search for LLM Agent Reinforcement Learning](#paper-037) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 38 | 2026 | [WebSailor-V2: Bridging the Chasm to Proprietary Agents via Synthetic Data and Scalable Reinforcement Learning](#paper-038) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 39 | 2026 | [ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory](#paper-039) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 40 | 2026 | [Holistic Agent Leaderboard: The Missing Infrastructure for AI Agent Evaluation](#paper-040) | GAIA; SWE-bench | Not confirmed | Not confirmed | Regression coefficients, not method gain |
| 41 | 2026 | [Context Learning for Multi-Agent Discussion](#paper-041) | GAIA | 3 | Yes | Not confirmed |
| 42 | 2026 | [Your Agent May Misevolve: Emergent Risks in Self-evolving LLM Agents](#paper-042) | GAIA; SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 43 | 2026 | [WebShaper: Agentically Data Synthesizing via Information-Seeking Formalization](#paper-043) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 44 | 2026 | [Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents](#paper-044) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 45 | 2026 | [Unlocking Long-Horizon Agentic Search with Large-Scale End-to-End RL](#paper-045) | GAIA | 4 | Not confirmed | Not confirmed |
| 46 | 2026 | [Improving Code Localization with Repository Memory](#paper-046) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 47 | 2026 | [Stop Wasting Your Tokens: Towards Efficient Runtime Multi-Agent Systems](#paper-047) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 48 | 2026 | [Pushing Test-Time Scaling Limits of Deep Search with Asymmetric Verification](#paper-048) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 49 | 2026 | [Programming with Pixels: Can Computer-Use Agents do Software Engineering?](#paper-049) | SWE-bench | Multiple; count unspecified | Not confirmed | McNemar on InterCode-CTF, not SWE |
| 50 | 2026 | [Gaia2: Benchmarking LLM Agents on Dynamic and Asynchronous Environments](#paper-050) | GAIA2 | 3 | Not confirmed | Not confirmed |
| 51 | 2026 | [ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases](#paper-051) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 52 | 2026 | [Empowering Efficiency and Efficacy in WebAgent via Enabling Info-Rich Seeking](#paper-052) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 53 | 2026 | [A²FM: An Adaptive Agent Foundation Model for Tool-Aware Hybrid Reasoning](#paper-053) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 54 | 2026 | [Towards Self-Evolving Agent Benchmarks : Validatable Agent Trajectory via Test-Time Exploration](#paper-054) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 55 | 2026 | [Agent Data Protocol: Unifying Datasets for Diverse, Effective Fine-tuning of LLM Agents](#paper-055) | GAIA; SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 56 | 2026 | [SWE-RM: Execution-free Feedback for Software Engineering Agents](#paper-056) | SWE-bench | 5 subsamples (separate) | Not confirmed | Not confirmed |
| 57 | 2026 | [Ambig-SWE: Interactive Agents to Overcome Underspecificity in Software Engineering](#paper-057) | SWE-bench | Not confirmed | Not confirmed | Derived-setting Wilcoxon; 12 raw p<0.05 |
| 58 | 2026 | [REAP the Experts: Why Pruning Prevails for One-Shot MoE compression](#paper-058) | SWE-bench | Not confirmed | Not confirmed | Not confirmed |
| 59 | 2026 | [Kimi-Dev: Agentless Training as Skill Prior for SWE-agents](#paper-059) | SWE-bench | 5 (Figure 7 pass@1) | Not confirmed | Not confirmed |
| 60 | 2026 | [FlowSearcher: Synthesizing Memory-Guided Agentic Workflows for Web Information Seeking](#paper-060) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 61 | 2026 | [Do LLM Agents Know How to Ground, Recover, and Assess? Evaluating Epistemic Competence in Information-Seeking Agents](#paper-061) | GAIA | Not confirmed | Not confirmed | Not confirmed |
| 62 | 2026 | [Sculptor: Empowering LLMs with Cognitive Agency via Active Context Management](#paper-062) | SWE-bench | Not confirmed | Not confirmed | Attention t-test, not SWE solving |
| 63 | 2026 | [AgentFold: Long-Horizon Web Agents with Proactive Context Folding](#paper-063) | GAIA | 3 (benchmarks below 200 examples) | Not confirmed | Not confirmed |


<a id="paper-details"></a>

### 7. All 63 individual paper assessments



<a id="paper-001"></a>

#### 1. GAIA: a benchmark for General AI Assistants


- **Year / benchmark:** ICLR 2024; GAIA.
- **Use:** Benchmark introduction and baseline evaluation on the original tasks.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2024/file/25ae35b5b1738d80f1f03a8713e405ec-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=fibxvahvs3).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Models accessible directly through an API were run three times and their results averaged. This does not cover every setup requiring manual plugin selection. |
| B. Between-run variability and uncertainty | Appendix Table 4 gives ± quantities for GPT-4/GPT-4 Turbo, without explicitly naming the uncertainty measure. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 1](https://proceedings.iclr.cc/paper_files/paper/2024/file/25ae35b5b1738d80f1f03a8713e405ec-Paper-Conference.pdf#page=1)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2024/file/25ae35b5b1738d80f1f03a8713e405ec-Paper-Conference.pdf#page=7), [PDF p. 21](https://proceedings.iclr.cc/paper_files/paper/2024/file/25ae35b5b1738d80f1f03a8713e405ec-Paper-Conference.pdf#page=21)



<a id="paper-002"></a>

#### 2. SWE-bench: Can Language Models Resolve Real-world Github Issues?


- **Year / benchmark:** ICLR 2024; SWE-bench.
- **Use:** Benchmark introduction and baseline evaluation on the original tasks.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2024/file/edac78c3e300629acfe6cbe9ca88fb84-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=VTF8yNQM66).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** The ±15 notation specifies code-context line counts. Re-executing test scripts is distinct from resampling model outputs.



**Benchmark-use evidence:** [PDF p. 1](https://proceedings.iclr.cc/paper_files/paper/2024/file/edac78c3e300629acfe6cbe9ca88fb84-Paper-Conference.pdf#page=1)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-003"></a>

#### 3. Multi-modal Agent Tuning: Building a VLM-Driven Agent for Efficient Tool Usage


- **Year / benchmark:** ICLR 2025; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/238747e153a84f50b43fd50fa8504f33-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=0bmGL4q7vJ).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** GAIA results are point estimates; repeated-evaluation counts, uncertainty quantities, and improvement tests were not confirmed.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2025/file/238747e153a84f50b43fd50fa8504f33-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-004"></a>

#### 4. TestGenEval: A Real World Unit Test Generation and Test Completion Benchmark


- **Year / benchmark:** ICLR 2025; SWE-bench.
- **Use:** Unit-test generation tasks derived from SWE-bench.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/26ded5c8ee8ec1bc4caced4e1c9b1584-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=7o6SG5gVev).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | Appendix G, Tables 12 and 17, reports 95% interval statistics for pass@1, together with pairwise win rates/Elo. |
| C. Formal tests of main and ablation improvements | The main text states that significance testing was performed. Appendix G confirms intervals, pairwise comparisons, win rates, and Elo, but a named hypothesis test with a corresponding p-value was not confirmed. |
| D. Test direction and observational unit | Intervals and pairwise comparisons concern test-generation items/model results; the direction of a named hypothesis test was not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** A section heading such as Statistical Tests and a pass@k metric alone do not establish a named test, a p-value, or independent repeated evaluation.



**Benchmark-use evidence:** [PDF p. 1](https://proceedings.iclr.cc/paper_files/paper/2025/file/26ded5c8ee8ec1bc4caced4e1c9b1584-Paper-Conference.pdf#page=1)

**Statistical/repetition evidence:** [PDF p. 5](https://proceedings.iclr.cc/paper_files/paper/2025/file/26ded5c8ee8ec1bc4caced4e1c9b1584-Paper-Conference.pdf#page=5), [PDF p. 47-52](https://proceedings.iclr.cc/paper_files/paper/2025/file/26ded5c8ee8ec1bc4caced4e1c9b1584-Paper-Conference.pdf#page=47)



<a id="paper-005"></a>

#### 5. CoRNStack: High-Quality Contrastive Data for Better Code Retrieval and Reranking


- **Year / benchmark:** ICLR 2025; SWE-bench.
- **Use:** File/function localization on SWE-bench Lite.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/285b0e63256699c04dbf2c8d4163fba4-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=iyJOUELYir).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiment: data-quality checks sample 10,000 pairs from each source with three seeds and LLM grading. These are not SWE-bench localization evaluations.



**Benchmark-use evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2025/file/285b0e63256699c04dbf2c8d4163fba4-Paper-Conference.pdf#page=9)

**Statistical/repetition evidence:** [PDF p. 4](https://proceedings.iclr.cc/paper_files/paper/2025/file/285b0e63256699c04dbf2c8d4163fba4-Paper-Conference.pdf#page=4)



<a id="paper-006"></a>

#### 6. RepoGraph: Enhancing AI Software Engineering with Repository-level Code Graph


- **Year / benchmark:** ICLR 2025; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=dw9VUsSHGB).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Different models, frameworks, and ablation configurations are not repeated evaluations of one fixed configuration.



**Benchmark-use evidence:** [PDF p. 18](https://proceedings.iclr.cc/paper_files/paper/2025/file/4a4a3c197deac042461c677219efd36c-Paper-Conference.pdf#page=18)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-007"></a>

#### 7. Internet of Agents: Weaving a Web of Heterogeneous Agents for Collaborative Intelligence


- **Year / benchmark:** ICLR 2025; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/59c27bf8d56d3d50c7aeaf7535dee975-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=o1Et3MogPw).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiment: the embodied-robotics comparison runs IoA and Roco Dialog ten times per task. This count does not apply to GAIA.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2025/file/59c27bf8d56d3d50c7aeaf7535dee975-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2025/file/59c27bf8d56d3d50c7aeaf7535dee975-Paper-Conference.pdf#page=9)



<a id="paper-008"></a>

#### 8. SWE-Search: Enhancing Software Agents with Monte Carlo Tree Search and Iterative Refinement


- **Year / benchmark:** ICLR 2025; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/a1e6783e4d739196cad3336f12d402bf-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=G7sIFXugTX).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Five Moatless baseline runs support pass@5; SWE-Search generates five candidates in one execution. Independent repeated evaluation of the main method was not confirmed. |
| B. Between-run variability and uncertainty | The SD in Figure 8 describes the state-reward distribution, not uncertainty in the resolved rate across evaluation runs. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2025/file/a1e6783e4d739196cad3336f12d402bf-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 21](https://proceedings.iclr.cc/paper_files/paper/2025/file/a1e6783e4d739196cad3336f12d402bf-Paper-Conference.pdf#page=21), [PDF p. 30](https://proceedings.iclr.cc/paper_files/paper/2025/file/a1e6783e4d739196cad3336f12d402bf-Paper-Conference.pdf#page=30)



<a id="paper-009"></a>

#### 9. OpenHands: An Open Platform for AI Software Developers as Generalist Agents


- **Year / benchmark:** ICLR 2025; GAIA; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/a4b6ad6b48850c0c331d1259fc66a69c-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=OJd3ayDDoF).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Supporting multiple benchmarks or reporting pass@k does not establish repeated evaluations.



**Benchmark-use evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2025/file/a4b6ad6b48850c0c331d1259fc66a69c-Paper-Conference.pdf#page=9), [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2025/file/a4b6ad6b48850c0c331d1259fc66a69c-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-010"></a>

#### 10. OSCAR: Operating System Control via State-Aware Reasoning and Re-Planning


- **Year / benchmark:** ICLR 2025; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/b2077e6d66da612fcb701589efa9ce88-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=VuTrZzrPfn).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Appendix B specifies four runs per model and benchmark, averaged. This is separate from up to four attempts within an execution. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2025/file/b2077e6d66da612fcb701589efa9ce88-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 17](https://proceedings.iclr.cc/paper_files/paper/2025/file/b2077e6d66da612fcb701589efa9ce88-Paper-Conference.pdf#page=17)



<a id="paper-011"></a>

#### 11. Diversity Empowers Intelligence: Integrating Expertise of Software Engineering Agents


- **Year / benchmark:** ICLR 2025; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/d7b50b8ac2c781a12f26155f48310d8d-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=cKlzKs3Nnb).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Agentless, Moatless, and Aider each run ten times with identical parameters for agent/run diversity and candidate-combination analysis. Repeats of the complete DEI method were not confirmed. |
| B. Between-run variability and uncertainty | Figure 3 computes means and SDs over candidate subsets. These are not ten-run uncertainty estimates for the complete DEI pipeline. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2025/file/d7b50b8ac2c781a12f26155f48310d8d-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** [PDF p. 6-7](https://proceedings.iclr.cc/paper_files/paper/2025/file/d7b50b8ac2c781a12f26155f48310d8d-Paper-Conference.pdf#page=6)



<a id="paper-012"></a>

#### 12. Learn-by-interact: A Data-Centric Framework For Self-Adaptive Agents in Realistic Environments


- **Year / benchmark:** ICLR 2025; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/dd745a0c4f91fe91866fe6788be9cc28-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=3UKOzGWCVY).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Training-data generation and multi-turn interaction are not counted as independent evaluation repeats.



**Benchmark-use evidence:** [PDF p. 5](https://proceedings.iclr.cc/paper_files/paper/2025/file/dd745a0c4f91fe91866fe6788be9cc28-Paper-Conference.pdf#page=5)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-013"></a>

#### 13. BOAD: Discovering Hierarchical Software Engineering Agents via Bandit Optimization


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/0d89023ee7f8728fb6018d5c84a720bf-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=O6stE173BD).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** The UCB confidence bound is part of the optimization algorithm, not a reported CI for performance improvement.



**Benchmark-use evidence:** [PDF p. 25](https://proceedings.iclr.cc/paper_files/paper/2026/file/0d89023ee7f8728fb6018d5c84a720bf-Paper-Conference.pdf#page=25)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-014"></a>

#### 14. AgenTracer: Who Is Inducing Failure in the LLM Agentic Systems?


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Failure attribution using trajectories from GAIA and other tasks, including mixed-source Who&When data.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/134ed7a477770f227f12450ef0cbb8f4-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=l05DseqvuD).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Appendix F reports three independent evaluations on the manual and automatic Who&When subsets. These are attribution evaluations, not repeated GAIA solver-success measurements. |
| B. Between-run variability and uncertainty | Table 7 reports mean±std for Who&When attribution accuracy. The manual subset mixes GAIA and AssistantBench trajectories. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/134ed7a477770f227f12450ef0cbb8f4-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/134ed7a477770f227f12450ef0cbb8f4-Paper-Conference.pdf#page=7), [PDF p. 23](https://proceedings.iclr.cc/paper_files/paper/2026/file/134ed7a477770f227f12450ef0cbb8f4-Paper-Conference.pdf#page=23)



<a id="paper-015"></a>

#### 15. Repurposing Synthetic Data for Fine-grained Search Agent Supervision


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/1801a817e29e8e69711dd7935651691c-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=CByVWPpb8T).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Within-group reward SD in GRPO is part of training, rather than a performance error bar.



**Benchmark-use evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/1801a817e29e8e69711dd7935651691c-Paper-Conference.pdf#page=9)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-016"></a>

#### 16. Do Large Language Models Know What They Are Capable Of?


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Confidence and calibration analysis on SWE-bench Verified.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/1a96349bbc03432c5ec8c6c502d102e7-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=EO6WtJ0q6G).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | For 499 SWE tasks, AUROC and its difference from step 1 are reported with 95% CIs using the DeLong method. |
| C. Formal tests of main and ablation improvements | Statistical inference is reported for confidence discrimination using AUROC and DeLong difference intervals. A named test and p-value for solver-success improvement were not confirmed. |
| D. Test direction and observational unit | Observations are outcomes on 499 SWE tasks used to analyze confidence discrimination. The direction of a solver-success test was not reported. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** The 512 nine-contract sequences occur in another experiment; they are not 512 independent complete SWE-bench runs.



**Benchmark-use evidence:** [PDF p. 2](https://proceedings.iclr.cc/paper_files/paper/2026/file/1a96349bbc03432c5ec8c6c502d102e7-Paper-Conference.pdf#page=2)

**Statistical/repetition evidence:** [PDF p. 5](https://proceedings.iclr.cc/paper_files/paper/2026/file/1a96349bbc03432c5ec8c6c502d102e7-Paper-Conference.pdf#page=5), [PDF p. 7-8](https://proceedings.iclr.cc/paper_files/paper/2026/file/1a96349bbc03432c5ec8c6c502d102e7-Paper-Conference.pdf#page=7)



<a id="paper-017"></a>

#### 17. Agentic Reinforced Policy Optimization


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/1c58e53bdf1fb045440256fd567531ae-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=TX4k7BF6aO).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Within-group advantage SD and multiple rollouts are training settings.



**Benchmark-use evidence:** [PDF p. 22](https://proceedings.iclr.cc/paper_files/paper/2026/file/1c58e53bdf1fb045440256fd567531ae-Paper-Conference.pdf#page=22)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-018"></a>

#### 18. ROGA: Scaling Generalist Agents for Office Productivity Tasks via Tool Generation


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Task evaluation on the GAIA-Office subset.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/1ed4723f12853cbd02aecb8160f5e0c9-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=KTyLxtODB9).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Up to three revisions after tool-generation failure are retries within one execution.



**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/1ed4723f12853cbd02aecb8160f5e0c9-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-019"></a>

#### 19. FeatureBench: Benchmarking Agentic Coding for Complex Feature Development


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/25203d1cc8c58381eab578f4fcf9c4f8-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=41xrZ3uGuI).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Resolved/passed results are reported. Multiple unit-test assertions are not independent evaluation repeats.



**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/25203d1cc8c58381eab578f4fcf9c4f8-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-020"></a>

#### 20. Scaling Agents via Continual Pre-training


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/26c806d4064fe68e3fb688bb838672fb-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=Dru5mm9anE).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Multiple checkpoints, rollouts, and training stages do not directly establish evaluation over multiple seeds.



**Benchmark-use evidence:** [PDF p. 20](https://proceedings.iclr.cc/paper_files/paper/2026/file/26c806d4064fe68e3fb688bb838672fb-Paper-Conference.pdf#page=20)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-021"></a>

#### 21. DoVer: Intervention-Driven Auto Debugging for LLM Multi-Agent Systems


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Intervention-based recovery from failed GAIA trajectories, also including Who&When.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/2f5fdce256ff0d7fb774da76e5e63209-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=mrEK16Jy6h).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Each intervention is run three times and validated using rules such as success in at least two of three runs. Who&When attribution baselines are also rerun three times. |
| B. Between-run variability and uncertainty | Appendix Table 5 gives ± quantities for attribution baselines on mixed-source Who&When data. Their SD/SE/CI definition is not specified; a corresponding CI for the main intervention-success rate was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/2f5fdce256ff0d7fb774da76e5e63209-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** [PDF p. 6-7](https://proceedings.iclr.cc/paper_files/paper/2026/file/2f5fdce256ff0d7fb774da76e5e63209-Paper-Conference.pdf#page=6), [PDF p. 13-14](https://proceedings.iclr.cc/paper_files/paper/2026/file/2f5fdce256ff0d7fb774da76e5e63209-Paper-Conference.pdf#page=13)



<a id="paper-022"></a>

#### 22. IterResearch: Rethinking Long-Horizon Agents with Interaction Scaling


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/3369a3b268a86804237ef4702ac99ed3-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=qQ5MZ5Mx7p).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | Table 1 reports GAIA accuracy as 72.8±2.3. The definition of ± and number of evaluation repeats were not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Five trials used to filter training-data difficulty are not five GAIA test evaluations.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/3369a3b268a86804237ef4702ac99ed3-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/3369a3b268a86804237ef4702ac99ed3-Paper-Conference.pdf#page=7), [PDF p. 19](https://proceedings.iclr.cc/paper_files/paper/2026/file/3369a3b268a86804237ef4702ac99ed3-Paper-Conference.pdf#page=19)



<a id="paper-023"></a>

#### 23. The Illusion of Diminishing Returns: Measuring Long Horizon Execution in LLMs


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Manual analysis of failed GAIA trajectories.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/3b4e1336f775c3dba16ebbb8d2afd258-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=3lm8lWYxiq).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | The synthetic experiment displays mean±1SD over 100 samples. An explicit target-improvement test using mean > baseline mean + SD was not located. |


**Additional scope and interpretation:** Other experiment: the main synthetic study plots mean±SD for 100 samples; GAIA is an appendix analysis of failed trajectories. The top-p sampling parameter is not a significance-test p-value.



**Benchmark-use evidence:** [PDF p. 17](https://proceedings.iclr.cc/paper_files/paper/2026/file/3b4e1336f775c3dba16ebbb8d2afd258-Paper-Conference.pdf#page=17)

**Statistical/repetition evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/3b4e1336f775c3dba16ebbb8d2afd258-Paper-Conference.pdf#page=6)



<a id="paper-024"></a>

#### 24. ReTool: Reinforcement Learning for Strategic Tool Use in LLMs


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/4038c9208dfc22644c60ad39c24e5c53-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=tRk1nofSmz).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other benchmarks average 32 AIME, eight GPQA, four MATH500, and two GSM8K evaluations. These settings were not confirmed for GAIA.



**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/4038c9208dfc22644c60ad39c24e5c53-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** [PDF p. 5](https://proceedings.iclr.cc/paper_files/paper/2026/file/4038c9208dfc22644c60ad39c24e5c53-Paper-Conference.pdf#page=5)



<a id="paper-025"></a>

#### 25. UIS-Digger: Towards Comprehensive Research Agent Systems for Real-world Unindexed Information Seeking


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/440a34859a9ba4cc59d415aa435f5568-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=aykkGh9TIy).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** SFT/RFT bootstrapping denotes the training process, not statistical bootstrap inference.



**Benchmark-use evidence:** [PDF p. 4](https://proceedings.iclr.cc/paper_files/paper/2026/file/440a34859a9ba4cc59d415aa435f5568-Paper-Conference.pdf#page=4)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-026"></a>

#### 26. TaskCraft: Automated Generation of Agentic Tasks


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/48644509339cb3076f7b0407c7588af6-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=UJFCyrYM1V).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Bootstrap few-shot is prompt optimization. Table 4 sigma-squared describes tool-use distributions, not uncertainty in GAIA accuracy.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/48644509339cb3076f7b0407c7588af6-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-027"></a>

#### 27. Flash-Searcher: Fast and Effective Web Agents via DAG-Based Parallel Execution


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/4a975de3dd9f9c06109e3015b51c587b-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=QuaJ6kJaBm).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Accuracy, execution time, and step counts are reported. Repeated-evaluation counts and accuracy uncertainty were not confirmed.



**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/4a975de3dd9f9c06109e3015b51c587b-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-028"></a>

#### 28. DeepScientist: Advancing Frontier-Pushing Scientific Findings Progressively


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** A derived failure-attribution study using GAIA/AssistantBench logs.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/4f64494ecc3442f1c9261baa036378bc-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=cZFgsLq8Gs).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The AI-generated A2P appendix study states five randomized ablation runs. Table 3 explicitly reports five-run means for the automatic subset. |
| B. Between-run variability and uncertainty | The methods state that means and SDs are reported, but numerical SDs were not confirmed in the main A2P result tables. |
| C. Formal tests of main and ablation improvements | A paired t-test is reported for root-cause-criterion ablations: Table 4 gives p=0.126 and p=0.148, both above 0.05. Corresponding p-values for the headline method comparison were not confirmed. The tested outcome is derived attribution, not original GAIA solver success. |
| D. Test direction and observational unit | Paired t-test; one-sided versus two-sided was not confirmed. Five ablation runs are stated, but the exact pairing unit and sample construction for Table 4 are not explicit. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** These results appear in an appendix study discovered and written by DeepScientist. The audit distinguishes stated methodology, actual numerical reporting, and the outcome covered by each test.



**Benchmark-use evidence:** [PDF p. 28](https://proceedings.iclr.cc/paper_files/paper/2026/file/4f64494ecc3442f1c9261baa036378bc-Paper-Conference.pdf#page=28)

**Statistical/repetition evidence:** [PDF p. 29-31](https://proceedings.iclr.cc/paper_files/paper/2026/file/4f64494ecc3442f1c9261baa036378bc-Paper-Conference.pdf#page=29)



<a id="paper-029"></a>

#### 29. In-the-Flow Agentic System Optimization for Effective Planning and Tool Use


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/52c4a736cd63b3c7bf52011a1f66f3f6-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=Mf5AleTUVK).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The main text and Appendix C.2 state that all experiments are averaged over three trials. |
| B. Between-run variability and uncertainty | The appendix states that SDs are reported, but the GAIA main table lists means without confirmed corresponding numerical SDs. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 23](https://proceedings.iclr.cc/paper_files/paper/2026/file/52c4a736cd63b3c7bf52011a1f66f3f6-Paper-Conference.pdf#page=23)

**Statistical/repetition evidence:** [PDF p. 6-7](https://proceedings.iclr.cc/paper_files/paper/2026/file/52c4a736cd63b3c7bf52011a1f66f3f6-Paper-Conference.pdf#page=6), [PDF p. 19](https://proceedings.iclr.cc/paper_files/paper/2026/file/52c4a736cd63b3c7bf52011a1f66f3f6-Paper-Conference.pdf#page=19)



<a id="paper-030"></a>

#### 30. The Hot Mess of AI: How Does Misalignment Scale With Model Intelligence and Task Complexity?


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Bias/variance analysis of output stochasticity on SWE-bench Verified.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/53d6e1581fea800e38df4ab2701aa0ab-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=sIBwirjYlY).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Appendix B.3 specifies 30 runs per model on SWE-bench Verified. Unit-test outcome vectors are used to decompose bias and variance. |
| B. Between-run variability and uncertainty | Output variance is itself the object of study. It is not counted as the SE or CI of an estimated performance gain. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** A GPQA bootstrap with 100 examples checks estimate stability; it is not a SWE-bench improvement test.



**Benchmark-use evidence:** [PDF p. 23](https://proceedings.iclr.cc/paper_files/paper/2026/file/53d6e1581fea800e38df4ab2701aa0ab-Paper-Conference.pdf#page=23)

**Statistical/repetition evidence:** [PDF p. 4](https://proceedings.iclr.cc/paper_files/paper/2026/file/53d6e1581fea800e38df4ab2701aa0ab-Paper-Conference.pdf#page=4), [PDF p. 23](https://proceedings.iclr.cc/paper_files/paper/2026/file/53d6e1581fea800e38df4ab2701aa0ab-Paper-Conference.pdf#page=23), [PDF p. 35](https://proceedings.iclr.cc/paper_files/paper/2026/file/53d6e1581fea800e38df4ab2701aa0ab-Paper-Conference.pdf#page=35)



<a id="paper-031"></a>

#### 31. Aegis: Automated Error Generation and Attribution for Multi-Agent Systems


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Mixed-source attribution tasks in Aegis/Who&When, including GAIA trajectories.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/56e8943ecd44b67bbea2702b9117b858-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=zqcYoxXiN3).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | DCL and its ablations use three different training seeds. These repeat attribution-model training/evaluation, not a complete GAIA solver. |
| B. Between-run variability and uncertainty | Table 10 reports mean±std for Aegis-Bench/Who&When F1 over three seeds. |
| C. Formal tests of main and ablation improvements | Table 11 reports p-values for Pearson correlations between model scores on two attribution datasets. These do not test the proposed method's performance gain. |
| D. Test direction and observational unit | Observations are non-random-model scores on Aegis-Bench and Who&When. Test direction is not explicit. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 17](https://proceedings.iclr.cc/paper_files/paper/2026/file/56e8943ecd44b67bbea2702b9117b858-Paper-Conference.pdf#page=17)

**Statistical/repetition evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/56e8943ecd44b67bbea2702b9117b858-Paper-Conference.pdf#page=9), [PDF p. 23](https://proceedings.iclr.cc/paper_files/paper/2026/file/56e8943ecd44b67bbea2702b9117b858-Paper-Conference.pdf#page=23), [PDF p. 25-26](https://proceedings.iclr.cc/paper_files/paper/2026/file/56e8943ecd44b67bbea2702b9117b858-Paper-Conference.pdf#page=25)



<a id="paper-032"></a>

#### 32. WebWatcher: Breaking New Frontiers of Vision-Language Deep Research Agent


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** A comparison using a single GAIA task as a case study.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/63ca1cca58101545e937302be7050098-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=8jsaazdAb3).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiments: HLE reports an average over three inference runs; judge–human agreement has a 95% Wilson CI. Neither establishes repetition or uncertainty for the single GAIA case.



**Benchmark-use evidence:** [PDF p. 2](https://proceedings.iclr.cc/paper_files/paper/2026/file/63ca1cca58101545e937302be7050098-Paper-Conference.pdf#page=2)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/63ca1cca58101545e937302be7050098-Paper-Conference.pdf#page=7), [PDF p. 26](https://proceedings.iclr.cc/paper_files/paper/2026/file/63ca1cca58101545e937302be7050098-Paper-Conference.pdf#page=26)



<a id="paper-033"></a>

#### 33. Supervised Reinforcement Learning: From Expert Trajectories to Step-wise Reasoning


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/7ab7fc1278add78fd6eae2da7a14c79b-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=Uro84w2xz5).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Reward SD is used in SRL training, not as SWE-bench performance uncertainty.



**Benchmark-use evidence:** [PDF p. 10](https://proceedings.iclr.cc/paper_files/paper/2026/file/7ab7fc1278add78fd6eae2da7a14c79b-Paper-Conference.pdf#page=10)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-034"></a>

#### 34. Think in Parallel, Answer as One: Logit Averaging for Open-Ended Reasoning


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/7d53575463291ea6b5a23cf6e571f59b-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=hvit36Dyzl).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Baselines on open-ended tasks including GAIA are rerun and averaged over five evaluations in Table 5. The K parallel reasoning trajectories are a separate inference mechanism. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Appendix A.2 mean±std tables concern AIME/GPQA, not GAIA. The top-p parameter is not a hypothesis-test p-value.



**Benchmark-use evidence:** [PDF p. 1](https://proceedings.iclr.cc/paper_files/paper/2026/file/7d53575463291ea6b5a23cf6e571f59b-Paper-Conference.pdf#page=1)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/7d53575463291ea6b5a23cf6e571f59b-Paper-Conference.pdf#page=7), [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/7d53575463291ea6b5a23cf6e571f59b-Paper-Conference.pdf#page=9), [PDF p. 15-16](https://proceedings.iclr.cc/paper_files/paper/2026/file/7d53575463291ea6b5a23cf6e571f59b-Paper-Conference.pdf#page=15)



<a id="paper-035"></a>

#### 35. SWERank: Software Issue Localization with Code Ranking


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** File/function localization on SWE-bench Lite.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/7f6901ebab786e43b21530328fc989ca-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=OnkRqbNhe3).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Differences between task-difficulty groups are not repeated-experiment error estimates.



**Benchmark-use evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/7f6901ebab786e43b21530328fc989ca-Paper-Conference.pdf#page=9)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-036"></a>

#### 36. Huxley-Gödel Machine: Human-Level Coding Agent Development by an Approximation of the Optimal Self-Improving Machine


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/821d20219c2f14850af1b5220f0ed13f-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=T0EiEuhOOL).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** The theoretical repeatable-trials assumption and five expansions of an initial agent do not report independent repeats of the complete main method.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/821d20219c2f14850af1b5220f0ed13f-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-037"></a>

#### 37. Tree Search for LLM Agent Reinforcement Learning


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/8c7304e77c832ddc70075dfee081ca6c-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=ZpQwAFhU13).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Tree-expansion rollouts and group-relative advantages are training-algorithm components.



**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/8c7304e77c832ddc70075dfee081ca6c-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-038"></a>

#### 38. WebSailor-V2: Bridging the Chasm to Proprietary Agents via Synthetic Data and Scalable Reinforcement Learning


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/9760f18785acf535321e50405fd36578-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=HuP16O5SJf).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Leave-one-out estimation reduces training-advantage variance; evaluation repeats or improvement CIs were not confirmed.



**Benchmark-use evidence:** [PDF p. 10](https://proceedings.iclr.cc/paper_files/paper/2026/file/9760f18785acf535321e50405fd36578-Paper-Conference.pdf#page=10)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-039"></a>

#### 39. ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/980ea04d23d1f6908964eba2a74afe45-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=jL7fwchScm).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | A separate memory pool is maintained for each independent run, but the number of repeated evaluations and their aggregation were not confirmed. The k trajectories in MATTS are inference-time scaling. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 2](https://proceedings.iclr.cc/paper_files/paper/2026/file/980ea04d23d1f6908964eba2a74afe45-Paper-Conference.pdf#page=2)

**Statistical/repetition evidence:** [PDF p. 22](https://proceedings.iclr.cc/paper_files/paper/2026/file/980ea04d23d1f6908964eba2a74afe45-Paper-Conference.pdf#page=22)



<a id="paper-040"></a>

#### 40. Holistic Agent Leaderboard: The Missing Infrastructure for AI Agent Evaluation


- **Year / benchmark:** ICLR 2026; GAIA; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/a0928f924a344aaebbb7f6cd8d56e34c-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=vUaY1t64ZZ).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The authors explicitly state that cost constraints lead most evaluations to rely on a single run and limit statistical validation. |
| B. Between-run variability and uncertainty | The page design can show run min–max values, but usable repeated-result uncertainty was not confirmed for the main GAIA/SWE comparisons. Regression CIs are recorded separately. |
| C. Formal tests of main and ablation improvements | Appendix A7 reports z statistics, p-values, and odds-ratio 95% CIs for logistic-regression behavior coefficients. These do not test improvements in scaffold/model benchmark scores. |
| D. Test direction and observational unit | Logistic regression uses task-trajectory outcomes and benchmark/model/task fixed effects. A one-sided/two-sided designation was not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/a0928f924a344aaebbb7f6cd8d56e34c-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** [PDF p. 22](https://proceedings.iclr.cc/paper_files/paper/2026/file/a0928f924a344aaebbb7f6cd8d56e34c-Paper-Conference.pdf#page=22), [PDF p. 30](https://proceedings.iclr.cc/paper_files/paper/2026/file/a0928f924a344aaebbb7f6cd8d56e34c-Paper-Conference.pdf#page=30), [PDF p. 44](https://proceedings.iclr.cc/paper_files/paper/2026/file/a0928f924a344aaebbb7f6cd8d56e34c-Paper-Conference.pdf#page=44)



<a id="paper-041"></a>

#### 41. Context Learning for Multi-Agent Discussion


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/a1c1bb8d4cc0fc2bcb5fcb61163008df-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=EUu8TILWpR).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Figure 4 and multiple GAIA scaling plots in the appendix use three seeds. |
| B. Between-run variability and uncertainty | The bands in the GAIA plots are explicitly identified as SDs over three seeds. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 31](https://proceedings.iclr.cc/paper_files/paper/2026/file/a1c1bb8d4cc0fc2bcb5fcb61163008df-Paper-Conference.pdf#page=31)

**Statistical/repetition evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/a1c1bb8d4cc0fc2bcb5fcb61163008df-Paper-Conference.pdf#page=9), [PDF p. 29-31](https://proceedings.iclr.cc/paper_files/paper/2026/file/a1c1bb8d4cc0fc2bcb5fcb61163008df-Paper-Conference.pdf#page=29)



<a id="paper-042"></a>

#### 42. Your Agent May Misevolve: Emergent Risks in Self-evolving LLM Agents


- **Year / benchmark:** ICLR 2026; GAIA; SWE-bench.
- **Use:** GAIA-derived tool-failure cases; SWE-bench is used for evolving memory.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/a24cd16bc361afa78e57d31d34f3d936-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=Fd1jgQQW28).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiment: AgentNet deployment-time reward hacking is evaluated over three independent runs. Three evolution rounds are not independent repeats, and discussion of difficulty demonstrating significance is not a reported test.



**Benchmark-use evidence:** [PDF p. 63](https://proceedings.iclr.cc/paper_files/paper/2026/file/a24cd16bc361afa78e57d31d34f3d936-Paper-Conference.pdf#page=63), [PDF p. 62](https://proceedings.iclr.cc/paper_files/paper/2026/file/a24cd16bc361afa78e57d31d34f3d936-Paper-Conference.pdf#page=62)

**Statistical/repetition evidence:** [PDF p. 6-7](https://proceedings.iclr.cc/paper_files/paper/2026/file/a24cd16bc361afa78e57d31d34f3d936-Paper-Conference.pdf#page=6), [PDF p. 64](https://proceedings.iclr.cc/paper_files/paper/2026/file/a24cd16bc361afa78e57d31d34f3d936-Paper-Conference.pdf#page=64)



<a id="paper-043"></a>

#### 43. WebShaper: Agentically Data Synthesizing via Information-Seeking Formalization


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/a6ffd1854c6191b1f33b7ad9509d46f9-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=hld4TzJsnD).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | Statistical-significance wording is used for the proportion of multi-hop trajectories, but a named test and p-value were not confirmed. This is not a test of GAIA accuracy improvement. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Five rollouts per training question are used for data filtering, not repeated GAIA evaluation.



**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/a6ffd1854c6191b1f33b7ad9509d46f9-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** [PDF p. 4](https://proceedings.iclr.cc/paper_files/paper/2026/file/a6ffd1854c6191b1f33b7ad9509d46f9-Paper-Conference.pdf#page=4), [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/a6ffd1854c6191b1f33b7ad9509d46f9-Paper-Conference.pdf#page=9)



<a id="paper-044"></a>

#### 44. Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/aa5f5e6eb6f613ec412f1d948dfa21a5-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=pUpzQZTvGY).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiment: the complete DGM algorithm is rerun three times on Polyglot, yielding 40.7%±2.3% (SD). This result is not attributed to SWE-bench.



**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/aa5f5e6eb6f613ec412f1d948dfa21a5-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** [PDF p. 26](https://proceedings.iclr.cc/paper_files/paper/2026/file/aa5f5e6eb6f613ec412f1d948dfa21a5-Paper-Conference.pdf#page=26)



<a id="paper-045"></a>

#### 45. Unlocking Long-Horizon Agentic Search with Large-Scale End-to-End RL


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/af125cae03cf4c7198f93060a7edec1f-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=MfPDdPUGKi).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | ASearcher pass@1 is evaluated with four seeds; some comparison scores are taken from official reports. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Generating and combining 16 additional candidates is test-time scaling, not independent repeated evaluation.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/af125cae03cf4c7198f93060a7edec1f-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 7-8](https://proceedings.iclr.cc/paper_files/paper/2026/file/af125cae03cf4c7198f93060a7edec1f-Paper-Conference.pdf#page=7)



<a id="paper-046"></a>

#### 46. Improving Code Localization with Repository Memory


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Code-localization evaluation on SWE-bench Verified.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/b4c06f095368497f3ac19422efef8133-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=8yjWLJy2eX).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Latency analysis on 50 randomly selected instances does not establish repeated evaluation on the same tasks.



**Benchmark-use evidence:** [PDF p. 15](https://proceedings.iclr.cc/paper_files/paper/2026/file/b4c06f095368497f3ac19422efef8133-Paper-Conference.pdf#page=15)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-047"></a>

#### 47. Stop Wasting Your Tokens: Towards Efficient Runtime Multi-Agent Systems


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/b86a195e70f27017c514fa0e5f80595f-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=pzFhtpkabh).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | Token-cost variances and distributions are reported, rather than repeated-evaluation uncertainty or CIs for accuracy gains. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 2](https://proceedings.iclr.cc/paper_files/paper/2026/file/b86a195e70f27017c514fa0e5f80595f-Paper-Conference.pdf#page=2)

**Statistical/repetition evidence:** [PDF p. 2](https://proceedings.iclr.cc/paper_files/paper/2026/file/b86a195e70f27017c514fa0e5f80595f-Paper-Conference.pdf#page=2), [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/b86a195e70f27017c514fa0e5f80595f-Paper-Conference.pdf#page=8)



<a id="paper-048"></a>

#### 48. Pushing Test-Time Scaling Limits of Deep Search with Asymmetric Verification


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/bc26087d3f82e62044fc77752e86737e-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=hxL4Uf9tR3).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiment: mean±std across three disjoint subsets is reported for two BrowseComp datasets. The question sets differ, rather than repeating a fixed set. Eight GAIA candidates plus verification are inference-time scaling.



**Benchmark-use evidence:** [PDF p. 3](https://proceedings.iclr.cc/paper_files/paper/2026/file/bc26087d3f82e62044fc77752e86737e-Paper-Conference.pdf#page=3)

**Statistical/repetition evidence:** [PDF p. 16-17](https://proceedings.iclr.cc/paper_files/paper/2026/file/bc26087d3f82e62044fc77752e86737e-Paper-Conference.pdf#page=16)



<a id="paper-049"></a>

#### 49. Programming with Pixels: Can Computer-Use Agents do Software Engineering?


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** A small SWE-bench sample evaluated through the PwP graphical interface.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/bce96750dcb64f3257ceabadf0b9c9bf-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=9N4Ps9Psfr).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The strongest Claude-Sonnet-4.0 setup, with and without file/bash APIs, is rerun over multiple trials. The number of trials was not confirmed. |
| B. Between-run variability and uncertainty | The SB column of Table 8 reports ± quantities, including 5.0±5.0 and 28.3±2.9, without specifying the definition of ±. |
| C. Formal tests of main and ablation improvements | McNemar p=0.014 tests an improvement on InterCode-CTF, not on the SWE-bench subset. |
| D. Test direction and observational unit | McNemar compares paired success/failure outcomes on InterCode-CTF. Test direction and the paired 2×2 counts are not explicit. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/bce96750dcb64f3257ceabadf0b9c9bf-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** [PDF p. 22-23](https://proceedings.iclr.cc/paper_files/paper/2026/file/bce96750dcb64f3257ceabadf0b9c9bf-Paper-Conference.pdf#page=22), [PDF p. 25](https://proceedings.iclr.cc/paper_files/paper/2026/file/bce96750dcb64f3257ceabadf0b9c9bf-Paper-Conference.pdf#page=25)



<a id="paper-050"></a>

#### 50. Gaia2: Benchmarking LLM Agents on Dynamic and Asynchronous Environments


- **Year / benchmark:** ICLR 2026; GAIA2.
- **Use:** Benchmark introduction and baseline evaluation on the original tasks.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/c26a67e0470774df98c12480ec5d2d7b-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=9gw03JpKK4).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Scenario/model evaluations are repeated three times. Additional pass@k sampling is recorded separately. |
| B. Between-run variability and uncertainty | Table 2 reports ± quantities; Table 3 explicitly reports means and standard errors over three runs. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 1](https://proceedings.iclr.cc/paper_files/paper/2026/file/c26a67e0470774df98c12480ec5d2d7b-Paper-Conference.pdf#page=1)

**Statistical/repetition evidence:** [PDF p. 6-7](https://proceedings.iclr.cc/paper_files/paper/2026/file/c26a67e0470774df98c12480ec5d2d7b-Paper-Conference.pdf#page=6), [PDF p. 10](https://proceedings.iclr.cc/paper_files/paper/2026/file/c26a67e0470774df98c12480ec5d2d7b-Paper-Conference.pdf#page=10)



<a id="paper-051"></a>

#### 51. ImpossibleBench: Measuring LLMs' Propensity of Exploiting Test Cases


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Impossible-task and cheating-propensity evaluations derived from SWE-bench.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/ca688eb14e29701a11bdba6633186328-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=SeO4vyAj7E).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | The paper uses statistical-significance language and intervals, but a named test with a corresponding p-value was not confirmed for the target-derived comparison. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Figure 6 reports 90% CIs for prompt ablations on Conflicting-LiveCodeBench. These are not assigned to SWE-derived tasks.



**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/ca688eb14e29701a11bdba6633186328-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/ca688eb14e29701a11bdba6633186328-Paper-Conference.pdf#page=6)



<a id="paper-052"></a>

#### 52. Empowering Efficiency and Efficacy in WebAgent via Enabling Info-Rich Seeking


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/d7a16282998da055c394825599b12479-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=MVFGY1nS6b).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | Mean and variance symbols occur in the ISE variance derivation. A target-improvement test based on mean > baseline mean + SD was not located. |


**Additional scope and interpretation:** ISE variance theory and training strategy are distinct from uncertainty in evaluation results. The phrase margin of variance has no confirmed corresponding numerical error quantity.



**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/d7a16282998da055c394825599b12479-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-053"></a>

#### 53. A²FM: An Adaptive Agent Foundation Model for Tool-Aware Hybrid Reasoning


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/d83fd70a31c64e020844ec80705ba87f-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=3kvV1nfWVq).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Multiple APO rollouts are used for training, rather than multiple training seeds or evaluation repeats.



**Benchmark-use evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/d83fd70a31c64e020844ec80705ba87f-Paper-Conference.pdf#page=9)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-054"></a>

#### 54. Towards Self-Evolving Agent Benchmarks : Validatable Agent Trajectory via Test-Time Exploration


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Evaluation on evolving tasks derived from GAIA.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/da8860a2fe8ddb7589136853bcc313fc-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=2H03gm4Rq6).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiment: AIME-2024 and its evolved versions report ten-run mean accuracies. This count is not assigned to GAIA.



**Benchmark-use evidence:** [PDF p. 8](https://proceedings.iclr.cc/paper_files/paper/2026/file/da8860a2fe8ddb7589136853bcc313fc-Paper-Conference.pdf#page=8)

**Statistical/repetition evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/da8860a2fe8ddb7589136853bcc313fc-Paper-Conference.pdf#page=9)



<a id="paper-055"></a>

#### 55. Agent Data Protocol: Unifying Datasets for Diverse, Effective Fine-tuning of LLM Agents


- **Year / benchmark:** ICLR 2026; GAIA; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/e79c09f39aca8507f527daad3601b3aa-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=tG6301ORHd).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** A fixed shuffle seed makes a sampling procedure reproducible; it does not constitute performance evaluation over multiple seeds.



**Benchmark-use evidence:** [PDF p. 9](https://proceedings.iclr.cc/paper_files/paper/2026/file/e79c09f39aca8507f527daad3601b3aa-Paper-Conference.pdf#page=9)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-056"></a>

#### 56. SWE-RM: Execution-free Feedback for Software Engineering Agents


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/e7feb9dbd9a94b6c552fc403fcebf2ef-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=H9wMe1G76j).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Thirty-two trajectories are collected per SWE-bench Verified task. For k<32, RM@k mean and variance use five random subsampling runs. This is candidate-pool resampling, not repeated full RL training. |
| B. Between-run variability and uncertainty | RM@k has explicitly reported means and variances over five random subsamples. Uncertainty across complete training seeds is not established. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 18](https://proceedings.iclr.cc/paper_files/paper/2026/file/e7feb9dbd9a94b6c552fc403fcebf2ef-Paper-Conference.pdf#page=18)

**Statistical/repetition evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/e7feb9dbd9a94b6c552fc403fcebf2ef-Paper-Conference.pdf#page=6), [PDF p. 18](https://proceedings.iclr.cc/paper_files/paper/2026/file/e7feb9dbd9a94b6c552fc403fcebf2ef-Paper-Conference.pdf#page=18)



<a id="paper-057"></a>

#### 57. Ambig-SWE: Interactive Agents to Overcome Underspecificity in Software Engineering


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Underspecified and interactive tasks derived from SWE-bench Verified.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed4deb2ba9d4640fb6a000c688c2972e-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=X2yzXtH4wp).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | The Std Dev in Table 3 describes summary-text metrics, not resolved-rate uncertainty. A paired task-level test can be conducted without repeating the complete benchmark. |
| C. Formal tests of main and ablation improvements | A one-sided paired Wilcoxon signed-rank test uses alpha=0.05. Table 4 compares Hidden < Interaction and Interaction < Full for six models; all 12 unadjusted p-values are below 0.05. Multiple-comparison correction was not confirmed. |
| D. Test direction and observational unit | The alternative H1 explicitly states median paired difference >0: a one-sided test. Observations are paired across settings, but the exact paired-sample construction is not detailed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Independent evaluation repeats and correction of the family of 12 tests were not confirmed.



**Benchmark-use evidence:** [PDF p. 3](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed4deb2ba9d4640fb6a000c688c2972e-Paper-Conference.pdf#page=3)

**Statistical/repetition evidence:** [PDF p. 5](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed4deb2ba9d4640fb6a000c688c2972e-Paper-Conference.pdf#page=5), [PDF p. 17-18](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed4deb2ba9d4640fb6a000c688c2972e-Paper-Conference.pdf#page=17)



<a id="paper-058"></a>

#### 58. REAP the Experts: Why Pruning Prevails for One-Shot MoE compression


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed93b2b5722acc2341d421b8916404a1-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=ukGxWd2aDG).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiments: coding/multiple-choice tasks for models at or below 50B use three compression-calibration seeds; Qwen3-Coder LiveCodeBench uses five seeds. Large-model SWE evaluation uses one seed.



**Benchmark-use evidence:** [PDF p. 22](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed93b2b5722acc2341d421b8916404a1-Paper-Conference.pdf#page=22)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed93b2b5722acc2341d421b8916404a1-Paper-Conference.pdf#page=7), [PDF p. 23](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed93b2b5722acc2341d421b8916404a1-Paper-Conference.pdf#page=23), [PDF p. 27](https://proceedings.iclr.cc/paper_files/paper/2026/file/ed93b2b5722acc2341d421b8916404a1-Paper-Conference.pdf#page=27)



<a id="paper-059"></a>

#### 59. Kimi-Dev: Agentless Training as Skill Prior for SWE-agents


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/f039544a51899ebac128dbec33dae81c-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=tYppHuGhxJ).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Figure 7 explicitly averages pass@1 over five runs for the SWE-agent RL-prior comparison. Pass@3/5 and 40 training candidates are separate quantities. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 6](https://proceedings.iclr.cc/paper_files/paper/2026/file/f039544a51899ebac128dbec33dae81c-Paper-Conference.pdf#page=6)

**Statistical/repetition evidence:** [PDF p. 8-10](https://proceedings.iclr.cc/paper_files/paper/2026/file/f039544a51899ebac128dbec33dae81c-Paper-Conference.pdf#page=8)



<a id="paper-060"></a>

#### 60. FlowSearcher: Synthesizing Memory-Guided Agentic Workflows for Web Information Seeking


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/f15747119e0e3d00a34a7c17776d2999-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=34v7DVz2l0).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Workflow retries and context memory operate within an execution; they are not independent reruns of a fixed configuration.



**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/f15747119e0e3d00a34a7c17776d2999-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** No corresponding passage located.



<a id="paper-061"></a>

#### 61. Do LLM Agents Know How to Ground, Recover, and Assess? Evaluating Epistemic Competence in Information-Seeking Agents


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Analysis of epistemic competence in information seeking on GAIA.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/f7c714fa40183e349891edf77ab5dcd4-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=r0L9GwlnzP).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** Other experiments: main SeekBench groundedness analyses have 95% CIs and judge agreement has kappa±std. Corresponding repeats or uncertainty were not confirmed in the GAIA appendix generalization table.



**Benchmark-use evidence:** [PDF p. 30](https://proceedings.iclr.cc/paper_files/paper/2026/file/f7c714fa40183e349891edf77ab5dcd4-Paper-Conference.pdf#page=30)

**Statistical/repetition evidence:** [PDF p. 18](https://proceedings.iclr.cc/paper_files/paper/2026/file/f7c714fa40183e349891edf77ab5dcd4-Paper-Conference.pdf#page=18), [PDF p. 25](https://proceedings.iclr.cc/paper_files/paper/2026/file/f7c714fa40183e349891edf77ab5dcd4-Paper-Conference.pdf#page=25), [PDF p. 32](https://proceedings.iclr.cc/paper_files/paper/2026/file/f7c714fa40183e349891edf77ab5dcd4-Paper-Conference.pdf#page=32)



<a id="paper-062"></a>

#### 62. Sculptor: Empowering LLMs with Cognitive Agency via Active Context Management


- **Year / benchmark:** ICLR 2026; SWE-bench.
- **Use:** SWE-bench is used only to evaluate the M3 baseline.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/f9155a06ba1b20e40c38bf8541db456f-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=HPeiH7da0Z).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | The number of independent repeated evaluations was not confirmed for the target experiment. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A one-sample t-test, p<0.001, concerns attention improvement after context folding, not SWE-bench task solving. |
| D. Test direction and observational unit | One-sample t-test on attention improvements for 46 semantic key–value pairs. One-sided versus two-sided is not explicit. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Additional scope and interpretation:** NeedleBench runs each configuration ten times. Repeated SWE-bench baseline evaluation was not confirmed.



**Benchmark-use evidence:** [PDF p. 18](https://proceedings.iclr.cc/paper_files/paper/2026/file/f9155a06ba1b20e40c38bf8541db456f-Paper-Conference.pdf#page=18)

**Statistical/repetition evidence:** [PDF p. 9-10](https://proceedings.iclr.cc/paper_files/paper/2026/file/f9155a06ba1b20e40c38bf8541db456f-Paper-Conference.pdf#page=9), [PDF p. 18](https://proceedings.iclr.cc/paper_files/paper/2026/file/f9155a06ba1b20e40c38bf8541db456f-Paper-Conference.pdf#page=18), [PDF p. 20](https://proceedings.iclr.cc/paper_files/paper/2026/file/f9155a06ba1b20e40c38bf8541db456f-Paper-Conference.pdf#page=20)



<a id="paper-063"></a>

#### 63. AgentFold: Long-Horizon Web Agents with Proactive Context Folding


- **Year / benchmark:** ICLR 2026; GAIA.
- **Use:** Direct task evaluation.
- **Original sources:** [Official PDF](https://proceedings.iclr.cc/paper_files/paper/2026/file/fa948624dfde013671e72c1a7ca4aebc-Paper-Conference.pdf); [OpenReview](https://openreview.net/forum?id=IuZoTgsUws).


| Dimension | Reported evidence / finding |
| --- | --- |
| A. Independent repeated evaluation | Benchmarks with fewer than 200 examples are averaged over three trials. The GAIA text-only subset falls within this rule. |
| B. Between-run variability and uncertainty | A numerical uncertainty measure for the target result was not confirmed. |
| C. Formal tests of main and ablation improvements | A named hypothesis test and corresponding p-value for the target performance improvement were not confirmed. |
| D. Test direction and observational unit | The direction and observational unit of a target-improvement test were not confirmed. |
| E. Multiple-comparison correction | No multiple-comparison correction method or adjusted p-value was confirmed for the target performance comparisons. |
| F. Mean-plus-SD description versus a formal test | No explicit use of the method-mean > baseline-mean + baseline-SD criterion was located for the target comparison. Formal tests are recorded separately under C. |


**Benchmark-use evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/fa948624dfde013671e72c1a7ca4aebc-Paper-Conference.pdf#page=7)

**Statistical/repetition evidence:** [PDF p. 7](https://proceedings.iclr.cc/paper_files/paper/2026/file/fa948624dfde013671e72c1a7ca4aebc-Paper-Conference.pdf#page=7)



<a id="paper-methods"></a>

### 8. Counting rules and supporting files

1. The 63 papers are deduplicated main-conference papers that actually use the target benchmarks. Benchmark introductions, original-task subsets, derived tasks, trajectory studies, and case experiments are included.
2. A counts independent repeated evaluations or multiple seeds. Pass@k candidate counts, within-workflow retries, evolution rounds, and candidate-pool resampling are recorded separately.
3. B distinguishes cross-run/seed uncertainty, CIs, SEs, undefined ± quantities, candidate-subset distributions, and output variance.
4. C records both main-versus-baseline and full-versus-ablation comparisons. Significant and non-significant tests both count as tests. The strict named-test count requires the test name and corresponding p-value.
5. D records direction, observational unit, pairing construction, and run aggregation. Direction is not inferred solely from a test name.
6. E checks the test family, correction method, and adjusted p-value. Screening terms include Holm, Bonferroni, Benjamini/Hochberg, family-wise, multiplicity, adjusted/corrected p-value, and false discovery. Keyword matches are contextual leads, not positive findings by themselves.
7. F records the mean > baseline mean + SD criterion separately from formal tests, mean±SD plotting, and theoretical variance formulas.
8. All paper numbering is one-based; the original source JSON uses a zero-based index linked through OpenReview IDs.

Supporting evidence:


- [Six-dimension workbook](iclr_benchmark_audit_20261116/statistical_rigor/ICLR_63_papers_review_blocks.xlsx)

- [Six-dimension CSV](iclr_benchmark_audit_20261116/statistical_rigor/review_blocks.csv)

- [Six-dimension source JSON](iclr_benchmark_audit_20261116/statistical_rigor/review_blocks.json)

- [Position/intersection statistics](iclr_benchmark_audit_20261116/statistical_rigor/our_position.json)

- [SD interval calculations](iclr_benchmark_audit_20261116/statistical_rigor/errorbar_comparisons.json)

- [Original detailed workbook](iclr_benchmark_audit_20261116/statistical_rigor/ICLR_63_papers_statistical_rigor.xlsx)

- [Original per-paper audit](iclr_benchmark_audit_20261116/statistical_rigor/rigor_audit.json)

- [Multiplicity/mean-plus-SD terminology review](iclr_benchmark_audit_20261116/statistical_rigor/multiplicity_screen.json)

- [Benchmark-use census](iclr_benchmark_audit_20261116/statistics.json)



<a id="vendors"></a>

## Part II: Official model-evaluation materials from three vendors

<a id="vendor-scope"></a>

### 1. Scope and interpretation

The period is January 1, 2024 through November 18, 2026, the cutoff of the source audit. The English edition does not extend that cutoff. The review starts from [Anthropic's system-card index](https://www.anthropic.com/system-cards), [Google DeepMind's model-card index](https://deepmind.google/models/model-cards/), and OpenAI's official release/research/system-card pages, including the [Deployment Safety Hub](https://deploymentsafety.openai.com/). Seventy-eight Anthropic/DeepMind index-linked materials were cached; historical 2023 cards retained in those indexes are outside the model-release period. Official methodology sheets, technical reports, and release posts provide supplementary evidence.

Rows group models sharing an evaluation description. They are model-group/benchmark entries, not a count of distinct models or all dated API snapshots. Reasoning effort, prompts, tools, release variants, and retrospective comparisons are identified where relevant. The table contains all 58 reviewed entries: 42 for original benchmarks/subsets and 16 for SWE-series extensions.

The main scope includes GAIA, Gaia2, and SWE-bench with Lite/Verified/hard subsets. SWE-bench Pro, Multilingual, and Multimodal are separate extensions. DeepSWE, Expert-SWE, FrontierSWE, and SWE-Lancer are not counted as the original SWE-bench.

The six audit dimensions are the same as in Part I. A model's own CI is not automatically a formal test of the difference between two models. Cons@64, best-of-N, and candidate reranking are inference aggregation; pass@3 is a multiple-attempt success metric. These are distinguished from SD across complete independently repeated evaluations. Statistics reported only for another benchmark are not transferred to a target result.

“Not confirmed” is a finding about explicit public reporting, not an assertion about undisclosed internal practice. The review examined main target tables, relevant methodology and figures, and full-text test/correction terminology. OpenAI pages returning local 403 errors were cross-checked using web retrieval and official CDN PDFs; failed local retrieval was not treated as evidence of absent reporting.

<a id="vendor-models"></a>

### 2. All model-group assessments

For every row below, a **named test with a corresponding p-value for the target performance improvement**, and a **multiplicity-adjusted p-value for that improvement**, were not confirmed in the listed relevant material. Those findings are also stored for each row in the English JSON/CSV. Target uncertainty is reported separately; error bars are not silently relabeled as cross-run SD.



#### OpenAI: Original benchmarks and subsets


| Year / models | Target benchmark | Repeated evaluation | Uncertainty | Details and sources |
| --- | --- | --- | --- | --- |
| 2024: GPT-4o (including later evaluated versions) | SWE-bench Verified | Not specified in the 2024 card; the later o1 card describes five Agentless candidate patches per task. | The early card gives a point estimate; later comparison plots belong to later evaluations. | The 2024 card reports 19%. Different model versions/configurations are not pooled into one set of repeats. [Source 1](https://cdn.openai.com/gpt-4o-system-card.pdf); [Source 2](https://cdn.openai.com/o1-system-card-20241205.pdf) |
| 2024: GPT-4o mini | SWE-bench Verified | Target evaluation count not confirmed. | Target uncertainty not confirmed. | An official 2025 comparison table retrospectively reports 8.7%; this is not a statistical report from the 2024 release. [Source 1](https://openai.com/index/gpt-4-1/) |
| 2024: o1-preview, o1-mini, o1 | SWE-bench Verified | Five Agentless candidate patches per task; pass@1 aggregates the success rates of valid patches. | The o1 target plot does not report SD/CI. | The December 2024 card covers three released models. Five candidate patches do not provide five complete-benchmark scores and their SD. [Source 1](https://cdn.openai.com/o1-system-card-20241205.pdf); [Source 2](https://openai.com/index/o1-and-new-tools-for-developers/) |
| 2025: o3-mini | SWE-bench Verified | Five attempts per task in Agentless; four per task in the internal-tools setting. | Target plot does not report SD/CI. | The internal-tools result uses a non-final checkpoint. The repeat counts from the two settings are kept separate. [Source 1](https://cdn.openai.com/o3-mini-system-card-feb10.pdf) |
| 2025: Deep research (early o3-derived model) | GAIA | Reports pass@1 and cons@64; independent complete-evaluation count is not explicit. | The GAIA table does not report SD/CI. | GAIA pass@1=67.36%; cons@64=72.57%. The 64 denotes consensus sampling, not 64 independent complete-evaluation scores with mean and SD. [Source 1](https://openai.com/index/introducing-deep-research/) |
| 2025: Deep research (same model family) | SWE-bench Verified | The card distinguishes five Agentless attempts and four o3-base attempts per task; it does not fully map counts to every deep-research setup. | The SWE plot has error bars; their identification as cross-run SD was not confirmed in its description. | SWE is evaluated, but the baseline four-attempt statement is not automatically assigned to every deep-research model. [Source 1](https://cdn.openai.com/deep-research-system-card.pdf) |
| 2025: GPT-4.5 | SWE-bench Verified | The target section does not specify a count; the later o3 card describes five-candidate Agentless for earlier models. | Target plot has error bars; cross-run SD was not confirmed. | Graphical uncertainty is recorded without assigning an unsupported SD definition. [Source 1](https://cdn.openai.com/gpt-4-5-system-card-2272025.pdf); [Source 2](https://cdn.openai.com/pdf/2221c875-02dc-4789-800b-e7758f3722c1/o3-and-o4-mini-system-card.pdf) |
| 2025: GPT-4.1, GPT-4.1 mini | SWE-bench Verified | Target repeat count is not specified on the release page. | Target results do not report SD/CI. | Main model 54.6%; mini 23.6%; nano is a dash in the target table. The five-run statement on that page concerns tau-bench, not SWE. [Source 1](https://openai.com/index/gpt-4-1/) |
| 2025: o3, o4-mini | SWE-bench Verified | Four attempts per task in the internal scaffold, aggregated as pass@1. | Target plot has error bars; cross-run SD was not confirmed. | 477 tasks; multiple checkpoints and browsing configurations are reported. [Source 1](https://cdn.openai.com/pdf/2221c875-02dc-4789-800b-e7758f3722c1/o3-and-o4-mini-system-card.pdf) |
| 2025: codex-1 | SWE-bench Verified | The release page does not specify codex-1 target repeats. | Target SD/CI not confirmed. | 477 tasks; 192k context and medium reasoning effort are specified. The o3 repeat count is not inherited. [Source 1](https://openai.com/index/introducing-codex/) |
| 2025: ChatGPT agent | SWE-bench Verified | The four-tries statement explicitly names the o3/o4-mini controls; the agent-specific count is not explicit. | Target plot has error bars; the general method specifies 95% bootstrap CIs for pass@1. | Target uncertainty is present, but a cross-complete-run SD is not established. [Source 1](https://cdn.openai.com/pdf/839e66fc-602c-48bf-81d3-b21eacc3459d/chatgpt_agent_system_card.pdf) |
| 2025: gpt-oss-120b, gpt-oss-20b | SWE-bench Verified | Four tries explicitly refers to o3/o4-mini; gpt-oss target counts are not explicit. | Target plot has error bars; cross-run SD was not confirmed. | Both open-weight models appear in the target plot. The card does not give target-improvement p-values. [Source 1](https://arxiv.org/pdf/2508.10925) |
| 2025: GPT-5, GPT-5 mini, GPT-5 nano; card variants thinking/thinking-mini | SWE-bench Verified | Four attempts per task in the card internal-tools setting; the release page separately lists main/mini/nano. | Card target plot has error bars; the general method uses 95% bootstrap CIs. Complete-run SD is not reported. | Card and release-page verbosity differ; 74%/72% and 74.9% are not treated as one evaluation. Nano uncertainty is not separately provided. [Source 1](https://cdn.openai.com/gpt-5-system-card.pdf); [Source 2](https://openai.com/index/introducing-gpt-5-for-developers/) |
| 2025: GPT-5-Codex | SWE-bench Verified | Target repeat count not confirmed. | Target SD/CI not confirmed. | The release starts reporting all 500 tasks. The safety addendum does not supply target-performance statistics. [Source 1](https://openai.com/index/introducing-upgrades-to-codex/); [Source 2](https://openai.com/index/gpt-5-system-card-addendum-gpt-5-codex/) |
| 2025: GPT-5.1 Thinking | SWE-bench Verified | Target repeat count not confirmed. | Target SD/CI not confirmed. | 76.3%. Averaging across 500 tasks is a task average, not a run average. Instant has no separate SWE score. [Source 1](https://openai.com/index/gpt-5-1-for-developers/); [Source 2](https://cdn.openai.com/pdf/4173ec8d-1229-47db-96de-06d87147e07e/5_1_system_card.pdf) |
| 2025: GPT-5.1-Codex, GPT-5.1-Codex-Max | SWE-bench Verified | Target repeat count not confirmed. | Target SD/CI not confirmed. | The official table gives 73.7% and 77.9%. Extra-high effort and compaction describe configurations. [Source 1](https://openai.com/index/gpt-5-1-codex-max/) |
| 2025: GPT-5.2 Thinking | SWE-bench Verified; also SWE-bench Pro | Target repeat count not confirmed. | Target SD/CI not confirmed. | Verified 80.0%; Pro benchmark 55.6%. Pro/Instant model variants do not have separate corresponding target scores; Thinking scores are not assigned to them. [Source 1](https://openai.com/index/introducing-gpt-5-2/); [Source 2](https://cdn.openai.com/pdf/3a4153c8-c748-4b71-8e31-aecbde944f8d/oai_5_2_system-card.pdf) |


#### OpenAI: SWE-series extensions


| Year / models | Target benchmark | Repeated evaluation | Uncertainty | Details and sources |
| --- | --- | --- | --- | --- |
| 2025: GPT-5.2-Codex | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/introducing-gpt-5-2-codex/) |
| 2026: GPT-5.3-Codex | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/introducing-gpt-5-3-codex/) |
| 2026: GPT-5.3-Codex-Spark | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/introducing-gpt-5-3-codex-spark/) |
| 2026: GPT-5.4 | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/introducing-gpt-5-4/) |
| 2026: GPT-5.4 mini, GPT-5.4 nano | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/introducing-gpt-5-4-mini-and-nano/) |
| 2026: GPT-5.5 | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/introducing-gpt-5-5/) |
| 2026: GPT-5.6 Sol, GPT-5.6 Terra, GPT-5.6 Luna | SWE-bench Pro | The release page does not specify target repeats. | Target cross-run SD/CI not confirmed on the release page. | The page reports point estimates/plots; other coding benchmarks are separate. The improvement-test and correction findings refer to the listed relevant materials. [Source 1](https://openai.com/index/gpt-5-6/) |


#### Anthropic: Original benchmarks and subsets


| Year / models | Target benchmark | Repeated evaluation | Uncertainty | Details and sources |
| --- | --- | --- | --- | --- |
| 2024: Claude 3 Opus, Claude 3 Haiku | SWE-bench Verified (official retrospective comparison) | Target repeat count not confirmed. | Target SD/CI not confirmed. | The October 2024 update gives 22.2%/7.2%. The combined Claude 3 PDF contains later appendices, which are not treated as March-release experiments. [Source 1](https://assets.claude.com/c7822cdc35ad788ec87e14b3a9d45010f1f86c38.pdf) |
| 2024: Claude 3.5 Sonnet (June version) | SWE-bench Verified (official retrospective comparison) | Target repeat count not confirmed. | Target SD/CI not confirmed. | A later card gives 33.4%. The internal coding evaluation in the June release is not automatically identified as SWE-bench. [Source 1](https://assets.claude.com/c7822cdc35ad788ec87e14b3a9d45010f1f86c38.pdf) |
| 2024: Claude 3.5 Sonnet (October version), Claude 3.5 Haiku | SWE-bench Verified | Target repeat count not confirmed. | Target SD/CI not confirmed. | 49.0%/40.6%. The same page's multi-trial pass^k analysis concerns tau-bench, not SWE. [Source 1](https://assets.claude.com/c7822cdc35ad788ec87e14b3a9d45010f1f86c38.pdf) |
| 2025: Claude 3.7 Sonnet | SWE-bench Verified; hard subset | The hard subset explicitly uses 20 attempts; full-set headline repeats are not explicit. | Target SD/CI not confirmed. | Card p30: mean 9.65 of 42 tasks solved. Ten runs describes the threshold; the actual result states 20 attempts. [Source 1](https://assets.claude.com/9ff93dfa8f445c932415d335c88852ef47f1201e.pdf); [Source 2](https://www.anthropic.com/news/claude-3-7-sonnet) |
| 2025: Claude Sonnet 4, Claude Opus 4 | SWE-bench Verified; hard subset | Hard-subset means are reported under a ten-run threshold specification; full-set repeats are not explicit on the current release page. | Target SD/CI not confirmed. | Card p107: means 15.4/16.6 of 42 tasks. High-compute parallel candidate selection is recorded separately from independent evaluation repeats. [Source 1](https://assets.claude.com/07b2a3f9902ee19fe39a36ca638e5ae987bc64dd.pdf); [Source 2](https://www.anthropic.com/news/claude-4) |
| 2025: Claude Opus 4.1 | SWE-bench Verified; hard subset | Hard-subset mean solved count is given; this addendum does not specify its repeat count. | Target SD/CI not confirmed. | Full set 74.5%; hard subset 18.4/42. Windsurf's one-SD statement concerns another benchmark and is not counted as SWE SD. [Source 1](https://assets.claude.com/9fa30625273bafdf5af82c93719d7ca606485a16.pdf); [Source 2](https://www.anthropic.com/news/claude-opus-4-1) |
| 2025: Claude Sonnet 4.5 | SWE-bench Verified; hard subset | Ten full-set trials; repeated means also appear for the hard subset. | Target SD/CI not confirmed. | Full set: 500 tasks, 77.2%. Hard subset: mean 20.4 of 45 tasks solved. [Source 1](https://assets.claude.com/963373e433e489a87a10c823c52a0a013e9172dd.pdf); [Source 2](https://www.anthropic.com/news/claude-sonnet-4-5) |
| 2025: Claude Haiku 4.5 | SWE-bench Verified | 50 trials. | Target SD/CI not confirmed. | 500 tasks, 73.3%. The 50-trial evidence comes from the target footnote on the release page. [Source 1](https://assets.claude.com/7aad69bf12627d42234e01ee7c36305dc2f6a970.pdf); [Source 2](https://www.anthropic.com/news/claude-haiku-4-5) |
| 2025: Claude Opus 4.5 | SWE-bench Verified; also Pro and Multilingual | Five independent trials for headline scores; a ten-trial threshold is separately described for the hard subset. | Target SD/CI not confirmed. | Card p20: three headline SWE variants average five trials. The same page's ±1.05% belongs to Terminal-Bench, not SWE. [Source 1](https://assets.claude.com/bf10f64990cfda0ba858290be7b8cc6317685f47.pdf); [Source 2](https://www.anthropic.com/news/claude-opus-4-5) |
| 2026: Claude Opus 4.6 | SWE-bench Verified; Multilingual | 25 headline trials; a ten-trial threshold is separately described for the hard subset. | Target SD/CI not confirmed. | Card pp18–19 and the release page both specify 25 target trials. [Source 1](https://anthropic.com/claude-opus-4-6-system-card); [Source 2](https://www.anthropic.com/news/claude-opus-4-6) |
| 2026: Claude Sonnet 4.6 | SWE-bench Verified; Multilingual | The dedicated target section and release page specify ten trials; the summary-table footnote says 25. | Target SD/CI not confirmed. | The audit records ten, supported by the dedicated section and release page, while retaining the conflicting table footnote. [Source 1](https://anthropic.com/claude-sonnet-4-6-system-card); [Source 2](https://www.anthropic.com/news/claude-sonnet-4-6) |
| 2026: Claude Mythos Preview | SWE-bench Verified; also Pro, Multilingual, Multimodal | Five trials averaged for each target variant. | Target SD/CI not confirmed. | The SWE capabilities subsection explicitly averages each score over five trials. CIs on other safety tasks are not assigned as SWE cross-run SD. [Source 1](https://www.anthropic.com/claude-mythos-preview-system-card) |
| 2026: Claude Opus 4.7 | SWE-bench Verified; also Pro, Multilingual, Multimodal | Five trials averaged for each target variant. | Target SD/CI not confirmed. | The SWE capabilities subsection explicitly averages each score over five trials. CIs on other safety tasks are not assigned as SWE cross-run SD. [Source 1](https://anthropic.com/claude-opus-4-7-system-card) |
| 2026: Claude Opus 4.8 | SWE-bench Verified; also Pro, Multilingual, Multimodal | Five trials averaged for each target variant. | Target SD/CI not confirmed. | The SWE capabilities subsection explicitly averages each score over five trials. CIs on other safety tasks are not assigned as SWE cross-run SD. [Source 1](https://anthropic.com/claude-opus-4-8-system-card) |
| 2026: Claude Fable 5, Claude Mythos 5 | SWE-bench Verified; also Pro, Multilingual, Multimodal | Five trials averaged for each target variant. | Target SD/CI not confirmed. | The SWE capabilities subsection explicitly averages each score over five trials. CIs on other safety tasks are not assigned as SWE cross-run SD. [Source 1](https://anthropic.com/claude-fable-5-mythos-5-system-card) |
| 2026: Claude Sonnet 5 | SWE-bench Verified; also Pro, Multilingual, Multimodal | Five trials averaged for each target variant. | Target SD/CI not confirmed. | The SWE capabilities subsection explicitly averages each score over five trials. CIs on other safety tasks are not assigned as SWE cross-run SD. [Source 1](https://anthropic.com/claude-sonnet-5-system-card) |
| 2026: Claude Opus 5 | SWE-bench Verified; also Pro, Multilingual, Multimodal | Five trials averaged for each target variant. | Target SD/CI not confirmed. | The SWE capabilities subsection explicitly averages each score over five trials. CIs on other safety tasks are not assigned as SWE cross-run SD. [Source 1](https://anthropic.com/claude-opus-5-system-card) |


#### Anthropic: SWE-series extensions


| Year / models | Target benchmark | Repeated evaluation | Uncertainty | Details and sources |
| --- | --- | --- | --- | --- |
| 2026: Claude Fable 5.1, Claude Mythos 5.1 | SWE-bench Pro, Multilingual, Multimodal | Five trials averaged per variant. | Target SD/CI not confirmed. | The SWE subsection no longer gives a headline Verified score. This entry belongs only to the extended-benchmark table. [Source 1](https://www.anthropic.com/claude-fable-5-1-mythos-5-1-system-card) |
| 2026: Claude Opus 5.5 | SWE-bench Pro, Multilingual, Multimodal | Five trials averaged per variant. | Target SD/CI not confirmed. | The SWE subsection no longer gives a headline Verified score. This entry belongs only to the extended-benchmark table. [Source 1](https://www.anthropic.com/claude-opus-5-5-system-card) |
| 2026: Claude Sonnet 5.5 | SWE-bench Pro, Multilingual, Multimodal | Five trials averaged per variant. | Target SD/CI not confirmed. | The SWE subsection no longer gives a headline Verified score. This entry belongs only to the extended-benchmark table. [Source 1](https://www.anthropic.com/claude-sonnet-5-5-system-card) |
| 2026: Claude Haiku 5.5 | SWE-bench Pro, Multilingual, Multimodal | Five trials averaged per variant. | Target SD/CI not confirmed. | The SWE subsection no longer gives a headline Verified score. This entry belongs only to the extended-benchmark table. [Source 1](https://www.anthropic.com/claude-haiku-5-5-system-card) |
| 2026: Claude Fable 5.2, Claude Mythos 5.2 | SWE-bench Pro, Multilingual, Multimodal | Five trials averaged per variant. | Target SD/CI not confirmed. | The SWE subsection no longer gives a headline Verified score. This entry belongs only to the extended-benchmark table. [Source 1](https://www.anthropic.com/claude-fable-5-2-mythos-5-2-system-card) |


#### Google DeepMind: Original benchmarks and subsets


| Year / models | Target benchmark | Repeated evaluation | Uncertainty | Details and sources |
| --- | --- | --- | --- | --- |
| 2024: Gemini 1.5 Pro, Gemini 1.5 Flash | SWE-bench Verified (official retrospective comparison) | Single-trajectory and multiple-candidate reranking settings; independent repeats for estimating means are not explicit. | Target SD/CI not confirmed. | Table 3 of the 2025 report gives retrospective results. Multiple candidates are an inference strategy, not a between-run SD. [Source 1](https://storage.googleapis.com/deepmind-media/gemini/gemini_v2_5_report.pdf) |
| 2024–2025: Gemini 2.0 Flash, Gemini 2.0 Flash-Lite | SWE-bench Verified (later official comparison) | Single-trajectory and candidate-reranking settings; independent repeat count is not explicit. | Target SD/CI not confirmed. | Table 3 includes both 2.0 models. Flash initially released in 2024, with later versions in 2025. [Source 1](https://storage.googleapis.com/deepmind-media/gemini/gemini_v2_5_report.pdf) |
| 2025: Gemini 2.5 Pro (preview/GA versions listed in the reports) | SWE-bench Verified | Single-trajectory and candidate-reranking settings; complete-evaluation repeat count is not explicit. | Target SD/CI not confirmed. | The card lists several versions. The report specifies model-based reranking; RE-Bench bootstrap CIs are not counted as SWE uncertainty. [Source 1](https://storage.googleapis.com/deepmind-media/gemini/gemini_v2_5_report.pdf); [Source 2](https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-2-5-Pro-Model-Card.pdf) |
| 2025: Gemini 2.5 Flash (versions listed in the card) | SWE-bench Verified | Single-trajectory and multiple-candidate settings; complete-evaluation repeat count is not explicit. | Target SD/CI not confirmed. | Flash Image shares a card with Flash; this does not establish Image-specific SWE results. [Source 1](https://storage.googleapis.com/deepmind-media/gemini/gemini_v2_5_report.pdf); [Source 2](https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-2-5-Flash-Model-Card.pdf) |
| 2025: Gemini 2.5 Flash-Lite | SWE-bench Verified | Target independent repeat count not confirmed. | Target SD/CI not confirmed. | Single-attempt scores are listed for different versions. Single attempt does not imply that the whole evaluation was performed only once. [Source 1](https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-2-5-Flash-Lite-Model-Card.pdf) |
| 2025: Gemini 3 Pro Preview | SWE-bench Verified | Ten runs. | Target table does not report SD/CI. | Official methodology p2 explicitly averages ten runs. Single attempt excludes majority voting/parallel inference aggregation. [Source 1](https://deepmind.google/models/evals-methodology/gemini-3-pro/) |
| 2025: Gemini 3 Flash Preview | SWE-bench Verified | Five runs. | Target table does not report SD/CI. | Official methodology p2 explicitly averages five runs. [Source 1](https://deepmind.google/models/evals-methodology/gemini-3-flash/) |
| 2026: Gemini 3.1 Pro Preview | SWE-bench Verified; also Pro | Verified: ten runs; Pro benchmark: five runs. | Target table does not report SD/CI. | Adjusting scores after fixing three harness bugs is a scoring correction, not a multiple-comparison correction. [Source 1](https://deepmind.google/models/evals-methodology/gemini-3-1-pro); [Source 2](https://deepmind.google/models/model-cards/gemini-3-1-pro/) |


#### Google DeepMind: SWE-series extensions


| Year / models | Target benchmark | Repeated evaluation | Uncertainty | Details and sources |
| --- | --- | --- | --- | --- |
| 2026: Gemini 3.1 Flash-Lite | SWE-bench Pro (later official comparison) | Target repeat count not confirmed. | Target SD/CI not confirmed. | Appears as a control in the 3.5 Flash-Lite table. This concerns SWE-bench Pro, not the original three benchmarks. [Source 1](https://deepmind.google/models/model-cards/gemini-3-5-flash-lite/) |
| 2026: Gemini 3.5 Flash | SWE-bench Pro | Five runs. | Target SD/CI not confirmed. | The official methodology explicitly specifies five runs using the Antigravity harness. [Source 1](https://deepmind.google/models/evals-methodology/gemini-3-5-flash); [Source 2](https://deepmind.google/models/model-cards/gemini-3-5-flash/) |
| 2026: Gemini 3.5 Flash-Lite | SWE-bench Pro | Target repeat count is not explicit. | Target SD/CI not confirmed. | The k=2 statement in the same methodology concerns MLE-Bench, not repeated SWE evaluation. [Source 1](https://deepmind.google/models/evals-methodology/gemini-3-5-flash-lite); [Source 2](https://deepmind.google/models/model-cards/gemini-3-5-flash-lite/) |
| 2026: Gemini 3.6 Flash | SWE-bench Pro | Target repeat count is not explicit. | Target SD/CI not confirmed. | Uses internal Antigravity; other long-horizon benchmarks are reported separately. [Source 1](https://deepmind.google/models/evals-methodology/gemini-3-6-flash); [Source 2](https://deepmind.google/models/model-cards/gemini-3-6-flash/) |


<a id="vendor-exclusions"></a>

### 3. GAIA, Gaia2, later releases, and non-target material

OpenAI's [Deep research release](https://openai.com/index/introducing-deep-research/) explicitly reports GAIA pass@1 and cons@64, but its GAIA table does not provide cross-run SD, an improvement hypothesis test, or adjusted p-values. No vendor self-reported Gaia2 performance table was confirmed in the reviewed model materials. An Anthropic model guessing that a task comes from GAIA, Google's unrelated Portuguese-language model named GAIA, and third-party papers using vendor APIs on Gaia2 are not vendor model-release evaluations of that benchmark.

- **OpenAI GPT-5.2-Codex, GPT-5.3-Codex/Spark, GPT-5.4/mini/nano, GPT-5.5, GPT-5.6 Sol/Terra/Luna:** relevant releases report SWE-bench Pro and appear in the extension table above. A single-attempt designation does not itself disclose independent repeat counts. GPT-5.6 preview and full release were checked separately; the full-release SWE-Pro table is included.
- **OpenAI GPT-6 Astra/Sol/Luna, GPT-6.1 Sol/Terra, GPT-6.2 Astra/Sol:** the checked release pages did not establish headline performance on the original three benchmarks. Other coding/agentic evaluations are separate. Astra's CoT-Control description mentions SWE-bench but explicitly reports QA subsets in that section, not a SWE solver-success improvement test.
- **OpenAI Instant, Realtime/Live, image/audio, Rosalind, Cyber, Operator, and Pro variants without separate target scores:** adjacent main-model scores are not assigned to them. A dash for GPT-4.1 nano or GPT-5.2 Pro is not an observed target score. An independent target report for GPT-5.1-Codex-mini was not confirmed.
- **Google experimental Gemini 2.0 Pro/Flash Thinking, Gemini 2.5 Deep Think/Computer Use, Gemini 3 image/audio/Omni, Gemini 3.7/3.8 Flash, and Gemini 4 Argon/Carbon/Hydrogen:** the reviewed index cards/methodology did not establish a dedicated headline score on the original three benchmarks. Other evaluations are outside the target fields.
- **Google Gemma, Robotics, Veo, Lyria, Imagen and related families:** their index cards were screened; a target-task success-rate report was not confirmed. Materials without target evaluations are not treated as target experiments missing statistics.
- **Anthropic's later 5.1/5.5/5.2 releases:** SWE extension variants and their repeated evaluation are retained in the extension table.

OpenAI's [Why we no longer evaluate SWE-bench Verified](https://openai.com/index/why-we-no-longer-evaluate-swe-bench-verified/) also describes selecting 138 tasks that o3 did not consistently solve over **64 independent runs** for a benchmark-quality audit. This is additional target-repeat evidence, not a new model release. The purpose is benchmark-quality/contamination analysis; an adjusted model-improvement p-value or SD of 64 complete-benchmark success rates is not reported there.

#### Findings organized by the six dimensions

| Dimension | Finding in the reviewed vendor materials |
|---|---|
| A | Explicit repetition exists, including four/five samples per task, five to 50 averaged trials, and the additional 64-run o3 problem audit. |
| B | Some OpenAI target figures provide error bars/CIs. Repeated means, within-task bootstrap intervals, and complete-run SD are recorded separately. |
| C | A named test and p-value for the listed target solver-success improvements were not confirmed. |
| D | Test direction is not invented where a target test is unconfirmed. Task sampling, complete runs, consensus aggregation, and candidate selection remain distinct units. |
| E | An adjusted p-value for the listed target performance improvements was not confirmed. |
| F | The mean-plus-SD description was not confirmed as a formal target test. The one-SD claim on the Opus 4.1 page refers to a separate Windsurf benchmark. |

<a id="vendor-quotes"></a>

### 4. Official wording on sample size and statistical power

#### Anthropic: detectable effect size

> “The larger your sample, the smaller the effect size you can detect.”

This appears in **Run → Preregister** in [Building strong safety evaluations](https://www.anthropic.com/research/building-strong-safety-evaluations). It concerns AI safety evaluation, and the size of an effect that can be detected, rather than the magnitude of the underlying effect itself. The same guide notes that multi-turn API-evaluation CIs can exceed ±10 percentage points and gives an Opus 5/Opus 5.5 example with 98% versus 94% where the difference is not statistically significant. That safety example is not counted as GAIA/SWE evidence. The guide also recommends statistical adjustment when many comparisons are performed.

#### OpenAI: uncertainty estimation on very small datasets

> “this method can underestimate uncertainty for very small datasets”

The [GPT-5 System Card](https://cdn.openai.com/gpt-5-system-card.pdf), Section 5.1, physical PDF p23, explains that its pass@1 bootstrap resamples attempts within each problem. This captures variability on fixed problems rather than all problem-level variation, and may yield overly narrow intervals on very small datasets. It describes an uncertainty-estimation limitation, not impossibility of obtaining significance.

High execution cost and small independent task sets limit the power achievable within a practical budget. The audit's central reporting finding is that no multiplicity-adjusted p-value for a target performance improvement was confirmed in the reviewed materials. The power discussion explains why detecting modest effects under strict adjusted thresholds can require more data.

<a id="vendor-position"></a>

### 5. Comparison with PORCHESTRA

| Evidence | Reviewed vendor practice | PORCHESTRA rebuttal |
|---|---|---|
| Repetition | Four/five attempts per task; five, ten, 25, or 50 averaged trials; additional 64-run o3 task audit. | Three independent evaluations. |
| Between-run uncertainty | Some target CIs; many repeated means without a target cross-run SD. | Cross-run mean±SD. |
| Multiple-attempt indicators | Cons@64 and candidate aggregation/reranking appear in some evaluations. | Pass@3. |
| Target improvement tests | Named tests and corresponding p-values were not confirmed in the listed target comparisons. | Main exact McNemar and ablation Welch tests. |
| Multiplicity correction | Adjusted target-improvement p-values were not confirmed. | Adjusted p-values not reported. |

The “among the more comprehensive” statement is confined to the combination of statistical evidence in the 63-paper ICLR sample. Vendor materials provide additional practice context rather than a combined percentile. Some vendor evaluations use substantially more repeats than PORCHESTRA.

### 6. Source records and reproducibility

The English edition retains all 63 paper identities, PDF/OpenReview links and page references, the six dimensions for each paper, all 58 vendor entries and their original source URLs, the interval calculations, and the principal scope qualifications. Its table layout is reorganized in English; it does not add new source verification or recompute p-values.

- [English paper-level data](ICLR_and_vendor_papers_EN.json).
- [English vendor data](ICLR_and_vendor_models_EN.json) and [CSV](ICLR_and_vendor_models_EN.csv).
- [Chinese combined report](ICLR_and_vendor_benchmark_statistical_audit.md).
- [Vendor index links](vendor_model_benchmark_audit_20261118/index_links.json), [card retrieval metadata](vendor_model_benchmark_audit_20261118/collected_cards.json), and [OpenAI sitemap leads](vendor_model_benchmark_audit_20261118/openai_sitemap.json). Sitemap lastmod values are update timestamps, not model-release dates.
- [Official methodology records](vendor_model_benchmark_audit_20261118/collected_methods.json), [PDF records](vendor_model_benchmark_audit_20261118/collected_pdfs.json), [Anthropic release records](vendor_model_benchmark_audit_20261118/collected_anthropic_launches.json), and [supplementary records](vendor_model_benchmark_audit_20261118/collected_supplements.json).
- The vendor source directory also retains web-retrieval receipts for OpenAI pages returning local 403 errors. Cached original PDFs/text are under `/tmp/vendor_model_benchmark_audit_20261118/`; these were not a new download of the ICLR corpus.
- [English report builder](build_english_benchmark_statistical_audit.py), [Chinese merge builder](merge_benchmark_statistical_audits.py), and [vendor source collector](vendor_model_benchmark_audit_20261118/collect_sources.py).

