# Operations Manager / COO

> **Tier**: Team ($129/mo) | **Connections**: Google Workspace, Slack, Notion

---

## Persona

**Marina**, 40, COO of a 100-person company with offices in two cities. She oversees finance, HR, office operations, and vendor management. She's the person everyone comes to when something breaks — from a broken AC to a missed payroll deadline to an unhappy vendor.

## The Problem

Marina's job is to make sure the company runs. But "runs" means tracking 20 different workstreams across 6 Slack channels, 10 Notion pages, and a dozen Google Sheets. She spends her mornings reading through everything to figure out what's on fire. By the time she has context, it's lunch. Afternoons are all reactive — putting out fires she found in the morning.

## How OpenClaw Solves It

Marina's agent gives her a single interface to everything operational.

### Morning Operations Briefing

```
Marina:   good morning. what needs my attention today?

Agent:    Morning! Here's your ops briefing:

          URGENT:
          1. Payroll: The February payroll sheet has 3 employees
             missing hours (from "Payroll Feb" spreadsheet). Due
             to finance by Wednesday — that's tomorrow.
             Missing: David (engineering), Sarah (marketing), new
             hire Lucas (sales, started Feb 10 — might not know
             the process).

          2. Office São Paulo: @jefferson posted in #office-sp
             yesterday at 6pm that the internet has been down
             since 4pm. No resolution yet. 12 people affected.

          NEEDS DECISION:
          3. Vendor renewal: CloudHost contract expires March 1.
             The renewal quote is in your Drive "Vendor Contracts"
             folder — they want a 15% increase ($4,200 → $4,830/mo).
             You bookmarked this for review last week.

          4. New hire onboarding: 2 people start next Monday.
             Notion "Onboarding Tracker" shows laptops ordered
             but IT setup not started.

          FYI (not urgent):
          5. The office snack budget is 20% over for February
             (from "Office Expenses" spreadsheet). Someone ordered
             premium coffee again.
          6. 4 new messages in #operations Slack since yesterday,
             all informational.
```

### Vendor Management

```
Marina:   pull up the CloudHost renewal details. What are we
          paying now and what are our options?

Agent:    From your "Vendor Contracts" folder in Drive:

          Current contract (signed March 2024):
          - $4,200/month, 12-month term
          - Includes: 10 cloud servers, 5TB storage, 24/7 support
          - Usage this year: averaging 7 servers, 2.8TB storage

          Renewal offer (in your email from Feb 5):
          - $4,830/month (+15%), same terms
          - "Market adjustment" — their words

          Things to consider:
          - You're only using 70% of the servers and 56% of storage.
            You could negotiate a smaller package.
          - A 10-server plan at the new rate costs more than what
            competitors charge for similar capacity (from the
            "Vendor Comparison" sheet you made in January).
          - Your top 3 alternatives from that sheet:
            1. HostPro: $3,600/mo for 8 servers, 3TB
            2. NovaClouds: $3,900/mo for 10 servers, 5TB
            3. Stay with CloudHost, negotiate: target $4,000/mo

          You have leverage — you're under-utilizing. Want me to
          draft a counter-offer email asking for $4,000/mo for a
          reduced 8-server package?
```

### Cross-Department Status

```
Marina:   I need a status update for the leadership meeting
          at 2pm. Hit all departments.

Agent:    Here's your cross-department status (from Notion + Sheets + Slack):

          FINANCE:
          - February burn: $182k (budget: $175k, +4% over)
          - Main variance: unplanned server migration ($8k)
          - AR outstanding: $34k (2 invoices overdue 15+ days)
          - Cash position: $2.1M (from "Cash Flow" spreadsheet)

          PEOPLE:
          - Headcount: 100 (hired 2, lost 1 this month)
          - Open roles: 4 (2 eng, 1 sales, 1 design)
          - Avg time-to-hire this quarter: 34 days (from HR Notion)
          - Employee survey results due Friday

          SALES:
          - February pipeline: $184k closed, target $200k
          - 10 business days left, $66k in "closing this week" stage
          - On track if BrightSign and Nexus close

          PRODUCT:
          - Sprint 12 in progress, 68% complete (Notion sprint board)
          - 1 sprint behind on API migration (flagged by VP Eng)
          - 2 customer-reported bugs, both P2, ETA fix: this week

          OFFICE:
          - São Paulo internet still down (from #office-sp, 14h now)
          - Curitiba office: no issues
          - 2 new hires starting Monday — onboarding behind

          TOP 3 FOR LEADERSHIP:
          1. São Paulo internet — need IT vendor escalation
          2. API migration behind — scope cut decision needed
          3. February burn 4% over — one-time or recurring?
```

## Why They Pay

$129/mo saves Marina 1.5-2 hours every morning. The morning briefing alone replaced a routine where she opened 8 browser tabs and 3 Slack channels just to understand the state of the company. The vendor analysis feature helped negotiate $2,400/year in savings on one contract. Her CEO (Ricardo) got his own agent after seeing hers in action.

## Connections Used

| Connection | How It's Used |
|---|---|
| Google Sheets | Read financials, payroll, vendor comparisons, expenses. |
| Google Drive | Read contracts, proposals, policy documents. |
| Slack | Read #operations, #office-sp, #office-cwb, #leadership. |
| Notion | Read departmental dashboards, onboarding tracker, sprint boards. |
