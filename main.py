from mcp.server.fastmcp import FastMCP
from datetime import date, timedelta

# ✅ Initialize MCP Server
mcp = FastMCP("HRLeaveMgmtSystem")

# ✅ Sample Employees & Roles
employees = {
    "alice": {"role": "Employee", "manager": "david"},
    "bob": {"role": "Employee", "manager": "david"},
    "charlie": {"role": "Employee", "manager": "david"},
    "david": {"role": "Manager", "manager": "farah"},
    "erika": {"role": "Employee", "manager": "david"},
    "farah": {"role": "HR", "manager": None}
}

# ✅ Leave Balances
leave_balances = {
    "alice":   {"annual": 12, "sick": 5,  "casual": 4},
    "bob":     {"annual": 8,  "sick": 2,  "casual": 3},
    "charlie": {"annual": 15, "sick": 8,  "casual": 2},
    "david":   {"annual": 6,  "sick": 6,  "casual": 2},
    "erika":   {"annual": 10, "sick": 5,  "casual": 2},
    "farah":   {"annual": 12, "sick": 3,  "casual": 2},
}

# ✅ Leave Type Policies (for info + min_notice)
leave_types = {
    "annual": {"max_days": 30, "min_notice_days": 2},
    "sick":   {"max_days": 15, "min_notice_days": 0},
    "casual": {"max_days": 7,  "min_notice_days": 0},
}

# ✅ Sample Leave Records
leave_records = [
    {"id": 1, "employee": "alice",   "type": "annual", "start": "2025-07-01", "end": "2025-07-03", "status": "approved", "approver": "david"},
    {"id": 2, "employee": "bob",     "type": "casual", "start": "2025-07-10", "end": "2025-07-10", "status": "approved", "approver": "david"},
    {"id": 3, "employee": "charlie", "type": "sick",   "start": "2025-07-05", "end": "2025-07-06", "status": "pending",  "approver": "david"},
    {"id": 4, "employee": "erika",   "type": "annual", "start": "2025-07-02", "end": "2025-07-04", "status": "rejected", "approver": "david"},
]

# Internal ID tracking
next_leave_id = 5

# ✅ Notification Simulation
def notify(user: str, message: str):
    print(f"📢 NOTIFY [{user}]: {message}")

# ✅ Tool: Apply for Leave
@mcp.tool()
def apply_leave(employee: str, leave_type: str, start: str, end: str) -> str:
    global next_leave_id
    
    if employee not in employees or employee not in leave_balances:
        return "❌ Employee not found."

    if leave_type not in leave_types:
        return "❌ Invalid leave type."

    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    today = date.today()

    # Check notice period
    notice_days = (start_date - today).days
    min_notice = leave_types[leave_type]["min_notice_days"]
    
    if notice_days < min_notice:
        return f"❌ Minimum {min_notice} days notice required for {leave_type} leave."

    leave_days = (end_date - start_date).days + 1
    if leave_days <= 0:
        return "❌ Invalid leave duration."

    available = leave_balances[employee].get(leave_type, 0)
    if leave_days > available:
        return f"❌ Not enough {leave_type} leave. Available: {available} days."

    # Check overlapping leave request
    for record in leave_records:
        if record["employee"] == employee and record["status"] in ("pending", "approved"):
            rec_start = date.fromisoformat(record["start"])
            rec_end = date.fromisoformat(record["end"])
            if start_date <= rec_end and end_date >= rec_start:
                return "❌ Conflicting leave request already exists."

    # Submit leave request
    leave_balances[employee][leave_type] -= leave_days
    leave_records.append({
        "id": next_leave_id,
        "employee": employee,
        "type": leave_type,
        "start": start,
        "end": end,
        "status": "pending",
        "approver": employees[employee]["manager"]
    })
    
    notify(employees[employee]["manager"], f"{employee} requested {leave_type} leave from {start} to {end}")
    next_leave_id += 1

    return f"✅ Leave request submitted for {employee} ({leave_type}) from {start} to {end}."

# ✅ Tool: Cancel Leave
@mcp.tool()
def cancel_leave(employee: str, leave_id: int) -> str:
    for record in leave_records:
        if record["id"] == leave_id and record["employee"] == employee and record["status"] in ("pending", "approved"):
            leave_days = (date.fromisoformat(record["end"]) - date.fromisoformat(record["start"])).days + 1
            leave_balances[employee][record["type"]] += leave_days
            record["status"] = "cancelled"
            notify(record["approver"], f"{employee} cancelled their leave (ID {leave_id})")
            return f"✅ Leave ID {leave_id} cancelled."
    return "❌ Leave request not found or already processed."

# ✅ Tool: Approve/Reject Leave
@mcp.tool()
def process_leave(manager: str, leave_id: int, approve: bool) -> str:
    for record in leave_records:
        if record["id"] == leave_id and record["status"] == "pending" and record["approver"] == manager:
            record["status"] = "approved" if approve else "rejected"
            if not approve:
                leave_days = (date.fromisoformat(record["end"]) - date.fromisoformat(record["start"])).days + 1
                leave_balances[record["employee"]][record["type"]] += leave_days
            notify(record["employee"], f"Leave (ID {leave_id}) has been {'approved' if approve else 'rejected'} by {manager}")
            return f"✅ Leave {record['status']}."
    return "❌ Leave ID not found or not authorized."

# ✅ Resource: Leave Balance (fixed param alignment)
@mcp.resource("leave_balance://{employee}")
def get_leave_balance(employee: str) -> dict:
    return leave_balances.get(employee, {})

# ✅ Resource: Leave Records by Employee (no optional params allowed in @resource)
@mcp.resource("leave_records://{employee}")
def list_leave_records(employee: str) -> list:
    return [r for r in leave_records if r["employee"] == employee]

# ✅ Tool: Filtered Leave Records (for searches with status, etc.)
@mcp.tool()
def get_filtered_leave_records(employee: str, status: str = None) -> list:
    records = [r for r in leave_records if r["employee"] == employee]
    if status:
        records = [r for r in records if r["status"] == status]
    return records

# ✅ Resource: Company Leave Report
@mcp.resource("report://leave")
def leave_report() -> list:
    report = []
    for name, bal in leave_balances.items():
        total_leave_taken = sum(
            (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days + 1
            for r in leave_records if r["employee"] == name and r["status"] == "approved"
        )
        report.append({
            "employee": name,
            "role": employees[name]["role"],
            "approved_leave_days": total_leave_taken,
            "leave_balance": bal
        })
    return report

# ✅ Prompt: Display Leave Policy
@mcp.prompt()
def view_leave_policy(leave_type: str) -> str:
    policy = leave_types.get(leave_type)
    if not policy:
        return "❌ Leave type not found."
    return (
        f"{leave_type.capitalize()} Leave Policy:\n"
        f"- Max days: {policy['max_days']} per year\n"
        f"- Min advance notice: {policy['min_notice_days']} days"
    )

# ✅ Run the server
if __name__ == "__main__":
    mcp.run()
