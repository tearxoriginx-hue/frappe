# Dispatch Module — Walkthrough

## What You Need to Know

You only interact with **one screen**: **Dispatch Entry**. The other tables (`Dispatch Product`, `Dispatch Item`) are internal — you never touch them directly.

---

## Step-by-Step: Creating a Dispatch

### 1. Open Dispatch Entry
Search for **"Dispatch Entry"** in the sidebar or search bar → click **+ Add Dispatch Entry**.

### 2. Header (mostly auto-filled)
| Field | What happens |
|---|---|
| **Posting Date / Time** | Auto-set to now, locked |
| **Company** | Auto-set from your login, locked |
| **Branch** | Auto-set from your warehouse, locked |
| **Customer** | ✏️ You pick the customer |
| **Invoice / Ref No** | ✏️ You type the invoice number |

### 3. Add Products
In the **Products** table, add one row per Item type you are dispatching:
1. Click **Add Row**
2. Select the **Item Code**
3. The **Expiry Date** auto-calculates (today + warranty days from the item master)

### 4. Scan Serial Numbers
This is the core action. In the grid you'll see a **Serial Numbers** column with a clickable badge:

- **"➕ Click to scan serials"** — no serials yet
- **"📋 42 serials — click to manage"** — 42 already scanned

**Click it** to open the scan popup:

| Feature | How it works |
|---|---|
| **Scan input** | Type or scan a barcode + press Enter. Barcode scanners auto-submit after 150ms |
| **Live counter** | Shows total scanned in real-time |
| **Search bar** | Instantly filter through thousands of serials |
| **Delete (✕)** | Remove a wrongly scanned serial before submitting |
| **Duplicate guard** | Orange alert if you scan the same serial twice |

Click **Save & Close** when done scanning for that product.

### 5. Submit
Click **Submit**. What happens next:

| Status | What it means |
|---|---|
| ⏳ **Pending** | Waiting to enter the processing queue |
| ⚙️ **In Queue** | Background worker is processing your serials (page auto-refreshes every 5s) |
| ✅ **Processed** | All serials are registered in the system with correct warranty dates |
| ❌ **Failed** | Something went wrong (see below) |

---

## What Happens If Processing Fails?

When the status shows **❌ Failed**, it means the background job hit an error while creating/updating serial numbers. This can happen due to:

- A permission issue (e.g., a role restriction on creating Serial No records)
- A data conflict (e.g., a serial number is locked by another process)
- A temporary database connectivity issue

**How to fix it:**

1. A blue **"Retry Processing"** button appears on the form — click it
2. The system re-queues the job and tries again
3. If it keeps failing, your Dispatch Manager can check **Error Log** (search "Error Log" in the sidebar) to see the exact error message and traceback

> The system is safe to retry — it won't duplicate serial numbers. If a serial was already created in a previous partial run, it will simply update it.

---

## Behind the Scenes (for Managers)

- **Fast Entry (The "Trick"):** Serials are temporarily stored as text in the product row during data entry. This skips Frappe's normal validation limits, allowing you to scan 5,000 items without the browser crashing.
- **Background Processing:** On Submit, a background worker processes these serials in batches of 50.
- **100% ERPNext Compatible:** For each scanned serial, the system **auto-creates or updates individual `Serial No` records** in standard ERPNext. This means:
  - Each serial number is still an **individual item unit** in the system.
  - The serial number uniquely tracks the product throughout all other ERPNext modules (warranty claims, support, etc.), exactly as it has always worked by default!
- Warranty Expiry = Posting Date + Item's warranty period (in days)

---

## Accessing Serial Records & PDF Printing

This system is designed specifically to prevent bloated tracking documents when handling high volumes (like 800+ items).

**1. PDF Printing**
When you print the `Dispatch Entry` document natively as a PDF or standard print format, the 800 individual serial lines are **intentionally hidden**. The physical paper will print a clean, short table showing a summary (e.g., MOUSE-001 | 800 Qty).

**2. Viewing the Serial List**
To access the full list of generated serials later:
- Navigate into the **Dispatch Entry** inside the Frappe browser.
- Click the **"📋 800 serials logged"** badge on the `Dispatch Product` grid.
- A clean, read-only version of the scanning popup opens directly. It includes a smart Search Bar allowing you to instantly locate any individual serial unit out of the thousands dispatched, without slowing down the ERP interfaces remotely!

---

## Security & Branch Access Control

This application supports Frappe's native **User Permissions** ecosystem to completely isolate data between physical locations.

**For Normal Operators (e.g., Branch A):**
1. The System Admin sets a standard **User Permission** for the employee: `Branch = Branch A`.
2. When the operator logs in, the `Dispatch Entry` list is strictly filtered. They can only see and create dispatches for Branch A. Other branches are invisible.

**For Head Managers (Accessing All Branches):**
1. Assign the employee the **"Dispatch Manager"** role in Frappe.
2. In the "Role Permission Manager", ensure that **"Ignore User Permissions"** is checked for the Dispatch Manager role.
3. The Manager will now see all branches globally and can manually select any branch from the `Branch` dropdown field when creating a new dispatch record to cover different shifts.
