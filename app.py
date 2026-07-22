import io
import hashlib
import streamlit as st
from PIL import Image
from google import genai
from streamlit_paste_button import paste_image_button

# ==========================================
# PASTE YOUR API KEY HERE IF NOT USING ENV VARS
# ==========================================
API_KEY = "AQ.Ab8RN6KKWU4c_xFMa9Cbrp0pCWsuRwnPfa6vBLsM1QV65Yy3MQ"

# 1. Page Configuration & UI Initialization
st.set_page_config(page_title="Wine Order Extractor", page_icon="🍷", layout="wide")
st.title("🍾 Wine Order Image Data Extractor")
st.write("Upload a data table screenshot to extract details, modify fields live, and generate ready-to-copy templates.")

# 2. Initialize Gemini Client
try:
    if API_KEY and API_KEY != "YOUR_GEMINI_API_KEY_HERE":
        client = genai.Client(api_key=API_KEY)
    else:
        client = genai.Client()
except Exception:
    st.error("Missing Gemini API Key. Please paste your key into the API_KEY variable at the top of app.py or set the GEMINI_API_KEY environment variable.")
    st.stop()

# Default session state values
defaults = {
    'full_name': "Courtney Stevenson",
    'first_name': "Courtney",
    'last_name': "Stevenson",
    'partner_name': "James",
    'contact_number': "0428341330",
    'booking_owner': "Daniel Steer Entertainment Manager",
    'formatted_address': "235 Joseph Street, CANADIAN VIC 3350",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Models tried in order. Each model has its OWN separate daily free-tier quota
# per project, so if one is exhausted (429) we fall through to the next.
# Flash-Lite is the most generous on the free tier, so it goes first.
EXTRACTION_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]


def is_quota_error(err):
    msg = str(err)
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg


def is_missing(v):
    """True if the model returned nothing usable for a field."""
    if v is None:
        return True
    s = str(v).strip().lower()
    if s.startswith("["):  # echoed placeholder like [Extract value]
        return True
    return s in ("", "n/a", "na", "none", "null", "not found", "unknown", "-", "—")


def extract_with_fallback(prompt, images):
    """Try each model in turn. On a quota (429) error, move to the next model.
    `images` is a list of PIL images sent together so the model can combine them.
    Returns (raw_text, model_used). Raises the last quota error if all are spent."""
    last_quota_err = None
    for model in EXTRACTION_MODELS:
        try:
            resp = client.models.generate_content(model=model, contents=[prompt] + images)
            return resp.text, model
        except Exception as e:
            if is_quota_error(e):
                last_quota_err = e
                continue  # this model is out for today, try the next one
            raise  # a real error (bad image, network, etc) - surface it
    raise last_quota_err

# 3. Sidebar File Uploader (accepts one or more reference screenshots)
uploaded_files = st.sidebar.file_uploader(
    "Upload Image(s)",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    help="You can upload more than one screenshot. If the address is missing on one, add another that has it and the details get combined."
)

# Paste straight from the clipboard (e.g. after using the Snipping Tool)
st.sidebar.markdown("**or paste a screenshot:**")
paste_result = paste_image_button(
    "📋 Paste from clipboard",
    background_color="#FF4B4B",
    hover_background_color="#3578F6",
    key="paste_btn",
)

# Keep every pasted screenshot for this session, so a second paste ADDS to the
# first instead of replacing it. Stored as (hash, image) pairs; hash dedupes
# the same image being returned again on later reruns.
if 'pasted' not in st.session_state:
    st.session_state.pasted = []

if paste_result.image_data is not None:
    pimg = paste_result.image_data
    buf = io.BytesIO()
    pimg.save(buf, format="PNG")
    h = hashlib.md5(buf.getvalue()).hexdigest()[:10]
    if h not in [p[0] for p in st.session_state.pasted]:
        st.session_state.pasted.append((h, pimg))

