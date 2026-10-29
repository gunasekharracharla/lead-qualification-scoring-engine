# Commercial Product PRD

## AI Lead Qualification & Scoring Engine

**Document purpose:** Upload this PRD to ChatGPT or another planning assistant to get a project-specific assessment, prioritized next steps, and implementation plan.  
**Document status:** Draft for product discovery and pilot planning  
**Prepared:** 29 October 2026  
**Product stage:** Working prototype / early MVP; commercial readiness has not been independently certified  
**Decision owner:** Product owner / project lead

> **Do not upload `.env` files, API keys, database files, real customer lead data, or other credentials with this document.** Use anonymized examples only. A provider key was exposed in an earlier conversation; revoke and rotate it before further use.

---

## 1. Executive summary

The product helps B2B sales teams qualify and prioritize leads. It combines AI interpretation of unstructured lead information with deterministic ICP checks and weighted scoring. It also generates recommendations and a sales action plan.

The repository already contains more than a scoring-only demo: it has a FastAPI application, a browser UI, SQLite/SQLAlchemy persistence, lead qualification and CRUD API routes, configurable ICP/scoring/offer rules, AI-provider configuration, website research, and sales-plan generation. The website research service currently makes a bounded, best-effort fetch of a company homepage and up to two relevant pages on the same site, and stores the summary and source URLs with the qualification result.

The commercial opportunity is to turn this prototype into a focused sales workflow product—not to add AI features indiscriminately. The first release should validate whether one specific sales team can use the product to qualify leads more consistently, understand the reasons behind results, and take action in its existing workflow.

The largest unknowns are the first target customer/use case, evidence of business value, operational/security readiness, and which CRM integration matters most. These must be resolved with customer discovery and a design partner before expanding scope.

## 2. Product vision

**Vision:** Help B2B revenue teams decide which leads deserve attention, understand why, and act on that decision using clear evidence and a consistent workflow.

**Proposed positioning:** Explainable B2B lead qualification and prioritization for sales teams.

**Product promise to validate:** Reduce time spent reviewing low-fit leads and make qualification decisions more consistent, while keeping the reasoning visible and reviewable by a human.

Do not claim increased revenue, conversion uplift, or prediction accuracy until a pilot measures those outcomes against a defined baseline.

## 3. Product context and current-state snapshot

This snapshot is based on a limited inspection of the project files, not a complete security, quality, or production-readiness audit.

### Observed in the project

- FastAPI serves both API routes and static frontend content.
- A lead qualification endpoint accepts lead and company fields and returns a structured qualification result.
- Qualification combines AI assessment with deterministic ICP evaluation, weighted scoring, classification, offer/next-action recommendation, and a sales action plan.
- Scoring weights and HOT/WARM/COLD thresholds are stored in JSON rule files.
- Website research fetches a bounded number of same-site HTML pages, extracts text, and retains source URLs. It is best-effort and can be unavailable for some websites.
- The system stores leads and qualification outputs with SQLAlchemy; the default configuration uses SQLite.
- The UI includes a lead form, qualification result area, recent-lead list, summary counts, and light/dark theme control.
- Automated tests exist for API behavior and multiple scoring/analysis services.
- AI provider and database configuration are environment-based.

### Not verified or not observed in the inspected files

Treat these as open questions, not confirmed absences:

- Authentication, workspace/tenant isolation, and role-based authorization.
- Production-grade deployment, monitoring, backups, restore testing, and incident response.
- CRM integration, CSV import/export, user invitations, assignment workflow, billing, and customer onboarding.
- Scoring-rule administration, approval, version history, and end-user override/audit workflow.
- Privacy, retention, deletion, consent/legal basis, and external provider data-handling review.
- Whether current tests cover production security, concurrent workloads, and all integration failure paths.

These are launch-readiness questions to verify before accepting production customer data.

## 4. Problem statement

B2B sales teams receive leads with variable completeness and quality. Reps may apply qualification criteria inconsistently, spend time on prospects that do not match the target customer profile, and lack useful context for what to do next. Managers may not know whether qualification decisions are consistent or whether the process improves downstream outcomes.

The product should help answer:

1. Does this lead fit the agreed ICP?
2. What information and evidence support the result?
3. What is the recommended next action?
4. What information is missing or uncertain?
5. Did the recommendation help the team progress the lead?

## 5. Target users and initial market hypothesis

### Primary users

