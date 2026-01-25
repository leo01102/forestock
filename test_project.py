import polars as pl
from project import sales_velocity, get_dates_range, priority_ranking


def test_sales_velocity():
    # mock data as if it came from get_quantity_sold (summed already)
    test_data = pl.DataFrame({
        "product_id": [101],
        "quantity_sold": [10]
    })
    # note: sales_velocity calls get_quantity_sold internally, so we provide the RAW sales format for the test
    raw_data = pl.DataFrame({
        "date": ["2026-01-01", "2026-01-02"],
        "product_id": [101, 101],
        "quantity_sold": [5, 5]
    })
    result = sales_velocity(raw_data)
    assert result.filter(pl.col("product_id") == 101)["sales_velocity"][0] == 5.0


def test_get_dates_range():
    test_data = pl.DataFrame({
        "date": ["2025-12-01", "2025-12-31", "2025-12-15"],
        "product_id": [1, 2, 3]
    })
    
    start, end = get_dates_range(test_data)
    
    assert start == "2025-12-01"
    assert end == "2025-12-31"


def test_priority_ranking():
    # report with mixed priority
    test_report = pl.DataFrame({
        "product_id": [1, 2, 3],
        "days_left": [10.0, 2.0, None], # 2.0 should be first, None last
        "capital_requirement": [100.0, 500.0, 0.0]
    })
    
    sorted_report = priority_ranking(test_report)
    
    # first item should be ID 2 (lowest days_left)
    assert sorted_report["product_id"][0] == 2
    # second item should be ID 1
    assert sorted_report["product_id"][1] == 1
    # last item should be ID 3 (None or N/A value)
    assert sorted_report["product_id"][2] == 3