# Let the user wipe pasted images before starting a new order
if st.session_state.pasted:
    if st.sidebar.button(f"🗑️ Clear {len(st.session_state.pasted)} pasted image(s)"):
        st.session_state.pasted = []
        st.rerun()

# Build a single list of images from BOTH the uploader and every pasted screenshot
images = []
id_parts = []

if uploaded_files:
    for f in uploaded_files:
        images.append(Image.open(f))
        id_parts.append(f.name + str(f.size))

for h, pimg in st.session_state.pasted:
    images.append(pimg)
    id_parts.append("paste-" + h)

if images:
    file_id = "|".join(id_parts)
    if 'last_processed_file' not in st.session_state or st.session_state.last_processed_file != file_id:

        for img in images:
            st.sidebar.image(img, use_container_width=True)

        with st.spinner("Extracting data and structuring layouts..."):
            try:
                prompt = """
                These are one or more screenshots that all refer to the SAME order.
                Read every image and combine the details across them.
                If a field is blank or missing in one image, look for it in the others.
                If the same field appears in more than one image, use the most complete, non-empty value.
                Return the output strictly in the following raw format (do not add markdown blocks, asterisks, or extra notes):
                Mailing Address: [Extract value]
                Mailing Suburb: [Extract value]
                Mailing Post Code: [Extract value]
                Contact Name: [Extract value]
                Second Name: [Extract value]
                Client Mobile: [Extract value]
                Booking Owner: [Extract value]
                """

                raw_text, model_used = extract_with_fallback(prompt, images)
                st.sidebar.caption(f"Extracted using: {model_used} ({len(images)} image{'s' if len(images) != 1 else ''})")
                data = {}
                for line in raw_text.split('\n'):
                    if ":" in line:
                        key, val = line.split(":", 1)
                        data[key.strip()] = val.strip()

                # Raw extracted values
                contact_name = data.get("Contact Name", "").strip()
                partner = data.get("Second Name", "").strip()
                mobile = data.get("Client Mobile", "").strip().replace(" ", "")
                booking_raw = data.get("Booking Owner", "").strip()
                addr_street = data.get("Mailing Address", "").strip()
                suburb = data.get("Mailing Suburb", "").strip()
                postcode = data.get("Mailing Post Code", "").strip()

                # Track anything the model couldn't find (Partner is optional, so not flagged)
                missing = []
                if is_missing(contact_name):
                    missing.append("Full Name")
                if is_missing(mobile):
                    missing.append("Mobile Number")
                if is_missing(addr_street):
                    missing.append("Address")
                if is_missing(suburb):
                    missing.append("Suburb")
                if is_missing(postcode):
                    missing.append("Post Code")
                if is_missing(booking_raw):
                    missing.append("Booking Owner")

                # Full name + split (blank if not found)
                st.session_state.full_name = "" if is_missing(contact_name) else contact_name
                name_parts = st.session_state.full_name.split(" ", 1)
                st.session_state.first_name = name_parts[0] if name_parts and name_parts[0] else ""
                st.session_state.last_name = name_parts[1] if len(name_parts) > 1 else ""

                st.session_state.partner_name = "" if is_missing(partner) else partner
                st.session_state.contact_number = "" if is_missing(mobile) else mobile

                if is_missing(booking_raw):
                    st.session_state.booking_owner = ""
                elif "Entertainment Manager" not in booking_raw:
                    st.session_state.booking_owner = f"{booking_raw} Entertainment Manager"
                else:
                    st.session_state.booking_owner = booking_raw

                # Address: normalise "St" -> "Street", build from whatever parts exist
                if is_missing(addr_street):
                    addr_street = ""
                elif addr_street.endswith("St."):
                    addr_street = addr_street[:-3] + "Street"
                elif addr_street.endswith("St"):
                    addr_street = addr_street[:-2] + "Street"

                suburb_fmt = "" if is_missing(suburb) else suburb.upper()
                postcode_fmt = "" if is_missing(postcode) else postcode

                if suburb_fmt and postcode_fmt:
                    loc = f"{suburb_fmt} VIC {postcode_fmt}"
                elif suburb_fmt:
                    loc = f"{suburb_fmt} VIC"
                elif postcode_fmt:
                    loc = f"VIC {postcode_fmt}"
                else:
                    loc = ""

                st.session_state.formatted_address = ", ".join(p for p in [addr_street, loc] if p)
                st.session_state.last_processed_file = file_id

                if missing:
                    st.warning(
                        "⚠️ Couldn't find these in the image(s): "
                        + ", ".join(missing)
                        + ". Those boxes are left blank, fill them in by hand before sending."
                    )
                else:
                    st.success("✅ All fields extracted.")

            except Exception as e:
                if is_quota_error(e):
                    st.error(
                        "Daily free-tier quota reached on every available model. "
                        "Google's free quota resets at midnight US Pacific time "
                        "(around 6pm AEST). You can either wait for the reset, or "
                        "enable billing on your Google Cloud project for a permanent fix "
                        "(pay-as-you-go, costs a few cents at this volume). "
                        "Note: extra API keys won't help, since the quota is per project, not per key."
                    )
                else:
                    st.error(f"Processing failed: {e}")