- **Sales representative / SDR:** Reviews leads, prioritizes follow-up, and needs actionable context.
- **Sales manager / RevOps:** Defines qualification policy, monitors consistency, and reviews team outcomes.
- **Workspace administrator:** Manages access, configuration, and integrations.

### Initial market hypothesis

Start with one B2B sales team that:

- Has a defined ICP and a repeatable qualification workflow.
- Receives enough inbound or prospecting leads to make prioritization valuable.
- Already uses a CRM or another system of record.
- Can provide a design partner and anonymized or permissioned pilot data.

B2B SaaS is a possible first segment, not a validated decision. Confirm segment and workflow through interviews before locking the roadmap.

## 6. Goals and non-goals

### Goals for the first commercial pilot

- Make qualification results understandable, traceable, and reviewable.
- Help a pilot team process leads using a repeatable workflow.
- Measure usage, time-to-qualification, override reasons, and downstream outcomes where available.
- Establish secure customer-data boundaries and operational basics before production use.
- Integrate with one CRM only if validated as a pilot requirement.

### Non-goals for the first release

- Replacing a CRM or sales engagement platform.
- Sending automated outreach or making autonomous sales decisions.
- Supporting every CRM, enrichment provider, and industry at launch.
- Building a general-purpose crawler or unrestricted scraping system.
- Claiming predictive conversion performance without adequate outcome data.
- Enterprise SSO, complex workflow builders, or forecasting unless a committed launch customer requires them.

## 7. MVP user journeys

### Journey A: Review one lead

1. User enters or imports a lead.
2. Product validates inputs and indicates missing information.
3. Product performs qualification and, when available, website research.
4. User sees the ICP decision, score, classification, score breakdown, source information, limitations, and recommended next step.
5. User records a workflow action or feedback/override with a reason.
6. User can revisit the lead and its qualification history.

### Journey B: Pilot team processes leads

1. Admin sets up the workspace and invites the pilot team.
2. Team imports a small, agreed dataset or connects the first supported source.
3. Reps review, filter, assign, and update lead statuses.
4. Manager reviews qualification distribution, missing-data patterns, overrides, and outcomes.
5. Product owner and pilot users review results on a regular cadence and decide what to improve.

### Journey C: CRM handoff (conditional MVP scope)

1. Admin authorizes the selected CRM integration.
2. Admin maps supported fields and tests with a safe sample record.
3. Product syncs the agreed qualification fields and status.
4. User can see sync state and safely retry failures.

Implement this journey only after the design partner confirms which CRM and workflow matter most.

## 8. Functional requirements

| ID | Priority | Requirement | Acceptance criteria |
|---|---|---|---|
| FR-01 | P0 | Secure user and workspace access | Protected operations require authentication. A user cannot read or modify another workspace's records. Tests cover unauthorized and cross-workspace access. |
| FR-02 | P0 | Lead management | Authorized users can create, view, edit, search, filter, and update lead workflow status. Validation errors explain how to correct input. |
| FR-03 | P0 | Explainable qualification | Each result shows score/classification, ICP fit, score components, matched/failed criteria, known missing data, recommendation, and source context where applicable. Displayed values agree with the stored result. |
| FR-04 | P0 | Qualification history | Each run retains its timestamp, inputs or safe input reference, output, and scoring/rules version. Requalification does not silently erase the previous result. |
| FR-05 | P1 | Human feedback and override | A permitted user can record an override or feedback with a reason. The original automated result remains available and the action is attributable and timestamped. |
| FR-06 | P1 | CSV intake | User can preview an import, see row-level validation issues, confirm import, and receive a created/updated/rejected summary. Duplicate behavior is explicit. |
| FR-07 | P1 | Team workflow | User can assign an owner and update a lead status. Manager can filter the team's work by status, owner, and classification. |
| FR-08 | P1 | Dashboard | Manager can see lead volume and classification, data completeness, and pilot outcomes over a defined period. Metric definitions are documented. |
| FR-09 | P1 | Source and freshness | Website-researched or externally enriched information is identified as sourced, with source URLs and retrieval time when available. It is distinguishable from user input and AI interpretation. |
| FR-10 | Conditional P1 | One CRM integration | Selected CRM supports authorization, field mapping, test sync, visible status/errors, and retry behavior that avoids creating duplicates for the supported flow. |
| FR-11 | P1 | User feedback loop | Users can mark recommendations helpful/not helpful and provide structured override reasons; these signals are available for product analysis. |
| FR-12 | P1 | Admin configuration | Authorized admins can review scoring configuration. Changes are validated, versioned, and attributable before affecting new qualifications. |
| FR-13 | P1 | Data lifecycle | Admin/operator can execute documented data export/deletion processes consistent with retention policy and applicable obligations. |

