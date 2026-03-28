from __future__ import annotations

import random
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from app.config import settings


RANDOM_SEED = 42

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Ananya", "Diya", "Saanvi", "Aadhya", "Pari", "Myra", "Ira", "Kiara", "Navya", "Riya",
    "Rahul", "Sneha", "Priya", "Karan", "Neha", "Rohan", "Pooja", "Nikhil", "Meera", "Aniket",
]
LAST_NAMES = [
    "Sharma", "Patel", "Gupta", "Reddy", "Iyer", "Verma", "Nair", "Kapoor", "Joshi", "Mehta",
    "Bose", "Chopra", "Malhotra", "Kumar", "Singh", "Desai", "Mishra", "Agarwal", "Kulkarni", "Rao",
]
CITY_CHOICES = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Pune", "Kolkata", "Ahmedabad", "Jaipur", "Lucknow"]
DOCTOR_BLUEPRINTS = [
    ("Dr. Meera Kapoor", "Dermatology", "Skin Care"),
    ("Dr. Vikram Sethi", "Dermatology", "Skin Care"),
    ("Dr. Anusha Rao", "Dermatology", "Skin Care"),
    ("Dr. Rohan Menon", "Cardiology", "Heart Care"),
    ("Dr. Kavya Shah", "Cardiology", "Heart Care"),
    ("Dr. Arvind Joshi", "Cardiology", "Heart Care"),
    ("Dr. Sana Siddiqui", "Orthopedics", "Bone & Joint"),
    ("Dr. Dev Malhotra", "Orthopedics", "Bone & Joint"),
    ("Dr. Nisha Kulkarni", "Orthopedics", "Bone & Joint"),
    ("Dr. Rahul Verma", "General", "Primary Care"),
    ("Dr. Tanvi Iyer", "General", "Primary Care"),
    ("Dr. Pankaj Desai", "General", "Primary Care"),
    ("Dr. Aditi Nair", "Pediatrics", "Child Care"),
    ("Dr. Kunal Mehta", "Pediatrics", "Child Care"),
    ("Dr. Shruti Bose", "Pediatrics", "Child Care"),
]
TREATMENTS = [
    ("General Consultation", 300, 20),
    ("Follow-up Review", 450, 25),
    ("Skin Allergy Panel", 1400, 40),
    ("ECG", 850, 30),
    ("Echocardiogram", 2200, 45),
    ("Fracture Follow-up", 1100, 35),
    ("Physiotherapy Session", 900, 50),
    ("Vaccination", 500, 15),
    ("Pediatric Checkup", 650, 25),
    ("Minor Procedure", 2600, 60),
]
APPOINTMENT_NOTES = [
    "Routine follow-up visit",
    "Patient reported mild improvement",
    "Recommended medication review",
    "Needs repeat tests next month",
    "Discussed lifestyle changes",
    "Symptoms resolved, continue monitoring",
]


def random_phone(rng: random.Random) -> str:
    return f"+91-{rng.randint(70000, 99999)}-{rng.randint(10000, 99999)}"


def maybe_email(first_name: str, last_name: str, rng: random.Random) -> str | None:
    if rng.random() < 0.18:
        return None
    handle = f"{first_name}.{last_name}{rng.randint(1, 99)}".lower()
    return f"{handle}@example.com"


def maybe_phone(rng: random.Random) -> str | None:
    if rng.random() < 0.12:
        return None
    return random_phone(rng)


def maybe_note(rng: random.Random) -> str | None:
    if rng.random() < 0.28:
        return None
    return rng.choice(APPOINTMENT_NOTES)


def build_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            date_of_birth DATE,
            gender TEXT,
            city TEXT,
            registered_date DATE
        );

        CREATE TABLE doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT,
            department TEXT,
            phone TEXT
        );

        CREATE TABLE appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date DATETIME NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(doctor_id) REFERENCES doctors(id)
        );

        CREATE TABLE treatments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            treatment_name TEXT NOT NULL,
            cost REAL NOT NULL,
            duration_minutes INTEGER NOT NULL,
            FOREIGN KEY(appointment_id) REFERENCES appointments(id)
        );

        CREATE TABLE invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            invoice_date DATE NOT NULL,
            total_amount REAL NOT NULL,
            paid_amount REAL NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY(patient_id) REFERENCES patients(id)
        );
        """
    )


def seed_doctors(connection: sqlite3.Connection, rng: random.Random) -> int:
    rows = [(name, specialization, department, random_phone(rng)) for name, specialization, department in DOCTOR_BLUEPRINTS]
    connection.executemany(
        "INSERT INTO doctors(name, specialization, department, phone) VALUES (?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def seed_patients(connection: sqlite3.Connection, rng: random.Random) -> int:
    today = date.today()
    patient_rows = []
    for _ in range(200):
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        age = rng.randint(2, 85)
        birth_date = today - timedelta(days=(age * 365) + rng.randint(0, 364))
        gender = rng.choice(["M", "F"])
        city = rng.choices(CITY_CHOICES, weights=[14, 12, 11, 9, 8, 8, 8, 7, 6, 5], k=1)[0]
        registered_date = today - timedelta(days=rng.randint(0, 540))
        patient_rows.append(
            (
                first_name,
                last_name,
                maybe_email(first_name, last_name, rng),
                maybe_phone(rng),
                birth_date.isoformat(),
                gender,
                city,
                registered_date.isoformat(),
            )
        )

    connection.executemany(
        """
        INSERT INTO patients(first_name, last_name, email, phone, date_of_birth, gender, city, registered_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        patient_rows,
    )
    return len(patient_rows)


