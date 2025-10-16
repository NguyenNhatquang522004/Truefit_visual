# app.py - Streamlit interface for AI Unified Shopping Assistant

import streamlit as st
import asyncio
from pathlib import Path
import base64
from PIL import Image
import io
import os
from dotenv import load_dotenv
from streamlit_drawable_canvas import st_canvas
import json
import numpy as np

# Load environment variables
load_dotenv()

# Import root agent
from agent import root_agent
from utils import classify_user_intent, generate_clarification_prompt

# Configure page
st.set_page_config(
    page_title="AI Visual Assistant",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed"  # Hide sidebar như trong hình mẫu
)

# Custom CSS - Dark theme với Bootstrap Icons
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
    
    /* === DARK THEME BASE === */
    .stApp {
        background-color: #0f0f0f;
        color: #e0e0e0;
    }
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    
    /* Hide sidebar completely */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Main container */
    .block-container {
        padding: 2rem 3rem 10rem 3rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* === HEADER === */
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
        margin-bottom: 0.5rem;
    }
    
    /* === CHAT MESSAGES === */
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
    
    .agent-badge i {
        font-size: 1.2rem;
    }
    
    .message-content {
        flex: 1;
        min-width: 0;
    }
    
    /* User message - Blue bubble */
    .user-message {
        background: linear-gradient(135deg, #1e3a8a 0%, #1e40af 100%);
        color: white;
        padding: 1rem 1.25rem;
        border-radius: 12px;
        max-width: 85%;
        margin-left: auto;
        box-shadow: 0 2px 8px rgba(30, 58, 138, 0.4);
    }
    
    /* AI message - Dark gray container */
    .ai-message {
        background: #1a1a1a;
        border: 1px solid #2d2d2d;
        color: #e0e0e0;
        padding: 1.25rem;
        border-radius: 12px;
        max-width: 100%;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    }
    
    /* Agent indicator chips */
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
    
    .agent-indicator-icon {
        color: #60a5fa;
        font-size: 1rem;
    }
    
    /* Function call badge */
    .function-call {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        background: #1a1a1a;
        border: 1px solid #2d2d2d;
        color: #e0e0e0;
        padding: 0.4rem 0.9rem;
        border-radius: 6px;
        font-size: 0.8rem;
        font-family: 'Monaco', 'Courier New', monospace;
        margin-top: 0.5rem;
    }
    
    /* Image container trong chat */
    .chat-image-container {
        background: #1a1a1a;
        border: 2px solid #1e3a8a;
        border-radius: 12px;
        padding: 0.5rem;
        margin: 1rem 0;
        max-width: 600px;
    }
    
    .chat-image-container img {
        border-radius: 8px;
        width: 100%;
        height: auto;
    }
    
    /* === FILE UPLOADER === */
    /* Hide drag-drop area but keep Browse button accessible for JavaScript */
    #file-uploader-container {
        position: fixed !important;
        top: -9999px !important;
        left: -9999px !important;
        width: 300px !important;
        height: 200px !important;
        overflow: visible !important;
        z-index: -1 !important;
        opacity: 0.01 !important;
        pointer-events: auto !important;
    }
    
    /* Make sure button and input are clickable even though hidden */
    #file-uploader-container button,
    #file-uploader-container input[type="file"] {
        pointer-events: auto !important;
        cursor: pointer !important;
    }
    
    /* Hide all Streamlit file uploader UI globally */
    section[data-testid="stFileUploadDropzone"],
    [data-testid="stFileUploadDropzone"],
    div[data-testid="stFileUploader"] section {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* === HIDE STREAMLIT CHAT INPUT COMPLETELY === */
    .stChatInput,
    section[data-testid="stChatInput"],
    [data-testid="stChatInput"],
    div[data-testid="stChatInputContainer"] {
        display: none !important;
        visibility: hidden !important;
        position: absolute !important;
        left: -9999px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        z-index: -9999 !important;
    }
    
    /* Custom hidden file input */
    #custom-file-input {
        position: absolute;
        left: -9999px;
        opacity: 0.01;
        pointer-events: all;
    }
    
    /* === CHAT INPUT - FIXED BOTTOM === */
    /* Chat input container - Always at bottom */
    .chat-input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #0f0f0f;
        border-top: 1px solid #2d2d2d;
        padding: 1rem 0;
        z-index: 999;
        box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.5);
    }
    
    /* Input wrapper - Centered with max width */
    .chat-input-wrapper {
        max-width: 750px;
        margin: 0 auto;
        padding: 0 1rem;
        display: flex;
        align-items: center;
        background: #2a2a2a;
        border: 1px solid #3d3d3d;
        border-radius: 24px;
        padding: 0.5rem 1rem;
        gap: 0.75rem;
        transition: border-color 0.3s ease;
    }
    
    .chat-input-wrapper:focus-within {
        border-color: #1e40af;
        box-shadow: 0 0 0 2px rgba(30, 64, 175, 0.2);
    }
    
    /* Icon buttons */
    .input-icon-btn {
        color: #888;
        font-size: 1.1rem;
        cursor: pointer;
        transition: all 0.2s ease;
        padding: 0.4rem;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 32px;
        height: 32px;
        background: transparent;
        border: none;
        flex-shrink: 0;
    }
    
    .input-icon-btn:hover {
        color: #e0e0e0;
        background: #3d3d3d;
    }
    
    /* Custom input field */
    #custom-chat-input {
        flex: 1;
        background: transparent;
        border: none;
        color: #e0e0e0;
        font-size: 0.95rem;
        font-family: 'Inter', -apple-system, sans-serif;
        outline: none;
        padding: 0.5rem 0;
        resize: none;
        overflow-y: auto;
        max-height: 150px;
        line-height: 1.5;
    }
    
    #custom-chat-input::placeholder {
        color: #666;
    }
    
    #custom-chat-input:focus {
        outline: none;
    }
    
    /* Hide file uploader completely but keep it accessible for JS */
    .hidden-file-uploader {
        position: absolute;
        left: -9999px;
        width: 1px;
        height: 1px;
        opacity: 0;
        pointer-events: all;
    }
    
    /* Remove all Streamlit default styling */
    [data-testid="column"] {
        background: transparent !important;
        padding: 0 !important;
    }
    
    /* === INFO BOXES === */
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
    
    /* === CANVAS === */
    .streamlit-drawable-canvas {
        border: 2px solid #2d2d2d !important;
        border-radius: 12px !important;
    }
    
    /* === EXPANDER === */
    .streamlit-expanderHeader {
        background: #1a1a1a !important;
        border: 1px solid #2d2d2d !important;
        border-radius: 8px !important;
        color: #e0e0e0 !important;
    }
    
    .streamlit-expanderContent {
        background: #1a1a1a !important;
        border: 1px solid #2d2d2d !important;
        border-radius: 8px !important;
    }
    
    /* === SCROLLBAR === */
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
    
    /* === HIDE STREAMLIT BRANDING === */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>

