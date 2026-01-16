# Virtual Employees

This directory contains role-based AI agents that act as virtual employees for RenfeServer. Each employee has specific expertise, responsibilities, and decision-making authority within their domain.

## Structure

```
employees/
├── csuite/          # C-Level executives
├── directors/       # Department directors (future)
├── managers/        # Team managers (future)
└── specialists/     # Domain specialists (future)
```

## How to Use

Reference an employee when you need their expertise:
- "Ask the CTO about the technical architecture"
- "Get the CMO's perspective on positioning"
- "Have the CFO review the pricing model"

## Current Employees

### C-Suite (7 executives)
| Role | Focus |
|------|-------|
| [CEO](csuite/ceo.md) | Vision, strategy, stakeholders |
| [CTO](csuite/cto.md) | Technology, architecture, engineering |
| [CFO](csuite/cfo.md) | Finance, metrics, unit economics |
| [CMO](csuite/cmo.md) | Marketing, brand, growth |
| [CPO](csuite/cpo.md) | Product strategy, roadmap, UX |
| [CLO](csuite/clo.md) | Legal, compliance, contracts |
| [CAIO](csuite/caio.md) | AI strategy, ethics, governance |

### Directors (7 directors)
| Role | Reports To | Focus |
|------|------------|-------|
| [Engineering](directors/engineering.md) | CTO | Development, delivery, quality |
| [Product](directors/product.md) | CPO | Features, specs, research |
| [Growth](directors/growth.md) | CEO | Sales, revenue, partnerships |
| [Customer Success](directors/customer-success.md) | CEO | Onboarding, retention, support |
| [Compliance](directors/compliance.md) | CLO | Regulations, content, guidance |
| [Design](directors/design.md) | CPO | UX, UI, design system |
| [People](directors/people.md) | CEO | Hiring, culture, HR |
