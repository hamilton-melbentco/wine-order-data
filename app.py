import streamlit as st
import streamlit.components.v1 as components
from PIL import Image
from google import genai
from streamlit_paste_button import paste_image_button as pbutton
import io
import hashlib

# 1. Page Configuration & UI Initialization
st.set_page_config(page_title="🥂 Wine Order Extractor", layout="wide")
st.title("🍾 Wine Order Image Data Extractor")
st.write("Upload or paste one or more data table screenshots to extract details, modify fields live, and generate ready-to-copy templates.")

# --- Sidebar API Key Configuration ---
st.sidebar.subheader("🔑 API Configuration")
if 'user_api_key' not in st.session_state:
    st.session_state.user_api_key = ""

api_key_input = st.sidebar.text_input(
    "Gemini API Key",
    value=st.session_state.user_api_key,
    type="password",
    placeholder="Paste your key here...",
    help="Enter your Gemini API key to enable image data extraction."
)

if api_key_input:
    st.session_state.user_api_key = api_key_input

# 2. Initialize Gemini Client using the sidebar input or environment fallback
client = None
if st.session_state.user_api_key.strip():
    try:
        client = genai.Client(api_key=st.session_state.user_api_key.strip())
    except Exception as e:
        st.sidebar.error(f"Invalid API Key initialization: {e}")

# Initialize default session state variables if they don't exist yet
# (left blank on purpose — the sample names/numbers now show only as grayed-out hint text)
if 'full_name' not in st.session_state:
    st.session_state.full_name = ""
if 'first_name' not in st.session_state:
    st.session_state.first_name = ""
if 'last_name' not in st.session_state:
    st.session_state.last_name = ""
if 'partner_name' not in st.session_state:
    st.session_state.partner_name = ""
if 'contact_number' not in st.session_state:
    st.session_state.contact_number = ""
if 'booking_owner' not in st.session_state:
    st.session_state.booking_owner = ""
if 'formatted_address' not in st.session_state:
    st.session_state.formatted_address = ""
if 'missing_fields' not in st.session_state:
    st.session_state.missing_fields = []

# JavaScript component listener to sync text input states
query_params = st.query_params
for key in ['full_name', 'formatted_address', 'first_name', 'last_name', 'contact_number', 'partner_name', 'booking_owner']:
    if f"sync_{key}" in query_params:
        st.session_state[key] = query_params[f"sync_{key}"]

# --- Helper: detect empty / placeholder-ish extraction values ---
MISSING_TOKENS = {"", "n/a", "na", "none", "null", "-", "unknown", "not found", "not available", "nil"}

def is_missing(value):
    if value is None:
        return True
    return value.strip().lower() in MISSING_TOKENS

# --- Custom Component Builders ---

def create_embedded_copy_input(label, current_value, state_key, flag_missing=False, placeholder=""):
    safe_val = current_value.replace('"', '&quot;')
    safe_placeholder = placeholder.replace('"', '&quot;')
    border_color = "#E05252" if flag_missing else "#4A4B57"
    label_suffix = " ⚠️ missing" if flag_missing else ""
    label_color = "#E88888" if flag_missing else "#E6E6E6"
    html_code = f"""
    <div style="font-family: sans-serif; margin-bottom: 18px; position: relative; width: 100%;">
        <style>
            #input_{state_key}::placeholder {{
                color: #6B6C76;
                font-style: italic;
                opacity: 1;
            }}
        </style>
        <label style="display: block; font-size: 14px; color: {label_color}; font-weight: 500; margin-bottom: 6px;">{label}{label_suffix}</label>
        <div style="position: relative; display: flex; align-items: center; width: 100%;">
            <input type="text" id="input_{state_key}" value="{safe_val}" placeholder="{safe_placeholder}" oninput="syncToStreamlit()" style="
                width: 100%;
                background-color: #262730;
                color: #FFFFFF;
                border: 1px solid {border_color};
                padding: 10px 42px 10px 14px;
                border-radius: 6px;
                font-size: 15px;
                outline: none;
                box-sizing: border-box;
            " />
            <button id="icon_{state_key}" onclick="copyText()" title="Copy to clipboard" style="
                position: absolute;
                right: 4px;
                background: transparent;
                border: none;
                color: #808495;
                cursor: pointer;
                padding: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                outline: none;
            ">
                <svg id="svg_copy_{state_key}" xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                <svg id="svg_check_{state_key}" xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#24A0ED" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display: none;"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </button>
        </div>
    </div>
    <script>
    function copyText() {{
        const inputEl = document.getElementById("input_{state_key}");
        navigator.clipboard.writeText(inputEl.value).then(() => {{
            const copyIcon = document.getElementById("svg_copy_{state_key}");
            const checkIcon = document.getElementById("svg_check_{state_key}");
            copyIcon.style.display = "none";
            checkIcon.style.display = "inline-block";
            setTimeout(() => {{
                checkIcon.style.display = "none";
                copyIcon.style.display = "inline-block";
            }}, 1500);
        }}).catch(err => {{ alert("Failed to copy text: " + err); }});
    }}
    function syncToStreamlit() {{
        const val = document.getElementById("input_{state_key}").value;
        const url = new URL(window.parent.location.href);
        url.searchParams.set("sync_{state_key}", val);
        window.parent.history.replaceState({{}}, "", url.toString());
    }}
    </script>
    """
    components.html(html_code, height=78 if not flag_missing else 78)

