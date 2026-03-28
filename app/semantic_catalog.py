from __future__ import annotations

import json
import re
from difflib import SequenceMatcher


SEMANTIC_CATALOG = [
    {
        "id": "total_patients",
        "question": "How many patients do we have?",
        "metric_type": "kpi",
        "business_definition": "Total number of patients registered in the clinic system.",
        "source_tables": ["patients"],
        "source_columns": ["patients.id"],
        "grain": "single summary row",
        "aggregation": "COUNT(*)",
        "filters": [],
        "sql": "SELECT COUNT(*) AS total_patients FROM patients",
        "example_questions": [
            "How many patients do we have?",
            "What is the patient count?",
            "How many total patients are registered?",
        ],
    },
    {
        "id": "doctor_specializations",
        "question": "List all doctors and their specializations",
        "metric_type": "listing",
        "business_definition": "Directory of doctors and their primary specializations.",
        "source_tables": ["doctors"],
        "source_columns": ["doctors.name", "doctors.specialization"],
        "grain": "one row per doctor",
        "aggregation": None,
        "filters": [],
        "sql": "SELECT name, specialization FROM doctors ORDER BY name",
        "example_questions": [
            "List all doctors and their specializations",
            "Show all doctors with their specialization",
            "Who are the doctors and what do they specialize in?",
        ],
    },
    {
        "id": "appointments_last_month",
        "question": "Show me appointments for last month",
        "metric_type": "time_window_listing",
        "business_definition": "Appointments that happened during the previous calendar month.",
        "source_tables": ["appointments"],
        "source_columns": ["appointments.id", "appointments.patient_id", "appointments.doctor_id", "appointments.appointment_date", "appointments.status"],
        "grain": "one row per appointment",
        "aggregation": None,
        "filters": ["previous calendar month"],
        "sql": "SELECT id, patient_id, doctor_id, appointment_date, status FROM appointments WHERE appointment_date >= date('now', 'start of month', '-1 month') AND appointment_date < date('now', 'start of month') ORDER BY appointment_date",
        "example_questions": [
            "Show me appointments for last month",
            "List appointments from the last month",
            "What appointments happened last month?",
        ],
    },
    {
        "id": "busiest_doctor",
        "question": "Which doctor has the most appointments?",
        "metric_type": "ranking",
        "business_definition": "Doctor with the highest appointment count.",
        "source_tables": ["doctors", "appointments"],
        "source_columns": ["doctors.name", "appointments.id", "appointments.doctor_id"],
        "grain": "single doctor row",
        "aggregation": "COUNT(appointments.id)",
        "filters": [],
        "sql": "SELECT d.name, COUNT(a.id) AS appointment_count FROM doctors d JOIN appointments a ON a.doctor_id = d.id GROUP BY d.id, d.name ORDER BY appointment_count DESC LIMIT 1",
        "example_questions": [
            "Which doctor has the most appointments?",
            "Who is the busiest doctor?",
            "Which doctor saw the most patients?",
        ],
    },
    {
        "id": "total_revenue",
        "question": "What is the total revenue?",
        "metric_type": "kpi",
        "business_definition": "Total invoiced amount across all invoices.",
        "source_tables": ["invoices"],
        "source_columns": ["invoices.total_amount"],
        "grain": "single summary row",
        "aggregation": "SUM(invoices.total_amount)",
        "filters": [],
        "sql": "SELECT ROUND(SUM(total_amount), 2) AS total_revenue FROM invoices",
        "example_questions": [
            "What is the total revenue?",
            "How much revenue did we make in total?",
            "Total billed amount",
        ],
    },
    {
        "id": "revenue_by_doctor",
        "question": "Show revenue by doctor",
        "metric_type": "breakdown",
        "business_definition": "Total invoiced revenue attributed to each doctor through patient appointments.",
        "source_tables": ["doctors", "appointments", "invoices"],
        "source_columns": ["doctors.name", "appointments.doctor_id", "appointments.patient_id", "invoices.total_amount"],
        "grain": "one row per doctor",
        "aggregation": "SUM(invoices.total_amount)",
        "filters": [],
        "sql": "SELECT d.name, ROUND(SUM(i.total_amount), 2) AS total_revenue FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN invoices i ON i.patient_id = a.patient_id GROUP BY d.id, d.name ORDER BY total_revenue DESC",
        "example_questions": [
            "Show revenue by doctor",
            "How much revenue did each doctor generate?",
            "Doctor wise revenue",
        ],
    },
    {
        "id": "cancelled_appointments_last_quarter",
        "question": "How many cancelled appointments last quarter?",
        "metric_type": "kpi",
        "business_definition": "Count of appointments cancelled during the previous full three-month window.",
        "source_tables": ["appointments"],
        "source_columns": ["appointments.id", "appointments.status", "appointments.appointment_date"],
        "grain": "single summary row",
        "aggregation": "COUNT(*)",
        "filters": ["status = Cancelled", "previous three calendar months"],
        "sql": "SELECT COUNT(*) AS cancelled_appointments_last_quarter FROM appointments WHERE status = 'Cancelled' AND appointment_date >= date('now', 'start of month', '-3 months') AND appointment_date < date('now', 'start of month')",
        "example_questions": [
            "How many cancelled appointments last quarter?",
            "Count cancelled appointments in the last quarter",
            "How many appointments were cancelled recently?",
        ],
    },
    {
        "id": "top_patients_by_spending",
        "question": "Top 5 patients by spending",
        "metric_type": "ranking",
        "business_definition": "Top patients ranked by total invoice amount.",
        "source_tables": ["patients", "invoices"],
        "source_columns": ["patients.first_name", "patients.last_name", "invoices.total_amount", "invoices.patient_id"],
        "grain": "one row per patient",
        "aggregation": "SUM(invoices.total_amount)",
        "filters": ["top 5"],
        "sql": "SELECT p.first_name, p.last_name, ROUND(SUM(i.total_amount), 2) AS total_spending FROM patients p JOIN invoices i ON i.patient_id = p.id GROUP BY p.id, p.first_name, p.last_name ORDER BY total_spending DESC LIMIT 5",
        "example_questions": [
            "Top 5 patients by spending",
            "Which five patients spent the most?",
            "Show the highest spending patients",
        ],
    },
    {
        "id": "avg_treatment_cost_by_specialization",
        "question": "Average treatment cost by specialization",
        "metric_type": "breakdown",
        "business_definition": "Average treatment cost grouped by doctor specialization.",
        "source_tables": ["treatments", "appointments", "doctors"],
        "source_columns": ["treatments.cost", "treatments.appointment_id", "appointments.doctor_id", "doctors.specialization"],
        "grain": "one row per specialization",
        "aggregation": "AVG(treatments.cost)",
        "filters": [],
        "sql": "SELECT d.specialization, ROUND(AVG(t.cost), 2) AS average_treatment_cost FROM treatments t JOIN appointments a ON a.id = t.appointment_id JOIN doctors d ON d.id = a.doctor_id GROUP BY d.specialization ORDER BY average_treatment_cost DESC",
        "example_questions": [
            "Average treatment cost by specialization",
            "What is the average treatment cost for each specialization?",
            "Specialization wise average treatment cost",
        ],
    },
    {
        "id": "monthly_appointment_count",
        "question": "Show monthly appointment count for the past 6 months",
        "metric_type": "trend",
        "business_definition": "Monthly appointment counts for the latest six-month reporting window.",
        "source_tables": ["appointments"],
        "source_columns": ["appointments.id", "appointments.appointment_date"],
        "grain": "one row per month",
        "aggregation": "COUNT(*)",
        "filters": ["latest six-month reporting window"],
        "sql": "SELECT strftime('%Y-%m', appointment_date) AS month, COUNT(*) AS appointment_count FROM appointments WHERE appointment_date >= date('now', 'start of month', '-5 months') GROUP BY month ORDER BY month",
        "example_questions": [
            "Show monthly appointment count for the past 6 months",
            "Monthly appointments for the last six months",
            "Appointment trend over the past 6 months",
        ],
    },
    {
        "id": "city_with_most_patients",
        "question": "Which city has the most patients?",
        "metric_type": "ranking",
        "business_definition": "City with the highest patient count.",
        "source_tables": ["patients"],
        "source_columns": ["patients.city", "patients.id"],
        "grain": "single city row",
        "aggregation": "COUNT(*)",
        "filters": [],
        "sql": "SELECT city, COUNT(*) AS patient_count FROM patients GROUP BY city ORDER BY patient_count DESC LIMIT 1",
        "example_questions": [
            "Which city has the most patients?",
            "What city has the highest number of patients?",
            "City with the most registered patients",
        ],
    },
    {
        "id": "repeat_patients",
        "question": "List patients who visited more than 3 times",
        "metric_type": "cohort_listing",
        "business_definition": "Patients with more than three completed visits.",
        "source_tables": ["patients", "appointments"],
        "source_columns": ["patients.id", "patients.first_name", "patients.last_name", "appointments.patient_id", "appointments.status"],
        "grain": "one row per patient",
        "aggregation": "COUNT(appointments.id)",
        "filters": ["completed appointments only", "visit_count > 3"],
        "sql": "SELECT p.id, p.first_name, p.last_name, COUNT(a.id) AS visit_count FROM patients p JOIN appointments a ON a.patient_id = p.id WHERE a.status = 'Completed' GROUP BY p.id, p.first_name, p.last_name HAVING COUNT(a.id) > 3 ORDER BY visit_count DESC, p.last_name",
        "example_questions": [
            "List patients who visited more than 3 times",
            "Show repeat patients with more than three visits",
            "Which patients came more than 3 times?",
        ],
    },
    {
        "id": "unpaid_invoices",
        "question": "Show unpaid invoices",
        "metric_type": "listing",
        "business_definition": "Invoices that are still pending or overdue.",
        "source_tables": ["invoices"],
        "source_columns": ["invoices.id", "invoices.patient_id", "invoices.invoice_date", "invoices.total_amount", "invoices.paid_amount", "invoices.status"],
        "grain": "one row per invoice",
        "aggregation": None,
        "filters": ["status in Pending, Overdue"],
        "sql": "SELECT id, patient_id, invoice_date, total_amount, paid_amount, status FROM invoices WHERE status IN ('Pending', 'Overdue') ORDER BY invoice_date DESC",
        "example_questions": [
            "Show unpaid invoices",
            "List pending and overdue invoices",
            "Which invoices are still unpaid?",
        ],
    },
    {
        "id": "no_show_percentage",
        "question": "What percentage of appointments are no-shows?",
        "metric_type": "kpi",
        "business_definition": "Percentage of appointments marked as no-show.",
        "source_tables": ["appointments"],
        "source_columns": ["appointments.status", "appointments.id"],
        "grain": "single summary row",
        "aggregation": "SUM(CASE)/COUNT(*)",
        "filters": ["status = No-Show"],
        "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN status = 'No-Show' THEN 1 ELSE 0 END) / COUNT(*), 2) AS no_show_percentage FROM appointments",
        "example_questions": [
            "What percentage of appointments are no-shows?",
            "What is the no show rate?",
            "Percentage of appointments marked no-show",
        ],
    },
    {
        "id": "busiest_weekday",
        "question": "Show the busiest day of the week for appointments",
        "metric_type": "ranking",
        "business_definition": "Day of week with the highest appointment volume.",
        "source_tables": ["appointments"],
        "source_columns": ["appointments.appointment_date", "appointments.id"],
        "grain": "single weekday row",
        "aggregation": "COUNT(*)",
        "filters": [],
        "sql": "SELECT CASE strftime('%w', appointment_date) WHEN '0' THEN 'Sunday' WHEN '1' THEN 'Monday' WHEN '2' THEN 'Tuesday' WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday' ELSE 'Saturday' END AS weekday, COUNT(*) AS appointment_count FROM appointments GROUP BY strftime('%w', appointment_date) ORDER BY appointment_count DESC LIMIT 1",
        "example_questions": [
            "Show the busiest day of the week for appointments",
            "Which weekday has the most appointments?",
            "What is the busiest day for appointments?",
        ],
    },
    {
        "id": "monthly_revenue_trend",
        "question": "Revenue trend by month",
        "metric_type": "trend",
        "business_definition": "Monthly total invoiced revenue.",
        "source_tables": ["invoices"],
        "source_columns": ["invoices.invoice_date", "invoices.total_amount"],
        "grain": "one row per month",
        "aggregation": "SUM(invoices.total_amount)",
        "filters": [],
        "sql": "SELECT strftime('%Y-%m', invoice_date) AS month, ROUND(SUM(total_amount), 2) AS revenue FROM invoices GROUP BY month ORDER BY month",
        "example_questions": [
            "Revenue trend by month",
            "Monthly revenue trend",
            "Show revenue over time by month",
        ],
    },
    {
        "id": "avg_duration_by_doctor",
        "question": "Average appointment duration by doctor",
        "metric_type": "breakdown",
        "business_definition": "Average treatment duration grouped by doctor, used as the assignment's proxy for appointment duration.",
        "source_tables": ["doctors", "appointments", "treatments"],
        "source_columns": ["doctors.name", "appointments.doctor_id", "treatments.duration_minutes", "treatments.appointment_id"],
        "grain": "one row per doctor",
        "aggregation": "AVG(treatments.duration_minutes)",
        "filters": [],
        "sql": "SELECT d.name, ROUND(AVG(t.duration_minutes), 2) AS average_duration_minutes FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN treatments t ON t.appointment_id = a.id GROUP BY d.id, d.name ORDER BY average_duration_minutes DESC",
        "example_questions": [
            "Average appointment duration by doctor",
            "What is the average treatment duration for each doctor?",
            "Doctor wise average appointment duration",
        ],
    },
    {
        "id": "patients_with_overdue_invoices",
        "question": "List patients with overdue invoices",
        "metric_type": "listing",
        "business_definition": "Patients associated with overdue invoices and the outstanding invoice details.",
        "source_tables": ["patients", "invoices"],
        "source_columns": ["patients.first_name", "patients.last_name", "invoices.invoice_date", "invoices.total_amount", "invoices.paid_amount", "invoices.status"],
        "grain": "one row per overdue invoice",
        "aggregation": None,
        "filters": ["status = Overdue"],
        "sql": "SELECT p.first_name, p.last_name, i.invoice_date, i.total_amount, i.paid_amount FROM invoices i JOIN patients p ON p.id = i.patient_id WHERE i.status = 'Overdue' ORDER BY i.invoice_date DESC",
        "example_questions": [
            "List patients with overdue invoices",
            "Which patients have overdue invoices?",
            "Show patients who still owe overdue payments",
        ],
    },
    {
        "id": "revenue_by_department",
        "question": "Compare revenue between departments",
        "metric_type": "breakdown",
        "business_definition": "Revenue comparison across doctor departments.",
        "source_tables": ["doctors", "appointments", "invoices"],
        "source_columns": ["doctors.department", "appointments.doctor_id", "appointments.patient_id", "invoices.total_amount"],
        "grain": "one row per department",
        "aggregation": "SUM(invoices.total_amount)",
        "filters": [],
        "sql": "SELECT d.department, ROUND(SUM(i.total_amount), 2) AS revenue FROM doctors d JOIN appointments a ON a.doctor_id = d.id JOIN invoices i ON i.patient_id = a.patient_id GROUP BY d.department ORDER BY revenue DESC",
        "example_questions": [
            "Compare revenue between departments",
            "Revenue by department",
            "How much revenue did each department generate?",
        ],
    },
    {
        "id": "patient_registration_trend",
        "question": "Show patient registration trend by month",
        "metric_type": "trend",
        "business_definition": "Monthly counts of new patient registrations.",
        "source_tables": ["patients"],
        "source_columns": ["patients.registered_date", "patients.id"],
        "grain": "one row per month",
        "aggregation": "COUNT(*)",
        "filters": [],
        "sql": "SELECT strftime('%Y-%m', registered_date) AS month, COUNT(*) AS registrations FROM patients GROUP BY month ORDER BY month",
        "example_questions": [
            "Show patient registration trend by month",
            "Monthly patient registration trend",
            "How are patient registrations changing by month?",
        ],
    },
]


