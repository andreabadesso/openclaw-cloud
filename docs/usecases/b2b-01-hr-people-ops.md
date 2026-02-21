# HR & People Operations

> **Tier**: Team ($129/mo) | **Connections**: Google Workspace, Slack, Notion

---

## Persona

**Fernanda**, 38, Head of People at a 120-person tech company. Her team is just her and one junior HR coordinator. They handle hiring, onboarding, employee questions, performance reviews, and compliance. Everything lives in Google Drive and Notion.

## The Problem

Fernanda answers the same 30 questions every week: "When do I get paid?", "How many vacation days do I have left?", "What's the policy on remote work?", "How do I expense something?". The answers are all in the employee handbook (a 40-page Google Doc) that nobody reads. She also spends entire weeks every quarter preparing performance review packets — pulling self-assessments from forms, manager feedback from Notion, and assembling them into review docs.

## How OpenClaw Solves It

Fernanda deploys the agent in a shared Telegram group for the company. Employees message it directly for HR questions. She uses it privately for the heavy analytical work.

### Employee Self-Service

```
Employee:  how many vacation days do I have? I want to take
           a week off in March

Agent:     From the employee handbook:
           Full-time employees get 20 vacation days per year.
           You need to request time off at least 2 weeks in
           advance for periods longer than 3 days.

           I don't have access to individual vacation balances —
           that's in the HR system. But you can check yours at
           [company HR portal link] or ask Fernanda directly.

           Want me to help you draft the time-off request email?
```

```
Employee:  whats the reimbursement policy for conferences?

Agent:     From the Employee Handbook (section "Professional Development"):

           The company covers up to R$3,000 per year per employee
           for conferences, workshops, and courses. This includes:
           - Registration/ticket
           - Travel (economy flights, standard hotel)
           - Meals (up to R$80/day)

           To get reimbursed:
           1. Get manager approval BEFORE the event
           2. Keep all receipts
           3. Submit via the expense form within 30 days
           4. Reimbursement hits your next paycheck

           The expense form is here: [link from handbook]

           Note: international conferences need VP approval
           (not just your direct manager).
```

### Performance Review Prep

```
Fernanda:  I need to prepare the Q4 review packet for the
           product team (8 people). Pull the self-assessments
           from the google form responses sheet, and the manager
           notes from the "Q4 Reviews" notion page.

Agent:     Assembled review data for 8 product team members:

           COMPLETE (self-assessment + manager notes):
           1. Ana Costa — Self: "exceeded in shipping 3 features
              ahead of schedule." Manager (Rafael): "Strong
              quarter. Promoted to Senior — well deserved."
           2. Bruno Lima — Self: "focused on tech debt reduction."
              Manager: "Solid. Needs to improve communication
              with design team."
           3. Carla Dias — Self: "onboarded 2 new engineers."
              Manager: "Great mentorship. Ready for tech lead."
           [... 4 more ...]

           INCOMPLETE:
           8. Pedro Santos — Self-assessment submitted but NO
              manager notes in Notion. Rafael hasn't written his
              review yet.

           I've created a Google Doc "Q4 Product Team Reviews"
           in your "Performance Reviews" Drive folder with all
           the data organized per person.

           Want me to message Rafael on Slack about Pedro's
           missing review?
```

### Onboarding Checklist Tracking

```
Fernanda:  we have 3 new hires starting Monday. where are we
           on their onboarding checklists?

Agent:     From Notion "Onboarding Tracker":

           1. Mariana Souza (Engineering)
              ✅ Laptop ordered (delivered Friday)
              ✅ Email account created
              ✅ Slack added
              ❌ GitHub access — not set up yet
              ❌ 1:1 with manager not scheduled
              ❌ Buddy not assigned

           2. Lucas Martins (Sales)
              ✅ Laptop ordered (arrives Monday)
              ✅ Email account created
              ✅ Slack added
              ✅ CRM access granted
              ❌ Sales playbook not shared
              ❌ 1:1 with manager not scheduled

           3. Isabela Rocha (Design)
              ✅ Laptop ordered (delivered Thursday)
              ❌ Email account NOT created yet
              ❌ Slack NOT added
              ❌ Figma license NOT assigned
              ❌ Basically nothing is done for Isabela

           Isabela's onboarding is way behind — only the laptop
           is handled. Want me to post a reminder in #it-support
           on Slack for the email and accounts?
```

## Why They Pay

$129/mo for the Team plan replaces what would be a full-time HR coordinator position ($3,000+/mo) for routine questions. The employee self-service alone cuts Fernanda's "quick questions" interruptions by 70%. The performance review assembly saves 2 full days per quarter. The company expanded to 3 agents: one for HR, one for IT support, one for finance questions.

## Connections Used

| Connection | How It's Used |
|---|---|
| Google Drive | Read employee handbook, create review docs. |
| Google Sheets | Read form responses (self-assessments, surveys). |
| Notion | Read/update onboarding checklists, review notes, policies. |
| Slack | Read questions from employees, post reminders to channels. |