### Product handling principles

- Preserve separation between deterministic score and AI-generated narrative.
- Do not describe a website-derived fact as verified if it is only an extracted or inferred detail.
- Show when website research could not be completed; do not imply that every company was researched.
- Do not silently overwrite user-provided data with sourced data.
- Keep original qualification results when rules or lead inputs change.
- Treat AI output as assistance, not as the final authority for a consequential sales decision.

## 9. Non-functional requirements

Set final service objectives with the team and pilot customers. Suggested beta starting points:

- **Security:** encrypted transport; secrets kept outside source code; least-privilege access; reviewed authorization and tenant boundaries.
- **Reliability:** documented service-health monitoring and safe failure behavior for AI, enrichment, and CRM dependencies.
- **Data protection:** documented collection purpose, retention, deletion, backup, and restore procedure.
- **Observability:** track API errors, latency, job failures, and sync outcomes without logging secrets or unnecessary lead details.
- **Performance:** measure baseline latency. Synchronous qualification should have an agreed p95 target; slow external enrichment should be asynchronous if it breaches the target.
- **Accessibility:** core workflows should be keyboard operable with clear labels, focus, contrast, and validation messages.
- **Maintainability:** CI should run focused tests for scoring, authorization, lead updates, import behavior, and integration retries.
- **Portability:** use SQLite for local development if appropriate; verify production database requirements and migration strategy before launch.

## 10. Data and integration requirements

### Core records anticipated

- Workspace, user, membership/role.
- Lead and company/contact details.
- Qualification result and score breakdown.
- Scoring/rules version.
- Source/enrichment record and retrieval timestamp.
- Workflow status, assignment, user feedback/override.
- CRM integration configuration and sync event.
- Audit event for administrative or consequential changes.

### Initial lead fields

Current code already supports name, company, job title, country, industry, company size, website, LinkedIn URL, pain point, buying signal, optional custom offer, and recent activity. The commercial product should additionally consider source, owner, lifecycle status, workspace, and timestamps/provenance where needed.

### Website research constraints

The current research service is best-effort website text extraction, not comprehensive company enrichment. It fetches up to three same-site HTML pages within bounded time/response limits and records source URLs when successful. It may miss JavaScript-rendered content, inaccessible pages, or data not published on the site. LinkedIn profile content is not fetched by the current service; any URL-derived hint must not be presented as verified profile data.

Before commercial use, review the approach for applicable law, website terms, robots/access expectations, provider policies, privacy impact, and user disclosure. Do not expand scraping scope without that review.

## 11. Success metrics

Collect a baseline during discovery or the first pilot. Do not invent targets before learning the baseline.

### Product adoption

- Weekly active users / invited pilot users.
- Percentage of eligible leads processed through the product.
- Time from lead arrival to qualification and first action.

### Trust and quality

- User-reported understanding of score explanations.
- Override rate and categorized override reasons.
- Required-field completeness and source/provenance coverage.
- Qualification agreement with manager-reviewed outcomes.

### Business outcomes

- Conversion to the next agreed sales stage by score band.
- Time spent per lead or time redirected to high-fit leads.
- Comparison with an agreed pre-pilot or control cohort, where feasible.

### Operations

- Qualification success/error rate.
- Website research success and timeout rate.
- CRM sync success, retry, and duplicate rate (if CRM is in scope).
- API latency and availability.

Interpret results by cohort and lead source. A high score or high HOT count alone is not evidence of product success.

## 12. Six-month delivery roadmap

This is a planning hypothesis for a focused team, not a guaranteed delivery date. A lean team of roughly 4–6 FTE-equivalent working consistently is assumed. A solo/part-time build, unresolved customer discovery, or complex integrations will extend it.

