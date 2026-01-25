import polars as pl
from polars import DataFrame
from models import Product
from datetime import date
from rich.console import Console
from rich.prompt import IntPrompt
from rich.panel import Panel
from rich.table import Table

console = Console()

# == CONSTANTS ==
    
INVENTORY_DIR = "data/inventory.csv"
HISTORY_DIR = "data/sales_history.csv"
SAFETY_STOCK = 30
PERIOD_SUPPLY = 30
WARNING_BUFFER_DAYS = 30 # how many safe days the manager wants to have before they hit the urgent reorder point

# === MAIN ===

def main():
    # INPUT
    try:
        sales_history: DataFrame = pl.read_csv(HISTORY_DIR)
        inventory: DataFrame = pl.read_csv(INVENTORY_DIR)
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] Data files not found.")
        return

    choice: int = user_choice()
    opts: dict = get_options(choice)
    
    config = {
        "period_supply": PERIOD_SUPPLY,
        "safety_stock": SAFETY_STOCK,
        "warning_buffer": WARNING_BUFFER_DAYS
    }

    # LOGIC
    report: DataFrame
    metadata: dict
    report, metadata = generate_report(inventory, sales_history, **config)

    # OUTPUT
    active_cols = [col for col, active in opts.items() if active]
    filtered_report = report.select(active_cols)
    
    display_dashboard(filtered_report, metadata)


# === DICSTS ===

def get_options(option: int) -> dict:
    """
    Returns a configuration dictionary defining which columns
    should be visible in the report based on the user's selection.

    Args:
        option (int): 1 for basic info, 2 for detailed info.

    Returns:
        dict: Mapping of column names to boolean visibility status.
    """

    basic = {
        "product_id": True,
        "product_name": True,
        "status_tag": True,
        "days_left": True,
        "reorder_point": True,
        "capital_requirement": True
    }

    extra = {
        "unit_cost": True,
        "current_stock": True,
        "lead_time_days": True,
        "total_sales": True,
        "target_reorder_quantity": True,
        "reorder_point": True,
        "sales_velocity": True
    }
    
    match option:
        case 1:
            return basic
        case 2:
            return basic | extra


# === FUNCTIONS ===

# INPUT

def generate_report(inventory: DataFrame, sales_data: DataFrame, **kwargs) -> tuple[DataFrame, dict]: #, options: dict
    """
    Joins multiple data sources and calculations into a
    single master report and collects metadata.

    Args:
        inventory (DataFrame): Current warehouse stock data.
        sales_data (DataFrame): Historical sales transactions.
        **kwargs: Must include `period_supply`, `safety_stock`, and `warning_buffer`

    Returns:
        `tuple[DataFrame, dict]`: The prioritized report and a dictionary of warehouse-wide metrics.
    """

    period_supply: int = kwargs["period_supply"]
    safety_stock: int = kwargs["safety_stock"]
    warning_buffer: int = kwargs["warning_buffer"]
    
    # TODO: i can optimize this by only calculating the selected type of report (basic/detailed)
    sv: DataFrame = sales_velocity(sales_data)
    dl: DataFrame = covered_days(inventory, sales_data)
    rp: DataFrame = reorder_point(inventory, sales_data, safety_stock)
    trq: DataFrame = target_reorder_quantity(inventory, sales_data, period_supply, safety_stock)
    sales: DataFrame = get_quantity_sold(sales_data)
    sq: DataFrame
    st: DataFrame
    st, sq = status_tag(inventory, sales_data, safety_stock, warning_buffer)
    cr: DataFrame
    cr_total: float
    cr, cr_total = capital_requirement(inventory, sales_data)
    
    basic: DataFrame = inventory.select("product_id", "product_name", "current_stock", "unit_cost", "lead_time_days")
    basic_and_sales: DataFrame = basic.join(sales, on="product_id")

    date_range: tuple[str, str] = get_dates_range(sales_data)
    total_warehouse_value = (inventory["current_stock"] * inventory["unit_cost"]).sum()

    metadata: dict = {
        "status_quantity": sq,
        "capital_requiered": cr_total,
        "total_value": total_warehouse_value,
        "date_range": date_range
    }

    report: DataFrame = (
        basic_and_sales
        .join(sv, on="product_id")
        .join(dl, on="product_id")
        .join(rp, on="product_id")
        .join(trq, on="product_id")
        .join(st, on="product_id")
        .join(cr, on="product_id")
    )

    report = priority_ranking(report)
    
    return report, metadata


