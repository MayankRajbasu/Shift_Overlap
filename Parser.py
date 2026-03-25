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
def parse_major_events(lines):
    # if not lines:
    #     return "<h3>1. Major Events</h3><p>N/A</p>"

    # blocks = split_blocks(lines, "major")

    # html = ["<h3>1. Major Events</h3>"]

    # for block_lines in blocks:
    #     block = "\n".join(block_lines)

    #     title = extract(block, r'(cd?ddos.*|bgp.*|attack.*|incident.*)')

    #     html.append(f"""
    #     <b>{title if title != "N/A" else "Security Event"}</b><br><br>

    #     <b>Submitted by:</b> {extract(block, r'submitted by[:\s]+(.*)')}<br>
    #     <b>Case #:</b> {extract(block, r'case[:\s]+([\w-]+)')}<br>
    #     <b>Service:</b> {extract(block, r'service[:\s]+(.*)')}<br>
    #     <b>Start Time:</b> {extract(block, r'start[:\s]+(.*)')}<br>
    #     <b>End Time:</b> {extract(block, r'end[:\s]+(.*)')}<br>
    #     <b>Impact:</b> {extract(block, r'impact[:\s]+(.*)')}<br><br>

    #     <b>High-Level Description:</b><br>
    #     {extract(block, r'description[:\s]+([\s\S]*?)current')}<br><br>

    #     <b>Actions Taken:</b> {extract(block, r'action[s]?[:\s]+(.*)')}<br>
    #     <b>SIE Issued:</b> {extract(block, r'sie[:\s]+(.*)')}<br>
    #     <b>Affected Area:</b> {extract(block, r'area.*?:\s*(.*)')}<br>
    #     <b>Next Update:</b> {extract(block, r'next update[:\s]+(.*)')}<br>
    #     <hr>
    #     """)

    # return "".join(html)
    # if not lines:
    #     return "<h3>1. Major Events</h3><p>N/A</p>"

    # blocks = split_blocks(lines, "major")

    # unique_events = {}

    # for block_lines in blocks:
    #     block = "\n".join(block_lines)

    #     case = extract(block, r'case[:\s]+([\w-]+)').lower().strip()
    #     title = extract(block, r'(cd?Subject.*|ddos.*|bgp.*|attack.*|incident.*)').lower().strip()

    #     # Prefer Case as unique key, fallback to title
    #     key = case if case != "n/a" else title

    #     if key == "n/a":
    #         continue

    #     # Keep latest occurrence
    #     unique_events[key] = block

    # html = ["<h3>1. Major Events</h3>"]

    # for block in unique_events.values():
    #     html.append(f"""
    #     <b>{extract(block, r'(cd?ddos.*|bgp.*|attack.*|incident.*)')}</b><br><br>

    #     <b>Submitted by:</b> {extract(block, r'submitted by[:\s]+(.*)')}<br>
    #     <b>Case #:</b> {extract(block, r'case[:\s]+([\w-]+)')}<br>
    #     <b>Service:</b> {extract(block, r'service[:\s]+(.*)')}<br>
    #     <b>Start Time:</b> {extract(block, r'start[:\s]+(.*)')}<br>
    #     <b>End Time:</b> {extract(block, r'end[:\s]+(.*)')}<br>
    #     <b>Impact:</b> {extract(block, r'impact[:\s]+(.*)')}<br><br>

    #     <b>High-Level Description:</b><br>
    #     {extract(block, r'description[:\s]+([\s\S]*?)current')}<br><br>

    #     <b>Actions Taken:</b> {extract(block, r'action[s]?[:\s]+(.*)')}<br>
    #     <b>SIE Issued:</b> {extract(block, r'sie[:\s]+(.*)')}<br>
    #     <b>Affected Area:</b> {extract(block, r'area.*?:\s*(.*)')}<br>
    #     <b>Next Update:</b> {extract(block, r'next update[:\s]+(.*)')}<br>
    #     <hr>
    #     """)

    # return "".join(html)
    # def parse_major_events(lines):
    if not lines:
        return "<h3>1. Major Events</h3><p>N/A</p>"

    # Split multiple Major Event blocks
    blocks = split_blocks(lines, "major")

    unique_events = {}

    for block_lines in blocks:
        block = "\n".join(block_lines)

        # ✅ NEW: Title from Subject
        subject = extract(block, r'Subject[:\s]+(.*)')

        case = extract(block, r'case[:#\s]+([\w-]+)').lower().strip()

        # Use case if available, else subject as key
        key = case if case != "n/a" else subject.lower()

        if key == "n/a" or key == "":
            continue

        # Keep latest occurrence
        unique_events[key] = block

    html = ["<h3>1. Major Events</h3>"]

    for block in unique_events.values():

        html.append(f"""
        <b>{extract(block, r'Subject[:\s]+(.*)')}</b><br><br>

        <b>Submitted by:</b> {extract(block, r'Submitted by[:\s]+(.*)')}<br>
        <b>Case #:</b> {extract(block, r'Case[:#\s]+([\w-]+)')}<br>
        <b>Service:</b> {extract(block, r'Service[:\s]+(.*)')}<br>
        <b>Customer/Site:</b> {extract(block, r'Customer/Site[:\s]+(.*)')}<br>
        <b>Area of Impact:</b> {extract(block, r'Area of Impact[:\s]+(.*)')}<br>
        <b>Scrubbing Center:</b> {extract(block, r'Scrubbing Center.*?:\s*(.*)')}<br><br>

        <b>Start Time:</b> {extract(block, r'Event Start[:\s]+(.*)')}<br>
        <b>End Time:</b> {extract(block, r'Event End[:\s]+(.*)')}<br>
        <b>Impact:</b> {extract(block, r'impact[:\s]+(.*)')}<br>
        <b>SIE Issued:</b> {extract(block, r'SIE.*?:\s*(.*)')}<br><br>

        <b>High-Level Description:</b><br>
        {extract(block, r'High Level Description[:\s]+([\s\S]*?)impact')}<br><br>

        <b>Current Situation:</b> {extract(block, r'Current Situation[:\s]+(.*)')}<br>
        <b>Actions Taken:</b> {extract(block, r'Actions Taken[:\s]+(.*)')}<br>
        <b>Next Update:</b> {extract(block, r'Next Update[:\s]+(.*)')}<br>

        <hr>
        """)

    return "".join(html)