def create_embedded_copy_textarea(label, current_value, unique_id, height=130):
    safe_val = current_value.replace('"', '&quot;')
    html_code = f"""
    <div style="font-family: sans-serif; margin-bottom: 18px; position: relative; width: 100%;">
        {f'<label style="display: block; font-size: 14px; color: #E6E6E6; font-weight: 500; margin-bottom: 6px;">{label}</label>' if label else ''}
        <div style="position: relative; display: flex; width: 100%;">
            <textarea id="textarea_{unique_id}" style="
                width: 100%;
                height: {height}px;
                background-color: #262730;
                color: #FFFFFF;
                border: 1px solid #4A4B57;
                padding: 12px 46px 12px 14px;
                border-radius: 6px;
                font-size: 15px;
                outline: none;
                resize: none;
                box-sizing: border-box;
                font-family: sans-serif;
                line-height: 1.4;
                overflow-y: hidden;
            ;">{safe_val}</textarea>
            <button id="icon_{unique_id}" onclick="copyLargeText()" title="Copy to clipboard" style="
                position: absolute;
                top: 6px;
                right: 6px;
                background: transparent;
                border: none;
                color: #808495;
                cursor: pointer;
                padding: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                border-radius: 4px;
                outline: none;
            ">
                <svg id="svg_copy_{unique_id}" xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                <svg id="svg_check_{unique_id}" xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#24A0ED" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="display: none;"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </button>
        </div>
    </div>
    <script>
    function copyLargeText() {{
        const txtEl = document.getElementById("textarea_{unique_id}");
        navigator.clipboard.writeText(txtEl.value).then(() => {{
            const copyIcon = document.getElementById("svg_copy_{unique_id}");
            const checkIcon = document.getElementById("svg_check_{unique_id}");
            copyIcon.style.display = "none";
            checkIcon.style.display = "inline-block";
            setTimeout(() => {{
                checkIcon.style.display = "none";
                copyIcon.style.display = "inline-block";
            }}, 1500);
        }}).catch(err => {{ alert("Failed to copy text: " + err); }});
    }}
    </script>
    """
    components.html(html_code, height=height + (30 if label else 10))

def create_dan_murphys_link_button(label, url):
    html_code = f"""
    <a href="{url}" target="_blank" style="text-decoration: none;">
        <button style="
            background-color: #0F522B;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            font-size: 14px;
            font-family: sans-serif;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.2);
            margin-top: 10px;
        ">
            {label}
        </button>
    </a>
    """
    components.html(html_code, height=55)

# --- Sidebar Input Section (Upload or Click-to-Paste Button) ---
st.sidebar.write("---")
st.sidebar.subheader("📥 Input Screenshot(s)")
st.sidebar.caption("1️⃣ Enter your Gemini API key above.  2️⃣ Paste or upload snip(s) below.  3️⃣ Press **Process** when ready.")

# Option 1: File Uploader (supports multiple files at once)
uploaded_files = st.sidebar.file_uploader(
    "Upload Image File(s)",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True
)

# Option 2: Direct "Paste Snip from Clipboard" Button (click once per snip to add it to the batch)
st.sidebar.markdown("<p style='font-size:14px; color:#E6E6E6; font-weight:500; margin-bottom:4px;'>Or Paste Directly from Clipboard</p>", unsafe_allow_html=True)

