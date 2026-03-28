# Assignment Audit Report

- Executed at: 2026-03-28 17:00:31
- LLM Provider: groq
- Database path: clinic.db

## Schema Snapshot

- `appointments`: id, patient_id, doctor_id, appointment_date, status, notes
- `doctors`: id, name, specialization, department, phone
- `invoices`: id, patient_id, invoice_date, total_amount, paid_amount, status
- `patients`: id, first_name, last_name, email, phone, date_of_birth, gender, city, registered_date
- `treatments`: id, appointment_id, treatment_name, cost, duration_minutes

## End-to-End Audit

| # | Question | Canonical SQL Safe | Canonical SQL Executes | `/chat` Status | Source | SQL Match | Returned Columns | Row Count Match | Audit |
|---|---|---|---|---|---|---|---|---|---|
| 1 | How many patients do we have? | Y | Y | 200 | agent | Y | total_patients | Y | PASS |
| 2 | List all doctors and their specializations | Y | Y | 200 | agent | Y | name, specialization | Y | PASS |
| 3 | Show me appointments for last month | Y | Y | 200 | agent | Y | id, patient_id, doctor_id, appointment_date, status | Y | PASS |
| 4 | Which doctor has the most appointments? | Y | Y | 200 | agent | Y | name, appointment_count | Y | PASS |
| 5 | What is the total revenue? | Y | Y | 200 | agent | Y | total_revenue | Y | PASS |
| 6 | Show revenue by doctor | Y | Y | 200 | agent | Y | name, total_revenue | Y | PASS |
| 7 | How many cancelled appointments last quarter? | Y | Y | 200 | agent | Y | cancelled_appointments_last_quarter | Y | PASS |
| 8 | Top 5 patients by spending | Y | Y | 200 | agent | Y | first_name, last_name, total_spending | Y | PASS |
| 9 | Average treatment cost by specialization | Y | Y | 200 | agent | Y | specialization, average_treatment_cost | Y | PASS |
| 10 | Show monthly appointment count for the past 6 months | Y | Y | 200 | agent | Y | month, appointment_count | Y | PASS |
| 11 | Which city has the most patients? | Y | Y | 200 | agent | Y | city, patient_count | Y | PASS |
| 12 | List patients who visited more than 3 times | Y | Y | 200 | agent | Y | id, first_name, last_name, visit_count | Y | PASS |
| 13 | Show unpaid invoices | Y | Y | 200 | agent | Y | id, patient_id, invoice_date, total_amount, paid_amount, status | Y | PASS |
| 14 | What percentage of appointments are no-shows? | Y | Y | 200 | agent | Y | no_show_percentage | Y | PASS |
| 15 | Show the busiest day of the week for appointments | Y | Y | 200 | agent | Y | weekday, appointment_count | Y | PASS |
| 16 | Revenue trend by month | Y | Y | 200 | agent | Y | month, revenue | Y | PASS |
| 17 | Average appointment duration by doctor | Y | Y | 200 | agent | Y | name, average_duration_minutes | Y | PASS |
| 18 | List patients with overdue invoices | Y | Y | 200 | agent | Y | first_name, last_name, invoice_date, total_amount, paid_amount | Y | PASS |
| 19 | Compare revenue between departments | Y | Y | 200 | agent | Y | department, revenue | Y | PASS |
| 20 | Show patient registration trend by month | Y | Y | 200 | agent | Y | month, registrations | Y | PASS |

## Summary

- Passed: 20/20
- This audit checks the canonical assignment SQL, verifies it executes, then verifies `/chat` returns the expected SQL shape, columns, and row counts.