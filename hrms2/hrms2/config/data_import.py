import frappe
import re


def parse_sql_records(raw_text):
    text = raw_text.replace('\n', ' ').replace('\r', '')
    m = re.search(r"VALUES\s*(.+)", text, re.DOTALL)
    if not m:
        return []
    values = m.group(1).strip().rstrip(';').strip()
    records = []
    current = ''
    depth = 0
    for ch in values:
        if ch == '(':
            if depth == 0:
                current = ''
            else:
                current += ch
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                records.append(current)
            else:
                current += ch
        elif depth >= 1:
            current += ch
    return records


def parse_fields(rec):
    fields = []
    i = 0
    while i < len(rec):
        if rec[i] == "'":
            j = i + 1
            while j < len(rec):
                if rec[j] == "'":
                    if j + 1 < len(rec) and rec[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            fields.append(rec[i+1:j])
            i = j + 1
        elif rec[i:i+4].upper() == 'NULL':
            fields.append(None)
            i += 4
        elif rec[i] in ' ,':
            i += 1
        else:
            j = i
            while j < len(rec) and (rec[j].isdigit() or rec[j] in '.-'):
                j += 1
            if j > i:
                fields.append(rec[i:j])
                i = j
            else:
                i += 1
    return fields


def import_items():
    print("IMPORTING ITEMS")
    print("=" * 60)

    with open('/tmp/items_data.txt', 'r') as f:
        item_raw = f.read()

    records = parse_sql_records(item_raw)
    print(f"Found {len(records)} item records")

    existing_ig = set(frappe.db.sql_list("select name from `tabItem Group`"))
    existing_uoms = set(frappe.db.sql_list("select name from `tabUOM`"))

    imported = 0
    skipped = 0
    errors = 0

    for rec in records:
        fields = parse_fields(rec)
        if len(fields) < 12:
            skipped += 1
            continue

        # Item column positions (0-indexed):
        # [0]=name(item_code), [7]=naming_series, [8]=item_code,
        # [9]=item_name, [10]=item_group, [11]=stock_uom
        item_code = fields[0] if fields[0] else ''
        if not item_code:
            skipped += 1
            continue

        if frappe.db.exists('Item', item_code):
            skipped += 1
            continue

        item_name = fields[9] if (len(fields) > 9 and fields[9]) else item_code
        item_group = fields[10] if (len(fields) > 10 and fields[10]) else 'SSD'
        stock_uom = fields[11] if (len(fields) > 11 and fields[11]) else 'Nos'

        if item_group not in existing_ig:
            print(f"  Missing group '{item_group}' for {item_code}, using SSD")
            item_group = 'SSD'
        if stock_uom not in existing_uoms:
            stock_uom = 'Nos'

        try:
            doc = frappe.get_doc({
                'doctype': 'Item',
                'item_code': item_code,
                'item_name': item_name,
                'item_group': item_group,
                'stock_uom': stock_uom
            })
            doc.insert(ignore_permissions=True)
            imported += 1
            if imported % 20 == 0:
                frappe.db.commit()
                print(f"  {imported} items imported...")
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Error: {item_code} - {str(e)[:100]}")

    frappe.db.commit()
    print(f"\nItems: {imported} imported, {skipped} skipped, {errors} errors")
    print(f"Total Items: {frappe.db.count('Item')}")
    return imported


def run():
    # Customers were already imported - just import Items now
    result = import_items()
    print("\n" + "=" * 60)
    print(f"Item import complete: {result} items imported")

if __name__ == "__main__":
    run()