def normalize_question(question: str) -> str:
    normalized = question.lower().strip()
    normalized = normalized.replace("?", " ")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


QUESTION_SQL_FALLBACKS = {normalize_question(item["question"]): item["sql"] for item in SEMANTIC_CATALOG}
SEED_QA_PAIRS = [(item["question"], item["sql"]) for item in SEMANTIC_CATALOG]


def get_catalog_prompt_context(limit: int = 12) -> str:
    compact_entries = []
    for item in SEMANTIC_CATALOG[:limit]:
        compact_entries.append(
            {
                "id": item["id"],
                "business_definition": item["business_definition"],
                "source_tables": item["source_tables"],
                "source_columns": item["source_columns"],
                "grain": item["grain"],
                "aggregation": item["aggregation"],
                "filters": item["filters"],
                "sql_template": item["sql"],
                "example_questions": item["example_questions"][:2],
            }
        )
    return json.dumps(compact_entries, indent=2)


def match_question_to_catalog_entry(question: str) -> tuple[dict[str, object] | None, str | None]:
    normalized = normalize_question(question)
    direct_match = next((item for item in SEMANTIC_CATALOG if normalize_question(item["question"]) == normalized), None)
    if direct_match is not None:
        return direct_match, "direct_catalog_match"

    best_match: dict[str, object] | None = None
    best_score = 0.0
    for item in SEMANTIC_CATALOG:
        examples = [item["question"], *item["example_questions"]]
        scores = [SequenceMatcher(None, normalized, normalize_question(example)).ratio() for example in examples]
        score = max(scores) if scores else 0.0
        if score > best_score:
            best_score = score
            best_match = item

    if best_match is not None and best_score >= 0.72:
        return best_match, "fuzzy_catalog_match"

    return None, None


def match_question_to_sql(question: str) -> tuple[str | None, str | None]:
    entry, source = match_question_to_catalog_entry(question)
    if entry is None:
        return None, None
    return str(entry["sql"]), source
