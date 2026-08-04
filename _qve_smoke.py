"""QVE smoke test: run compute_placement against in-memory DuckDB."""
import sys
import duckdb

sys.path.insert(0, ".")
from mandi_rdd.storage.duckdb_store import init_schema
from mandi_rdd.omega.qve import compute_placement

conn = duckdb.connect(":memory:")
init_schema(conn)
conn.execute(
    "INSERT INTO rdd_results (commodity, computed_at, effect, std_error, p_value) VALUES "
    "('Wheat', '2026-07-01', 12.5, 3.2, 0.01), "
    "('Rice', '2026-07-01', -8.2, 2.9, 0.04), "
    "('Potato', '2026-07-01', 3.1, 1.5, 0.31)"
)
conn.execute(
    "INSERT INTO forecast_metrics (commodity, computed_at, model, test_mape, test_mae, test_rmse) VALUES "
    "('Wheat','2026-07-01','prophet',8.4,10,12),"
    "('Rice','2026-07-01','prophet',12.1,15,18),"
    "('Potato','2026-07-01','prophet',25.3,20,24)"
)
conn.execute(
    "INSERT INTO prices (state,district,market,commodity,arrival_date,modal_price) VALUES "
    "('KA','D1','M1','Wheat','2026-06-01',2200),"
    "('KA','D1','M1','Rice','2026-06-01',3100),"
    "('KA','D1','M1','Potato','2026-06-01',1400)"
)
res = compute_placement(conn, limit=10, n_iter=500, seed=42)
print("n_particles:", res["n_particles"])
print("energy:", res["energy"])
print("schedule:", res["schedule"])
print("first particle:", res["particles"][0]["id"], res["particles"][0]["position"])
conn.close()
print("QVE SMOKE TEST OK")
