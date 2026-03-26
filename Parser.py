import re
import unicodedata
from collections import defaultdict
from flask import Flask, request, render_template

# ---------------- CLEANING ----------------
def remove_emojis(text):
    return ''.join(c for c in text if not unicodedata.category(c).startswith('So'))

def strip_metadata(line):
    line = re.sub(r'^\[.*?\]\s*[^:]+:\s*', '', line)
    line = re.sub(r'^\d{1,2}[:.]\d{2}.*?\d{6,8}.*?\s', '', line)
    return line.strip()

def clean_text(text):
    return [remove_emojis(strip_metadata(l)).strip() for l in text.split('\n') if l.strip()]

# ---------------- CLASSIFICATION ----------------
def classify_lines(lines):
    sections = defaultdict(list)
    current_section = "general"

    for line in lines:
        l = line.lower()

        if "major event" in l:
            current_section = "major"
        elif "action performed" in l or "reason for action" in l:
            current_section = "operations"
        elif "session summary" in l or "call summary" in l:
            current_section = "session"
        elif re.match(r'\d+\.', line):
            current_section = "ddos"

        sections[current_section].append(line)

    return sections

# ---------------- COMMON ----------------
def extract(block, pattern):
    m = re.search(pattern, block, re.IGNORECASE)
    return m.group(1).strip() if m else "N/A"

def split_blocks(lines, keyword):
    blocks, current = [], []

    for line in lines:
        if keyword in line.lower() and current:
            blocks.append(current)
            current = []
        current.append(line)

    if current:
        blocks.append(current)

    return blocks

# ---------------- MAJOR EVENTS ----------------

def parse_major_events(text):

    major_events = []

    # Split WhatsApp lines
    lines = text.splitlines()

    current_block = []
    capturing = False

    for line in lines:

        # Remove whatsapp timestamp prefix
        clean_line = re.sub(r"^\d{4}/\d{2}/\d{2},.*?:\s", "", line).strip()

        # Remove stars
        clean_line = clean_line.replace("*", "").strip()

        # Detect start of Major Event
        if "Major Event" in clean_line or "Major event on" in clean_line:
            capturing = True
            current_block = [clean_line]
            continue

        if capturing:
            # Stop if new timestamp detected
            if re.match(r"^\d{4}/\d{2}/\d{2},", line):
                major_events.append("\n".join(current_block))
                capturing = False
            else:
                current_block.append(clean_line)

    # Append last block
    if current_block:
        major_events.append("\n".join(current_block))

    parsed_major = []

    for block in major_events:
        event = {}

        def extract(pattern):
            match = re.search(pattern, block, re.IGNORECASE)
            return match.group(1).strip() if match else "N/A"

        event["subject"] = extract(r"Subject\s*:\s*(.+)")
        event["submitted"] = extract(r"Submitted by\s*:\s*(.+)")
        event["case"] = extract(r"Case\s*#\s*:\s*(.+)")
        event["service"] = extract(r"Service\s*:\s*(.+)")
        event["customer"] = extract(r"Customer/Site\s*:\s*(.+)")
        event["area"] = extract(r"Area of Impact\s*:\s*(.+)")
        event["scrubbing"] = extract(r"Scrubbing Center.*?:\s*(.+)")
        event["start"] = extract(r"Event Start\s*:\s*(.+)")
        event["end"] = extract(r"Event End\s*:\s*(.+)")
        event["impact"] = extract(r"impact\s*:\s*(.+)")
        event["sie"] = extract(r"SIE.*?:\s*(.+)")
        event["description"] = extract(r"High Level Description\s*:\s*(.+)")
        event["current"] = extract(r"Current Situation\s*:\s*(.+)")
        event["actions"] = extract(r"Actions Taken\s*:\s*(.+)")
        event["next"] = extract(r"Next Update\s*:\s*(.+)")

        parsed_major.append(event)

    return parsed_major

def deduplicate_events(events):
    unique = []
    seen = set()

    for e in events:
        key = (e['subject'], e['case'], e['start'])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique

# ---------------- OPERATIONS ----------------

