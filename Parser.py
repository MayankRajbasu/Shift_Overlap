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
        elif re.search(r'action(?:\s+to\s+be)?\s+performed', l) or "reason for action" in l:
            # FIX: also catches "action to be performed"
            current_section = "operations"
        elif "session summary" in l or "call summary" in l:
            current_section = "session"
        elif re.match(r'\d+\.', line):
            current_section = "ddos"

        sections[current_section].append(line)

    return sections


# ---------------- COMMON ----------------
def extract(text, pattern, flags=re.IGNORECASE):
    # FIX: default flags to IGNORECASE so all callers benefit
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else "N/A"

def split_blocks(lines, pattern):
    # FIX: now uses re.search so regex patterns work correctly
    blocks, current = [], []

    for line in lines:
        if re.search(pattern, line, re.IGNORECASE) and current:
            blocks.append(current)
            current = []
        current.append(line)

    if current:
        blocks.append(current)

    return blocks


# ---------------- MAJOR EVENTS ----------------
def parse_major_events(lines):
    if not lines:
        return "<h3>1. Major Events</h3><p>N/A</p>"

    blocks = split_blocks(lines, r'major\s+event')

    unique_events = {}

    for block_lines in blocks:
        block = "\n".join(block_lines)

        subject = extract(block, r'Subject[:\s]+(.*)')
        case    = extract(block, r'Case[:#\s]+([\w-]+)').lower().strip()

        key = case if case != "n/a" else subject.lower().strip()

        if not key or key == "n/a":
            continue

        unique_events[key] = block

    if not unique_events:
        return "<h3>1. Major Events</h3><p>N/A</p>"

    html = ["<h3>1. Major Events</h3>"]

    for block in unique_events.values():
        def field(pattern, blk=block):
            val = extract(blk, pattern)
            return val if val.lower() != "n/a" else "N/A"

        html.append(f"""
        <b>{field(r'Subject[:\s]+(.*)')}</b><br><br>

        <b>Submitted by:</b> {field(r'Submitted\s+by[:\s]+(.*)')}<br>
        <b>Case #:</b> {field(r'Case[:#\s]+([\w-]+)')}<br>
        <b>Service:</b> {field(r'Service[:\s]+(.*)')}<br>
        <b>Customer/Site:</b> {field(r'Customer/Site[:\s]+(.*)')}<br>
        <b>Area of Impact:</b> {field(r'Area\s+of\s+Impact[:\s]+(.*)')}<br>
        <b>Scrubbing Center:</b> {field(r'Scrubbing\s+Center.*?:\s*(.*)')}<br><br>

        <b>Start Time:</b> {field(r'Event\s+Start[:\s]+(.*)')}<br>
        <b>End Time:</b> {field(r'Event\s+End[:\s]+(.*)')}<br>
        <b>Impact:</b> {field(r'Impact[:\s]+(.*)')}<br>
        <b>SIE Issued:</b> {field(r'SIE.*?:\s*(.*)')}<br><br>

        <b>High-Level Description:</b><br>
        {field(r'High\s+Level\s+Description[:\s]+([\s\S]*?)(?=Current Situation|Actions Taken|$)')}<br><br>

        <b>Current Situation:</b> {field(r'Current\s+Situation[:\s]+(.*)')}<br>
        <b>Actions Taken:</b> {field(r'Actions\s+Taken[:\s]+(.*)')}<br>
        <b>Next Update:</b> {field(r'Next\s+Update[:\s]+(.*)')}<br>
        <hr>
        """)

    return "".join(html)


# ---------------- OPERATIONS ----------------
def parse_operations(lines):
    if not lines:
        return "<h3>2. Operational Activities</h3><p>N/A</p>"

    blocks = split_blocks(lines, r'action(?:\s+to\s+be)?\s+performed')

    unique_ops = {}

    for b in blocks:
        block = "\n".join(b)

        action = extract(block, r'Action(?:\s+to\s+be)?\s+Performed[:\s]+(.*)').lower().strip()

        if not action or action == "n/a":
            continue

        unique_ops[action] = block

    if not unique_ops:
        # FIX: was missing — rendered empty <h3> when all blocks were N/A
        return "<h3>2. Operational Activities</h3><p>N/A</p>"

    html = ["<h3>2. Operational Activities</h3>"]

    for action, block in unique_ops.items():
        def field(pattern, blk=block):
            val = extract(blk, pattern)
            return val if val.lower() != "n/a" else "N/A"

        html.append(f"""
        <b>{field(r'Action(?:\s+to\s+be)?\s+Performed[:\s]+(.*)')}</b><br><br>

        <b>Reason:</b> {field(r'Reason[:\s]+(.*)')}<br>
        <b>Time & Date:</b> {field(r'Time[:\s]+(.*)')}<br>
        <b>Performed By:</b> {field(r'(?:Who\s+performed|Who|By)[:\s]+(.*)')}<br>
        <b>PoP:</b> {field(r'POP[:\s]+(.*)')}<br>
        <b>Devices:</b> {field(r'Device[:\s]+(.*)')}<br>
        <b>Jira:</b> {field(r'Jira\s+reference[:\s]+(.*)')}<br>
        <hr>
        """)

    return "".join(html)


