# tools.py - VisualAgent tools only (Furniture Placement + Virtual Try-On)

from google import genai
from google.genai import types
from google.adk.tools import ToolContext
from pydantic import BaseModel, Field
import json
from typing import Optional

# Support both relative and absolute imports
try:
    from .api_key_manager import get_api_key_manager
except ImportError:
    from api_key_manager import get_api_key_manager

# === API KEY HELPER ===
def get_genai_client() -> genai.Client:
    """
    Get Google Genai Client with current API key from manager.
    Automatically uses rotation/failover system.
    """
    manager = get_api_key_manager()
    current_key = manager.get_current_key()
    return genai.Client(api_key=current_key)

# === FURNITURE PLACEMENT ===
class RemoveAndPlaceObjectInput(BaseModel):
    room_image_filename: str = Field(description="Filename of room image uploaded by user")
    furniture_image_filename: str = Field(description="Filename of furniture/object image to place")
    mask_coordinates: str = Field(default="{}", description="JSON string with x, y, width, height for removal area (optional - leave empty for AI auto-detect)")
    removal_prompt: str = Field(default="", description="Text description of object to remove (e.g., 'Remove the bed from the room')")
    placement_description: str = Field(description="Where to place the object (e.g., 'center of room', 'next to wall')")
    asset_name: str = Field(default="furniture_placement", description="Name for output file")