# Batch of pasted images lives in session_state so it survives reruns.
if 'pasted_batch' not in st.session_state:
    st.session_state.pasted_batch = []   # list of {"image": PIL.Image, "hash": str}
if 'last_paste_hash' not in st.session_state:
    st.session_state.last_paste_hash = None

with st.sidebar:
    paste_result = pbutton("📋 Add Snip from Clipboard")

# The component keeps returning the last-pasted image on every rerun, so we
# only add it to the batch if it's actually new (compared by content hash).
if paste_result.image_data is not None:
    buf = io.BytesIO()
    paste_result.image_data.save(buf, format="PNG")
    img_hash = hashlib.md5(buf.getvalue()).hexdigest()
    if img_hash != st.session_state.last_paste_hash:
        st.session_state.pasted_batch.append({"image": paste_result.image_data, "hash": img_hash})
        st.session_state.last_paste_hash = img_hash

if st.session_state.pasted_batch:
    if st.sidebar.button("🗑️ Clear Pasted Snips"):
        st.session_state.pasted_batch = []
        st.session_state.last_paste_hash = None
        st.rerun()

# --- Gather every image (pasted batch + uploaded batch) into one list ---
images = [item["image"] for item in st.session_state.pasted_batch]
file_ids = [item["hash"] for item in st.session_state.pasted_batch]

if uploaded_files:
    for f in uploaded_files:
        images.append(Image.open(f))
        file_ids.append(f.name + str(f.size))

file_id = "|".join(file_ids)

if images:
    st.sidebar.write(f"**{len(images)} image(s) ready to process:**")
    preview_cols = st.sidebar.columns(min(len(images), 3))
    for i, img in enumerate(images):
        with preview_cols[i % len(preview_cols)]:
            st.image(img, use_container_width=True)

st.sidebar.write("---")
process_clicked = st.sidebar.button(
    "🔍 Process Images & Extract Data",
    type="primary",
    disabled=(len(images) == 0),
    use_container_width=True
)

# Processing only ever runs on the exact click of the button above —
# entering your API key or adding another snip will never trigger it by itself.
if process_clicked:
    if not client:
        st.error("Please enter your Gemini API Key in the sidebar first to process images.")
    else:
        with st.spinner("Extracting data and structuring layouts..."):
            try:
                prompt = """
                Analyze the attached image(s) of a data table. If more than one image is provided,
                they all belong to the same single client order — combine information across all of
                them into one unified answer (e.g. one image may show the name/address while another
                shows the phone number).
                Return the output strictly in the following raw format (do not add markdown blocks, asterisks, or extra notes).
                If a field genuinely cannot be found in any image, return it as N/A.
                Mailing Address: [Extract value]
                Mailing Suburb: [Extract value]
                Mailing Post Code: [Extract value]
                Contact Name: [Extract value]
                Second Name: [Extract value]
                Client Mobile: [Extract value]
                Booking Owner: [Extract value]
                """

                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=[prompt] + images
                )

                raw_text = response.text
                data = {}
                for line in raw_text.split('\n'):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        data[key.strip()] = val.strip()

                missing = []

                # Contact name
                contact_name_raw = data.get("Contact Name", "")
                if is_missing(contact_name_raw):
                    missing.append("Full Name")
                else:
                    st.session_state.full_name = contact_name_raw
                    name_parts = st.session_state.full_name.split(" ", 1)
                    st.session_state.first_name = name_parts[0] if len(name_parts) > 0 else st.session_state.first_name
                    st.session_state.last_name = name_parts[1] if len(name_parts) > 1 else st.session_state.last_name

                # Partner / second name — genuinely optional, not treated as "missing"
                partner_raw = data.get("Second Name", "")
                st.session_state.partner_name = "" if is_missing(partner_raw) else partner_raw

                # Mobile number
                mobile_raw = data.get("Client Mobile", "")
                if is_missing(mobile_raw):
                    missing.append("Recipient Mobile Number")
                else:
                    st.session_state.contact_number = mobile_raw.replace(" ", "")

                # Booking owner
                booking_raw = data.get("Booking Owner", "")
                if is_missing(booking_raw):
                    missing.append("Booking Owner")
                else:
                    if "Entertainment Manager" not in booking_raw:
                        st.session_state.booking_owner = f"{booking_raw} Entertainment Manager"
                    else:
                        st.session_state.booking_owner = booking_raw

                # Address
                address_raw = data.get("Mailing Address", "")
                suburb_raw = data.get("Mailing Suburb", "")
                postcode_raw = data.get("Mailing Post Code", "")
                if is_missing(address_raw) and is_missing(suburb_raw) and is_missing(postcode_raw):
                    missing.append("Address")
                else:
                    address_street = address_raw if not is_missing(address_raw) else "235 Joseph St"
                    if address_street.endswith("St"):
                        address_street = address_street[:-2] + "Street"
                    elif address_street.endswith("St."):
                        address_street = address_street[:-3] + "Street"

                    suburb = (suburb_raw if not is_missing(suburb_raw) else "CANADIAN").upper()
                    postcode = postcode_raw if not is_missing(postcode_raw) else "3350"

                    st.session_state.formatted_address = f"{address_street}, {suburb} VIC {postcode}"

                st.session_state.missing_fields = missing
                st.session_state.last_processed_file = file_id
                st.success("✅ Data extracted — fields updated below.")
                st.rerun()

            except Exception as e:
                st.error(f"Processing failed: {e}")
