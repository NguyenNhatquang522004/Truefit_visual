# utils.py - Simplified for VisualAgent only

from typing import Tuple, List

def classify_user_intent(
    user_message: str, 
    uploaded_files: List[str]
) -> Tuple[str, float]:
    """
    Classify user intent for VisualAgent only.
    Returns: (agent_name, confidence_score)
    
    Agent mapping:
    - "visual": VisualAgent (Furniture Placement + Virtual Try-on with 2 images)
    - "unclear": Need 2 images
    """
    msg = user_message.lower()
    
    # Check if 2 images uploaded
    if len(uploaded_files) == 2:
        # Check for furniture or fashion keywords
        furniture_kw = ['xóa', 'đặt', 'thay', 'phòng', 'bàn', 'ghế', 'tủ', 'nội thất', 'sofa', 'kệ']
        fashion_kw = ['thử', 'mặc', 'áo', 'quần', 'đồ', 'váy', 'jacket', 'dress', 'shirt', 'pants']
        
        has_furniture = any(kw in msg for kw in furniture_kw)
        has_fashion = any(kw in msg for kw in fashion_kw)
        
        if has_furniture or has_fashion:
            return ("visual", 0.9)
        # No keywords but 2 images uploaded - still visual
        return ("visual", 0.6)
    
    # Not enough images
    return ("unclear", 0.4)

def generate_clarification_prompt(uploaded_files: List[str], intent: str) -> str:
    """
    Generate clarification message for VisualAgent.
    """
    # Special case: 2 images but unclear intent
    if len(uploaded_files) == 2 and intent in ["unclear", "visual"]:
        return """🤔 Bạn muốn:
1️⃣ Đặt nội thất vào phòng
2️⃣ Thử quần áo

Trả lời: 1 hoặc 2"""
    
    # Need 2 images
    return """⚠️ Cần 2 ảnh để xử lý. Vui lòng tải lên:
- Ảnh 1: Phòng/người
- Ảnh 2: Sản phẩm (nội thất/quần áo)

Tôi có thể giúp:
1️⃣ Đặt nội thất vào phòng
2️⃣ Thử quần áo ảo"""