<script>
// ============================================
// FILE UPLOAD TRIGGER - SIMPLIFIED VERSION
// ============================================
function openFileUpload() {
    console.log('========================================');
    console.log('🔵 PAPERCLIP CLICKED!');
    console.log('========================================');
    
    // Wait a bit for Streamlit to fully render
    setTimeout(function() {
        console.log('Starting search for file upload elements...');
        
        // Debug: Show all file inputs
        const allFileInputs = document.querySelectorAll('input[type="file"]');
        console.log('📊 Total file inputs found:', allFileInputs.length);
        
        allFileInputs.forEach((input, index) => {
            console.log(`Input ${index}:`, {
                id: input.id,
                name: input.name,
                accept: input.accept,
                multiple: input.multiple,
                visible: input.offsetParent !== null,
                offsetTop: input.offsetTop,
                offsetLeft: input.offsetLeft
            });
        });
        
        // Debug: Show all buttons
        const allButtons = document.querySelectorAll('button');
        console.log('📊 Total buttons found:', allButtons.length);
        
        const browseButtons = [];
        allButtons.forEach((btn, index) => {
            const text = btn.textContent.toLowerCase();
            if (text.includes('browse') || text.includes('file')) {
                console.log(`Button ${index} (POTENTIAL):`, {
                    text: btn.textContent,
                    visible: btn.offsetParent !== null
                });
                browseButtons.push(btn);
            }
        });
        
        // TRY METHOD 1: Click Browse button
        if (browseButtons.length > 0) {
            console.log('✅ METHOD 1: Found', browseButtons.length, 'browse buttons');
            const btn = browseButtons[0];
            console.log('Clicking button:', btn.textContent);
            btn.click();
            console.log('✅ Button clicked!');
            return;
        }
        
        // TRY METHOD 2: Click file input directly
        if (allFileInputs.length > 0) {
            console.log('✅ METHOD 2: Found', allFileInputs.length, 'file inputs');
            const input = allFileInputs[0];
            
            // Make absolutely sure it's clickable
            input.style.position = 'fixed';
            input.style.top = '0';
            input.style.left = '0';
            input.style.opacity = '0.01';
            input.style.pointerEvents = 'auto';
            input.style.width = '100px';
            input.style.height = '100px';
            input.style.zIndex = '99999';
            
            console.log('Clicking file input...');
            input.click();
            console.log('✅ File input clicked!');
            return;
        }
        
        // FAILED
        console.error('❌ FAILED: No file input or browse button found');
        console.log('Container check:');
        const container = document.querySelector('#file-uploader-container');
        console.log('  #file-uploader-container exists:', !!container);
        if (container) {
            console.log('  Container HTML preview:', container.innerHTML.substring(0, 300));
        }
        
        alert('❌ Cannot find file uploader.\n\nPlease:\n1. Reload page (Ctrl+R)\n2. Wait 5 seconds\n3. Try again');
        
    }, 500);  // Wait 500ms for Streamlit to render
}