elif not images:
    st.info("👈 Enter your API Key, add snip(s) or upload image(s) in the sidebar, then press **'🔍 Process Images & Extract Data'** when you're ready.")
else:
    st.info(f"📎 {len(images)} image(s) staged. Click **'🔍 Process Images & Extract Data'** in the sidebar when you're ready.")

if st.session_state.missing_fields:
    st.warning("⚠️ Couldn't find the following in the screenshot(s) — please fill them in manually: " + ", ".join(st.session_state.missing_fields))

# --- Render layout globally ---
col1, col2 = st.columns([1, 1])

with col1:
    # Quick Procurement Section
    st.subheader("🛒 Quick Procurement")
    st.write("Select a wine type below to instantly open its official Dan Murphy's order page:")

    wine_tab1, wine_tab2, wine_tab3, wine_tab4 = st.tabs(["Red Wine", "White Wine", "Sparkling Wine", "Moscato"])

    with wine_tab1:
        create_dan_murphys_link_button("🍷 Order Red Wine (Little Yering Pinot Noir)", "https://www.danmurphys.com.au/product/DM_727725/yering-station-little-yering-pinot-noir")
    with wine_tab2:
        create_dan_murphys_link_button("🥂 Order White Wine (Tim Adams Pinot Gris)", "https://www.danmurphys.com.au/product/DM_908219/tim-adams-clare-valley-pinot-gris")
    with wine_tab3:
        create_dan_murphys_link_button("🍾 Order Sparkling Wine (Dal Zotto Prosecco)", "https://www.danmurphys.com.au/product/DM_377397/dal-zotto-pucino-prosecco")
    with wine_tab4:
        create_dan_murphys_link_button("🍇 Order Moscato (Brown Brothers Moscato)", "https://www.danmurphys.com.au/product/DM_93537/brown-brothers-moscato")
    with wine_tab5:
        create_dan_murphys_link_button("🌹 Order Rose (La Planchelière Cabernet d'Anjou Rosé)", "https://www.danmurphys.com.au/product/DM_93537/brown-brothers-moscato")

    st.write("---")

    # Fully Editable Core Information Blocks with Embedded Copy Icons
    st.subheader("📌 Extracted Core Information (Editable)")
    st.write("Correct fields live inside the boxes. Click the embedded icon on the right edge to copy:")

    create_embedded_copy_input("Full Name", st.session_state.full_name, "full_name", "Full Name" in st.session_state.missing_fields, placeholder="e.g. Courtney Stevenson")
    create_embedded_copy_input("Address", st.session_state.formatted_address, "formatted_address", "Address" in st.session_state.missing_fields, placeholder="e.g. 235 Joseph Street, CANADIAN VIC 3350")
    create_embedded_copy_input("First Name", st.session_state.first_name, "first_name", placeholder="e.g. Courtney")
    create_embedded_copy_input("Last Name", st.session_state.last_name, "last_name", placeholder="e.g. Stevenson")
    create_embedded_copy_input("Recipient Mobile Number", st.session_state.contact_number, "contact_number", "Recipient Mobile Number" in st.session_state.missing_fields, placeholder="e.g. 0428341330")
    create_embedded_copy_input("Partner's Name (leave blank if none)", st.session_state.partner_name, "partner_name", placeholder="e.g. James")
    create_embedded_copy_input("Booking Owner", st.session_state.booking_owner, "booking_owner", "Booking Owner" in st.session_state.missing_fields, placeholder="e.g. Daniel Steer Entertainment Manager")

