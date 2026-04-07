# Value-Based Care AI Platforms: Business Model and Healthcare Data Workflow

## 1. Core Objectives of AI-Driven Patient Risk Platforms

Value-based care enablement platforms with AI-driven patient risk assessment help primary care groups, health systems, and independent physician associations (IPAs) identify high-risk Medicare patients, prioritize action, and reduce administrative burden while improving outcomes and shared savings performance in Medicare risk-based programs.

These platforms operate within specific CMS programs — primarily **ACO REACH** and the **Medicare Shared Savings Program (MSSP)**, with **Medicare Advantage** tracks as well. CMS plans to transition ACO REACH to the **LEAD Model (Long-term Enhanced ACO Design)** in 2027. These platforms collectively support hundreds of thousands of Medicare beneficiaries across multiple states, managing billions in total Medicare medical spend.

Key players in this space include **Optum AI**, **Change Healthcare Analytics**, **Humana-AI partnerships**, **CVS/Aetna Intelligent Risk**, and others that combine predictive analytics with care coordination workflows.

Many of these platforms are not purely SaaS vendors — they act as **participant entities in ACO programs**, co-bearing financial risk (upside and downside) alongside the provider groups they support.

### Top 5 objectives
1. Help providers deliver proactive, higher-quality care and get rewarded for keeping patients healthy.
2. Support primary care teams with tools and intelligence for value-based care operations.
3. Shift care from reactive, visit-based work to continuous, outside-the-visit patient management.
4. Focus attention on the patients who need help most, rather than just closing generic care gaps.
5. Reduce administrative burden and make value-based care workflows simpler to run.

## 2. Differentiating Features of Leading Platforms in This Space

Competitive platforms differentiate themselves by prioritizing patient-centered action, using advanced AI and predictive signals, and automating work that would otherwise be manual.

### Top 5 differentiators
1. Patient-centric prioritization instead of gap-centric task lists.
2. Proactive care alerts that extend beyond the office visit, including post-discharge prediction beyond standard ADT alerts.
3. AI and automation that turn fragmented data into prioritized opportunities.
4. Predictive models that use historical claims and diagnosis/procedure similarity to identify risk.
5. A design philosophy that empowers primary care providers rather than replacing them.

## 3. Medicare Programs in the Value-Based Care Ecosystem

The business model of AI-driven patient risk platforms is defined by the specific CMS programs they participate in. Understanding these programs is essential to modeling data workflows and incentive structures.

### Key programs
- **ACO REACH** — Primary program for value-based platforms. Participants act as risk-bearing entities, sharing in financial savings and losses with provider groups. Targets Traditional Medicare beneficiaries.
- **MSSP (Medicare Shared Savings Program)** — A shared savings program where ACOs are rewarded for reducing spending below benchmarks while maintaining quality.
- **Medicare Advantage** — Separate business track for MA populations, which differ from Traditional Medicare in data availability and risk adjustment rules.
- **LEAD Model** — CMS's planned successor to ACO REACH, expected to launch in 2027. Platforms are positioning to transition into this program.

## 4. Industry Standards for Entering Patient Data After Visits

Clinical documentation after visits emphasizes completeness, accuracy, timeliness, and support for billing and medical necessity.

### Up to 10 common standards
- Record the reason for the visit and relevant history.
- Document physical findings and any prior test results.
- Include the assessment, impression, or diagnosis.
- Note the plan of care and rationale for any orders.
- Include date, signer identity, and credentials.
- Ensure the record is complete and legible.
- Make progress, response to treatment, and diagnosis changes visible over time.
- Support CPT and ICD-10 coding with the chart documentation.
- Keep amendments, corrections, and delayed entries clearly identified.
- Maintain supporting evidence such as orders, imaging, and correspondence.

## 5. How Patient Health Trends Get Recorded and Determined

Patient health trends are usually determined by combining repeated observations over time, including diagnoses, vitals, labs, medications, utilization, discharge events, and care gaps.

A trend is not usually inferred from one visit. It comes from longitudinal patterns across claims, EHR notes, ADT (Admission-Discharge-Transfer) feeds, and structured data, often with reconciliation of incomplete or delayed records. Leading platforms in this space emphasize looking beyond immediate discharge data and using historical claims to infer whether a patient is moving toward a higher-risk state.

### Key data inputs in value-based care AI workflows
- **Claims data** — primary signal for risk stratification and longitudinal trend analysis.
- **EHR data** — diagnosis codes, medications, problem lists, and notes.
- **ADT feeds** — real-time admission, discharge, and transfer events used to trigger proactive outreach and post-discharge risk prediction.
- **Care gap data** — structured quality measures used for supplemental prioritization.

## 6. How an LLM Can Assist in Patient Risk Assessment

An LLM can help by summarizing longitudinal records, extracting relevant entities from notes, grouping related concepts, and drafting short explanations of why a patient appears higher risk.

It can also normalize messy text into structured fields, compare new notes against prior history, and surface patterns that rule-based systems may miss. In value-based care workflows, the LLM should be used after reconciliation so it sees the cleanest version of the patient timeline.

## 7. Why Value-Based Care AI Is Complex

The main complexity is that healthcare data is incomplete, delayed, corrected, and spread across systems, so a final view often arrives later than the original event.

Another difficulty is that clinical meaning is contextual: one diagnosis or code may imply different risk depending on history, timing, and related findings. Medicare program rules add further complexity — Traditional Medicare and Medicare Advantage differ in how risk is adjusted, how data flows, and what benchmarks apply. That is why a strong system relies on prioritized workflows, advanced AI-driven predictive signals, and human review rather than fully automated decisions.

## 8. Learning Project Takeaway

This is a strong learning project because it mirrors the architecture and workflows used by leading value-based care AI platforms. It combines data ingestion, reconciliation, healthcare workflow logic, and AI-based recommendation generation.

A good MVP would show:
- Raw patient data ingestion from multiple sources (claims, EHR, ADT feeds).
- Reconciliation of corrected, delayed, and conflicting records.
- A clean, unified patient timeline across sources.
- LLM-generated recommendations or risk assessments based on reconciled data.
- A simple dashboard or interface for clinical review and prioritization.

This mirrors the core capabilities that platforms like Optum AI, Change Healthcare Analytics, Humana AI partnerships, and similar vendors provide to health systems managing Medicare risk-based programs.