elif 'last_processed_file' not in st.session_state:
    st.info("👈 Upload one or more screenshots, or paste one from your clipboard, to generate templates automatically. Add a second image if the address is missing on the first.")


# Procurement Link Button Helper (stays native Streamlit)
def create_dan_murphys_link_button(label, url):
    html_code = f"""
    <a href="{url}" target="_blank" style="text-decoration: none;">
        <button style="
            background-color: #0F522B; color: white; border: none;
            padding: 10px 20px; border-radius: 4px; cursor: pointer;
            font-weight: bold; font-size: 14px; font-family: sans-serif;
            display: flex; align-items: center; gap: 8px;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.2); margin-top: 10px;">
            {label}
        </button>
    </a>
    """
    st.components.v1.html(html_code, height=55)


# Quick Procurement (independent of extracted data, kept native)
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


# ------------------------------------------------------------------
# Single unified workspace: inputs (left) + live outputs (right).
# Everything lives in ONE component so JS can recompute outputs live.
# ------------------------------------------------------------------
def esc(v):
    return str(v).replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


COPY_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" '
            'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
            '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>')


def input_field(label, fid, value):
    return f"""
    <div class="fld">
      <label>{label}</label>
      <div class="wrap">
        <input id="{fid}" value="{esc(value)}" oninput="recompute()" />
        <button class="cpy" title="Copy" onclick="copyEl('{fid}', this)">{COPY_SVG}</button>
      </div>
    </div>"""


def output_box(tid, height):
    return f"""
    <div class="wrap ta">
      <textarea id="{tid}" style="height:{height}px"></textarea>
      <button class="cpy tacpy" title="Copy" onclick="copyEl('{tid}', this)">{COPY_SVG}</button>
    </div>"""


left = (
    '<h3 class="hd">📌 Extracted Core Information (Editable)</h3>'
    '<p class="sub">Correct fields live inside the boxes. Everything on the right updates as you type. '
    'Click the icon on the right edge of any box to copy.</p>'
    + input_field("Full Name", "inp_full_name", st.session_state.full_name)
    + input_field("Address", "inp_formatted_address", st.session_state.formatted_address)
    + input_field("First Name", "inp_first_name", st.session_state.first_name)
    + input_field("Last Name", "inp_last_name", st.session_state.last_name)
    + input_field("Recipient Mobile Number", "inp_contact_number", st.session_state.contact_number)
    + input_field("Partner's Name", "inp_partner_name", st.session_state.partner_name)
    + input_field("Booking Owner", "inp_booking_owner", st.session_state.booking_owner)
)

