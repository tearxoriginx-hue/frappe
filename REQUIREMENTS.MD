📄 Product Requirements Document (PRD) v2.0

Primary Objective: Sub-second Serial/Warranty logging for 5,000+ units/day.

1.Executive Summary The fast_warranty_dispatch app is a high-velocity utility designed to bypass the "heavy" overhead of standard ERPNext Delivery Notes.Main Purpose: To provide a dedicated interface for high-speed dispatch where Accounting, Tax, and Stock-level checks are skipped to prioritize speed. The system ensures that the physical movement of goods is never blocked by digital data missing from the system. If a serial number is scanned but doesn't exist in the database, the app auto-creates it in real-time, links it to the product, and activates the warranty.
2. Updated Problem Statement: The "5,000 Unit" ChallengeStandard ERPNext workflows fail when a warehouse moves 5,000+ items per day because:Manual Verification: Checking if a product exists before scanning adds 2–3 seconds per unit. Over 5,000 units, this is 4 hours of lost time.Accounting Friction: Delivery Notes trigger complex GL entry calculations and stock ledger locks that cause "Row Locked" errors during high-volume periods.The "Stop-the-Line" Bug: If a Serial No isn't pre-registered, the dispatcher is forced to stop the physical line to perform manual data entry.
3. The "Zero-Friction" SolutionAuto-Provisioning: A "Scan-to-Create" logic where the database adapts to the physical barcode, not the other way around.Async Processing: Submission handles the heavy lifting of creating records in bulk, keeping the UI snappy.Warranty Automation: Upon submission, the system calculates the warranty end-date based on the Item's predefined period, starting from the posting_date.
4. User Personas & Refined Workflow👤 Warehouse Dispatcher (The "Power Scanner")Goal: Scan 5,000+ units with zero clicks between scans.StepActionSystem Logic1. HeaderSelect Customer & Enter Invoice Number.Branch, Date, and Time are auto-filled and Locked (Read-Only) based on user profile.2. Item SelectionSelect/Enter Item Code.Filters the scanning logic to this specific product type.3. The ScanStart scanning Serial Numbers.JS Listener: Captures barcode, pushes to table, clears input. No "Searching..." spinner.4. SubmissionClick "Submit".Backend: Loops through 900+ rows. If Serial No exists, update it. If not, frappe.get_doc + insert.
5. Visual Wireflow (Conceptual)Code snippetgraph TD
    A[Start: New Warranty Dispatch] --> B[Auto-Fill: Branch/Date/Time]
    B --> C[Input: Customer & Invoice No]
    C --> D[Select: Item Code]
    D --> E[Field: 'READY TO SCAN']
    E --> F[Scan Barcode]
    F --> G{Serial in DB?}
    G -- Yes --> H[Link to Dispatch]
    G -- No --> I[Queue for Auto-Creation]
    H --> J[Submit]
    I --> J
    J --> K[Warranty Start = Today]
    K --> L[Finish: Dispatch Logged]

6. High-Level Functional RequirementsFR1: Automated Header: Use user_permission or Session User to hardcode the Branch so the user can't accidentally change it.FR2: Scan-to-Exist Engine: On on_submit, the system must check tabSerial No. If missing, it must create the record with:item_code: From the header.status: Active.warranty_start_date: Today.customer: Linked from header.FR3: RMA/Warranty Sync: The logic must mirror the behavior of a Delivery Note regarding warranty periods (e.g., if Item A has 12 months warranty, set warranty_expiry_date to Today + 12 months).FR4: Massive Batch Handling: Python logic must use frappe.db.commit() strategically or bulk inserts to ensure 5,000+ items don't timeout the server.