| Phase | Timing | Main outcomes | Exit gate |
|---|---:|---|---|
| 0. Discovery and scope | Weeks 1–2 | Interview target users; choose first segment and workflow; identify design partner; baseline metrics; confirm CRM demand | One target use case and pilot hypothesis approved |
| 1. Product foundation | Weeks 3–8 | Verify and implement identity/access model, secure workspace boundaries, core lead workflow, clear score explanations, error handling, CI/deployment basics | Internal team can operate without direct database edits; critical access and workflow tests pass |
| 2. Private beta | Weeks 9–14 | Onboard pilot team; lead intake/import as needed; history, statuses, ownership, feedback, basic reporting; measure usage | Pilot users complete workflow and provide repeatable feedback |
| 3. Workflow integration | Weeks 15–20 | One validated CRM integration and/or bounded enrichment improvement, with provenance and failure visibility | End-to-end test in a non-production CRM tenant; recovery/retry tested |
| 4. Launch readiness | Weeks 21–24 | Reliability/security review, data lifecycle procedures, user help, support runbook, pricing test, launch decision | No unresolved critical launch blocker; restore and support procedures tested; pilot evidence supports paid beta or scope revision |

### Scope guardrails

- Choose one ICP segment, one primary workflow, and at most one CRM for first release.
- Prefer CSV/API ingestion before broad connector development if pilot needs are uncertain.
- Do not train a predictive model until the team has enough reliable, permissioned outcome data.
- Defer billing automation, SSO, multiple CRMs, complex forecasting, and custom workflow builders unless a launch customer makes one essential.
- Reserve capacity for customer feedback, security, testing, and operational work; do not allocate all capacity to features.

## 13. Jira-style epic outline

### E1 — Secure identity and workspace foundation

- As a user, I can sign in and sign out securely.
- As an admin, I can invite and deactivate workspace members.
- As a workspace member, I can access only my workspace's data.
- As an operator, I can rotate secrets without changing application source.

### E2 — Lead intake and workflow

- As a rep, I can create and edit a lead with validation.
- As a user, I can search and filter the team's leads.
- As a manager, I can assign owners and track lead status.
- As a user, I can import a CSV preview and correct row-level errors.
- As a user, I can export the leads I am authorized to access.

### E3 — Qualification trust and feedback

- As a rep, I can understand why the lead received its score.
- As a rep, I can distinguish supplied data, website research, and AI interpretation.
- As a manager, I can identify the rules version behind each qualification.
- As a rep, I can submit a reasoned override without deleting the original result.
- As a product owner, I can analyze structured feedback and downstream outcomes.

### E4 — Reporting and pilot measurement

- As a manager, I can see lead volume and qualification distribution over time.
- As a product owner, I can measure workflow adoption and time to action.
- As a manager, I can compare score bands with agreed funnel outcomes.

### E5 — First CRM integration (conditional)

- As an admin, I can authorize the selected CRM.
- As an admin, I can map supported fields and test the connection.
- As a rep, I can see sync status and safe error details.
- As an operator, I can retry a failed sync without duplicating supported records.

### E6 — Enrichment provenance and data lifecycle

- As a user, I can see whether company information came from website research or manual input.
- As a user, I can see sources and retrieval freshness when available.
- As an admin, I can request an export or deletion according to documented policy.
- As an operator, I can review provider failure without exposing private data in logs.

### E7 — Operations and launch readiness

- As an operator, I can monitor health and critical errors.
- As an engineer, I can run automated tests for permissions and critical workflows.
- As an operator, I can restore service from a tested backup.
- As support, I can diagnose a failed import or sync from a runbook.

## 14. Risks and mitigations

| Risk | Impact | Mitigation / decision |
|---|---|---|
| Weak evidence of customer need | Product built without willingness to adopt/pay | Interview users and secure a design partner before expanding scope |
| Sales users do not trust AI output | Low adoption or inappropriate decisions | Show evidence, limits, missing inputs, score components, version, and human override |
| Poor or stale lead data | Misleading qualification | Surface completeness, source, and freshness; let users correct fields |
| Tenant/access-control gap | Customer data exposure | Verify security architecture and test workspace boundaries before real customer data |
| Scraping/provider restrictions | Legal, contractual, or operational risk | Review sources, provider terms, privacy obligations, and permitted use before launch |
| CRM scope expands | Schedule slips and brittle integrations | Select one CRM from pilot evidence; define supported fields and flows |
| AI/provider outage or cost | Delayed/expensive qualification | Define fallback, retries, cost/usage tracking, provider limits, and user-visible status |
| Unproven ROI claims | Commercial and trust risk | Establish baseline and report measured pilot results with caveats |
| Solo/part-time capacity | Roadmap exceeds six months | Reduce scope and deliver one workflow before additional integrations/features |

## 15. Open decisions for discovery

Do not treat these as settled until validated:

1. Who is the first paying customer persona and industry?
2. Is the first workflow inbound lead triage, outbound prospect prioritization, or another use case?
3. Which CRM is used by the design partner, and is integration mandatory for the pilot?
4. What does “qualified” mean for that customer, and who owns the ICP rules?
5. What lead volume, accuracy, latency, and price would make the product valuable?
6. Which website research/enrichment sources are acceptable to the customer and permitted for the product?
7. What customer data can be used to evaluate outcomes, and for how long may it be retained?
8. What is the initial operating model: local/internal tool, hosted private beta, or multi-tenant SaaS?
9. What human review is required before a recommendation changes sales treatment?
10. Which metrics are available from the customer's CRM to measure business impact?

## 16. Commercial MVP launch checklist

### Customer validation

- [ ] First segment and workflow selected using interview evidence.
- [ ] Design partner and pilot users identified.
- [ ] Pilot goals, baseline, data access, and review cadence agreed.
- [ ] Product language and limitations reviewed with pilot users.

### Product

- [ ] Core workflow works from lead intake through next action.
- [ ] Score explanation is understandable and matches the stored result.
- [ ] Missing, uncertain, and website-derived data is clearly labeled.
- [ ] Qualification history and user feedback are retained appropriately.
- [ ] CSV behavior, duplicate handling, and error messages are tested if import is in scope.
- [ ] One CRM is tested end-to-end if integration is launch-critical.

### Security and operations

- [ ] Exposed provider credentials revoked and rotated.
- [ ] No secrets or real customer data are included in PRD, screenshots, logs, or demos.
- [ ] Authentication, authorization, and workspace isolation reviewed and tested.
- [ ] Production database, migrations, backup, and restore process tested.
- [ ] Privacy, retention, deletion, and data-processing documentation prepared.
- [ ] AI, hosting, and enrichment providers reviewed for data handling and contractual fit.
- [ ] Monitoring, incident escalation, and support runbooks are in place.

### Go-to-market

- [ ] Pricing hypothesis tested with target buyers.
- [ ] Onboarding instructions and product limitations documented.
- [ ] Support contact and response expectations agreed for the beta.
- [ ] Launch decision based on pilot evidence and blocker review.
- [ ] No conversion or accuracy claims published without evidence.

## 17. Stakeholder / investor presentation outline

1. Product and one-sentence value proposition.
2. Customer problem with interview evidence.
3. Existing qualification workflow and where it fails.
4. Product demo: evidence → score → next action → human review.
5. Initial customer segment and why the first wedge is focused.
6. Differentiation supported by current capabilities and validated feedback.
7. Pilot design, measured usage, and outcome data (clearly label what is not yet measured).
8. Business model hypothesis and buyer validation status.
9. Go-to-market and onboarding approach.
10. Six-month roadmap and milestone gates.
11. Key risks: data quality, trust, CRM, privacy, security, and adoption.
12. Team, required resources, and specific stakeholder ask.

## 18. Prompt to use with ChatGPT

Upload this PRD and, if you want a code-aware assessment, also upload a **sanitized** project overview such as README, folder/file listing, relevant source files, and test summary. Do not upload `.env`, keys, database files, real lead records, or customer data.

Then paste this prompt:

> Act as a senior B2B SaaS product manager and pragmatic technical delivery lead. Analyze the attached PRD and project context for the AI Lead Qualification & Scoring Engine.
>
> First, distinguish facts verified in the material from assumptions, missing evidence, and recommendations. Do not claim that a feature exists unless the files show it. Do not invent customers, traction, conversion results, legal compliance, security certification, or market size.
>
> Give me:
> 1. A concise product-readiness assessment and the five biggest gaps.
> 2. The recommended first customer segment and use case, including what evidence is still needed to choose it.
> 3. A prioritized next-30-days action plan with deliverables, owners/roles, dependencies, and acceptance criteria.
> 4. A revised MVP scope divided into launch blockers, pilot requirements, and post-launch items.
> 5. The top risks and questions I must resolve before accepting real customer data.
> 6. A realistic timeline for my stated team size and weekly hours. If I have not supplied them, state your assumptions and provide solo/part-time and small-team ranges.
> 7. Specific user interviews and pilot measures needed to test willingness to use/pay and measurable business value.
> 8. The next five engineering tasks in dependency order, with tests or validation for each.
>
> Keep recommendations specific to the attached product. Flag contradictions between the PRD and code. Ask only the highest-impact follow-up questions; do not recommend building every feature in the roadmap at once.

---

**End of PRD**
