# Working Documentation

## Philosophy: Analysis Informs, Never Blocks

**THE USER ALWAYS DECIDES.**

| Principle | Meaning |
|-----------|---------|
| Analysis is informative | Shows risks, gaps, impacts - does NOT block |
| User decides | If they say "proceed", we proceed |
| Not bureaucracy | Better definition helps, but never creates gates |
| Historical context | SaaS products often ship incomplete features, patches on patches |
| Purpose | Help avoid repeating patterns, but as a tool, not a barrier |

**In practice:** Flag concerns → Ask user → Execute their decision

---

## Requirement Types & Folder Structure

```
docs/working_docs/
├── epics/           # Large initiatives with full business justification
├── features/        # Features linked to epics (can reference parent epic)
├── hotfixes/        # Urgent fixes for production issues
└── cases/           # Incident analysis (investigation, NOT implementation)
```

Each type has different requirements and workflows:

| Type | Purpose | Business Justification | Full Analysis | Implementation |
|------|---------|----------------------|---------------|----------------|
| **Epic** | Large initiative | MANDATORY (full) | MANDATORY | Yes |
| **Feature** | Part of an epic | Reference to epic | Simplified | Yes |
| **Hotfix** | Fix production issue | Problem-focused | Minimal | Yes |
| **Case** | Analyze incident | N/A | Investigation only | NO |

---

## 1. EPICS (`docs/working_docs/epics/`)

### Purpose
Large business initiatives that justify investment. Epics contain the full business case.

### Required Content (ALL MANDATORY)
- Business Alignment (objectives, KPIs, evidence)
- Full context and problem statement
- Complete use case analysis
- Entity states and transitions
- Slicing strategy
- Time constraints
- Testing requirements
- Definition of Done

### Workflow
```
Epic Requirement → Full Validation → Design → Tasks → Implementation
```

### Folder Structure
```
docs/working_docs/epics/multi-framework-assessment/
├── multi-framework-assessment_requirements.md    # Full business case
├── multi-framework-assessment_validation.md      # Full validation
├── multi-framework-assessment_design.md          # Architecture design
└── multi-framework-assessment_tasks.md           # Master task list
```

### Example
```markdown
# Epic: Multi-Framework Assessment

**Epic ID:** EPIC-001
**Objective:** Increase Sales / Reduce Churn
**KPIs:**
- Reduce assessment time by 40% for multi-framework companies
- Increase Professional plan upgrades by 25%

[Full requirements with all sections...]
```

---

## 2. FEATURES (`docs/working_docs/features/`)

### Purpose
Individual features that are part of an epic. Can reference the parent epic instead of duplicating information.

### Required Content
- **Reference to parent epic** (MANDATORY)
- Feature-specific requirements
- Feature-specific acceptance criteria
- Inherited from epic: business alignment, context, slicing strategy

### What Can Be Referenced (not duplicated)
| Section | In Feature | Reference Epic For |
|---------|------------|-------------------|
| Business Alignment | Reference | Full KPIs, objectives, evidence |
| Context | Brief summary | Full business context |
| Slicing | This feature's scope | Overall slicing strategy |
| States/Transitions | Feature-specific | Full entity lifecycle |
| Testing | Feature tests | Overall testing strategy |
| DoD | Feature-specific | Project-wide DoD |

### Workflow
```
Feature Requirement → Simplified Validation → Design → Tasks → Implementation
```

### Folder Structure
```
docs/working_docs/features/domain-radar-chart/
├── domain-radar-chart_requirements.md    # References EPIC-001
├── domain-radar-chart_validation.md
├── domain-radar-chart_design.md
└── domain-radar-chart_tasks.md
```

### Example
```markdown
# Feature: Domain Radar Chart Widget

**Parent Epic:** [EPIC-001: Multi-Framework Assessment](../epics/multi-framework-assessment/multi-framework-assessment_requirements.md)
**Feature Scope:** Radar chart visualization for 8 compliance domains

## Business Alignment
See parent epic for full business justification.
This feature contributes to: Better compliance visualization (Professional+ feature)

## Feature Requirements
[Feature-specific requirements only...]
```

---

## 3. HOTFIXES (`docs/working_docs/hotfixes/`)

### Purpose
Urgent fixes for production issues. Focus on solving the problem, not business justification.

### Required Content
- **Problem description** (MANDATORY)
- **Impact** (who is affected, severity)
- **Root cause** (if known)
- **Proposed solution**
- **Testing to verify fix**
- **Rollback plan**

### NOT Required
- Full business alignment (the problem IS the justification)
- Full use case analysis
- Slicing (hotfixes should be small)
- KPIs

### Workflow
```
Problem Report → Quick Analysis → Fix → Test → Deploy
```

### Folder Structure
```
docs/working_docs/hotfixes/HF-2026-001-assessment-score-error/
├── hotfix_requirements.md     # Problem + solution
├── hotfix_validation.md       # Quick validation
└── hotfix_tasks.md            # Fix steps
```

### Example
```markdown
# Hotfix: Assessment Score Calculation Error

**Hotfix ID:** HF-2026-001
**Severity:** Critical
**Reported:** 2026-01-15
**Affected:** All Professional users with multi-framework assessments

## Problem
Framework projections showing incorrect scores after domain weighting update.

## Impact
- ~50 assessments showing wrong compliance percentages
- Customer complaints escalating
- Enterprise demo scheduled for tomorrow

## Root Cause
Weight normalization not applied when calculating framework projections.

## Proposed Solution
Add weight normalization step in projection calculation.

## Testing
- Test single-framework assessment scores
- Test multi-framework assessment scores
- Verify against known correct calculations

## Rollback Plan
Revert projection calculation to previous implementation.
```