def user_choice() -> int:
    """
    Displays an interactive menu to the user via the console.

    Returns:
        int: The selected report type (1 or 2).
    """

    menu_text = (
        "[bold white]1.[/bold white] Basic info\n"
        "[bold white]2.[/bold white] Detailed info"
    )

    console.print(Panel(menu_text, title="Report Options", expand=False))
    choice = IntPrompt.ask("Choose your report type", choices=["1", "2"])
    
    return choice


# LOGIC

def sales_velocity(sales_data: DataFrame) -> DataFrame:
    """
    Calculates the average daily sales units for each product over the history period.

    Args:
        sales_data (DataFrame): Sales transactions.

    Returns:
        DataFrame: `product_id` and `sales_velocity` (units/day).
    """

    # total days
    earliest_date: str
    latest_date: str
    earliest_date, latest_date = get_dates_range(sales_data)
    d1: date = date.fromisoformat(earliest_date)
    d2: date = date.fromisoformat(latest_date)
    days: int = (d2 - d1).days + 1

    # quantity sold per product
    sales_product: DataFrame = get_quantity_sold(sales_data)

    # sales velocity per product
    velocity: pl.Expr = pl.col("total_sales") / days 
    return sales_product.select(
        "product_id",
        pl.when(velocity.is_infinite())
        .then(0)
        .otherwise(velocity)
        .alias("sales_velocity")
    )


def get_quantity_sold(sales_data: DataFrame) -> DataFrame:
    """
    Aggregates raw sales transactions to find the total units sold per product.

    Args:
        sales_data (DataFrame): Raw sales history.

    Returns:
        DataFrame: `product_id` and `total_sales`.
    """

    return sales_data.group_by("product_id").agg(pl.col("quantity_sold").sum().alias("total_sales"))


def covered_days(inventory: DataFrame, sales_data: DataFrame) -> DataFrame:
    """
    Predicts the number of days remaining until current stock reaches zero.

    Args:
        inventory (DataFrame): Current stock levels.
        sales_data (DataFrame): Sales history to determine velocity.

    Returns:
        DataFrame: `product_id` and `days_left` (None if velocity is 0).
    """

    # get stock per product
    stock: DataFrame = get_stock(inventory)

    # get sales velocity per product
    sales_vel: DataFrame = sales_velocity(sales_data)

    # join both in the same DataFrame
    merge: DataFrame = stock.join(sales_vel, "product_id")

    # covered days per product
    cov_days: pl.Expr = pl.col("current_stock") / pl.col("sales_velocity")
    return merge.select(
        "product_id",
        pl.when(cov_days.is_infinite())
        .then(None)
        .otherwise(cov_days)
        .alias("days_left")
    )


def get_stock(inventory: DataFrame) -> DataFrame:
    """
    Extracts the current stock from the inventory.

    Args:
        inventory (DataFrame): The entire inventory table.

    Returns:
        DataFrame: `product_id` and `current_stock`.
    """

    return inventory.select("product_id", "current_stock")


