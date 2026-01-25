from dataclasses import dataclass
from rich.console import Console

console = Console()

@dataclass
class Product:
    id: str
    name: str
    status: str
    days_left: float
    reorder_point: float
    capital_req: float
    unit_cost: float
    current_stock: int
    lead_time_days: int
    total_sales: int
    target_reorder_qty: float
    sales_velocity: float
    

    @classmethod
    def from_row(cls, row: dict):
        """
        Instantiate a Product object from a dictionary
        representing a single row of a Polars DataFrame.

        Args:
            row (dict): Dictionary with keys that match the expected DataFrame columns.

        Returns:
            Product: Instance of the class populated with row data.
        """
            
        return cls(
            id=str(row.get("product_id")),
            name=row.get("product_name", "Unknown"),
            status=row.get("status_tag", "OK"),
            days_left=row.get("days_left"), # can be None
            reorder_point=row.get("reorder_point", 0.0),
            capital_req=row.get("capital_requirement", 0.0),
            unit_cost=row.get("unit_cost", 0.0),
            current_stock=row.get("current_stock", 0),
            lead_time_days=row.get("lead_time_days", 0),
            total_sales=row.get("total_sales", 0),
            target_reorder_qty=row.get("target_reorder_quantity", 0.0),
            sales_velocity=row.get("sales_velocity", 0.0)
        )
    
    def get_status_style(self) -> str:
        """
        Maps the internal status_tag to a specific `rich` console color.

        Returns:
            str: Rich style string (`bold red`, `bold yellow`, `green`)
        """
            
        if self.status == "URGENT":
            return "bold red"
        elif self.status == "WARNING":
            return "bold yellow"
        return "green"
    
    def to_rich_row(self, active_columns: list) -> list:
        """
        Generates a list of formatted strings representing the product's data
        for use in a `rich` table row.

        Args:
            active_columns (list): List of column keys to include in the output.

        Returns:
            list: Formatted strings (includes currency and decimal rounding).
        """
            
        attr_map = {
            "product_id": self.id,
            "product_name": self.name,
            "status_tag": self.status,
            "days_left": self.days_left,
            "capital_requirement": self.capital_req,
            "reorder_point": self.reorder_point,
            "unit_cost": self.unit_cost,
            "current_stock": self.current_stock,
            "lead_time_days": self.lead_time_days,
            "total_sales": self.total_sales,
            "target_reorder_quantity": self.target_reorder_qty,
            "sales_velocity": self.sales_velocity,
        }
        
        return [format_cell(attr_map.get(col, "N/A"), col) for col in active_columns]


def format_cell(value, column_name: str) -> str:
    """
    Converts raw python/polars types into user-friendly strings for display.
    Handles None/Null cases, currency formatting, and decimal precision.

    Args:
        value (any): The data to be formatted.
        column_name (str): Used to determine if currency symbols ($) are required.

    Returns:
        str: The string representation of the data (N/A, $3,141.59, 67.69).
    """

    if value is None:
        return "N/A"
    
    if not isinstance(value, (float, int)):
        return str(value)
    
    if "cost" in column_name or "requirement" in column_name:
        return f"${value:,.2f}"
        
    if isinstance(value, float):
        return f"{value:.2f}"
        
    return str(value)