async def remove_and_place_object(
    tool_context: ToolContext,
    inputs: RemoveAndPlaceObjectInput
) -> str:
    """Two-step: Remove object → Place furniture using Gemini image generation"""
    client = get_genai_client()
    
    try:
        room_img = await tool_context.load_artifact(inputs.room_image_filename)
        furniture_img = await tool_context.load_artifact(inputs.furniture_image_filename)
        
        # Step 1: Removal (support both coordinate-based and prompt-based)
        coords = json.loads(inputs.mask_coordinates) if inputs.mask_coordinates and inputs.mask_coordinates != "{}" else None
        
        if coords and all(k in coords for k in ['x', 'y', 'width', 'height']):
            # Coordinate-based removal (old method)
            removal_prompt = f"""Remove the object at coordinates x={coords['x']}, y={coords['y']}, 
            width={coords['width']}, height={coords['height']}. Fill the area naturally to match 
            the surrounding environment. Maintain original lighting and perspective."""
        else:
            # Prompt-based removal - UNIVERSAL DETAILED TEMPLATE for ALL objects
            removal_text = inputs.removal_prompt if inputs.removal_prompt else "Remove the main object"
            
            # UNIVERSAL DETAILED REMOVAL - Works for ANY object type
            removal_prompt = f"""CRITICAL INSTRUCTION: {removal_text} COMPLETELY from this image.

UNIVERSAL OBJECT REMOVAL PROCESS (Applies to ALL objects):

STEP 1 - IDENTIFY THE ENTIRE OBJECT:
• Detect the COMPLETE boundary of the object mentioned
• Include ALL components:
  - Main body/structure (thân chính)
  - Supporting parts: legs, base, frame (chân đế, khung)
  - Attached elements: cushions, panels, accessories (đệm, tấm, phụ kiện)
  - Surface items: anything ON or ATTACHED to the object (đồ vật bên trên)
  - Shadows cast BY the object (bóng đổ của vật)
  - Reflections of the object (phản chiếu)

• Determine object boundaries:
  - Left edge → Right edge (từ cạnh trái → cạnh phải)
  - Front → Back (từ phía trước → phía sau)
  - Bottom (floor contact) → Top (highest point) (từ sàn → đỉnh cao nhất)

STEP 2 - REMOVE EVERY PIXEL:
• Delete 100% of the object - NOTHING must remain visible
• Start from center, expand to all edges
• Continue until:
  ☐ NO main body visible (không còn thân chính)
  ☐ NO supporting parts visible (không còn phần đỡ)
  ☐ NO attached elements visible (không còn phần gắn kèm)
  ☐ NO surface items visible (không còn đồ vật bên trên)
  ☐ NO shadows of object visible (không còn bóng đổ)
  ☐ NO partial edges, corners, or fragments (không còn góc cạnh hay mảnh vụn)

STEP 3 - FILL THE EMPTY SPACE NATURALLY:
• Reconstruct background as if object never existed:
  - Floor/Ground: Continue texture pattern (wood, tile, carpet, grass, concrete, etc.)
  - Walls: Extend texture/color where object was against wall
  - Baseboards: Continue lines if object blocked them
  - Background: Match pattern (curtains, artwork, furniture behind object)

• Maintain environmental consistency:
  - Lighting: Match direction and intensity from surroundings
  - Shadows: Add natural shadows from OTHER objects/people (not from removed object)
  - Color grading: Keep consistent with rest of image
  - Perspective: Maintain vanishing points and depth
  - Texture detail: Match sharpness/resolution of surrounding area

STEP 4 - QUALITY VERIFICATION (ALL must pass):
☐ Object is 100% GONE - not even 1 pixel visible
☐ Floor/ground texture continuous and natural
☐ Wall/background texture seamless (if applicable)
☐ Lighting consistent across filled area
☐ NO editing artifacts (seams, blurs, color shifts)
☐ NO discontinuities in patterns/lines
☐ Perspective maintained correctly
☐ Result looks PHOTOREALISTIC - as if object was never there

FINAL CHECK: 
Output MUST show the scene WITHOUT the specified object.
If you can see ANY trace of the object (even a tiny corner, shadow, or edge) → This task has COMPLETELY FAILED.

EXAMPLES (This process works for):
- Furniture: bed, sofa, table, chair, cabinet, desk
- People: person, child, adult, group
- Vehicles: car, bike, motorcycle, truck
- Electronics: TV, computer, phone, speaker
- Decorations: plant, vase, picture frame, lamp
- Animals: dog, cat, bird, pet
- ANY other object user specifies"""
        
        contents = [types.Content(role="user", parts=[
            types.Part(text=removal_prompt), room_img
        ])]
        
        removed_img = None
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        ):
            if chunk.candidates and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data:
                    removed_img = types.Part(inline_data=part.inline_data)
        
        if not removed_img:
            return "❌ Step 1 FAILED: Could not remove object. AI did not generate removal image."
        
        # Optional: Save intermediate removal image for debugging
        if hasattr(tool_context, 'output_dir'):
            debug_filename = f"{inputs.asset_name}_step1_removal_debug.png"
            try:
                await tool_context.save_artifact(debug_filename, removed_img)
            except:
                pass  # Non-critical, continue even if debug save fails
        
        # Step 2: Placement - UNIVERSAL DETAILED TEMPLATE for ANY object
        placement_prompt = f"""CRITICAL INSTRUCTION: Place the object from the second image {inputs.placement_description}.

CONTEXT: The first image shows a scene where an object has been removed, leaving empty space.

UNIVERSAL OBJECT PLACEMENT PROCESS (Works for ALL objects):

STEP 1 - ANALYZE THE EMPTY SCENE:
• Understand the space:
  - Type of space: room, outdoor, office, street, etc.
  - Floor/Ground type: wood, tile, carpet, grass, concrete, asphalt
  - Walls/Background: color, texture, distance from placement area
  - Existing objects: furniture, people, decorations for scale reference

• Study lighting conditions:
  - Light sources: window, ceiling light, sun, lamps (identify ALL)
  - Light direction: from which side (left/right/top/behind)
  - Light intensity: bright, moderate, dim
  - Color temperature: warm (yellow), cool (blue), neutral (white)
  - Time of day: morning, afternoon, evening (affects shadows)

• Analyze perspective:
  - Camera angle: eye level, high angle, low angle
  - Vanishing points: where parallel lines converge
  - Depth perception: near objects larger, far objects smaller
  - Field of view: wide angle or telephoto

STEP 2 - ANALYZE THE NEW OBJECT (from second image):
• Physical characteristics:
  - Dimensions: length, width, height (estimate in meters/cm)
  - Shape: rectangular, round, irregular, etc.
  - Weight appearance: heavy (needs solid base) or light (can sit delicately)
  
• Visual properties:
  - Color: main colors, accents, patterns
  - Texture: smooth, rough, fabric, metal, wood, glass
  - Material: wood, metal, plastic, fabric, leather, glass, etc.
  - Finish: matte, glossy, semi-gloss

• Contact points:
  - How object touches ground: legs, flat base, wheels, uneven bottom
  - Number of contact points: 4 legs, continuous base, single pedestal
  - Expected indent/shadow pattern based on contact type

STEP 3 - POSITION THE OBJECT CORRECTLY:
• Placement location (follow user's description):
  - Exact position: {inputs.placement_description}
  - Alignment: centered, against wall, in corner, parallel to edge
  - Spacing: distance from walls, other objects (30-50cm typical for furniture)
  - Orientation: facing direction (toward door, window, camera, etc.)

• Scale and proportion:
  - Match object size to space size (not too large/small)
  - Reference existing objects for realistic scale
  - Typical sizes:
    * Sofa: 180-240cm wide, 80-100cm deep, 80-90cm high
    * Bed: 140-200cm wide, 200-220cm long, 50-60cm high
    * Table: 120-180cm wide, 70-90cm deep, 70-75cm high
    * Chair: 40-60cm wide, 40-50cm deep, 80-100cm high
    * TV: 100-150cm wide, 5-10cm thick, 60-90cm high
    * Person: 160-180cm tall, 40-50cm wide at shoulders

• Perspective adjustment:
  - Apply correct perspective distortion (objects farther = smaller)
  - Align edges with scene's vanishing points
  - Ensure vertical lines are vertical (unless intentional perspective)
  - Match camera angle and viewing position

STEP 4 - PERFECT INTEGRATION (Make it look REAL):
• Ground contact (CRITICAL):
  - Object MUST touch floor/ground naturally
  - NO floating above surface (common AI error)
  - NO sinking into surface (also common error)
  - Contact points clear and stable
  - If object has legs: each leg touches ground individually
  - If flat base: entire base edge touches ground

• Shadows (ESSENTIAL for realism):
  - Cast shadow FROM object in direction OPPOSITE to light source
  - Shadow length based on light angle (low sun = long shadow, overhead = short)
  - Shadow softness: sharp edges for hard light, soft edges for diffused light
  - Shadow darkness: darker near object, lighter further away
  - Shadow on multiple surfaces: floor AND wall if near wall
  - Ambient occlusion: darker area where object meets ground

• Lighting match (MUST be perfect):
  - Illuminate object from SAME direction as scene lighting
  - Match light intensity: bright scene = bright object, dim scene = dim object
  - Match color temperature: warm scene = warm light on object
  - Highlight areas facing light source
  - Shadow areas on opposite side from light
  - Rim lighting if backlit
  - Reflected light from surroundings (subtle bounce light)

• Color and material integration:
  - Match color grading of scene (warm, cool, neutral tone)
  - Adjust saturation to match scene (don't oversaturate)
  - Match contrast level with rest of image
  - Apply same film look/filter as original scene
  - If scene has specific style (vintage, modern, minimal): match it

• Reflections (if applicable):
  - Shiny floor: add reflection of object (wood, tile, marble)
  - Glass/mirror nearby: show object in reflection
  - Reflection intensity matches surface shininess
  - Reflection follows perspective and is vertically flipped

• Environmental effects:
  - Depth of field: If background is blurred, blur object appropriately at that distance
  - Air perspective: Slight haze for objects far from camera
  - Lens effects: Vignetting, chromatic aberration if present in original
  - Film grain: Match grain/noise level of original image

STEP 5 - QUALITY ASSURANCE:
☐ Object positioned exactly as user described
☐ Scale proportional and realistic
☐ Perspective matches scene perfectly
☐ Ground contact natural and stable (NO floating/sinking)
☐ Shadows present, realistic direction and softness
☐ Lighting direction matches scene
☐ Lighting intensity matches scene
☐ Color temperature matches scene
☐ Color grading consistent with scene
☐ Reflections present if floor is shiny
☐ NO visible seams or compositing artifacts
☐ Object looks like it BELONGS in this scene
☐ 8K photorealistic quality maintained

FINAL VERIFICATION:
The output should show the NEW object placed in the scene so naturally that it looks like it was ALWAYS THERE.
A person viewing the image should NOT be able to tell that the object was added digitally.
If there are ANY visual clues of editing (floating, wrong shadows, color mismatch, etc.) → This task has FAILED.

EXAMPLES (This process works for placing):
- Furniture: sofa, bed, table, chair, cabinet into rooms
- People: person, child, group into any scene
- Vehicles: car, bike into street, parking lot, garage
- Electronics: TV, computer into room, desk
- Decorations: plant, vase, artwork into room, outdoor
- Animals: dog, cat into home, garden
- ANY other object into ANY scene"""
        
        final_contents = [types.Content(role="user", parts=[
            types.Part(text=placement_prompt), removed_img, furniture_img
        ])]
        
        version = get_next_version_number(tool_context, inputs.asset_name)
        filename = f"{inputs.asset_name}_v{version}.png"
        
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-image",
            contents=final_contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"])
        ):
            if chunk.candidates and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data:
                    await tool_context.save_artifact(
                        filename=filename,
                        artifact=types.Part(inline_data=part.inline_data)
                    )
                    return f"✅ Successfully saved: {filename}"
        
        return "❌ Failed to place furniture. Please try again."
    
    except Exception as e:
        return f"❌ Error: {str(e)}"