def seed_appointments(connection: sqlite3.Connection, rng: random.Random) -> tuple[int, list[int]]:
    today = datetime.now().replace(microsecond=0, second=0)
    patient_ids = [row[0] for row in connection.execute("SELECT id FROM patients ORDER BY id").fetchall()]
    doctor_ids = [row[0] for row in connection.execute("SELECT id FROM doctors ORDER BY id").fetchall()]

    patient_weights = [5 if patient_id <= 60 else 2 if patient_id <= 130 else 1 for patient_id in patient_ids]
    doctor_weights = [8, 7, 7, 6, 6, 5, 5, 4, 4, 7, 6, 5, 6, 5, 4]
    status_choices = ["Completed", "Scheduled", "Cancelled", "No-Show"]
    status_weights = [72, 12, 10, 6]

    appointment_rows = []
    for _ in range(500):
        patient_id = rng.choices(patient_ids, weights=patient_weights, k=1)[0]
        doctor_id = rng.choices(doctor_ids, weights=doctor_weights, k=1)[0]
        days_ago = rng.randint(0, 364)
        visit_time = today - timedelta(
            days=days_ago,
            hours=rng.randint(0, 8),
            minutes=rng.choice([0, 15, 30, 45]),
        )
        status = rng.choices(status_choices, weights=status_weights, k=1)[0]
        appointment_rows.append(
            (
                patient_id,
                doctor_id,
                visit_time.strftime("%Y-%m-%d %H:%M:%S"),
                status,
                maybe_note(rng),
            )
        )

    connection.executemany(
        """
        INSERT INTO appointments(patient_id, doctor_id, appointment_date, status, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        appointment_rows,
    )

    completed_ids = [
        row[0]
        for row in connection.execute(
            "SELECT id FROM appointments WHERE status = 'Completed' ORDER BY appointment_date"
        ).fetchall()
    ]
    return len(appointment_rows), completed_ids


def seed_treatments(connection: sqlite3.Connection, rng: random.Random, completed_appointment_ids: list[int]) -> int:
    selected_ids = rng.sample(completed_appointment_ids, k=350)
    treatment_rows = []
    for appointment_id in selected_ids:
        treatment_name, base_cost, base_duration = rng.choice(TREATMENTS)
        cost = round(max(50, min(5000, rng.gauss(base_cost, base_cost * 0.18))), 2)
        duration = max(10, int(rng.gauss(base_duration, 8)))
        treatment_rows.append((appointment_id, treatment_name, cost, duration))

    connection.executemany(
        """
        INSERT INTO treatments(appointment_id, treatment_name, cost, duration_minutes)
        VALUES (?, ?, ?, ?)
        """,
        treatment_rows,
    )
    return len(treatment_rows)


def seed_invoices(connection: sqlite3.Connection, rng: random.Random) -> int:
    patient_ids = [row[0] for row in connection.execute("SELECT id FROM patients ORDER BY id").fetchall()]
    patient_visit_counts = Counter(
        row[0]
        for row in connection.execute(
            "SELECT patient_id FROM appointments WHERE status = 'Completed'"
        ).fetchall()
    )
    patient_weights = [max(1, patient_visit_counts.get(patient_id, 0)) for patient_id in patient_ids]

    invoice_rows = []
    today = date.today()
    for _ in range(300):
        patient_id = rng.choices(patient_ids, weights=patient_weights, k=1)[0]
        invoice_date = today - timedelta(days=rng.randint(0, 364))
        total_amount = round(rng.uniform(150, 4500), 2)
        status = rng.choices(["Paid", "Pending", "Overdue"], weights=[58, 24, 18], k=1)[0]
        if status == "Paid":
            paid_amount = total_amount
        elif status == "Pending":
            paid_amount = round(total_amount * rng.choice([0.0, 0.25, 0.5, 0.75]), 2)
        else:
            paid_amount = round(total_amount * rng.choice([0.0, 0.1, 0.3]), 2)
        invoice_rows.append((patient_id, invoice_date.isoformat(), total_amount, paid_amount, status))

    connection.executemany(
        """
        INSERT INTO invoices(patient_id, invoice_date, total_amount, paid_amount, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        invoice_rows,
    )
    return len(invoice_rows)


def rebuild_database(database_path: Path) -> dict[str, int]:
    if database_path.exists():
        database_path.unlink()

    rng = random.Random(RANDOM_SEED)
    with sqlite3.connect(database_path) as connection:
        build_schema(connection)
        doctor_count = seed_doctors(connection, rng)
        patient_count = seed_patients(connection, rng)
        appointment_count, completed_ids = seed_appointments(connection, rng)
        treatment_count = seed_treatments(connection, rng, completed_ids)
        invoice_count = seed_invoices(connection, rng)
        connection.commit()

    return {
        "patients": patient_count,
        "doctors": doctor_count,
        "appointments": appointment_count,
        "treatments": treatment_count,
        "invoices": invoice_count,
    }


def main() -> None:
    summary = rebuild_database(settings.database_path)
    print(
        "Created "
        f"{summary['patients']} patients, "
        f"{summary['doctors']} doctors, "
        f"{summary['appointments']} appointments, "
        f"{summary['treatments']} treatments, "
        f"{summary['invoices']} invoices."
    )


if __name__ == "__main__":
    main()
