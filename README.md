# Behavioral Anomaly Detection Simulator

Backend-only Phase 1 scaffold for a behavioral anomaly detection system. The project generates synthetic single-customer transaction data with a normal baseline and controlled anomalies for downstream unsupervised model training.

## Project Structure

```text
FRMS_ML/
|-- app/
|   |-- api/routes/simulator.py
|   |-- core/config.py
|   |-- db/postgres.py
|   |-- models/schemas.py
|   |-- services/simulator.py
|   `-- main.py
|-- data/output/
|-- db/schema.sql
|-- scripts/generate_transactions.py
|-- requirements.txt
`-- README.md
```

## Setup

```powershell
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Generate Synthetic Data

CSV output:

```powershell
python scripts\generate_transactions.py --output csv
```

Postgres output:

```powershell
python scripts\generate_transactions.py --output postgres
```

Both CSV and Postgres:

```powershell
python scripts\generate_transactions.py --output both
```

Optional arguments:

```powershell
python scripts\generate_transactions.py --months 6 --seed 7 --output both
```

Rules enforced by the generator:

- Baseline covers 3 to 6 months for one synthetic `account_id`.
- Baseline transactions only happen in the morning.
- Baseline transaction amounts always stay below 3000 INR.
- Baseline monthly volume never exceeds 20 transactions.
- Final month includes a 1:00 AM transaction and a spike to 50 transactions.

## Start FastAPI

```powershell
uvicorn app.main:app --reload
```

Sample endpoint:

`GET /simulator/preview?months=4&seed=42`

## Database Notes

`db/schema.sql` contains:

- `raw_transactions`
- `behavioral_profiles`
- `behavioral_config`

The database flow now targets PostgreSQL directly using the connection values in `.env`.

## Environment Variables

```env
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=your_postgres_server_ip
DB_PORT=5432
DB_NAME=behaviour_db
```

Initialize the schema in Postgres by running:

```powershell
psql -U postgres -h your_postgres_server_ip -p 5432 -d behaviour_db -f db\schema.sql
```
