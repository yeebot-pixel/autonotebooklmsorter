import streamlit as st
import asyncio
from google import genai
import notebooklm
from pypdf import PdfReader
import io

st.set_page_config(page_title="Auto Study Sorter", page_icon="🎓", layout="centered")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("🔐 Authentication")

user_gemini_key = st.sidebar.text_input(
    "Enter Gemini API Key", 
    type="password", 
    help="Get a free key from Google AI Studio"
)

# Your secret personal key shortcut
MY_HIDDEN_KEY = "YOUR_GEMINI_API_KEY" # <-- Leave your real key here!
final_api_key = user_gemini_key if user_gemini_key else MY_HIDDEN_KEY

ai_client = None
if final_api_key and final_api_key != "YOUR_GEMINI_API_KEY":
    try:
        ai_client = genai.Client(api_key=final_api_key)
    except Exception:
        st.sidebar.error("❌ Invalid Gemini API Key.")

# Live-scan the active user's notebooks
async def get_user_notebooks():
    try:
        async with notebooklm.NotebookLMClient.from_storage() as n_client:
            notebooks_list = await n_client.notebooks.list()
            return {n.title: n.id for n in notebooks_list}
    except Exception:
        return None

user_notebooks = asyncio.run(get_user_notebooks())

if user_notebooks:
    st.sidebar.success(f"🔗 Connected to NotebookLM!")
    st.sidebar.write("### 🗂 Detected Notebooks:")
    for name in user_notebooks.keys():
        st.sidebar.write(f"- `{name}`")
else:
    st.sidebar.warning("⚠️ Please run 'notebooklm login' in your local terminal to connect.")

# --- AUTOMATED AI SORTING BRAIN ---
async def auto_categorize_content(content_text: str, notebook_names: list) -> str:
    """Gemini dynamically maps content directly to notebook names using zero keywords."""
    if not ai_client:
        return None
    
    prompt = f"""
    You are an expert academic filing assistant.
    Analyze the following study material snippet and choose the single best notebook from this list where it belongs: {notebook_names}.
    
    CRITICAL: The notebook names might be in English, Japanese (Kanji/Kana), or Romanized Japanese (e.g., 'eisei' for hygiene/microbiology, 'yasai' for vegetables/crops, 'shouhi' for consumer economics/statistics). Use your multilingual knowledge to translate and match the concepts perfectly.
    
    Reply with ONLY the exact notebook name string from the list. Do not include spaces, thoughts, or explanations.
    
    Content:
    {content_text[:2500]}
    """
    response = ai_client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
    chosen = response.text.strip().replace("'", "").replace('"', "")
    
    # Validation safety check
    return chosen if chosen in notebook_names else notebook_names[0]

async def upload_to_notebooklm(notebook_id: str, title: str, text_content: str):
    async with notebooklm.NotebookLMClient.from_storage() as n_client:
        await n_client.sources.add_text(
            notebook_id=notebook_id,
            title=title,
            content=text_content
        )

# --- VISUAL WEB DASHBOARD ---
st.title("🎓 Smart Study Sorter (Fully Automated)")
st.write("Drag and drop your files. Gemini will live-scan your dashboard and automatically route them to the right notebook.")

if not ai_client:
    st.info("💡 To begin, please ensure a valid Gemini API key is active or provided in the sidebar.")
elif not user_notebooks:
    st.error("❌ Cannot read your Notebooks dashboard. Please verify your local login session.")
else:
    tab1, tab2 = st.tabs(["📄 Upload Document (PDF/TXT)", "🔗 Paste Custom Text"])
    notebook_list_names = list(user_notebooks.keys())
    
    with tab1:
        uploaded_file = st.file_uploader("Drop lecture PDF or notes here", type=["pdf", "txt"])
        if uploaded_file and st.button("⚡ Automatically Sort & Upload PDF"):
            with st.spinner("AI is analyzing content and matching it to your dashboard..."):
                file_title = uploaded_file.name
                if uploaded_file.type == "application/pdf":
                    pdf_reader = PdfReader(io.BytesIO(uploaded_file.read()))
                    text_content = "".join([page.extract_text() for page in pdf_reader.pages])
                else:
                    text_content = uploaded_file.read().decode("utf-8")
                
                # Zero-keyword dynamic AI match
                target_nb = asyncio.run(auto_categorize_content(text_content, notebook_list_names))
                st.info(f"🧠 AI detected topic meaning and selected notebook: **{target_nb}**")
                
                asyncio.run(upload_to_notebooklm(user_notebooks[target_nb], file_title, text_content))
                st.success(f"✅ Success! Sent '{file_title}' straight into your **{target_nb}** notebook.")

    with tab2:
        source_title = st.text_input("Document Title")
        source_content = st.text_area("Paste lecture material, syllabus details, or article text here", height=200)
        if source_title and source_content and st.button("⚡ Automatically Sort & Upload Text"):
            with st.spinner("Analyzing content..."):
                target_nb = asyncio.run(auto_categorize_content(source_content, notebook_list_names))
                st.info(f"🧠 AI detected topic meaning and selected notebook: **{target_nb}**")
                
                asyncio.run(upload_to_notebooklm(user_notebooks[target_nb], source_title, source_content))
                st.success(f"✅ Success! Sent '{source_title}' straight into your **{target_nb}** notebook.")