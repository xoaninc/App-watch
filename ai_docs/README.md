# RenfeServer AI Documentation

Complete development documentation for AI assistants working on this AI compliance self-assessment SaaS platform.

## Quick Start

**ALWAYS read these first:**
1. [Business Overview](/docs/business/overview.md) - **MANDATORY** before any task
2. [Critical Rules](architecture/critical-rules.md) - **MUST READ** before coding
3. [Agents README](agents/README.md) - Understand the development pipeline

## Virtual Employees (Role-Playing Profiles)

You can ask Claude to act as different virtual employees for domain-specific expertise. See [employees/README.md](employees/README.md) for full details.

**Usage:** "Act as the CTO" or "Ask the Director of Growth about sales strategy"

### C-Suite
| Role | Focus |
|------|-------|
| [CEO](employees/csuite/ceo.md) | Vision, strategy, stakeholders |
| [CTO](employees/csuite/cto.md) | Technology, architecture, engineering |
| [CFO](employees/csuite/cfo.md) | Finance, metrics, unit economics |
| [CMO](employees/csuite/cmo.md) | Marketing, brand, growth |
| [CPO](employees/csuite/cpo.md) | Product strategy, roadmap, UX |
| [CLO](employees/csuite/clo.md) | Legal, compliance, contracts |
| [CAIO](employees/csuite/caio.md) | AI strategy, ethics, governance |

### Directors
| Role | Reports To | Focus |
|------|------------|-------|
| [Engineering](employees/directors/engineering.md) | CTO | Development, delivery, quality |
| [Product](employees/directors/product.md) | CPO | Features, specs, research |
| [Growth](employees/directors/growth.md) | CEO | Sales, revenue, partnerships |
| [Customer Success](employees/directors/customer-success.md) | CEO | Onboarding, retention, support |
| [Compliance](employees/directors/compliance.md) | CLO | Regulations, content, guidance |
| [Design](employees/directors/design.md) | CPO | UX, UI, design system |
| [People](employees/directors/people.md) | CEO | Hiring, culture, HR |

## Documentation Index

### Business Context
- **[Business Overview](/docs/business/overview.md)** - Platform purpose, users, entities, metrics

### Development Process
- **[Agents README](agents/README.md)** - 10-agent development pipeline
- **[Development Process](/docs/development/development_process.md)** - Full workflow guide
- **[Working Documentation](working_documentation.md)** - Requirement types (Epic/Feature/Hotfix/Case)
- **[Requirement Analysis Guide](requirement_analysis_guide.md)** - How to validate requirements

### Backend Architecture
- **[Critical Rules](architecture/critical-rules.md)** - MUST READ before any implementation
- **[Architecture](architecture/architecture.md)** - DDD, Clean Architecture overview
- **[Application Layer](architecture/application-layer.md)** - CQRS patterns, Commands, Queries
- **[Infrastructure](architecture/infrastructure.md)** - Repository patterns, persistence
- **[HTTP Layer](architecture/http-layer-actions.md)** - API endpoints, controllers
- **[Code Quality](architecture/code-quality.md)** - SOLID, naming conventions

### Frontend Architecture
- **[Technical Architecture](architecture/frontend/TECHNICAL_ARCHITECTURE.md)** - React + TypeScript stack
- **[Coding Standards](architecture/frontend/CODING_STANDARDS.md)** - React/TypeScript best practices
- **[Component Library](architecture/frontend/COMPONENT_LIBRARY.md)** - shadcn/ui and custom components

### Domain Requirements
- **[Domain 1: SaaS Core](/docs/requirements/domain-1-saas-core-requirements.md)** - Organizations, Users, Billing
- **[Domain 2: Regulatory Intelligence](/docs/requirements/domain-2-regulatory-intelligence-requirements.md)** - Frameworks, Metamodel
- **[Domain 3: Assessment Engine](/docs/requirements/domain-3-assessment-engine-requirements.md)** - Assessments, Scoring
- **[Domain 4: Reporting & Analytics](/docs/requirements/domain-4-reporting-analytics-requirements.md)** - Reports, Dashboards
- **[Domain 5: Remediation & Tracking](/docs/requirements/domain-5-remediation-tracking-requirements.md)** - Tasks, Workflows

### Key Architecture Documents
- **[Technology Stack](/docs/architecture/TECHNOLOGY_STACK.md)** - Python, FastAPI, React, PostgreSQL
- **[Compliance Metamodel](/docs/architecture/architecture-compliance-metamodel.md)** - Universal domains, framework mappings
- **[Requirements Slicing](/docs/requirements/requirements-slicing.md)** - Domain overview and plan features
- **[Business Documentation](/docs/business/business-documentation.md)** - Full business context and PRD

## Claude Commands

| Command | Purpose |
|---------|---------|
| `/requirement-write` | Create requirement document |
| `/requirement-validate` | Validate requirement completeness |
| `/requirement-design` | Design technical solution |
| `/requirement-tasks` | Create implementation tasks |
| `/check-dod` | Verify definition of done |
| `/check-architecture` | Check architecture compliance |
| `/check-quality` | Check code quality |
| `/check-performance` | Check performance issues |
| `/linter` | Run linter/compile |
| `/testing` | Run and analyze tests |