// ============================================
// CUSTOM CHAT INPUT HANDLER
// ============================================
const customChatInput = {
    init: function() {
        const textarea = document.getElementById('custom-chat-input');
        if (!textarea) {
            console.log('⚠️ Custom textarea not found yet');
            return;
        }
        
        console.log('✅ Custom chat input initialized');
        
        // Handle Enter key (submit)
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                customChatInput.submitMessage();
            }
        });
        
        // Auto-resize textarea
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 150) + 'px';
        });
    },
    
    submitMessage: function() {
        const textarea = document.getElementById('custom-chat-input');
        const message = textarea.value.trim();
        
        if (message) {
            console.log('📤 Submitting message:', message);
            
            // Find Streamlit's hidden chat input
            const stInput = document.querySelector('.stChatInput textarea');
            if (stInput) {
                stInput.value = message;
                stInput.dispatchEvent(new Event('input', { bubbles: true }));
                
                // Trigger form submission
                const form = stInput.closest('form');
                if (form) {
                    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                }
                
                console.log('✅ Message submitted to Streamlit');
            } else {
                console.error('❌ Streamlit chat input not found');
            }
            
            // Clear custom input
            textarea.value = '';
            textarea.style.height = 'auto';
        }
    }
};

// ============================================
// INITIALIZATION
// ============================================
window.addEventListener('load', function() {
    console.log('========================================');
    console.log('🟢 PAGE LOADED - App ready');
    console.log('========================================');
    
    // Initialize custom chat input
    setTimeout(customChatInput.init, 500);
    
    // Re-initialize on Streamlit reruns
    const observer = new MutationObserver(function() {
        setTimeout(customChatInput.init, 100);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    
    console.log('✅ Event listeners attached');
    console.log('✅ Ready to upload files - Click paperclip icon');
});
</script>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'canvas_coordinates' not in st.session_state:
    st.session_state.canvas_coordinates = None
if 'show_canvas' not in st.session_state:
    st.session_state.show_canvas = False
if 'session_id' not in st.session_state:
    import uuid
    st.session_state.session_id = str(uuid.uuid4())[:8]
if 'show_file_upload' not in st.session_state:
    st.session_state.show_file_upload = False

# Header - Session ID
st.markdown(f"""
<div class="main-header">
    <div class="session-id">SESSION ID {st.session_state.session_id}</div>
</div>
""", unsafe_allow_html=True)

# Display uploaded images if any
if st.session_state.uploaded_files:
    st.markdown("#### Uploaded Images")
    cols = st.columns(min(len(st.session_state.uploaded_files), 4))
    for idx, file in enumerate(st.session_state.uploaded_files):
        with cols[idx % 4]:
            image = Image.open(file)
            st.image(image, use_container_width=True, caption=file.name)

# Canvas for furniture placement (nếu có 2 ảnh)
if st.session_state.uploaded_files and len(st.session_state.uploaded_files) == 2:
    with st.expander("Draw mask for furniture placement", expanded=False):
        room_image = Image.open(st.session_state.uploaded_files[0])
        
        # Resize for canvas
        max_width = 600
        if room_image.width > max_width:
            ratio = max_width / room_image.width
            new_size = (max_width, int(room_image.height * ratio))
            room_image_resized = room_image.resize(new_size, Image.Resampling.LANCZOS)
        else:
            room_image_resized = room_image
            
        scale_ratio = room_image.width / room_image_resized.width
        
        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#FFFFF",
            background_image=room_image_resized,
            update_streamlit=True,
            drawing_mode="rect",
            point_display_radius=0,
            key="furniture_canvas",
            height=room_image_resized.height,
            width=room_image_resized.width,
        )
        
        if canvas_result.json_data is not None:
            objects = canvas_result.json_data.get("objects", [])
            if len(objects) > 0:
                last_rect = objects[-1]
                canvas_x = int(last_rect["left"])
                canvas_y = int(last_rect["top"])
                canvas_width = int(last_rect["width"])
                canvas_height = int(last_rect["height"])
                
                original_x = int(canvas_x * scale_ratio)
                original_y = int(canvas_y * scale_ratio)
                original_width = int(canvas_width * scale_ratio)
                original_height = int(canvas_height * scale_ratio)
                
                st.session_state.canvas_coordinates = {
                    "x": original_x,
                    "y": original_y,
                    "width": original_width,
                    "height": original_height
                }
                
                st.success(f"Mask saved: {original_width}×{original_height} px at ({original_x}, {original_y})")

st.markdown("---")

# Chat messages display
for message in st.session_state.messages:
    role = message["role"]
    content = message["content"]
    
    if role == "user":
        # User message - Blue bubble (right-aligned)
        st.markdown(f"""
        <div class="chat-message" style="justify-content: flex-end;">
            <div class="user-message">
                {content}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    elif role == "assistant":
        # AI message - Dark container with agent badge on left
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
        # System/Agent indicator
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

# === FILE UPLOADER - HIDDEN BUT ACCESSIBLE ===
# Place BEFORE chat input so JavaScript can find it reliably
st.markdown('<div id="file-uploader-container" class="hidden-file-uploader">', unsafe_allow_html=True)
uploaded_files = st.file_uploader(
    "Upload images",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    label_visibility="collapsed",
    key="file_uploader_main"
)
if uploaded_files:
    st.session_state.uploaded_files = uploaded_files
    st.rerun()  # Reload to show uploaded files
st.markdown('</div>', unsafe_allow_html=True)

# Chat input - Fixed at bottom with embedded icons (PURE HTML)
st.markdown("""
<div class="chat-input-container">
    <div class="chat-input-wrapper">
        <button class="input-icon-btn" onclick="openFileUpload()" title="Upload files">
            <i class="fa-solid fa-paperclip"></i>
        </button>
        <textarea 
            id="custom-chat-input" 
            placeholder="Type a Message..."
            rows="1"
        ></textarea>
        <button class="input-icon-btn" title="Menu">
            <i class="fa-solid fa-ellipsis-vertical"></i>
        </button>
        <button class="input-icon-btn" title="Voice input">
            <i class="fa-solid fa-microphone"></i>
        </button>
        <button class="input-icon-btn" title="Video call">
            <i class="fa-solid fa-video"></i>
        </button>
    </div>
</div>
""", unsafe_allow_html=True)

# Hidden Streamlit chat input (for backend processing only)
user_input = st.chat_input("Type a Message...", key="hidden_chat_input")

# Process user input
async def process_message(user_message: str, files: list):
    """Process user message with root agent"""
    try:
        # Classify intent
        intent, confidence = classify_user_intent(user_message, files)
        
        # Check if this is furniture placement and validate canvas coordinates
        if intent == "furniture_placement" and len(files) == 2:
            if st.session_state.canvas_coordinates is None:
                error_msg = """
                <div class="warning-box">
                <i class="fa-solid fa-triangle-exclamation"></i> <strong>Missing step!</strong><br><br>
                You need to draw a rectangle on the room image to indicate the area to remove. 
                Scroll up to see the "Draw mask" section.
                </div>
                """
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                return
        
        # Add system message for routing
        routing_info = f"Detected intent: <strong>{intent}</strong> (confidence: {confidence:.0%})"
        st.session_state.messages.append({"role": "system", "content": routing_info})
        
        # Show clarification if confidence is low
        if confidence < 0.6:
            clarification = generate_clarification_prompt(files, intent)
            st.session_state.messages.append({"role": "assistant", "content": clarification})
            return
        
        # Call root agent
        with st.spinner("🤖 AI đang xử lý..."):
            # Prepare context
            context = {
                "user_message": user_message,
                "uploaded_files": [f.name for f in files] if files else [],
                "intent": intent,
                "canvas_coordinates": st.session_state.canvas_coordinates if intent == "furniture_placement" else None
            }
            
            # Build response based on intent
            if intent == "furniture_placement" and st.session_state.canvas_coordinates:
                coords = st.session_state.canvas_coordinates
                coords_str = json.dumps(coords, indent=2)
                
                response = f"""
                <div class="success-box">
                <i class="fa-solid fa-circle-check"></i> <strong>Furniture placement request received!</strong>
                </div>
                
                **Information:**
                - Task type: Furniture placement
                - Confidence: {confidence:.0%}
                - Images: {len(files)} (room + furniture)
                - Mask coordinates: Saved
                
                **Selected area:**
                ```json
                {coords_str}
                ```
                
                **Processing steps:**
                1. Room image: `{files[0].name}`
                2. Furniture image: `{files[1].name}`
                3. Removal area: x={coords['x']}, y={coords['y']}, width={coords['width']}, height={coords['height']}
                4. Calling VisualAgent...
                   - Step 1: Remove old object at selected area
                   - Step 2: Place new furniture with proper lighting & shadows
                5. Generate high-quality composite image
                
                **Note:** Coordinates have been automatically scaled to original image size. 
                The tool will inpaint the selected area and place furniture naturally, 
                synchronized with room lighting and perspective.
                
                <i class="fa-solid fa-rocket"></i> **Ready to process with canvas coordinates!**
                """
            elif intent == "visual":
                response = f"""
                <div class="success-box">
                <i class="fa-solid fa-circle-check"></i> <strong>Visual request received!</strong>
                </div>
                
                **Information:**
                - Task type: {intent}
                - Confidence: {confidence:.0%}
                - Uploaded files: {len(files) if files else 0}
                
                **Processing with:**
                - Visual Agent: Furniture placement or Virtual try-on
                
                **Note:** Google ADK integration is being finalized. 
                This is a demo interface. In production:
                1. Root agent receives message + files + canvas coordinates
                2. Routes to VisualAgent
                3. Agent calls corresponding tools (remove_and_place_object or virtual_tryon)
                4. Returns formatted results
                
                **Next steps:**
                - Full google-adk integration
                - Test with Google API key
                - Validate 2 visual features
                """
            else:
                response = f"""
                <div class="warning-box">
                <i class="fa-solid fa-triangle-exclamation"></i> <strong>Request not supported</strong>
                </div>
                
                Currently only supports 2 features:
                - Furniture placement (requires 2 images)
                - Virtual try-on (requires 2 images)
                
                Detected intent: {intent} (not visual)
                """
            
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    except Exception as e:
        error_msg = f"""
        <div class="error-box">
        <i class="fa-solid fa-circle-xmark"></i> <strong>An error occurred:</strong><br><br>
        {str(e)}<br><br>
        <small>Please try again or contact support if the error persists.</small>
        </div>
        """
        st.session_state.messages.append({"role": "assistant", "content": error_msg})

if user_input and not st.session_state.processing:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Set processing flag
    st.session_state.processing = True
    
    # Process message
    asyncio.run(process_message(user_input, st.session_state.uploaded_files))
    
    # Reset processing flag
    st.session_state.processing = False
    
    # Rerun to show new messages
    st.rerun()

# Minimal footer
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0 1rem 0; font-size: 0.8rem; border-top: 1px solid #2d2d2d; margin-top: 3rem;">
    AI Visual Assistant  Powered by Google ADK 
</div>
""", unsafe_allow_html=True)
