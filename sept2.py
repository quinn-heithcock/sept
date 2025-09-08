import streamlit as st
import pdfplumber
import re

# ------------------ ARCHITECTURAL EXTRACTOR ------------------
def extract_store_info(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        page = pdf.pages[0]
        text = page.extract_text()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\b(?:[A-Z]-\d{3}[A-Z]?|[A-Z] \d\.\d)\b', '', text)

    start_pos = re.search(r'STORE\s*#\s*\d+', text, re.IGNORECASE)
    if start_pos:
        text = text[start_pos.start():]

    store_pattern = r'S(?i:TORE)\s*#\s*\d+'
    space_pattern = r'(?:S(?i:pace)|S(?i:uite)) #?\w+'
    mall_pattern = r'\b([A-Z][a-z]+(?: (?:[a-z]+|[A-Z][a-z]+)){0,4})\b'
    address_pattern = r'(\d{1,5}(?: [A-Z]\.)?(?: [A-Z][a-z]{1,15}){1,3})'
    city_state_pattern = r'([A-Z][a-z]+(?: [A-Z][a-z]+)*,?\s*[A-Z]{2},?\s*\d{5}(?:-\d{4})?)'

    store_match = re.search(store_pattern, text)
    mall_text = text[store_match.end():store_match.end() + 300] if store_match else text

    mall_match = re.search(mall_pattern, mall_text)
    space_match = re.search(space_pattern, text)

    address_text = text[space_match.end():space_match.end() + 300] if space_match else text
    address_match = re.search(address_pattern, address_text)
    city_state_match = re.search(city_state_pattern, address_text)

    parts = [
        "JOURNEYS " + store_match.group() if store_match else "ERROR_store_not_found",
        mall_match.group(1) if mall_match else "ERROR_mall_not_found",
        space_match.group() if space_match else "ERROR_space_not_found",
        address_match.group(1) if address_match else "ERROR_address_not_found",
        city_state_match.group(1) if city_state_match else "ERROR_city_state_not_found"
    ]

    return "\n".join(filter(None, parts))


# ------------------ QUOTE EXTRACTORS ------------------
def extract_quote_info_accel(pdf_file):
    quote_number = None
    quote_amount = None

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            quote_number_match = re.search(r'Order Acknowledgement #\s*([\w-]+)', text)
            if quote_number_match:
                quote_number = quote_number_match.group(1)
            quote_amount_match = re.search(
                r'Grand Total \(Payable in U\.S\. Dollars\):\s*\$?([\d,]+\.\d{2})', text
            )
            if quote_amount_match:
                quote_amount = quote_amount_match.group(1)
            if quote_number and quote_amount:
                break

    return {"Quote Number": quote_number or "Not Found", "Quote Amount": quote_amount or "Not Found"}


def extract_quote_info_ceildeck(pdf_file):
    date = None
    distributor_info = []
    total_cost = None
    delivery_cost = None

    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    date_match = re.search(r"DATE:\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
    if date_match:
        date = date_match.group(1)

    total_match = re.search(r"TOTAL\s*\$\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if total_match:
        total_cost = total_match.group(1)

    delivery_match = re.search(r"DELIVERY\s*\$\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
    if delivery_match:
        delivery_cost = delivery_match.group(1)

    lines = text.splitlines()
    distributor_info = []
    capture = False

    for i, line in enumerate(lines):
        if not capture:
            match = re.search(r"Distrubitor:\s*(.*?)\s*TOTAL\s*\$\s*[\d,]+\.\d{2}", line, re.IGNORECASE)
            if match:
                distributor_info.append(match.group(1).strip())  
                capture = True
                continue
        elif capture:
            distributor_info.append(line.strip())

    distributor_block = "\n".join(distributor_info).strip()

    return {
        "Date": date or "Not Found",
        "Distributor Info": distributor_block or "Not Found",
        "Total Cost": total_cost or "Not Found",
        "Delivery Cost": delivery_cost or "Not Found"
    }


def extract_quote_info_louisville(pdf_file):
    product_keywords = {
        "ULTIMATE 6": "Ultimate 6",
        "GRAY ASH": "Gray Ash",
        "REFLEX NIGHT": "Reflex Night",
        "RONDEC": "Rondec",
        "TEC65-934N-25": "Slate Gray",
        "TEC65-941-25": "Raven",
        "HD CLIPS": "HD Clips",
        "LEVELING": "Leveling"
    }

    results = {}
    quote_date = None

    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    quotation_sections = [m.start() for m in re.finditer(r"QUOTATION", text)]
    if len(quotation_sections) >= 2:
        slice_start = quotation_sections[1]
        snippet = text[slice_start : slice_start + 100]
        date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{2}\b", snippet)
        if date_match:
            quote_date = date_match.group(0)
    
    for line in text.splitlines():
        for keyword, name in product_keywords.items():
            if keyword in line.upper():
                match = re.search(r"(\d{1,5}\.\d{2})", line)
                if match:
                    qty = float(match.group(1))
                    results[name] = qty

    results["Quote Date"] = quote_date or "Not Found"
    return results


def extract_quote_info_nds(pdf_file):
    total = quote_number = quote_date = "Not Found"

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            if quote_number == "Not Found":
                m = re.search(r'Quote(?: Number)?:?\s*#?\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
                if m:
                    quote_number = m.group(1)

            if total == "Not Found":
                m = re.search(r'Total:\s*\$?([0-9,]+\.\d{2})', text, re.IGNORECASE)
                if m:
                    total = m.group(1)

            if quote_date == "Not Found":
                m = re.search(r'QUOTE DATE', text, re.IGNORECASE)
                if m:
                    snippet = re.sub(r'\s+', ' ', text[m.start():m.start()+100].replace("\n", " "))
                    d1 = re.search(r'\b(0[1-9]|1[0-2])/([0][1-9]|[12][0-9]|3[01])/[0-9]{4}\b', snippet)
                    if d1:
                        quote_date = d1.group(0)
                    else:
                        d2 = re.search(r'(0[1-9]|1[0-2])/([0][1-9]|[12][0-9]|3[01])/[^0-9]*([0-9]{4})', snippet)
                        if d2:
                            quote_date = f"{d2.group(1)}/{d2.group(2)}/{d2.group(3)}"

    return {
        "Quote Number": quote_number,
        "Quote Date": quote_date,
        "Total": total
    }

# ------------------ VENDOR MAPPING ------------------
VENDOR_SCRIPTS = {
    "Accel": extract_quote_info_accel,
    "Ceildeck": extract_quote_info_ceildeck,
    "Louisville Tile 24X24": extract_quote_info_louisville,
    "NDS": extract_quote_info_nds
}

# ------------------ STREAMLIT APP ------------------
# Title with image
st.markdown("<h1 style='display: inline-block;'>Q's PO Helper</h1>", unsafe_allow_html=True)
st.image("fish.jpg", width=300)  # make the image much bigger
st.write("---")

# === 1. ARCHITECTURE PDF ===
st.header("Architecturals - Extract Address")
arch_file = st.file_uploader("Upload Architectural PDF", type=["pdf"], key="arch")

if arch_file:
    try:
        result = extract_store_info(arch_file)
        st.text_area("Extracted Address", result, height=200)
    except Exception as e:
        st.error(f"Error extracting address: {e}")

# === 2. QUOTE PDF ===
st.header("Quote PDF - Extract Quote Info")
vendor = st.selectbox("Select Vendor", list(VENDOR_SCRIPTS.keys()))
quote_file = st.file_uploader("Upload Quote PDF", type=["pdf"], key="quote")

if quote_file and vendor:
    try:
        result = VENDOR_SCRIPTS[vendor](quote_file)
        quote_text = "\n".join(f"{key}: {value}" for key, value in result.items())
        st.text_area("Extracted Quote Info", quote_text, height=200)
    except Exception as e:
        st.error(f"Error extracting quote info: {e}")

# === 3. EMAIL GENERATOR ===
st.header("📧 Email Template Generator")
store_city = st.text_input("Store # and City", value="")
delivery_date = st.text_area("Delivery Date", value="", height=100)
construction_dates = st.text_area("Construction Dates", value="", height=100)
store_address = st.text_area("Store Address", value="", height=100)
super_info = st.text_area("Super Info", value="", height=100)
design_type = st.text_input("Design Type", value="")
distro_number= st.text_input("Distro #", value="")

def fill(value):
    return value if value.strip() else "<blank>"

email_templates = {
    "Plan Distribution": f"""
JY # {fill(store_city)} / Plan Distribution - Design {fill(design_type)}

Hi everyone,

See attached plans for Journeys # {fill(store_city)}.

Vendors – please advise with any questions or concerns and submit your quotes by {fill(delivery_date)}.

Best,
""",
    "Delivery Dates (Accel, Regency, Ceildeck, LT)": f"""
Y- {fill(store_city)} // Delivery Dates

Hi,

Please schedule this to deliver {fill(delivery_date)}.

Super:
{fill(super_info)}

Best,
""",
    "Delivery (FE Rough and Trim)": f"""
Y- {fill(store_city)} // Delivery Dates

Hi David,

Please schedule the following to deliver:
{fill(delivery_date)}

Construction Dates:
{fill(construction_dates)}

Super:
{fill(super_info)}

Best,
""",
    "Delivery (FE PM check Only)": f"""
Y- {fill(store_city)} / Construction Dates

Hi David,

Please see below construction dates and contact for this project. This is for the PM check.

{fill(construction_dates)}

Super:
{fill(super_info)}

Thanks,
""",
    "Construction Dates (Wolf Metal)": f"""
Y- {fill(store_city)} / Construction Dates

Hi Mike,

Here are the construction dates for this project:

{fill(construction_dates)}

Super:
{fill(super_info)}

Best,
""",
    "Sign Install and Construction Dates": f"""
Y- {fill(store_city)} // Delivery Dates

Hi,

The sign install date for this project is {fill(delivery_date)}.

Please coordinate with the super accordingly.

Super:
{fill(super_info)}

Construction Dates:
{fill(construction_dates)}

Best,
""",
    "Distro Email (TP/PT)": f"""
DISTRO# {fill(distro_number)}  / Journeys #{fill(store_city)} - TP/PT Holders

Hello,
 
Please be on the lookout for Distro # {fill(distro_number)}:
 
QTY (1) 5221 – TP Holder
QTY (1) 5222 – PT Holder
Set needs to be New & Matching.

SHIP GROUND:
{fill(store_address)}

Contact:
{fill(super_info)}

Best,
"""
}

selected_email_template = st.selectbox("Choose an Email Template", list(email_templates.keys()))
email_content = email_templates[selected_email_template]

# Display email text area
st.text_area("Generated Email", email_content, height=400)

# === 4. TEAM EMAIL LIST ===
st.header("📧 Team Email List")

# Define your different groups here
email_groups = {
    "Quinn": "atorres1@genesco.com; oholmes@genesco.com; jshelton@genesco.com",
    "Anthony": "qheithcock@genesco.com; oholmes@genesco.com; jshelton@genesco.com",
    "Shae": "atorres1@genesco.com; qheithcock@genesco.com; jshelton@genesco.com",
    "Jeanette": "atorres1@genesco.com; oholmes@genesco.com; qheithcock@genesco.com"
}

# Dropdown to select group
selected_group = st.selectbox("Who are you?", list(email_groups.keys()))

# Display the selected email list
st.text_area("Copy these emails:", email_groups[selected_group], height=100)