# === VIRTUAL TRY-ON ===
class VirtualTryOnInput(BaseModel):
    person_image_filename: str = Field(description="Filename of person photo")
    clothing_image_filename: str = Field(description="Filename of clothing item")
    clothing_type: str = Field(description="Type: shirt, pants, dress, or jacket")
    asset_name: str = Field(default="tryon", description="Output filename base")

async def virtual_tryon(
    tool_context: ToolContext,
    inputs: VirtualTryOnInput
) -> str:
    """Apply clothing to person photo using Gemini image generation"""
    client = get_genai_client()
    
    try:
        person_img = await tool_context.load_artifact(inputs.person_image_filename)
        clothing_img = await tool_context.load_artifact(inputs.clothing_image_filename)
        
        prompts = {
            "shirt": "Replace the person's shirt with this exact clothing item",
            "pants": "Replace the person's pants with these exact pants",
            "dress": "Replace the person's outfit with this exact dress",
            "jacket": "Add this jacket over the person's current outfit"
        }
        
        prompt = f"""Fashion photography task: {prompts.get(inputs.clothing_type, prompts['shirt'])}.
        Requirements:
        - Match exact colors, patterns, and fabric texture from the clothing image
        - Maintain perfect lighting consistency with the original photo
        - Keep the person's face, hands, and body proportions completely unchanged
        - Ensure natural wrinkles and fabric draping
        - Output must be 8K photorealistic quality
        - Natural color grading matching original photo's tone"""
        
        contents = [types.Content(role="user", parts=[
            types.Part(text=prompt), person_img, clothing_img
        ])]
        
        version = get_next_version_number(tool_context, inputs.asset_name)
        filename = f"{inputs.asset_name}_v{version}.png"
        
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"], temperature=0.3)
        ):
            if chunk.candidates and chunk.candidates[0].content.parts:
                part = chunk.candidates[0].content.parts[0]
                if part.inline_data:
                    await tool_context.save_artifact(
                        filename=filename,
                        artifact=types.Part(inline_data=part.inline_data)
                    )
                    return f"✅ Successfully saved: {filename}"
        
        return "❌ Failed to apply clothing. Please try again."
    
    except Exception as e:
        return f"❌ Error: {str(e)}"

# === HELPER FUNCTIONS ===
def get_next_version_number(tool_context: ToolContext, asset_name: str) -> int:
    """Get next version number for artifact filename"""
    try:
        artifacts = tool_context.list_artifacts()
        version = 1
        for a in artifacts:
            if asset_name in a:
                try:
                    v = int(a.split('_v')[1].split('.')[0])
                    version = max(version, v + 1)
                except:
                    pass
        return version
    except:
        return 1