---

## 4. CASES (`docs/working_docs/cases/`)

### Purpose
**INVESTIGATION ONLY** - Analyze incidents to understand what happened. NOT for implementing solutions.

### Workflow (DIFFERENT from other types)
```
Incident Report → Investigation → Root Cause Analysis → Recommendations
                                                              ↓
                            (If fix needed) → Create Hotfix or Feature
```

### Required Content
- **Incident description**
- **Timeline of events**
- **Investigation findings**
- **Root cause analysis**
- **Recommendations** (may lead to hotfix/feature)

### NOT Included
- Implementation details
- Task lists
- Design documents
- Solution code

### Folder Structure
```
docs/working_docs/cases/CASE-2026-001-missing-gaps/
├── case_report.md              # Investigation report
└── case_recommendations.md     # What to do next
```

### Example
```markdown
# Case: Missing Compliance Gaps After Assessment

**Case ID:** CASE-2026-001
**Reported:** 2026-01-10
**Status:** Under Investigation

## Incident Description
Customer reported 15 gaps missing after completing multi-framework assessment.

## Timeline
- 2026-01-08 10:00: Assessment completed with 3 frameworks selected
- 2026-01-08 10:05: Report generated showing only 10 gaps
- 2026-01-09 09:00: Customer reports missing gaps (expected ~25 based on score)
- 2026-01-09 14:00: Investigation started

## Investigation Findings
1. Gap generation only ran for primary framework
2. Cross-framework gap mapping not triggered
3. affected_frameworks array was empty for all gaps

## Root Cause
Event handler for gap generation not subscribed to multi-framework completion event.

## Recommendations
1. **Hotfix:** Fix event subscription → Create HF-2026-002
2. **Feature:** Add gap reconciliation job → Add to EPIC-003
3. **Process:** Add gap count verification to QA checklist
```

---

## Validation by Type

### `/requirement-validate` Behavior

The command detects the type based on folder path:

| Path Contains | Type | Validation Level |
|---------------|------|------------------|
| `/epics/` | Epic | FULL (all checks) |
| `/features/` | Feature | SIMPLIFIED (check epic reference) |
| `/hotfixes/` | Hotfix | PROBLEM-FOCUSED |
| `/cases/` | Case | INVESTIGATION (no implementation) |

### Validation Differences

| Check | Epic | Feature | Hotfix | Case |
|-------|------|---------|--------|------|
| Business Alignment | Full | Reference | N/A | N/A |
| KPIs | Required | Reference | N/A | N/A |
| Use Cases | Full | Feature-specific | N/A | N/A |
| States/Transitions | Full | Feature-specific | If relevant | N/A |
| Collateral Impact | Full | Feature-specific | Quick check | N/A |
| Slicing | Required | Reference | N/A | N/A |
| Time Constraints | Full | Feature deadline | ASAP | N/A |
| Testing | Full | Feature tests | Verify fix | N/A |
| DoD | Full | Feature-specific | Fix verified | N/A |
| Root Cause | N/A | N/A | Required | Required |
| Recommendations | N/A | N/A | Rollback | Next steps |

---

## Claude Commands

### `/requirement-validate`
Validates requirement based on type (detected from path).

### `/requirement-design-solution`
Designs implementation (NOT for Cases).

### For Cases: `/case-analyze` (if created)
Investigates incident and produces recommendations.

---

## Quick Reference: Which Type to Use?

| Situation | Use |
|-----------|-----|
| "We need multi-framework compliance dashboards" | **Epic** |
| "Add domain radar chart to dashboard" | **Feature** (link to epic) |
| "Assessment scores are wrong!" | **Hotfix** |
| "Why did the report generation fail yesterday?" | **Case** |
| "Companies want export to Excel" | **Feature** or **Epic** (depending on size) |
| "The app is slow" | **Case** (investigate first) |

---

## RenfeServer-Specific Considerations

### Plan-Based Features
When documenting features, always specify:
- Which plans have access
- What content is limited/gated by plan
- Upgrade triggers for lower plans

### Multi-Framework Features
When documenting multi-framework features:
- Impact on all 8 compliance domains
- Framework projection calculations
- Cross-framework gap handling

### Compliance Metamodel
When working with metamodel features:
- Universal question mappings
- Domain-framework weight changes
- Impact on existing assessments

---

## Progress Tracking (MANDATORY)

**After completing ANY feature or epic, ALWAYS update:**

### 1. Roadmap (`docs/working_docs/roadmap.md`)
- Update epic status: `⬜` → `🚧` → `✅`
- Update progress percentages
- Update "What's Left for MVP" section
- Update "Last Updated" date

### 2. Slicing Documents (`docs/working_docs/epics/*/slicing.md`)
- Mark features as complete in the status table
- Update feature status: `⬜ Pending` → `🚧 In Progress` → `✅ Done`
- Add completion date when epic is fully done

### 3. Task Documents (`docs/working_docs/epics/*/features/*/tasks.md`)
- Check off completed acceptance criteria
- Mark final checklist when verified

### Workflow After Implementation
```
Implementation Complete
    ↓
Run Tests (pytest)
    ↓
Update tasks.md (check acceptance criteria)
    ↓
Update slicing.md (mark feature ✅)
    ↓
Update roadmap.md (update epic progress)
    ↓
Inform user of completion
```

**NEVER skip progress tracking. The user needs visibility into what's done.**
