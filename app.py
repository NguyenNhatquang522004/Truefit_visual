# app_v2.py - FIXED VERSION with Native Streamlit File Uploader

import streamlit as st
import asyncio
from PIL import Image
import json
import uuid

# Import modules
from tools import remove_and_place_object, virtual_tryon, RemoveAndPlaceObjectInput, VirtualTryOnInput
from google.adk.tools import ToolContext
from google.genai import types
from utils import classify_user_intent, generate_clarification_prompt
from pathlib import Path
import tempfile
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Verify API key
if not os.getenv("GOOGLE_API_KEY"):
    st.error("❗ GOOGLE_API_KEY not found in environment variables!")
    st.stop()


# ===== STREAMLIT TOOL CONTEXT =====
class StreamlitToolContext(ToolContext):
    """ToolContext implementation for Streamlit app"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.version_counters = {}
    
    async def load_artifact(self, filename: str):
        """Load image from file"""
        file_path = Path(filename)
        if not file_path.is_absolute():
            file_path = self.output_dir.parent / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            image_data = f.read()
        
        # Determine MIME type
        suffix = file_path.suffix.lower()
        mime_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }.get(suffix, 'image/jpeg')
        
        return types.Part(
            inline_data=types.Blob(
                mime_type=mime_type,
                data=image_data
            )
        )
    
    async def save_artifact(self, filename: str, artifact):
        """Save generated image"""
        output_path = self.output_dir / filename
        
        if hasattr(artifact, 'inline_data') and artifact.inline_data:
            with open(output_path, 'wb') as f:
                f.write(artifact.inline_data.data)
                f.flush()  # Force flush to disk
                os.fsync(f.fileno())  # Ensure data written to disk
            
            # Verify file exists and has content
            if output_path.exists() and output_path.stat().st_size > 0:
                return output_path
            else:
                raise ValueError(f"Failed to save artifact to {output_path}")
        else:
            raise ValueError("Artifact does not contain inline_data")

# Page config
st.set_page_config(
    page_title="AI Visual Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Native Streamlit với style đẹp
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
    
    /* Dark theme */
    .stApp {
        background-color: #0f0f0f;
        color: #e0e0e0;
    }
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar - Resizable */
    [data-testid="stSidebar"] {
        background-color: #1a1a1a;
        border-right: 1px solid #2d2d2d;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        color: #e0e0e0;
    }
    
    [data-testid="stSidebar"] h3 {
        color: #1e40af;
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    
    [data-testid="stSidebar"] h4 {
        color: #3b82f6;
        font-size: 1rem;
        font-weight: 600;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #2d2d2d;
        padding-bottom: 0.5rem;
    }
    
    [data-testid="stSidebar"] ul {
        color: #a0a0a0;
        font-size: 0.875rem;
    }
    
    [data-testid="stSidebar"] hr {
        border-color: #2d2d2d;
        margin: 1rem 0;
        opacity: 0.5;
    }
    
    /* Sidebar file uploader */
    [data-testid="stSidebar"] [data-testid="stFileUploader"] {
        background: #0f0f0f;
        border: 2px dashed #2d2d2d;
        border-radius: 8px;
        padding: 1rem;
    }
    
    [data-testid="stSidebar"] [data-testid="stFileUploader"]:hover {
        border-color: #1e40af;
        background: #1a1a1a;
    }
    
    [data-testid="stSidebar"] [data-testid="stFileUploader"] button {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%) !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1rem !important;
    }
    
    /* Sidebar expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #0f0f0f;
        border: 1px solid #2d2d2d;
        border-radius: 6px;
        margin: 0.5rem 0;
    }
    
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        font-size: 0.875rem !important;
        color: #e0e0e0 !important;
    }
    
    /* Sidebar metrics */
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: #0f0f0f;
        padding: 0.75rem;
        border-radius: 6px;
        border: 1px solid #2d2d2d;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        color: #a0a0a0 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
        color: #1e40af !important;
        font-weight: 700 !important;
    }
    
    /* Main container */
    .block-container {
        padding: 2rem 3rem 3rem 3rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* Header */
    .main-header {
        text-align: center;
        padding: 1.5rem 0 2rem 0;
        border-bottom: 1px solid #2d2d2d;
        margin-bottom: 2rem;
    }
    
    .session-id {
        color: #666;
        font-size: 0.75rem;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    
    /* NATIVE FILE UPLOADER STYLING */
    [data-testid="stFileUploader"] {
        background: #1a1a1a;
        border: 2px dashed #3d3d3d;
        border-radius: 12px;
        padding: 2rem;
        transition: all 0.3s ease;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: #1e40af;
        background: #1e1e1e;
    }
    
    [data-testid="stFileUploader"] label {
        color: #e0e0e0 !important;
        font-size: 1rem !important;
        font-weight: 500 !important;
    }
    
    [data-testid="stFileUploader"] button {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    
    [data-testid="stFileUploader"] button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(30, 64, 175, 0.4) !important;
    }
    
    /* Chat messages */
    .chat-message {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
        align-items: flex-start;
    }
    
    .agent-badge {
        background: #1e3a8a;
        color: white;
        width: 40px;
        height: 40px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        flex-shrink: 0;
        box-shadow: 0 2px 8px rgba(30, 58, 138, 0.3);
    }
    
    .user-message {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        color: white;
        padding: 1rem 1.25rem;
        border-radius: 12px;
        max-width: 85%;
        margin-left: auto;
        box-shadow: 0 2px 8px rgba(30, 58, 138, 0.4);
    }
    
    .ai-message {
        background: #1a1a1a;
        border: 1px solid #2d2d2d;
        color: #e0e0e0;
        padding: 1.25rem;
        border-radius: 12px;
        max-width: 100%;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    }
    
    .agent-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: #1a1a1a;
        border: 1px solid #2d2d2d;
        color: #e0e0e0;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-size: 0.875rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
    }
    
    /* Info boxes */
    .success-box {
        background: #064e3b;
        border-left: 3px solid #10b981;
        color: #d1fae5;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .warning-box {
        background: #78350f;
        border-left: 3px solid #f59e0b;
        color: #fef3c7;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    .error-box {
        background: #7f1d1d;
        border-left: 3px solid #ef4444;
        color: #fecaca;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: #1a1a1a !important;
        border: 1px solid #2d2d2d !important;
        border-radius: 8px !important;
        color: #e0e0e0 !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    
    .streamlit-expanderHeader:hover {
        border-color: #1e40af !important;
        background: #1e1e1e !important;
    }
    
    /* Full size image expander */
    details[open] summary {
        margin-bottom: 1rem;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #0f0f0f;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #2d2d2d;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #3d3d3d;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]
if 'processed_message_id' not in st.session_state:
    st.session_state.processed_message_id = None
if 'last_generated_image' not in st.session_state:
    st.session_state.last_generated_image = None
if 'processed_message_ids' not in st.session_state:
    st.session_state.processed_message_ids = set()  # Track all processed message IDs
if 'generating_image' not in st.session_state:
    st.session_state.generating_image = False  # Track image generation status

# === SIDEBAR ===
with st.sidebar:
    st.markdown("### <i class='fas fa-robot'></i> AI Visual Assistant", unsafe_allow_html=True)
    st.markdown(f"<p style='color: #666; font-size: 0.75rem;'>Session: {st.session_state.session_id}</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    # FILE UPLOADER IN SIDEBAR
    st.markdown("#### <i class='fas fa-cloud-upload-alt'></i> Upload Images", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 0.875rem; color: #a0a0a0; margin-bottom: 1rem;'>Upload 2 images for processing</p>", unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "Choose images",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="file_uploader_sidebar",
        help="Upload exactly 2 images (Room/Person + Product)",
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        st.session_state.uploaded_files = uploaded_files
        
        # Display uploaded images in sidebar
        st.markdown(f"<p style='color: #10b981; font-size: 0.875rem; margin-top: 1rem;'><i class='fas fa-check-circle'></i> {len(uploaded_files)} image(s) uploaded</p>", unsafe_allow_html=True)
        
        for idx, file in enumerate(uploaded_files):
            with st.expander(f"🖼️ {file.name}", expanded=False):
                image = Image.open(file)
                st.image(image, use_column_width=True)
                # Show image info
                img_size = len(file.getvalue()) / 1024
                st.caption(f"Size: {img_size:.1f} KB")
    else:
        st.session_state.uploaded_files = []
        st.markdown("<p style='color: #666; font-size: 0.875rem; font-style: italic;'>No images uploaded yet</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # QUICK STATS
    st.markdown("#### <i class='fas fa-chart-bar'></i> Session Stats", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Messages", len(st.session_state.messages))
    with col2:
        st.metric("Images", len(st.session_state.uploaded_files) if st.session_state.uploaded_files else 0)
    
    st.markdown("---")
    
    # QUICK GUIDE
    
    
    st.markdown("---")
    
    # MODEL INFO
    st.markdown("#### <i class='fas fa-cog'></i> Model Info", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size: 0.8rem; color: #666;'>
    <b>Engine:</b> Gemini 2.5 Flash<br/>
    <b>Mode:</b> 2-Image Processing<br/>
    <b>Provider:</b> Google ADK
    </div>
    """, unsafe_allow_html=True)