def reorder_point(inventory: DataFrame, sales_data: DataFrame, safety_stock: int) -> DataFrame:
    """
    Calculates the stock level at which a reorder must be placed to avoid stockouts,
    considering the supplier lead time and a safety buffer.

    Args:
        inventory (DataFrame): To get the `lead_time_days` per product.
        sales_data (DataFrame): To determine daily velocity.
        safety_stock (int): Fixed unit buffer for unexpected demand.

    Returns:
        DataFrame: `product_id` and `reorder_point`
    """

    # get sales velocity per product
    sales_vel: DataFrame = sales_velocity(sales_data)

    # get lead time per product
    lead_time: DataFrame = inventory.drop("product_name", "current_stock", "unit_cost")

    # join both in the same DataFrame
    merge: DataFrame = lead_time.join(sales_vel, "product_id")

    # reorder point per product
    reorder_point: pl.Expr = (pl.col("sales_velocity") * pl.col("lead_time_days")) + safety_stock
    return merge.select(
        "product_id",
        reorder_point.alias("reorder_point")
    )


def target_reorder_quantity(inventory: DataFrame, sales_data: DataFrame, period_supply: int, safety_stock: int) -> DataFrame:
    """
    Calculates the number of units to order to satisfy demand for a 
    specific future period while maintaining safety levels.

    Args:
        inventory (DataFrame): Current stock.
        sales_data (DataFrame): Historical velocity.
        period_supply (int): Days of future stock to buy.
        safety_stock (int): Unit buffer

    Returns:
        DataFrame: `product_id` and `target_reorder_quantity`.
    """

    vel: DataFrame = sales_velocity(sales_data)
    stock: DataFrame = get_stock(inventory)
    merge: DataFrame = vel.join(stock, "product_id")

    trq: pl.Expr = (pl.col("sales_velocity") * period_supply) + safety_stock - pl.col("current_stock")
    return merge.select(
        "product_id",
        trq.alias("target_reorder_quantity")
    )


def get_dates_range(sales_data: DataFrame) -> tuple[str, str]:
    """
    Gives the start and end dates of the provided sales history.

    Args:
        sales_data (DataFrame): Table containing a `date` column.

    Returns:
        `tuple[str, str]`: (earliest_date, latest_date)
    """

    earliest_date: str = sales_data.select(pl.min("date")).item()
    latest_date: str = sales_data.select(pl.max("date")).item()
    
    dates: tuple[str, str] = earliest_date, latest_date

    return dates

# OUTPUT

def priority_ranking(df: DataFrame) -> DataFrame:
    """
    Sorts the report by risk and financial impact: items running out 
    soonest appear first, followed by the most expensive reorders.

    Args:
        df (DataFrame): the joined report table.

    Returns:
        DataFrame: Sorted report with N/A values at the bottom.
    """

    return df.sort(["days_left", "capital_requirement"], descending=[False, True], nulls_last=True)


def status_tag(inventory: DataFrame, sales_data: DataFrame, safety_stock: int, warning_buffer: int) -> tuple[DataFrame, DataFrame]:
    """
    Assigns a status label (URGENT, WARNING, OK) to each product 
    based on their proximity to the reorder point.

    Args:
        inventory (DataFrame): Current warehouse data.
        sales_data (DataFrame): Historical demand data.
        safety_stock (int): Minimum buffer.
        warning_buffer (int): Days of runway required for a WARNING status

    Returns:
        `tuple[DataFrame, DataFrame]`: (status labels table, count summary table)
    """

    rop: DataFrame = reorder_point(inventory, sales_data, safety_stock)
    stock: DataFrame = inventory.select("product_id", "current_stock")
    sales_vel: DataFrame = sales_velocity(sales_data)

    merge0 = rop.join(stock, "product_id")

    wt: DataFrame = warning_threshold(rop, sales_vel, buffer_days=warning_buffer)

    merge = merge0.join(wt, "product_id")

    results: DataFrame = merge.select(
        "product_id",
        pl.when(pl.col("current_stock").le(pl.col("reorder_point")))
        .then(pl.lit("URGENT"))
        .when(pl.col("current_stock").le(pl.col("warning_threshold")))
        .then(pl.lit("WARNING"))
        .otherwise(pl.lit("OK"))        
        .alias("status_tag")
    )

    # total quantity of status tags
    status_tags: DataFrame = results.group_by("status_tag").len()

    return results, status_tags