right = f"""
  <h3 class="hd">🎁 Gift Message</h3>
  <div class="tabs">
    <button class="tab active" onclick="showTab('gift','nc',this)">Not Confirmed</button>
    <button class="tab" onclick="showTab('gift','c',this)">Confirmed</button>
  </div>
  <div class="pane pane-gift" id="pane_gift_nc">{output_box("out_gift_nc", 120)}</div>
  <div class="pane pane-gift hidden" id="pane_gift_c">{output_box("out_gift_c", 120)}</div>
  <div class="divider"></div>

  <h3 class="hd">🚚 Note for Your Driver Message</h3>
  {output_box("out_driver_note", 70)}
  <div class="divider"></div>

  <h3 class="hd">💬 Generated Text Templates</h3>
  <div class="tabs">
    <button class="tab active" onclick="showTab('tmpl','68',this)">6-8 PM</button>
    <button class="tab" onclick="showTab('tmpl','46',this)">4-6 PM</button>
    <button class="tab" onclick="showTab('tmpl','noinst',this)">NO INSTANT</button>
    <button class="tab" onclick="showTab('tmpl','sms',this)">BOOKED SMS</button>
  </div>
  <div class="pane pane-tmpl" id="pane_tmpl_68">{output_box("out_t_68", 150)}</div>
  <div class="pane pane-tmpl hidden" id="pane_tmpl_46">{output_box("out_t_46", 150)}</div>
  <div class="pane pane-tmpl hidden" id="pane_tmpl_noinst">{output_box("out_t_noinst", 160)}</div>
  <div class="pane pane-tmpl hidden" id="pane_tmpl_sms">{output_box("out_t_sms", 150)}</div>
  <div class="divider"></div>

  <h3 class="hd">📋 Client Contact Card (For Booking Owner)</h3>
  {output_box("out_owner_card", 72)}
"""

markup = f"""
<div class="workspace">
  <div class="col">{left}</div>
  <div class="col">{right}</div>
</div>
"""

styles = """
<style>
  .workspace {
    font-family: "Source Sans Pro", sans-serif;
    display: grid; grid-template-columns: 1fr 1fr; gap: 34px;
    color: #E6E6E6;
  }
  .hd { font-size: 20px; font-weight: 700; margin: 4px 0 6px 0; color: #FFFFFF; }
  .sub { font-size: 14px; color: #B5B7C0; margin: 0 0 14px 0; }
  .fld { margin-bottom: 16px; }
  .fld label { display: block; font-size: 14px; color: #E6E6E6; font-weight: 500; margin-bottom: 6px; }
  .wrap { position: relative; display: flex; align-items: center; width: 100%; }
  .wrap input, .wrap textarea {
    width: 100%; background-color: #262730; color: #FFFFFF;
    border: 1px solid #4A4B57; border-radius: 6px; font-size: 15px;
    outline: none; box-sizing: border-box; font-family: inherit;
  }
  .wrap input { padding: 10px 42px 10px 14px; }
  .wrap textarea { padding: 12px 46px 12px 14px; resize: none; line-height: 1.4; overflow: auto; scrollbar-width: none; -ms-overflow-style: none; }
  .wrap textarea::-webkit-scrollbar { display: none; }
  .wrap input:focus, .wrap textarea:focus { border-color: #6C6E7E; }
  .cpy {
    position: absolute; right: 4px; background: transparent; border: none;
    color: #808495; cursor: pointer; padding: 8px; display: flex;
    align-items: center; justify-content: center; border-radius: 4px; outline: none;
  }
  .cpy:hover { color: #C8CAD4; }
  .cpy.tacpy { top: 6px; right: 6px; }
  .divider { height: 1px; background: #3A3B45; margin: 20px 0; }
  .tabs { display: flex; gap: 18px; border-bottom: 1px solid #3A3B45; margin-bottom: 14px; }
  .tab {
    background: transparent; border: none; color: #B5B7C0; cursor: pointer;
    font-size: 14px; padding: 6px 2px 10px 2px; outline: none;
    border-bottom: 2px solid transparent; margin-bottom: -1px; font-family: inherit;
  }
  .tab.active { color: #FF4B4B; border-bottom-color: #FF4B4B; }
  .pane.hidden { display: none; }
</style>
"""