# Header
st.markdown(f"""
<div class="main-header">
    <h1><i class="fas fa-robot"></i> AI Visual Assistant</h1>
    <div class="session-id">SESSION ID {st.session_state.session_id}</div>
</div>
""", unsafe_allow_html=True)

# Main content area - removed file uploader (now in sidebar)

# Chat controls
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🗑️ Clear Chat", help="Clear all chat messages"):
        st.session_state.messages = []
        st.session_state.processing = False
        st.session_state.last_generated_image = None
        st.session_state.processed_message_ids = set()  # Reset processed IDs
        st.rerun()

# Chat messages display
for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    
    if role == "user":
        st.markdown(f"""
        <div class="chat-message" style="justify-content: flex-end;">
            <div class="user-message">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    elif role == "assistant":
        st.markdown(f"""
        <div class="chat-message">
            <div class="agent-badge">
                <i class="fa-solid fa-microchip"></i>
            </div>
            <div class="message-content">
                <div class="ai-message">
                    {content}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    elif role == "system":
        st.markdown(f"""
        <div class="chat-message">
            <div class="agent-badge">
                <i class="fa-solid fa-bolt"></i>
            </div>
            <div class="message-content">
                <div class="agent-indicator">
                    <span class="agent-indicator-icon"><i class="fa-solid fa-gear"></i></span>
                    {content}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Display last generated image if exists
# Show loading state if generating image
if st.session_state.generating_image:
    st.markdown("---")
    st.markdown("### <i class='fas fa-image'></i> Generated Image", unsafe_allow_html=True)
    st.markdown("""
    <div style='background-color: #1a5490; border-left: 4px solid #3b82f6; padding: 1.5rem; border-radius: 6px; margin: 1rem 0; text-align: center;'>
        <span style='color: #e0e0e0; font-size: 1.1rem;'>
            <i class='fas fa-spinner fa-spin'></i> <strong>Generating image, please wait...</strong>
        </span>
    </div>
    """, unsafe_allow_html=True)
elif st.session_state.last_generated_image:
    st.markdown("---")
    st.markdown("### <i class='fas fa-image'></i> Generated Image", unsafe_allow_html=True)
    try:
        img_path = Path(st.session_state.last_generated_image)
        if img_path.exists():
            # Display image with expander for full size view
            image = Image.open(img_path)
            
            # Show thumbnail (smaller version)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(image, caption=f"Generated: {img_path.name}", use_column_width=True)
            
            # Show image info
            file_size = img_path.stat().st_size / 1024
            st.markdown(f"""
            <div style='background-color: #1a5490; border-left: 4px solid #3b82f6; padding: 1rem; border-radius: 6px; margin: 1rem 0;'>
                <span style='color: #e0e0e0;'>
                    <i class='fas fa-info-circle'></i> <strong>Size:</strong> {file_size:.1f} KB | 
                    <i class='fas fa-folder'></i> <strong>
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            # Expandable full-size view
            with st.expander("🔍 Click to view full size image"):
                st.image(image, use_column_width=True)
        else:
            st.markdown(f"""
            <div style='background-color: #78350f; border-left: 4px solid #f59e0b; padding: 1rem; border-radius: 6px; margin: 1rem 0;'>
                <span style='color: #fef3c7;'>
                    <i class='fas fa-exclamation-triangle'></i> <strong>Warning:</strong> Generated image file not found: <code style='background: #0f0f0f; padding: 0.2rem 0.5rem; border-radius: 4px;'>{img_path}</code>
                </span>
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div style='background-color: #7f1d1d; border-left: 4px solid #ef4444; padding: 1rem; border-radius: 6px; margin: 1rem 0;'>
            <span style='color: #fecaca;'>
                <i class='fas fa-times-circle'></i> <strong>Error displaying image:</strong> {str(e)}
            </span>
        </div>
        """, unsafe_allow_html=True)

# === CHAT INPUT - NATIVE STREAMLIT ===
st.markdown("")

# Placeholder for 2-image mode only
num_files = len(st.session_state.uploaded_files) if st.session_state.uploaded_files else 0
if num_files == 2:
    placeholder_text = "Describe placement (e.g., 'Place the sofa in the center')"
else:
    placeholder_text = "Upload 2 images first, then type your request..."

user_input = st.chat_input(placeholder_text)

# Process user input
async def process_message(user_message: str, files: list):
    """Process user message with REAL ROOT AGENT from Google ADK"""
    try:
        # Classify intent
        intent, confidence = classify_user_intent(user_message, files)
        
        # Show clarification only if intent is unclear (no images uploaded)
        if intent == "unclear":
            clarification = generate_clarification_prompt(files, intent)
            st.session_state.messages.append({"role": "assistant", "content": clarification})
            return
        
        # VISUAL INTENT - Call REAL AGENT
        if intent == "visual" and len(files) == 2:
            # No canvas coordinates (canvas feature removed)
            coords = None
            
            # Save uploaded files to temp directory
            temp_dir = Path(tempfile.gettempdir()) / "ai_visual_assistant"
            temp_dir.mkdir(exist_ok=True, parents=True)
            
            # Save files
            file_paths = []
            for file in files:
                file_path = temp_dir / file.name
                with open(file_path, 'wb') as f:
                    f.write(file.getvalue())
                file_paths.append(str(file_path))
            
            # Create tool context
            output_dir = Path("generated_images")
            output_dir.mkdir(exist_ok=True, parents=True)
            tool_context = StreamlitToolContext(output_dir)
            
            # Classify task type from user message
            furniture_keywords = ["xóa", "đặt", "thay", "phòng", "bàn", "ghế", "tủ", "nội thất", "sofa", "kệ"]
            fashion_keywords = ["thử", "mặc", "áo", "quần", "đồ", "váy", "jacket", "dress", "shirt", "pants"]
            
            is_furniture = any(kw in user_message.lower() for kw in furniture_keywords)
            is_fashion = any(kw in user_message.lower() for kw in fashion_keywords)
            
            # Default to furniture if unclear
            if not is_fashion:
                # FURNITURE PLACEMENT
                tool_input = RemoveAndPlaceObjectInput(
                    room_image_filename=file_paths[0],
                    furniture_image_filename=file_paths[1],
                    mask_coordinates=json.dumps(coords) if coords else "{}",
                    removal_prompt=user_message,
                    placement_description=user_message,
                    asset_name="furniture_placement"
                )
                
                result = await remove_and_place_object(tool_context, tool_input)
                
                # Find generated image
                generated_files = sorted(output_dir.glob("furniture_placement_v*.png"), 
                                       key=lambda p: p.stat().st_mtime, reverse=True)
                
            else:
                # VIRTUAL TRY-ON
                # Auto-detect clothing type
                if "áo" in user_message.lower() or "shirt" in user_message.lower():
                    clothing_type = "shirt"
                elif "quần" in user_message.lower() or "pants" in user_message.lower():
                    clothing_type = "pants"
                elif "váy" in user_message.lower() or "dress" in user_message.lower():
                    clothing_type = "dress"
                elif "jacket" in user_message.lower():
                    clothing_type = "jacket"
                else:
                    clothing_type = "shirt"  # Default
                
                tool_input = VirtualTryOnInput(
                    person_image_filename=file_paths[0],
                    clothing_image_filename=file_paths[1],
                    clothing_type=clothing_type,
                    asset_name="virtual_tryon"
                )
                
                result = await virtual_tryon(tool_context, tool_input)
                
                # Find generated image
                generated_files = sorted(output_dir.glob("virtual_tryon_v*.png"), 
                                       key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Display result
            if generated_files:
                latest_image = generated_files[0]
                st.session_state.last_generated_image = str(latest_image)
                
                response = f"""<i class='fas fa-check-circle' style='color: #10b981;'></i> **Processing completed!**

<i class='fas fa-chart-line'></i> **Result:** {result}

<i class='fas fa-image'></i> **Generated:** `{latest_image.name}` ({latest_image.stat().st_size / 1024:.1f} KB)"""
            else:
                response = f"""<i class='fas fa-exclamation-triangle' style='color: #f59e0b;'></i> **Tool executed but no image found**

<i class='fas fa-chart-line'></i> **Result:** {result}"""
            
            st.session_state.messages.append({"role": "assistant", "content": response})
        
        else:
            response = f"""<i class='fas fa-exclamation-triangle' style='color: #f59e0b;'></i> **Request not supported**

Currently requires exactly 2 images for processing.

**Detected:**
- Images uploaded: {len(files)}
- Intent: {intent}

<i class='fas fa-lightbulb' style='color: #3b82f6;'></i> Please upload 2 images to continue."""
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        error_msg = f"""<i class='fas fa-times-circle' style='color: #ef4444;'></i> **Error occurred:**

{str(e)}

**Technical Details:**
```
{error_details}
```

<i class='fas fa-lightbulb' style='color: #3b82f6;'></i> Please try again or contact support."""
        st.session_state.messages.append({"role": "assistant", "content": error_msg})

if user_input and not st.session_state.processing:
    # Create unique message ID
    message_id = str(uuid.uuid4())
    
    # CRITICAL: Check if this exact user input was already processed recently
    # This prevents duplicate processing when Streamlit reruns
    recent_messages = [msg for msg in st.session_state.messages if msg.get("role") == "user"]
    if recent_messages and len(recent_messages) > 0:
        last_user_msg = recent_messages[-1]
        if last_user_msg.get("content") == user_input and last_user_msg.get("processed") == True:
            # Same message already processed - ignore this rerun
            st.stop()
    
    # Double check - ensure this message ID is not already processed
    if message_id in st.session_state.processed_message_ids:
        st.warning("⚠️ Duplicate message detected. Please try again.")
        st.stop()
    
    # Add user message with ID and processed flag
    st.session_state.messages.append({
        "role": "user", 
        "content": user_input,
        "id": message_id,
        "processed": False  # Mark as not processed yet
    })
    
    # Set processing flag
    st.session_state.processing = True
    st.session_state.processed_message_id = message_id
    
    # Rerun immediately to show user message
    st.rerun()

# Process pending message (separate from input handling)
if st.session_state.processing:
    # Find the message that needs processing
    for msg in st.session_state.messages:
        if (msg["role"] == "user" and 
            msg.get("id") == st.session_state.processed_message_id and 
            msg.get("id") not in st.session_state.processed_message_ids):  # Check if not already processed
            
            # CRITICAL: Double-check that we haven't already generated a response for this
            # Count messages after this user message to see if response already exists
            msg_index = st.session_state.messages.index(msg)
            messages_after = st.session_state.messages[msg_index + 1:]
            if any(m.get("role") == "assistant" for m in messages_after):
                # Response already exists - skip processing
                st.session_state.processing = False
                st.session_state.processed_message_id = None
                st.session_state.processed_message_ids.add(msg.get("id"))
                break
            
            # Mark as processed IMMEDIATELY to prevent duplicate processing
            st.session_state.processed_message_ids.add(msg.get("id"))
            msg["processed"] = True
            
            # Set generating state before processing
            st.session_state.generating_image = True
            
            # Process message
            asyncio.run(process_message(msg["content"], st.session_state.uploaded_files))
            
            # Reset generating state after processing
            st.session_state.generating_image = False
            
            # Reset processing flag BEFORE rerun
            st.session_state.processing = False
            st.session_state.processed_message_id = None
            
            # IMPORTANT: Only rerun once to show response
            # After this rerun, processing=False so won't enter this block again
            st.rerun()
            break
    
    # If we get here and still processing, something went wrong
    # Reset to prevent infinite loop
    if st.session_state.processing:
        st.session_state.processing = False
        st.session_state.processed_message_id = None

# Footer
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0 1rem 0; font-size: 0.8rem; border-top: 1px solid #2d2d2d; margin-top: 3rem;">
    <i class="fas fa-robot"></i> AI Visual Assistant | Powered by Google ADK & Gemini 2.5 Flash
</div>
""", unsafe_allow_html=True)
