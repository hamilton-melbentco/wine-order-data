import streamlit as st
from PIL import Image
from google import genai
import re

# 1. Page Configuration & UI Initialization
st.set_page_config(page_title="🥂 Wine Order Extractor", layout="wide")
st.title("🍾 Wine Order Image Data Extractor")
st.write("Upload a data table screenshot to extract details, modify fields live, and generate ready-to-copy templates.")

# --- Sidebar API Key Configuration ---
st.sidebar.subheader("🔑 API Configuration")
# Initialize session state for api_key if not present
if 'user_api_key' not in st.session_state:
    st.session_state.user_api_key = ""

# API key input field in the sidebar (masked for privacy)
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
if 'full_name' not in st.session_state:
    st.session_state.full_name = "Courtney Stevenson"
if 'first_name' not in st.session_state:
    st.session_state.first_name = "Courtney"
if 'last_name' not in st.session_state:
    st.session_state.last_name = "Stevenson"
if 'partner_name' not in st.session_state:
    st.session_state.partner_name = "James"
if 'contact_number' not in st.session_state:
    st.session_state.contact_number = "0428341330"
if 'booking_owner' not in st.session_state:
    st.session_state.booking_owner = "Daniel Steer Entertainment Manager"
if 'formatted_address' not in st.session_state:
    st.session_state.formatted_address = "235 Joseph Street, CANADIAN VIC 3350"

# --- Custom Component Builders for Templates, Cards, and Messages ---

# Multi-line Textarea Box with Embedded Copy Icon (Perfect for Templates, Cards, and Messages)
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
    st.components.v1.html(html_code, height=height + (30 if label else 10))

# Procurement Link Button Helper
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
    st.components.v1.html(html_code, height=55)

# 3. Sidebar File Uploader Component
st.sidebar.write("---")
uploaded_file = st.sidebar.file_uploader("Upload Image", type=["png", "jpg", "jpeg", "webp"])

# If a file is uploaded, handle processing logic and rendering
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.sidebar.image(image, caption="Uploaded Screenshot", use_container_width=True)
    
    file_id = uploaded_file.name + str(uploaded_file.size)
    if 'last_processed_file' not in st.session_state or st.session_state.last_processed_file != file_id:
        if not client:
            st.error("Please enter your Gemini API Key in the sidebar first to process images.")
        else:
            with st.spinner("Extracting data and structuring layouts..."):
                try:
                    prompt = """
                    Analyze this image table and extract the data fields. 
                    Return the output strictly in the following raw format (do not add markdown blocks, asterisks, or extra notes):
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
                        contents=[prompt, image]
                    )
                    
                    raw_text = response.text
                    data = {}
                    for line in raw_text.split('\n'):
                        if ":" in line:
                            key, val = line.split(":", 1)
                            data[key.strip()] = val.strip()
                    
                    st.session_state.full_name = data.get("Contact Name", st.session_state.full_name)
                    name_parts = st.session_state.full_name.split(" ", 1)
                    st.session_state.first_name = name_parts[0] if len(name_parts) > 0 else st.session_state.first_name
                    st.session_state.last_name = name_parts[1] if len(name_parts) > 1 else st.session_state.last_name
                    
                    st.session_state.partner_name = data.get("Second Name", "")
                    st.session_state.contact_number = data.get("Client Mobile", st.session_state.contact_number).replace(" ", "")
                    
                    booking_raw = data.get("Booking Owner", "Daniel Steer")
                    if "Entertainment Manager" not in booking_raw:
                        st.session_state.booking_owner = f"{booking_raw} Entertainment Manager"
                    else:
                        st.session_state.booking_owner = booking_raw

                    address_street = data.get("Mailing Address", "235 Joseph St")
                    if address_street.endswith("St"):
                        address_street = address_street[:-2] + "Street"
                    elif address_street.endswith("St."):
                        address_street = address_street[:-3] + "Street"
                        
                    suburb = data.get("Mailing Suburb", "CANADIAN").upper()
                    postcode = data.get("Mailing Post Code", "3350")
                    
                    st.session_state.formatted_address = f"{address_street}, {suburb} VIC {postcode}"
                    st.session_state.last_processed_file = file_id
                    st.rerun()

                except Exception as e:
                    st.error(f"Processing failed: {e}")
else:
    st.info("👈 Enter your API Key and upload your table screenshot in the left sidebar to generate templates automatically.")


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
    
    st.write("---")
    
    # Fully Editable Core Information Blocks with Individual Copy Buttons
    st.subheader("📌 Extracted Core Information (Editable)")
    st.write("Edit fields to update templates; click the icon to copy individual values:")

    def create_editable_row(label, state_key):
        c_a, c_b = st.columns([0.88, 0.12])
        with c_a:
            st.session_state[state_key] = st.text_input(label, value=st.session_state[state_key], key=f"input_{state_key}")
        with c_b:
            st.write("###") # vertical alignment spacing
            if st.button("📋", key=f"btn_{state_key}", help=f"Copy {label}"):
                st.write(f'<script>navigator.clipboard.writeText("{st.session_state[state_key]}")</script>', unsafe_allow_html=True)
                st.toast(f"Copied {label}!")

    create_editable_row("Full Name", "full_name")
    create_editable_row("Address", "formatted_address")
    create_editable_row("First Name", "first_name")
    create_editable_row("Last Name", "last_name")
    create_editable_row("Recipient Mobile Number", "contact_number")
    create_editable_row("Partner's Name", "partner_name")
    create_editable_row("Booking Owner", "booking_owner")

# --- Dynamic Greeting Setup ---
if st.session_state.partner_name.strip():
    greeting_names = f"{st.session_state.first_name.strip()} & {st.session_state.partner_name.strip()}"
else:
    greeting_names = f"{st.session_state.first_name.strip()}"

contact_card_display = f"{st.session_state.full_name}\n{st.session_state.contact_number}"

with col2:
    # Client Contact Card
    st.subheader("📋 Client Contact Card (For Booking Owner)")
    create_embedded_copy_textarea("", contact_card_display, "owner_card", height=65)
    
    st.write("---")
    
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

# Persistent Sidebar footer
st.sidebar.write("---")
st.sidebar.caption("_Designed by Hamilton R._")
