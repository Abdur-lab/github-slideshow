"""Reporting aggregation: occupancy, rent collection, overdue analysis, and
maintenance cost summaries (UC-24 / UC-25)."""
from datetime import date, datetime, time, timedelta

from backend.models import Lease, MaintenanceCost, MaintenanceRequest, Property, PropertyExpense, RentPayment, Unit


# Report metrics in display order, with their English names.
REPORT_METRICS = {
    "total_units": "Total Units",
    "occupied_units": "Occupied Units",
    "occupancy_rate": "Occupancy Rate",
    "rent_collected": "Rent Collected",
    "rent_outstanding": "Outstanding",
    "maintenance_cost": "Maintenance Cost",
    "general_expenses": "General Expenses",
    "total_expenses": "Total Expenses",
    "net_income_estimate": "Net Income",
    "open_maintenance_requests": "Open Requests",
}


def property_performance(property_obj: Property, start: date = None, end: date = None) -> dict:
    units = property_obj.units.filter(Unit.status != "ARCHIVED").all()
    total_units = len(units)
    occupied = sum(1 for u in units if u.status == "OCCUPIED")

    unit_ids = [u.id for u in units]
    leases = Lease.query.filter(Lease.unit_id.in_(unit_ids)).all() if unit_ids else []
    lease_ids = [lease.id for lease in leases]

    payments_q = RentPayment.query.filter(RentPayment.lease_id.in_(lease_ids)) if lease_ids else RentPayment.query.filter(False)
    if start:
        payments_q = payments_q.filter(RentPayment.paid_at >= start)
    if end:
        payments_q = payments_q.filter(RentPayment.paid_at <= end)
    total_collected = round(sum(p.amount for p in payments_q.all()), 2)

    total_outstanding = round(sum(lease.balance for lease in leases if lease.status == "ACTIVE"), 2)

    requests = MaintenanceRequest.query.filter(MaintenanceRequest.unit_id.in_(unit_ids)).all() if unit_ids else []
    request_ids = [r.id for r in requests]
    costs_q = MaintenanceCost.query.filter(MaintenanceCost.request_id.in_(request_ids)) if request_ids else MaintenanceCost.query.filter(False)
    total_maintenance_cost = round(sum(c.amount for c in costs_q.all()), 2)

    expenses_q = PropertyExpense.query.filter(PropertyExpense.property_id == property_obj.id)
    if start:
        expenses_q = expenses_q.filter(PropertyExpense.incurred_at >= start)
    if end:
        expenses_q = expenses_q.filter(PropertyExpense.incurred_at <= end)
    general_expenses = round(sum(e.amount for e in expenses_q.all()), 2)
    total_expenses = round(general_expenses + total_maintenance_cost, 2)

    return {
        "property_name": property_obj.name,
        "property_code": property_obj.property_code,
        "currency": property_obj.currency,
        "total_units": total_units,
        "occupied_units": occupied,
        "occupancy_rate": round((occupied / total_units) * 100, 1) if total_units else 0.0,
        "rent_collected": total_collected,
        "rent_outstanding": total_outstanding,
        "maintenance_cost": total_maintenance_cost,
        "general_expenses": general_expenses,
        "total_expenses": total_expenses,
        "net_income_estimate": round(total_collected - total_expenses, 2),
        "open_maintenance_requests": sum(1 for r in requests if r.status not in ("COMPLETED", "CLOSED")),
    }


def portfolio_performance(properties) -> dict:
    summaries = [property_performance(p) for p in properties]
    if not summaries:
        return {
            "properties": [],
            "currency": None,
            "total_units": 0,
            "occupied_units": 0,
            "occupancy_rate": 0.0,
            "rent_collected": 0.0,
            "rent_outstanding": 0.0,
            "maintenance_cost": 0.0,
            "general_expenses": 0.0,
            "total_expenses": 0.0,
            "net_income_estimate": 0.0,
        }
    total_units = sum(s["total_units"] for s in summaries)
    occupied_units = sum(s["occupied_units"] for s in summaries)
    rent_collected = round(sum(s["rent_collected"] for s in summaries), 2)
    total_expenses = round(sum(s["total_expenses"] for s in summaries), 2)
    currencies = {s["currency"] for s in summaries}
    return {
        "properties": summaries,
        # Totals get a currency only when every property uses the same one.
        "currency": currencies.pop() if len(currencies) == 1 else None,
        "total_units": total_units,
        "occupied_units": occupied_units,
        "occupancy_rate": round((occupied_units / total_units) * 100, 1) if total_units else 0.0,
        "rent_collected": rent_collected,
        "rent_outstanding": round(sum(s["rent_outstanding"] for s in summaries), 2),
        "maintenance_cost": round(sum(s["maintenance_cost"] for s in summaries), 2),
        "general_expenses": round(sum(s["general_expenses"] for s in summaries), 2),
        "total_expenses": total_expenses,
        "net_income_estimate": round(rent_collected - total_expenses, 2),
    }


# FR-036 groups the six request stages into the three the SRS reports on.
MAINTENANCE_STAGE_GROUPS = {
    "open": ("SUBMITTED", "ACKNOWLEDGED", "ASSIGNED"),
    "in_progress": ("IN_PROGRESS",),
    "closed": ("COMPLETED", "CLOSED"),
}


def maintenance_summary(properties, start: date, end: date) -> dict:
    """FR-036: open, in-progress and closed maintenance requests per property
    for requests raised between start and end (both inclusive), by their
    current stage."""
    window_start = datetime.combine(start, time.min)
    window_end = datetime.combine(end + timedelta(days=1), time.min)
    rows = []
    for prop in properties:
        unit_ids = [u.id for u in prop.units]
        requests = (
            MaintenanceRequest.query.filter(
                MaintenanceRequest.unit_id.in_(unit_ids),
                MaintenanceRequest.created_at >= window_start,
                MaintenanceRequest.created_at < window_end,
            ).all()
            if unit_ids
            else []
        )
        row = {"property_id": prop.id, "property_name": prop.name}
        for group, stages in MAINTENANCE_STAGE_GROUPS.items():
            row[group] = sum(1 for r in requests if r.status in stages)
        row["total"] = len(requests)
        rows.append(row)
    totals = {key: sum(r[key] for r in rows) for key in (*MAINTENANCE_STAGE_GROUPS, "total")}
    return {"start": start, "end": end, "properties": rows, "totals": totals}