def parse_operations(lines):
    if not lines:
        return "<h3>2. Operational Activities</h3><p>N/A</p>"

    blocks = split_blocks(lines, "action performed")

    unique_ops = {}
    
    for b in blocks:
        block = "\n".join(b)

        action = extract(block, r'Action Performed[:\s]+(.*)').lower().strip()

        # Skip empty
        if action == "n/a":
            continue

        # Always overwrite → keeps latest occurrence
        unique_ops[action] = block

    html = ["<h3>2. Operational Activities</h3>"]

    for action, block in unique_ops.items():
        html.append(f"""
        <b>{extract(block, r'Action Performed[:\s]+(.*)')}</b><br><br>

        <b>Reason:</b> {extract(block, r'Reason[:\s]+(.*)')}<br>
        <b>Time & Date:</b> {extract(block, r'Time[:\s]+(.*)')}<br>
        <b>Performed By:</b> {extract(block, r'Who performed[:\s]+(.*)')}<br>
        <b>PoP:</b> {extract(block, r'POP[:\s]+(.*)')}<br>
        <b>Devices:</b> {extract(block, r'Device[:\s]+(.*)')}<br>
        <b>Jira:</b> {extract(block, r'Jira reference[:\s]+(.*)')}<br> 
        <hr>
        """)

    return "".join(html)

# ---------------- SESSIONS ----------------

def parse_sessions(lines):
    if not lines:
        return "<h3>3. Customer Sessions</h3><p>N/A</p>"

    # Combine both types of session blocks
    blocks = split_blocks(lines, "session summary") + split_blocks(lines, "call summary")

    unique_sessions = {}

    for b in blocks:
        block = "\n".join(b)

        customer = extract(block, r'Customer[:\s*]+(.*)').lower().strip()
        agenda = extract(block, r'Agenda[:\s*]+(.*)').lower().strip()

        # Unique key → Customer + Agenda
        key = f"{customer}-{agenda}"

        if customer == "n/a" and agenda == "n/a":
            continue

        # Keep latest occurrence
        unique_sessions[key] = block

    html = ["<h3>3. Customer Sessions</h3>"]

    for block in unique_sessions.values():
        html.append(f"""
        <b>Customer:</b> {extract(block, r'Customer[:\s*]+(.*)')}<br>
        <b>Reported by:</b> {extract(block, r'Reported by[:\s*]+(.*)')}<br>
        <b>Product:</b> {extract(block, r'Product[:\s*]+(.*)')}<br>
        <b>Agenda:</b> {extract(block, r'Agenda[:\s*]+(.*)')}<br>
        <b>Planned:</b> {extract(block, r'Planned.*?:\s*(.*)')}<br>
        <b>Status:</b> {extract(block, r'Status[:\s*]+(.*)')}<br>
        <b>Notes:</b> {extract(block, r'Notes[:\s*]+(.*)')}<br>
        <hr>
        """)

    return "".join(html)

# ---------------- DDOS & WebDDoS Alerts ----------------

def parse_ddos_events(text):
    ddos_events = []

    # Split by WhatsApp timestamp lines
    messages = re.split(r'\d{4}/\d{2}/\d{2},.*?:', text)

    for msg in messages:
        if "1. Customer name" in msg:

            event = {}

            def extract(field):
                pattern = rf"{field}\s*(.+)"
                match = re.search(pattern, msg)
                return match.group(1).strip() if match else ""

            event["customer"] = extract(r"1\. Customer name")
            event["asset"] = extract(r"2\. Asset")
            event["impact"] = extract(r"3\. Impact.*")
            event["attack_size"] = extract(r"4\. Attack Size")
            event["protection_engine"] = extract(r"5\. Protection Engine")
            event["attack_vector"] = extract(r"6\. Attack Vector")
            event["owner"] = extract(r"7\. Owner")
            event["case"] = extract(r"8\. Case")
            event["service"] = extract(r"9\. Service Type")
            event["manual"] = extract(r"10\. Manual intervention")

            # Can be either WebDDOS Status or Device Name
            status_match = re.search(r"11\. WebDDOS Status\s*(.+)", msg)
            device_match = re.search(r"11\. Device Name\s*(.+)", msg)

            event["status"] = (
                status_match.group(1).strip()
                if status_match else
                (device_match.group(1).strip() if device_match else "")
            )

            ddos_events.append(event)

    return ddos_events

# ---------------- REPORT ----------------

def generate_report_html(raw_text):
    sections = classify_lines(clean_text(raw_text))

    # major_events = parse_major_events(raw_text)

    return f"""
    <html>
    <head>
    <style>
        body {{ font-family: Arial; margin: 30px; background:#f7f9fb; }}
        h3 {{ border-bottom:2px solid #2c3e50; }}
        table {{ border-collapse: collapse; width:100%; }}
        th {{ background:#979797; }}
        td, th {{ padding:8px; border:1px solid #ddd; }}
        tr:nth-child(even) {{ background:#f2f2f2; }}
        b {{ color:#2c3e50; }}
    </style>
    </head>
    <body>
    {parse_operations(sections.get("operations", []))}
    {parse_sessions(sections.get("session", []))}

    </body>
    </html>
    """

