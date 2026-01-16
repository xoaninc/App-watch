# Requirement Analysis Guide for AI

Instructions for AI to analyze and validate requirement documents for the RenfeServer platform.

**IMPORTANT**: This is NOT a strict template validation. AI must verify that the requirement contains the necessary **content**, regardless of the exact format or structure used.

---

## Philosophy: Analysis Informs, Never Blocks

**THE USER ALWAYS DECIDES.** This analysis framework is informative, not bureaucratic.

### Core Principles

1. **Analysis identifies risks and gaps - it does NOT block development**
   - Show risks, impacts, missing information
   - The user decides whether to proceed anyway
   - If they say "proceed", we proceed

2. **Better upfront definition helps, but never creates bureaucracy**
   - If more analysis adds value → do it
   - If the user wants to move fast → move fast
   - Document concerns, then execute

3. **Context: Why this analysis matters**
   SaaS products often suffer from:
   - Features not fully developed ("patches on patches")
   - Shipping features nobody uses
   - Incomplete implementations

   This analysis helps avoid repeating those patterns, but it's a **tool, not a gate**.

### What This Means in Practice

| Situation | AI Response |
|-----------|-------------|
| Missing KPIs | Flag it, ask if they want to proceed anyway |
| Incomplete states | Document the gap, continue if user says so |
| High risk identified | Show the risk clearly, let user decide |
| User says "just do it" | Document concerns briefly, then execute |

**NEVER say:** "Cannot proceed until X is defined"
**ALWAYS say:** "X is missing/risky. Do you want to proceed anyway or define it first?"

---

## STEP 0: Detect Requirement Type (FIRST)

**Before any analysis, detect the requirement type from the file path:**

| Path Contains | Type | Validation Mode |
|---------------|------|-----------------|
| `/epics/` | Epic | FULL validation |
| `/features/` | Feature | SIMPLIFIED (check epic reference) |
| `/hotfixes/` | Hotfix | PROBLEM-FOCUSED |
| `/cases/` | Case | INVESTIGATION ONLY |

### Validation Rules by Type

#### EPIC (Full Validation)
- All steps apply
- Business alignment MANDATORY with full evidence
- KPIs MANDATORY (or Experiment Definition - see bypass below)
- Full use case analysis
- Full state/transition analysis
- Slicing analysis required