# ---------------- OPERATIONS ----------------
def parse_operations(lines):
    # if not lines:
    #     return "<h3>2. Operational Activities</h3><p>N/A</p>"

    # blocks = split_blocks(lines, "action performed")
    # html = ["<h3>2. Operational Activities</h3>"]

    # for b in blocks:
    #     block = "\n".join(b)

    #     html.append(f"""
    #     <b>{extract(block, r'Action Performed[:\s]+(.*)')}</b><br><br>
    #     <b>Reason:</b> {extract(block, r'Reason[:\s]+(.*)')}<br>
    #     <b>Time & Date:</b> {extract(block, r'Time[:\s]+(.*)')}<br>
    #     <b>Performed By:</b> {extract(block, r'(Who|By)[:\s]+(.*)')}<br>
    #     <b>PoP:</b> {extract(block, r'POP[:\s]+(.*)')}<br>
    #     <b>Devices:</b> {extract(block, r'Device[:\s]+(.*)')}<br>
    #     <hr>
    #     """)

    # return "".join(html)
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
    # if not lines:
    #     return "<h3>3. Customer Sessions</h3><p>N/A</p>"

    # blocks = split_blocks(lines, "session summary") + split_blocks(lines, "call summary")

    # html = ["<h3>3. Customer Sessions</h3>"]

    # for b in blocks:
    #     block = "\n".join(b)

    #     html.append(f"""
    #     <b>Customer:</b> {extract(block, r'Customer[:\s*]+(.*)')}<br>
    #     <b>Reported by:</b> {extract(block, r'Reported by[:\s*]+(.*)')}<br>
    #     <b>Product:</b> {extract(block, r'Product[:\s*]+(.*)')}<br>
    #     <b>Agenda:</b> {extract(block, r'Agenda[:\s*]+(.*)')}<br>
    #     <b>Planned:</b> {extract(block, r'Planned.*?:\s*(.*)')}<br>
    #     <b>Status:</b> {extract(block, r'Status[:\s*]+(.*)')}<br>
    #     <b>Notes:</b> {extract(block, r'(Notes|Case)[:\s*]+(.*)')}<br>
    #     <hr>
    #     """)

    # return "".join(html)
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
        <b>Notes:</b> {extract(block, r'(Notes|Case)[:\s*]+(.*)')}<br>
        <hr>
        """)

    return "".join(html)

# ---------------- DDOS (FIXED LOGIC) ----------------
def clean_field(val):
    val = re.sub(r'^(Customer name|Asset|Impact.*?(confirmed with customer).|Attack Size|Protection Engine|Attack Vector|Owner|Case|Service Type|Manual intervention|WebDDOS Status|Device Name)\s*', '', val, flags=re.IGNORECASE)
    # val = val.replace("radware.com", "radware.com")
    val = re.sub(r'(\d{6})(\d+)', r'\1-\2', val)
    return val.strip()

def parse_ddos_html(lines):
    if not lines:
        return "<hr><h3>4. DDoS and Security Events</h3> <br> <p>N/A</p>"

    headers = [
        "Customer", "Application / Policy", "Impact Confirmed", "Attack Size",
        "Attack Vector", "Protection Engine", "Owner",
        "Case #", "Service Type", "DDoS/WebDDoS", "Manual Intervention"
    ]

    records, current = [], []

    for line in lines:
        if re.match(r'1\.', line) and current:
            records.append(current)
            current = []
        current.append(line)

    if current:
        records.append(current)

    html = ["<h3>4. DDoS and Security Events</h3><table> <br>"]
    html.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")

    for record in records:
        data = [""] * 11
        service_type = ""

        for line in record:
            m = re.match(r'(\d+)\.\s*(.*)', line)
            if m:
                idx = int(m.group(1)) - 1
                val = clean_field(m.group(2))
                data[idx] = val

                if idx == 8:
                    service_type = val.lower()

        # Normalize CWAF values (Fix reversed issue)
        if "cwaf" in service_type:
            # If values are swapped → fix them
            # if data[9].lower() == "blocking" and data[10].lower() == "no":
            #     pass  # already correct
            # elif data[9].lower() == "no" and data[10].lower() == "blocking":
            # # elif data[9].lower() == "blocking" and data[10].lower() == "no":
            #     data[9], data[10] = data[10], data[9]  # swap
            if data[9].lower() == "blocking" and data[10].lower() == "no":
                pass  # already correct
            elif data[9].lower() == "Under Attack" and data[10].lower() == "no":
                pass  # already correct
            elif data[9].lower() == "no" and data[10].lower() == "blocking":
                data[9], data[10] = data[10], data[9]  # swap
            elif data[9].lower() == "no" and data[10].lower() == "under attack":
                data[9], data[10] = data[10], data[9]  # swap

        # CDDoS logic
        else:
            data[9] = "Blocking"
            data[10] = "—"

        html.append("<tr>" + "".join(f"<td>{c}</td>" for c in data) + "</tr>")

    html.append("</table>")
    return "".join(html)

# ---------------- REPORT ----------------
def generate_email_report(form, parsed_html):
    
    team = "<br>".join([t.strip() for t in form.get("team","").split("\n") if t.strip()])
    cases = "<br>".join([c.strip() for c in form.get("cases","").split("\n") if c.strip()])
    notes = "<br>".join([nt.strip() for nt in form.get("notes","").split("\n") if nt.strip()])

    return f"""
    <html>
    <body style="font-family:Arial">

    <p>Hi Team,<p>
    <p>Please find the shift overlap summary below.</p>

    <h2>Team Members on Shift:</h2>
    {team}

    <hr>
    
    {parsed_html}

    <hr>
    <h3>5. Cases to be Handled by Next Shift</h3>
    {cases if cases else "N/A"}

    <hr><h3>6. Additional Notes :</h3>
    {notes if notes else "N/A"}

    <hr>
    <h3>7. Statistics</h3>
    Number of "No value" cases: {form.get("novalue","N/A")}<br>
    Alerts NOC: {form.get("noc","N/A")}<br>
    Alerts SOC: {form.get("soc","N/A")}<br>

    </body>
    </html>
    """

def generate_report_html(raw_text):
    sections = classify_lines(clean_text(raw_text))

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
        text = request.form["text"]
        parsed = generate_report_html(text)

        output = generate_email_report(request.form, parsed)

    return render_template("home.html", output=output, text=text)

# @app.route("/", methods=["GET", "POST"])
# def home():
#     output = ""
#     form_data = {}

#     if request.method == "POST":
#         form_data = request.form.to_dict()

#         raw_text = form_data.get("text", "")
#         parsed = generate_report_html(raw_text)

#         output = generate_email_report(form_data, parsed)

#     return render_template("home.html", output=output, form=form_data)

if __name__ == "__main__":
    app.run(port=5020, debug=True)