## Quick Reference by Task

### Adding New Feature
1. Read: [Business Overview](/docs/business/overview.md)
2. Read: [Critical Rules](architecture/critical-rules.md) → Multi-tenant + Metamodel rules
3. Use: `/requirement-write` or `/requirement-validate`
4. Use: `/requirement-design` → Design solution
5. Use: `/requirement-tasks` → Create tasks

### Working with Compliance Metamodel
1. Read: [Compliance Metamodel](/docs/architecture/architecture-compliance-metamodel.md)
2. Read: [Domain 2](/docs/requirements/domain-2-regulatory-intelligence-requirements.md) → Universal questions
3. Understand: 8 domains, 32 subdomains, framework mappings

### Creating API Endpoint
1. Read: [HTTP Layer](architecture/http-layer-actions.md)
2. Read: [Critical Rules](architecture/critical-rules.md) → Response patterns
3. Follow: Multi-tenant queries, Plan-based gating

### Code Review
1. Use: `/check-architecture`
2. Use: `/check-quality`
3. Use: `/check-performance`
4. Use: `/linter`
5. Use: `/testing`

## File Structure

```
ai_docs/
├── README.md                       # This file - Documentation index
├── working_documentation.md        # Requirement types & workflows
├── requirement_analysis_guide.md   # AI analysis instructions
│
├── employees/                      # Virtual employee profiles (role-playing)
│   ├── README.md                   # Employee profiles overview
│   ├── csuite/                     # C-Level executives (CEO, CTO, CFO, etc.)
│   └── directors/                  # Department directors (Growth, Engineering, etc.)
│
├── agents/                         # 10 Agent definitions
│   ├── README.md                   # Agent pipeline overview
│   ├── 1. requirement_writer.md
│   ├── 2. requirement_validator.md
│   ├── 3. requirement_design_solution.md
│   ├── 4. requirement_make_tasks.md
│   ├── 5. check_definition_of_done.md
│   ├── 6. check_architecture.md
│   ├── 7. check_code_quality.md
│   ├── 8. check_performance.md
│   ├── 9. linter_compile.md
│   └── 10. testing.md
│
└── architecture/                   # Architecture guides
    ├── critical-rules.md           # MUST READ
    ├── architecture.md             # DDD overview
    ├── application-layer.md        # CQRS
    ├── infrastructure.md           # Repositories
    ├── http-layer-actions.md       # API patterns
    ├── code-quality.md             # SOLID, naming
    └── frontend/                   # Frontend architecture
        ├── TECHNICAL_ARCHITECTURE.md  # React stack
        ├── CODING_STANDARDS.md        # React best practices
        └── COMPONENT_LIBRARY.md       # Components guide

docs/
├── business/
│   ├── overview.md                 # MANDATORY - Business context
│   └── business-documentation.md   # Full PRD and business docs
├── requirements/                   # Domain requirements
│   ├── domain-1-saas-core-requirements.md
│   ├── domain-2-regulatory-intelligence-requirements.md
│   ├── domain-3-assessment-engine-requirements.md
│   ├── domain-4-reporting-analytics-requirements.md
│   ├── domain-5-remediation-tracking-requirements.md
│   └── requirements-slicing.md
├── architecture/
│   ├── TECHNOLOGY_STACK.md           # Technology decisions
│   └── architecture-compliance-metamodel.md  # Compliance metamodel
├── development/
│   └── development_process.md      # Full development workflow
└── working_docs/
    ├── epics/                      # Large initiatives
    ├── features/                   # Features linked to epics
    ├── hotfixes/                   # Urgent fixes
    └── cases/                      # Incident investigations

.claude/commands/                   # Claude slash commands
├── requirement-write.md
├── requirement-validate.md
├── requirement-design.md
├── requirement-tasks.md
├── check-dod.md
├── check-architecture.md
├── check-quality.md
├── check-performance.md
├── linter.md
└── testing.md
```

## Domain Model Overview

### Compliance Metamodel (Core Concept)

```
8 Universal Domains → 32 Subdomains → ~150 Universal Questions
                                              ↓
                                    User Responses
                                              ↓
                              Domain Scores (GOV: 85%, TRA: 72%, ...)
                                              ↓
                              Framework Projections
                              (EU AI Act: 78%, NIST: 82%, ISO: 75%)
```

### Plan-Based Feature Gating

| Plan | AI Systems | Frameworks | Questions | Gaps Shown |
|------|------------|------------|-----------|------------|
| Free | 1 | 1 | 30 | 5 |
| Starter | 3 | 2 | 60 | 10 |
| Professional | 15 | All | 150 | All |
| Enterprise | Unlimited | All + Custom | Custom | All |

## Key Commands (when code exists)

```bash
# Development
npm run dev          # Start development server
npm run build        # Build for production
npm run test         # Run tests
npm run lint         # Run linter

# Database
npm run migrate      # Run migrations
npm run seed         # Seed test data
```

---

**Note:** This documentation is optimized for AI consumption and reflects the RenfeServer AI Compliance Self-Assessment SaaS platform.