**Experimentation Bypass:** If the requirement is marked as an experiment, KPIs can be replaced with:
- Hypothesis (what we believe will happen)
- Test method (how we'll validate)
- Success metrics (what tells us it works)
- Investment limit (max effort before validation)
- Decision criteria (what happens if success/failure)

#### FEATURE (Simplified Validation)
- **MUST have parent epic reference**
- Business alignment: verify reference to epic exists
- KPIs: reference epic's KPIs
- Use cases: feature-specific only
- States: feature-specific subset
- Slicing: verify this is part of epic's slice

#### HOTFIX (Problem-Focused Validation)
- Skip: Business alignment, KPIs, slicing, full use cases
- **REQUIRED:** Problem description, Impact, Root cause
- **REQUIRED:** Proposed solution, Testing, Rollback plan
- Focus: Will this fix the problem? What could go wrong?

#### CASE (Investigation Only - NO Implementation)
- **THIS IS NOT AN IMPLEMENTATION REQUEST**
- Skip all implementation-related checks
- **REQUIRED:** Incident description, Timeline, Findings
- **REQUIRED:** Root cause analysis, Recommendations
- Output: Investigation report, NOT design/tasks
- If fix needed → recommend creating Hotfix or Feature

---

## Analysis Objective

When analyzing a requirement, AI must ensure:
1. All necessary information is present (content over form)
2. No obvious use cases are missing (Epics/Features only)
3. Entity states and transitions are defined (Epics/Features only)
4. The requirement is complete enough to implement (NOT for Cases)

---

## Step-by-Step Analysis Process

**Note:** Steps below apply to EPICS. For Features/Hotfixes/Cases, see type-specific rules above.

### Step 1: Identify Entities

- What is the main entity/resource being acted upon?
- Are there secondary entities involved?
- Example: "Add multi-framework assessment" → Entity = Assessment, Framework, ComplianceDomain

### Step 2: Apply CRUD Check

For each entity, verify if ALL CRUD operations are addressed or explicitly excluded:

| Operation | Question |
|-----------|----------|
| **Create** | Is there a way to create this entity? |
| **Read** | Is there a way to view this entity? |
| **Update** | Is there a way to modify this entity? |
| **Delete** | Is there a way to remove this entity? |
| **List** | Is there a way to see all entities? |

### Step 3: Apply Status & State Analysis (MANDATORY)

**Almost every business entity has a status.** At minimum: "exists" vs "deleted".

For EVERY entity, AI MUST verify:

| Check | Question |
|-------|----------|
| Initial status | What status does the entity have when created? |
| All statuses | What are ALL possible statuses? |
| Transitions | What transitions are valid between statuses? |
| Triggers | What triggers each transition? (user action, system event, time) |
| Conditions | What conditions must be met for each transition? |
| Side effects | What happens when transition occurs? (notifications, cascades) |
| Delete strategy | Is delete hard (DB removal) or soft (status change)? |
| Restore | Can deleted entities be restored? |

#### RenfeServer Common Status Patterns

| Entity Type | Common Statuses |
|-------------|-----------------|
| Assessment | draft, in_progress, completed, expired, archived |
| ComplianceGap | identified, acknowledged, in_progress, resolved, accepted |
| RemediationTask | open, in_progress, pending_review, resolved, wont_fix |
| Report | pending, generating, completed, failed, expired |
| Organization | trial, active, past_due, cancelled, suspended |

### Step 4: Apply Use Case Pattern Detection

Check for missing use cases using these patterns:

#### CRUD Pattern
- Create, Read, Update, Delete, List
- Filter, Search, Sort, Paginate
- Export, Import

#### Lifecycle Pattern
- What happens at each stage?
- Who can perform actions at each stage?
- Are there time-based transitions?

#### State Machine Pattern
- All transitions covered?
- Invalid transitions blocked?
- History/audit of transitions?

#### Bulk Operations Pattern
- Can operations be done in bulk?
- What about bulk import/export?
- How are bulk errors handled?

#### Reporting Pattern
- Who needs visibility into this data?
- What aggregations are needed?
- Historical data requirements?

#### Plan-Based Access Pattern (RenfeServer-specific)
- Which plans have access?
- What content is gated/limited?
- What triggers upgrade prompts?

### Step 5: Inverse Operation Check

For every action, verify its opposite is considered:

| Action | Inverse |
|--------|---------|
| Add | Remove |
| Enable | Disable |
| Assign | Unassign |
| Publish | Unpublish |
| Archive | Restore |
| Approve | Reject |
| Start | Cancel |
| Complete | Reopen |

### Step 6: User Journey Check

- **Preconditions**: What must be true before the action?
- **Postconditions**: What must be true after success?
- **Error recovery**: What if something fails mid-process?
- **Undo/cancel**: Can the user cancel or undo?

### Step 7: Collateral Impact Analysis (MANDATORY)

Analyze impact on existing functionality:

| Category | Questions |
|----------|-----------|
| **Entities** | Which existing entities are affected? |
| **Data** | Shared data dependencies? Schema changes? |
| **Business Rules** | Do existing rules change? New validations? |
| **Workflows** | Impact on existing user flows? |
| **Integrations** | External systems affected? (Stripe, Jira) |
| **Reports** | Dashboard/report changes needed? |
| **Permissions** | New roles/permissions required? |
| **Breaking Changes** | Backward compatibility issues? |
| **Plans** | Impact on plan feature matrix? |
| **Metamodel** | Impact on domains, questions, mappings? |

### Step 8: Requirement Slicing Analysis

| Check | Question |
|-------|----------|
| Size | Is this requirement appropriately sized? |
| Independence | Can slices be developed/deployed independently? |
| Value | Does each slice deliver value? |
| Dependencies | Are there hidden dependencies between slices? |
| Out of Scope | Is information needed from out-of-scope items? |

#### Red Flags
- Slice depends on another slice to be useful
- "Phase 2" contains core functionality
- Out of scope items block understanding of in-scope items

### Step 9: Business Alignment Check (MANDATORY for Epics)

| Check | Question |
|-------|----------|
| Objective | Which company objective? (Revenue / Churn / Sales) |
| Contribution | How does this contribute to the objective? |
| KPIs | Are measurable targets defined? |
| Evidence | Is there objective data supporting need? |

#### Red Flags for Business Alignment
- Subjective justifications ("users would love this")
- No revenue/cost impact estimated
- No customer evidence
- "Competitors have it" without analysis

### Step 10: Time Constraints Check

| Check | Question |
|-------|----------|
| Deadline | Is there a hard deadline? |
| Reason | Why this deadline? (event, contract, season) |
| Realistic | Is scope achievable in timeframe? |
| Buffer | Time for testing/training included? |
| Fallback | Plan if deadline is missed? |

### Step 11: Testing Requirements Check

| Check | Question |
|-------|----------|
| Test types | Unit, Integration, E2E, UAT defined? |
| Critical scenarios | Happy path and edge cases identified? |
| Test data | What test data is needed? |
| Regression | What existing tests might be affected? |

### Step 12: Definition of Done Check

| Check | Question |
|-------|----------|
| Acceptance criteria | Are they testable and specific? |
| Quality gates | What must pass before release? |
| Sign-off | Who approves completion? |
| Training | Is user training needed? |

---

## Output: Analysis Checklist

After analysis, produce:

```markdown
# Requirement Analysis Checklist

## Business Alignment
- [ ] Objective identified
- [ ] Contribution explained
- [ ] KPIs defined (or Experiment defined)
- [ ] Evidence provided (or Experiment justification)

## Entities & Operations
- [ ] All entities identified
- [ ] CRUD coverage verified
- [ ] States/transitions defined
- [ ] Delete strategy specified

## Use Cases
- [ ] All patterns checked
- [ ] Inverse operations considered
- [ ] Bulk operations considered
- [ ] Plan-based access defined

## Impact
- [ ] Collateral impact analyzed
- [ ] Breaking changes identified
- [ ] Integration impact assessed
- [ ] Metamodel impact assessed

## Constraints
- [ ] Time constraints documented
- [ ] Testing requirements defined
- [ ] Definition of Done specified

## Gaps Identified
| Gap | Severity | Recommendation |
|-----|----------|----------------|
| [gap] | Critical/High/Medium/Low | [action] |

## Questions for Stakeholder
1. [question]
2. [question]
```

---

## Anti-Patterns to Flag

| Anti-Pattern | Why It's Bad | How to Flag |
|--------------|--------------|-------------|
| "Customers are asking for it" | Subjective, no evidence | Request specific customer names/tickets |
| "Users would love this" | Assumption without validation | Request user research or experiment plan |
| Missing states | Incomplete implementation | List all expected states, ask for confirmation |
| No delete strategy | Data management issues | Ask: hard delete, soft delete, or archive? |
| Huge scope without slicing | Risk of never finishing | Suggest MVP and follow-up phases |
| No deadline mentioned | May deprioritize forever | Ask: when is this needed? Why? |
| No plan consideration | Feature gating issues | Ask: which plans? What's limited? |
| Metamodel changes without impact | Data integrity risk | Ask: how does this affect existing assessments? |

---

## RenfeServer-Specific Checks

### Multi-Framework Assessment Features
- [ ] Impact on domain score calculation
- [ ] Impact on framework projection calculation
- [ ] Cross-framework gap handling
- [ ] Question mapping changes

### Plan Feature Matrix
- [ ] Which plans have access?
- [ ] What content is limited by plan?
- [ ] What triggers upgrade prompts?
- [ ] Report page/content limits defined?

### Stripe/Billing Integration
- [ ] Subscription changes handled?
- [ ] Usage tracking affected?
- [ ] Invoice line items affected?
