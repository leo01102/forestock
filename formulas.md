# Inventory Forecasting Logic

This file explains the the formulas used in **ForeStock**.

### 1. Sales Velocity ($V$)

**Formula:**  
$$V = \frac{\sum quantity\_sold}{days\_in\_history}$$

In business, sales are rarely consistent; you might sell 20 units on Monday and 0 on Tuesday.

By dividing the total quantity sold by the total number of days in that period, we find the **average daily drain** on our inventory

---

### 2. Days of Cover ($DC$)

**Formula:**  
$$DC = \frac{current\_stock}{V}$$

A manager needs to know their "runway". Simply knowing you have 100 units is useless unless you know how fast they are disappearing.

We divide the current pile of stock by the daily sales velocity. This answers the question: _"How many groups of 'one day's worth of sales' fit into my current stock?"_ If the result is 5, we have 5 days before the shelves are empty.

---

### 3. Reorder Point ($ROP$)

**Formula:**  
$$ROP = (V \times lead\_time) + safety\_stock$$

This is the "Red Line". If you wait until you have 0 stock to order more, you will be out of stock for the entire time it takes the supplier to deliver the goods.

- $(V \times lead\_time)$: This calculates exactly how many units will be sold while the delivery truck is on its way.
- $+ safety\_stock$: We add a buffer because the real world is unpredictable (e.g., a sudden surge in sales or a shipping delay)
- $ROP$: If the stock hits this number, we must order **now** to ensure the new shipment arrives exactly as the old stock hits zero.

---

### 4. Target Reorder Quantity ($TRQ$)

**Formula:**  
$$TRQ = (V \times period\_supply) + safety\_stock - current\_stock$$

Placing orders is expensive and time-consuming. Instead of ordering every day, businesses order enough to last for a specific "Period of Supply" (e.g., 30 days).

- $(V \times period\_supply)$: We multiply the daily sales velocity by the number of days we want the new stock to last (the period supply). This calculation scales our daily "burn rate" to a larger timeframe, telling us exactly how many units we expect to sell during that entire period
- $+ safety\_stock$: We add the safety stock to this total to act as an emergency floor. So we ensure that even if there is a sudden spike in demand or a delay in shipping, we won't hit zero
- $- current\_stock$: We subtract what we already have so we don't accidentally over-purchase.
- $TRQ$: The exact shopping list quantity needed to return the warehouse to its ideal state.

---

### 5. Capital Requirement ($CR$)

**Formula:**  
$$CR = \sum (TRQ \times unit\_cost)$$

The manager needs to know how much money must be spent to execute the reorder plan.

We multiply the number of units we need to buy ($TRQ$) by the price the supplier charges us ($unit\_cost$). We then sum ($\sum$) these totals for every product to get a single, warehouse-wide dollar amount.
