import streamlit as st
import asyncio
from google import genai
import notebooklm
from pypdf import PdfReader
import io

st.set_page_config(page_title="Batch Study Sorter", page_icon="🎓", layout="centered")

# --- BROWSER MEMORY STORAGE INITIALIZATION ---
if "saved_api_key" not in st.session_state:
    st.session_state["saved_api_key"] = ""

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("🔐 Authentication")

user_gemini_key = st.sidebar.text_input(
    "Enter Gemini API Key", 
    value=st.session_state["saved_api_key"],
    type="password", 
    help="Get a free key from Google AI Studio"
)

if user_gemini_key:
    st.session_state["saved_api_key"] = user_gemini_key

final_api_key = ""
ai_client = None

if user_gemini_key:
    final_api_key = user_gemini_key
else:
    try:
        if "MY_SECRET_KEY" in st.secrets:
            final_api_key = st.secrets["MY_SECRET_KEY"]
    except Exception:
        pass 

if final_api_key:
    try:
        ai_client = genai.Client(api_key=final_api_key)
    except Exception:
        st.sidebar.error("❌ Invalid Gemini API Key.")

# Live-scan the active user's notebooks
async def get_user_notebooks():
    try:
        async with notebooklm.NotebookLMClient.from_storage() as n_client:
            notebooks_list = await n_client.notebooks.list()
            # Returns a dictionary mapping names to IDs
            return {n.title: n.id for n in notebooks_list}
    except Exception:
        return None

user_notebooks = asyncio.run(get_user_notebooks())

# --- CRITICAL SIDEBAR STATUS INTERFACE ---
if user_notebooks is not None and len(user_notebooks) > 0:
    st.sidebar.success(f"🔗 Connected to NotebookLM!")
    st.sidebar.write("### 🗂 Detected Notebooks:")
    for name in user_notebooks.keys():
        st.sidebar.write(f"- `{name}`")
else:
    # Force user_notebooks to be an empty dictionary instead of None to prevent crashing math errors
    user_notebooks = {}
    st.sidebar.error("🛑 DISCONNECTED: NotebookLM session expired!")
    st.sidebar.warning("👉 To fix this: Open your terminal, close the server with Ctrl+C, run 'notebooklm login', then restart!")

if user_gemini_key and st.sidebar.button("🗑️ Clear Saved Key from Browser"):
    st.session_state["saved_api_key"] = ""
    st.rerun()

# --- AUTOMATED AI SORTING BRAIN ---
async def auto_categorize_content(content_text: str, notebook_names: list) -> str:
    if not ai_client or not notebook_names:
        return None
    
    prompt = f"""
    Analyze the following study material snippet and choose the single best notebook from this list where it belongs: {notebook_names}.
    Notebook names might be Romanized Japanese (e.g. 'eisei'=microbiology, 'yasai'=crops/vegetables, 'shouhi'=consumer economics). Match the concepts perfectly.
    Reply with ONLY the exact notebook name string. No spaces, no punctuation.
    
    Content:
    {content_text[:2500]}
    """
    response = ai_client.models.generate_content(model='gemini-3.5-flash', contents=prompt)
    chosen = response.text.strip().replace("'", "").replace('"', "")
    return chosen if chosen in notebook_names else notebook_names[0]

async def upload_to_notebooklm(notebook_id: str, title: str, text_content: str):
    async with notebooklm.NotebookLMClient.from_storage() as n_client:
        await n_client.sources.add_text(
            notebook_id=notebook_id,
            title=title,
            content=text_content
        )

# --- VISUAL WEB DASHBOARD ---
st.title("🎓 Batch Study Sorter (Fully Automated)")
st.write("Drag and drop your files. Gemini will sort and route each one automatically.")

if not final_api_key:
    st.info("💡 To begin, please ensure a valid Gemini API key is active or provided in the sidebar.")
elif not user_notebooks:
    st.error("❌ App cannot upload files because your NotebookLM session is disconnected. Check the sidebar instructions.")
else:
    tab1, tab2 = st.tabs(["📄 Upload Documents (PDF/TXT)", "🔗 Paste Custom Text"])
    notebook_list_names = list(user_notebooks.keys())
    
    with tab1:
        uploaded_files = st.file_uploader(
            "Drop your lecture PDFs or notes here", 
            type=["pdf", "txt"], 
            accept_multiple_files=True
        )
        
        if uploaded_files and st.button("⚡ Automatically Sort & Upload All Files"):
            total_files = len(uploaded_files)
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for index, uploaded_file in enumerate(uploaded_files):
                file_title = uploaded_file.name
                status_text.markdown(f"⏳ **Processing ({index+1}/{total_files}):** `{file_title}`...")
                
                if uploaded_file.type == "application/pdf":
                    pdf_reader = PdfReader(io.BytesIO(uploaded_file.read()))
                    text_content = "".join([page.extract_text() for page in pdf_reader.pages])
                else:
                    text_content = uploaded_file.read().decode("utf-8")
                
                if text_content.strip():
                    target_nb = asyncio.run(auto_categorize_content(text_content, notebook_list_names))
                    
                    # Complete protection safety fallback
                    if not target_nb or target_nb not in user_notebooks:
                        if "sharon" in user_notebooks:
                            target_nb = "sharon"
                        else:
                            target_nb = notebook_list_names[0]
                    
                    st.info(f"🧠 AI matched `{file_title}` ➡️ **{target_nb}**")
                    asyncio.run(upload_to_notebooklm(user_notebooks[target_nb], file_title, text_content))
                    st.toast(f"✅ Sent {file_title} ➡️ [{target_nb}]", icon="🚀")
                else:
                    st.error(f"❌ Could not extract text from `{file_title}`, skipping...")
                
                progress_bar.progress((index + 1) / total_files)
            
            status_text.success(f"🎉 Completed! All files processed successfully.")

    with tab2:
        source_title = st.text_input("Document Title")
        source_content = st.text_area("Paste lecture material or article text here", height=200)
        if source_title and source_content and st.button("⚡ Automatically Sort & Upload Text"):
            with st.spinner("Analyzing content..."):
                target_nb = asyncio.run(auto_categorize_content(source_content, notebook_list_names))
                
                if not target_nb or target_nb not in user_notebooks:
                    if "sharon" in user_notebooks:
                        target_nb = "sharon"
                    else:
                        target_nb = notebook_list_names[0]
                        
                st.info(f"🧠 AI matched topic meaning to notebook: **{target_nb}**")
                asyncio.run(upload_to_notebooklm(user_notebooks[target_nb], source_title, source_content))
                st.success(f"✅ Success! Sent '{source_title}' straight into your **{target_nb}** notebook.")