script = r"""
<script>
  const CHECK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#24A0ED" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';

  function val(id) { return document.getElementById(id).value; }

  function greetingNames() {
    const first = val('inp_first_name').trim();
    const partner = val('inp_partner_name').trim();
    return partner ? (first + ' & ' + partner) : first;
  }

  function recompute() {
    const first  = val('inp_first_name').trim();
    const full   = val('inp_full_name');
    const mobile = val('inp_contact_number');
    const g = greetingNames();

    document.getElementById('out_owner_card').value = full + '\n' + mobile;

    document.getElementById('out_driver_note').value =
      'Handle with care, inside is the first toast to the best party you will ever throw...';

    document.getElementById('out_gift_nc').value =
      'Hi ' + g + ', wedding planning is hard, toasting to your love story is easy. Enjoy this bottle of wine on us, sit back, put your feet up and sip, while you digest our amazing entertainment options for your big day. Cheers to the best day of your life from Melbourne Entertainment Company';

    document.getElementById('out_gift_c').value =
      'Hi ' + g + ', wedding planning can be a lot, so here\u2019s something to help you unwind. Enjoy this bottle of wine on us\u2014put your feet up, sip, and get excited for the incredible celebration ahead. We can\u2019t wait to be part of your special day! Cheers, Melbourne Entertainment Company';

    document.getElementById('out_t_68').value =
      'Hi ' + first + '! I\u2019m just sending a quick courtesy message to let you know that your delivery is scheduled for this evening between 6:00 pm and 8:00 pm. You should receive a confirmation via text or email shortly. This will include an option to reschedule if that window no longer works for you. Please keep in mind that someone over 18 with a valid ID must be present to accept the delivery. Happy planning!';

    document.getElementById('out_t_46').value =
      'Hi ' + first + '! I\u2019m just sending a quick courtesy message to let you know that your delivery is scheduled for today, between 4:00-6:00 pm. You should receive a confirmation via text or email shortly. This will include an option to reschedule if that window no longer works for you. Please keep in mind that someone over 18 with a valid ID must be present to accept the delivery. Happy planning!';

    document.getElementById('out_t_noinst').value =
      'Hi ' + first + '! I\u2019m just sending a quick courtesy message to let you know that your delivery is scheduled for later this week. We looked into instant delivery, but since it wasn\u2019t available for your address, we\u2019ve organized the shipment through Dan Murphy\u2019s instead. You should receive a text or email shortly with the specific window and an option to reschedule. Please keep in mind that someone over 18 with a valid ID must be present to complete the order. Happy planning! :)';

    document.getElementById('out_t_sms').value =
      'Hi ' + first + '! We are so incredibly excited to be part of your wedding day. To celebrate, we have a little something special heading your way this evening between 6:00 pm and 8:00 pm. You\u2019ll receive a tracking/confirmation alert shortly, which includes an option to reschedule if you won\u2019t be home. Because it\u2019s a little toast to your future, please make sure someone over 18 with a valid ID is there to accept it. Cheers! \uD83C\uDF89';
  }

  function copyEl(id, btn) {
    const el = document.getElementById(id);
    navigator.clipboard.writeText(el.value).then(function () {
      const orig = btn.innerHTML;
      btn.innerHTML = CHECK_SVG;
      setTimeout(function () { btn.innerHTML = orig; }, 1500);
    }).catch(function (err) { alert('Failed to copy text: ' + err); });
  }

  function showTab(group, key, btn) {
    const panes = document.querySelectorAll('.pane-' + group);
    panes.forEach(function (p) { p.classList.add('hidden'); });
    document.getElementById('pane_' + group + '_' + key).classList.remove('hidden');
    const tabs = btn.parentNode.querySelectorAll('.tab');
    tabs.forEach(function (t) { t.classList.remove('active'); });
    btn.classList.add('active');
  }

  recompute();
</script>
"""

st.components.v1.html(styles + markup + script, height=900, scrolling=True)

# Sidebar footer
st.sidebar.write("---")
st.sidebar.caption("_Designed by Hamilton R._")