def generate_email_report(form, parsed_html, ddos_events, parsed_major):

    team = "<br>".join([t.strip() for t in form.get("team", "").split("\n") if t.strip()])
    cases = "<br>".join([c.strip() for c in form.get("cases", "").split("\n") if c.strip()])
    notes = "<br>".join([nt.strip() for nt in form.get("notes", "").split("\n") if nt.strip()])

    # ------ Major events --------------
    parsed_major = deduplicate_events(parsed_major)

    major = ""

    for e in parsed_major:

        # Impact should be derived from subject
        impact_line = ""
        if "analysis at" in e["subject"]:
            impact_line = e["subject"].split("Major event on")[-1].strip()

        major += f"""
            <b>{e['subject']}</b><br><br>

            <b>Submitted by:</b> {e['submitted']}<br>
            <b>Case #:</b> {e['case']}<br>
            <b>Service:</b> {e['service']}<br>
            <b>Customer/Site:</b> {e['customer']}<br>
            <b>Area of Impact:</b> {e['area']}<br>
            <b>Scrubbing Center:</b> {e['scrubbing']}<br><br>

            <b>Start Time:</b> {e['start']}<br>
            <b>End Time:</b> {e['end']}<br>
            <b>Impact:</b> {impact_line}<br>
            <b>SIE Issued:</b> {e['sie']}<br><br>

            <b>High-Level Description:</b><br>
            {e['description']}<br><br>

            <b>Current Situation:</b> {e['current']}<br>
            <b>Actions Taken:</b> {e['actions']}<br>
            <b>Next Update:</b> {e['next']}<br>

            <hr>
            """


    # -------- Build DDoS table rows in Python --------
    ddos_rows = ""
    for e in ddos_events:
        ddos_rows += f"""
        <tr>
            <td>{e.get('customer','')}</td>
            <td>{e.get('asset','')}</td>
            <td>{e.get('impact','')}</td>
            <td>{e.get('attack_size','')}</td>
            <td>{e.get('attack_vector','')}</td>
            <td>{e.get('protection_engine','')}</td>
            <td>{e.get('owner','')}</td>
            <td>{e.get('case','')}</td>
            <td>{e.get('service','')}</td>
            <td>{e.get('status','')}</td>
            <td>{e.get('manual','')}</td>
        </tr>
        """

    ddos_table = f"""
    <h3>4. DDoS and WebDDoS Alert Events</h3>
    <table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;">
        <tr style="background:#6d8dac;color:white;">
            <th>Customer</th>
            <th>Application / Policy</th>
            <th>Impact Confirmed</th>
            <th>Attack Size</th>
            <th>Attack Vector</th>
            <th>Protection Engine</th>
            <th>Owner</th>
            <th>Case #</th>
            <th>Service Type</th>
            <th>WebDDoS Status / DDoS Device</th>
            <th>Manual Intervention</th>
        </tr>
        {ddos_rows if ddos_rows else "<tr><td colspan='11'>No events found</td></tr>"}
    </table>
    """

    return f"""
    <html>
    <body style="font-family:Arial">

    <p>Hi Team,</p>
    <p>Please find the shift overlap summary below.</p>

    <h2>Team Members on Shift:</h2>
    {team if team else "N/A"}

    <hr>
                     
    <h3>Major Event</h3>
    {major}

    <hr>
    
    {parsed_html}

    <hr>

    {ddos_table}

    <hr>
    <h3>5. Cases to be Handled by Next Shift</h3>
    {cases if cases else "N/A"}

    <hr>
    <h3>6. Additional Notes :</h3>
    {notes if notes else "N/A"}

    <hr>
    <h3>7. Statistics</h3>
    Number of "No value" cases: {form.get("novalue","N/A")}<br>
    Alerts NOC: {form.get("noc","N/A")}<br>
    Alerts SOC: {form.get("soc","N/A")}<br>

    </body>
    </html>
    """

# ---------------- FLASK ----------------

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    output = ""
    text = ""

    if request.method == "POST":
        text = request.form["text"]
        parsed_html = generate_report_html(text)
        ddos_events = parse_ddos_events(text)
        parsed_major = parse_major_events(text)

        output = generate_email_report(request.form, parsed_html, ddos_events,parsed_major)
    return render_template("home.html", output=output, text=text)

if __name__ == "__main__":
    app.run(port=5020, debug=True)