# ---------------- SESSIONS ----------------
def parse_sessions(lines):
    if not lines:
        return "<h3>3. Customer Sessions</h3><p>N/A</p>"

    # FIX: deduplicate blocks from both split calls before processing
    seen = set()
    blocks = []
    for b in split_blocks(lines, r'session\s+summary') + split_blocks(lines, r'call\s+summary'):
        key = tuple(b)
        if key not in seen:
            seen.add(key)
            blocks.append(b)

    unique_sessions = {}

    for b in blocks:
        block = "\n".join(b)

        customer = extract(block, r'Customer[:\s*]+(.*)').lower().strip()
        agenda   = extract(block, r'Agenda[:\s*]+(.*)').lower().strip()

        key = f"{customer}-{agenda}"

        if customer == "n/a" and agenda == "n/a":
            continue

        unique_sessions[key] = block

    if not unique_sessions:
        return "<h3>3. Customer Sessions</h3><p>N/A</p>"

    html = ["<h3>3. Customer Sessions</h3>"]

    for block in unique_sessions.values():
        def field(pattern, blk=block):
            val = extract(blk, pattern)
            return val if val.lower() != "n/a" else "N/A"

        html.append(f"""
        <b>Customer:</b> {field(r'Customer[:\s*]+(.*)')}<br>
        <b>Reported by:</b> {field(r'Reported\s+by[:\s*]+(.*)')}<br>
        <b>Product:</b> {field(r'Product[:\s*]+(.*)')}<br>
        <b>Agenda:</b> {field(r'Agenda[:\s*]+(.*)')}<br>
        <b>Planned:</b> {field(r'Planned.*?:\s*(.*)')}<br>
        <b>Status:</b> {field(r'Status[:\s*]+(.*)')}<br>
        <b>Notes:</b> {field(r'(?:Notes|Case)[:\s*]+(.*)')}<br>
        <hr>
        """)

    return "".join(html)


# ---------------- DDOS ----------------
def clean_field(val):
    val = re.sub(
        r'^(Customer name|Asset|Impact.*?(confirmed with customer).|Attack Size|'
        r'Protection Engine|Attack Vector|Owner|Case|Service Type|Manual intervention|'
        r'WebDDOS Status|Device Name)\s*',
        '', val, flags=re.IGNORECASE
    )
    val = re.sub(r'(\d{6})(\d+)', r'\1-\2', val)
    return val.strip()

def parse_ddos_html(lines):
    if not lines:
        return "<hr><h3>4. DDoS and Security Events</h3><p>N/A</p>"

    headers = [
        "Customer", "Application / Policy", "Impact Confirmed", "Attack Size",
        "Attack Vector", "Protection Engine", "Owner",
        "Case #", "Service Type", "DDoS/WebDDoS", "Jira", "Manual Intervention"
    ]

    records, current = [], []

    for line in lines:
        if re.match(r'1\.', line) and current:
            records.append(current)
            current = []
        current.append(line)

    if current:
        records.append(current)

    html = ["<h3>4. DDoS and Security Events</h3><table><br>"]
    html.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")

    for record in records:
        data = [""] * 12
        service_type = ""

        for line in record:
            m = re.match(r'(\d+)\.\s*(.*)', line)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(data):
                    val = clean_field(m.group(2))
                    data[idx] = val
                    if idx == 8:
                        service_type = val.lower()

        if "cwaf" in service_type:
            d9  = data[9].lower()
            d11 = data[11].lower()
            # FIX: was comparing .lower() result to mixed-case strings like "Under Attack"
            if d9 in ("blocking", "under attack"):
                pass  # already correct order
            elif d11 in ("blocking", "under attack") and d9 in("no","yes"):
                data[9], data[11] = data[11], data[9]  # swap
        else:
            # CDDoS
            data[9]  = "Blocking"
            data[11] = "No"

        html.append("<tr>" + "".join(f"<td>{c}</td>" for c in data) + "</tr>")

    html.append("</table>")
    return "".join(html)


# ---------------- REPORT ----------------
def generate_email_report(form, parsed_html):
    team  = "<br>".join([t.strip()  for t in form.get("team",  "").split("\n") if t.strip()])
    cases = "<br>".join([c.strip()  for c in form.get("cases", "").split("\n") if c.strip()])
    notes = "<br>".join([nt.strip() for nt in form.get("notes", "").split("\n") if nt.strip()])

    return f"""
    <html>
    <body style="font-family:Arial">

    <p>Hi Team,</p>
    <p>Please find the shift overlap summary below.</p>

    <h2>Team Members on Shift:</h2>
    {team if team else "N/A"}

    <hr>

    {parsed_html}

    <hr>
    <h3>5. Cases to be Handled by Next Shift</h3>
    {cases if cases else "N/A"}

    <hr>
    <h3>6. Additional Notes:</h3>
    {notes if notes else "N/A"}

    <hr>
    <h3>7. Statistics</h3>
    Number of "No value" cases: {form.get("novalue", "N/A")}<br>
    Alerts NOC: {form.get("noc", "N/A")}<br>
    Alerts SOC: {form.get("soc", "N/A")}<br>

    </body>
    </html>
    """

def generate_report_html(raw_text):
    sections = classify_lines(clean_text(raw_text))

    return f"""
    <html>
    <head>
    <style>
        body {{ font-family: Arial; margin: 30px; background: #f7f9fb; }}
        h3 {{ border-bottom: 2px solid #2c3e50; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th {{ background: #979797; }}
        td, th {{ padding: 8px; border: 1px solid #ddd; }}
        tr:nth-child(even) {{ background: #f2f2f2; }}
        b {{ color: #2c3e50; }}
    </style>
    </head>
    <body>
    {parse_major_events(sections.get("major", []))}
    {parse_operations(sections.get("operations", []))}
    {parse_sessions(sections.get("session", []))}
    {parse_ddos_html(sections.get("ddos", []))}
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
        text   = request.form["text"]
        parsed = generate_report_html(text)
        output = generate_email_report(request.form, parsed)

    return render_template("home.html", output=output, text=text)

if __name__ == "__main__":
    app.run(port=5020, debug=True)