# --- Dynamic Greeting Setup ---
if st.session_state.partner_name.strip():
    greeting_names = f"{st.session_state.first_name.strip()} & {st.session_state.partner_name.strip()}"
else:
    greeting_names = f"{st.session_state.first_name.strip()}"

contact_card_display = f"{st.session_state.full_name}\n{st.session_state.contact_number}"

with col2:
    # Gift Message Layout
    st.subheader("🎁 Gift Message")
    gift_tab1, gift_tab2 = st.tabs(["Not Confirmed", "Confirmed"])

    with gift_tab1:
        gift_msg = f"Hi {greeting_names}, wedding planning is hard, toasting to your love story is easy. Enjoy this bottle of wine on us, sit back, put your feet up and sip, while you digest our amazing entertainment options for your big day. Cheers to the best day of your life from Melbourne Entertainment Company"
        create_embedded_copy_textarea("", gift_msg, "gift_msg_nc", height=120)

    with gift_tab2:
        msg_booked = f"Hi {greeting_names}, wedding planning can be a lot, so here’s something to help you unwind. Enjoy this bottle of wine on us—put your feet up, sip, and get excited for the incredible celebration ahead. We can’t wait to be part of your special day! Cheers, Melbourne Entertainment Company"
        create_embedded_copy_textarea("", msg_booked, "gift_msg_c", height=120)

    st.write("---")

    # Delivery Note
    st.subheader("📦 Delivery Note")
    delivery_note = "Handle with care, inside is the first toast to the best party you will ever throw..."
    create_embedded_copy_textarea("", delivery_note, "delivery_note", height=70)

    st.write("---")

    # Text Templates
    st.subheader("💬 Generated Text Templates")
    st.write("Review, tweak, or copy your operational templates instantly from the icons:")

    tab1, tab2, tab3, tab4 = st.tabs(["6-8 PM", "4-6 PM", "NO INSTANT", "BOOKED SMS"])

    with tab1:
        msg_6_8 = f"Hi {st.session_state.first_name}! I’m just sending a quick courtesy message to let you know that your delivery is scheduled for this evening between 6:00 pm and 8:00 pm. You should receive a confirmation via text or email shortly. This will include an option to reschedule if that window no longer works for you. Please keep in mind that someone over 18 with a valid ID must be present to accept the delivery. Happy planning!"
        create_embedded_copy_textarea("", msg_6_8, "t_6_8", height=150)

    with tab2:
        msg_4_6 = f"Hi {st.session_state.first_name}! I’m just sending a quick courtesy message to let you know that your delivery is scheduled for today, between 4:00-6:00 pm. You should receive a confirmation via text or email shortly. This will include an option to reschedule if that window no longer works for you. Please keep in mind that someone over 18 with a valid ID must be present to accept the delivery. Happy planning!"
        create_embedded_copy_textarea("", msg_4_6, "t_4_6", height=150)

    with tab3:
        msg_no_inst = f"Hi {st.session_state.first_name}! I’m just sending a quick courtesy message to let you know that your delivery is scheduled for later this week. We looked into instant delivery, but since it wasn’t available for your address, we’ve organized the shipment through Dan Murphy’s instead. You should receive a text or email shortly with the specific window and an option to reschedule. Please keep in mind that someone over 18 with a valid ID must be present to complete the order. Happy planning! :)"
        create_embedded_copy_textarea("", msg_no_inst, "t_no_inst", height=160)

    with tab4:
        msg_booked_sms = f"Hi {st.session_state.first_name}! We are so incredibly excited to be part of your wedding day. To celebrate, we have a little something special heading your way this evening between 6:00 pm and 8:00 pm. You’ll receive a tracking/confirmation alert shortly, which includes an option to reschedule if you won't be home. Because it's a little toast to your future, please make sure someone over 18 with a valid ID is there to accept it. Cheers! 🎉"
        create_embedded_copy_textarea("", msg_booked_sms, "t_booked_sms", height=150)

    st.write("---")

    # Client Contact Card (moved below Generated Text Templates)
    st.subheader("📋 Client Contact Card (For Booking Owner)")
    create_embedded_copy_textarea("", contact_card_display, "owner_card", height=70)

# Persistent Sidebar footer
st.sidebar.write("---")
st.sidebar.caption("_Designed by Hamilton R._")