def warning_threshold(reorder_point: DataFrame, sales_velocity: DataFrame, buffer_days: int) -> DataFrame:
    """
    Calculates the alert threshold stock level based on the
    reorder point plus additional days of buffer

    Args:
        reorder_point (DataFrame): The red line stock level.
        sales_velocity (DataFrame): Daily unit movement.
        buffer_days (int): Time buffer for the warning zone.

    Returns:
        DataFrame: `product_id` and `warning_threshold`.
    """

    merge = reorder_point.join(sales_velocity, "product_id")
    wt: pl.Expr = pl.col("reorder_point") + (pl.col("sales_velocity") * buffer_days)

    return merge.select(
        "product_id",
        wt
        .alias("warning_threshold")
    )


def capital_requirement(inventory: DataFrame, sales_data: DataFrame) -> tuple[DataFrame, float]:
    """
    Calculates the investment needed per product and in total to reach 
    ideal stock levels, and clips negative values (overstock).

    Args:
        inventory (DataFrame): Unit costs and stock levels.
        sales_data (DataFrame): Sales velocity.

    Returns:
        tuple[DataFrame, float]: (Per-product requirement, Total company-wide cash needed).
    """
    
    trq: DataFrame = target_reorder_quantity(inventory, sales_data, period_supply=PERIOD_SUPPLY, safety_stock=SAFETY_STOCK)
    unit_cost: DataFrame = inventory.select("product_id", "unit_cost")
    merge = trq.join(unit_cost, "product_id")

    cap_req_res: pl.Expr = pl.col("target_reorder_quantity").clip(lower_bound=0) * pl.col("unit_cost")

    cap_req: DataFrame = merge.select(
        "product_id",
        cap_req_res
        .alias("capital_requirement")
    )

    total: float = cap_req.select(pl.col("capital_requirement").sum()).item()

    return cap_req, total


def display_dashboard(report: DataFrame, metadata: dict):
    """
    Prints a formatted, color-coded dashboard in the terminal with 
    an executive summary panel and a table.

    Args:
        report (DataFrame): The filtered and sorted inventory data.
        metadata (dict): Summary statistics (total value, capital, dates).
    """

    table = Table(title="[bold blue]Inventory Analysis Report[/bold blue]", header_style="bold magenta")
    
    cool_names = {
        "product_id": "ID",
        "product_name": "Product Name",
        "status_tag": "Status",
        "days_left": "Days Left",
        "reorder_point": "ROP",
        "capital_requirement": "Capital Needed",
        "unit_cost": "Unit Cost",
        "current_stock": "Stock",
        "lead_time_days": "Lead Time",
        "total_sales": "Total Sales",
        "target_reorder_quantity": "TRQ",
        "sales_velocity": "Velocity"
    }
    
    for col in report.columns:
        title = cool_names.get(col, col)
        table.add_column(title, justify="right" if report[col].dtype != pl.String else "left")

    for row_dict in report.iter_rows(named=True):
        p = Product.from_row(row_dict)
        table.add_row(*p.to_rich_row(report.columns), style=p.get_status_style())

    # show final results finally
    dr = metadata["date_range"]
    summary_text = (
        f"[bold white]Analysis Period:[/bold white] {dr[0]} to {dr[1]}\n"
        f"[bold white]Total Capital Requirement:[/bold white] [bold green]${metadata['capital_requiered']:,.2f}[/bold green]\n"
        f"[bold white]Total Inventory Value:[/bold white] [bold cyan]${metadata['total_value']:,.2f}[/bold cyan]"
    )
    console.print("\n")
    console.print(Panel(summary_text, title="Executive Summary", expand=False))
    console.print(table)


# === CALL MAIN ===

if __name__ == "__main__":
    main()