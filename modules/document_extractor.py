"""
Document Extraction Module
--------------------------
Pillar 1 of BPS Transformation: Intelligent Document Processing (IDP)

This module leverages NVIDIA NIM APIs for:
- OCR with NemoRetriever OCR v1 (per-word confidence)
- Vision LLM for complex document understanding
- Entity extraction with confidence scores
"""

import json
import os
import io
import base64
import time
from typing import Any, Dict, Tuple, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

import requests
from PIL import Image


@dataclass
class ExtractionResult:
    """Structured result from document extraction."""
    document_id: str
    filename: str
    timestamp: str
    pages_processed: int
    raw_text: str
    entities: Dict[str, Any]
    confidence_scores: Dict[str, float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "timestamp": self.timestamp,
            "pages_processed": self.pages_processed,
            "raw_text": self.raw_text,
            "entities": self.entities,
            "confidence_scores": self.confidence_scores,
            "metadata": self.metadata
        }
    
    def get_entity(self, key: str, default: Any = None) -> Any:
        """Get entity value by key."""
        return self.entities.get(key, default)
    
    def get_confidence(self, key: str) -> float:
        """Get confidence score for a specific entity."""
        return self.confidence_scores.get(key, 0.0)
    
    @property
    def average_confidence(self) -> float:
        """Calculate average confidence across all entities."""
        if not self.confidence_scores:
            return 0.0
        return sum(self.confidence_scores.values()) / len(self.confidence_scores)


class DocumentExtractor:
    """
    Intelligent Document Processing (IDP) using NVIDIA NIM APIs.
    
    Supports:
    - PDF documents (multi-page)
    - Images (PNG, JPG, JPEG)
    - Multiple OCR models (NemoRetriever, Llama Vision)
    - Entity extraction with confidence scoring
    """
    
    # API Endpoints
    NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    NEMO_OCR_URL = "https://ai.api.nvidia.com/v1/cv/nvidia/nemoretriever-ocr-v1"
    VISION_API_URL = "https://ai.api.nvidia.com/v1/gr/meta/llama-3.2-90b-vision-instruct/chat/completions"
    
    # OCR Model Options
    OCR_MODELS = {
        "nemoretriever": {
            "name": "NemoRetriever OCR v1",
            "model": "nvidia/nemoretriever-ocr-v1",
            "url": NEMO_OCR_URL,
            "type": "nemo_ocr",
        },
        "llama_90b": {
            "name": "Llama 3.2 90B Vision",
            "model": "meta/llama-3.2-90b-vision-instruct",
            "url": VISION_API_URL,
            "type": "vision_llm",
        },
    }
    
    # LLM Models for Entity Extraction
    LLM_MODELS = {
        "nemotron_30b": {
            "model": "nvidia/nemotron-3-nano-30b-a3b",
            "url": NVIDIA_API_URL,
        },
        "nemotron_49b": {
            "model": "nvidia/llama-3.3-nemotron-super-49b-v1",
            "url": NVIDIA_API_URL,
        },
    }
    
    def __init__(self, api_key: str, ocr_model: str = "nvidia/nemoretriever-ocr-v1", llm_model: str = "nvidia/nemotron-3-nano-30b-a3b"):
        """
        Initialize the Document Extractor.
        
        Args:
            api_key: NVIDIA API key
            ocr_model: Full model name for OCR (e.g., 'nvidia/nemoretriever-ocr-v1')
            llm_model: Full model name for entity extraction (e.g., 'nvidia/nemotron-3-nano-30b-a3b')
        """
        self.api_key = api_key
        
        # Determine OCR config based on model name
        if "nemoretriever" in ocr_model.lower():
            self.ocr_config = {
                "name": "NemoRetriever OCR v1",
                "model": ocr_model,
                "url": self.NEMO_OCR_URL,
                "type": "nemo_ocr",
            }
        else:
            self.ocr_config = {
                "name": "Vision LLM",
                "model": ocr_model,
                "url": self.VISION_API_URL,
                "type": "vision_llm",
            }
        
        # LLM config
        self.llm_config = {
            "model": llm_model,
            "url": self.NVIDIA_API_URL,
        }
        self.timeout = 180
        
    def extract(
        self, 
        file_bytes: bytes, 
        filename: str,
        document_type: str = "auto",
        custom_schema: Optional[Dict] = None,
        progress_callback: Optional[callable] = None
    ) -> ExtractionResult:
        """
        Extract data from a document.
        
        Args:
            file_bytes: Raw bytes of the document
            filename: Original filename
            document_type: Type of document ('invoice', 'claim', 'application', 'auto')
            custom_schema: Custom extraction schema
            progress_callback: Optional callback for progress updates
            
        Returns:
            ExtractionResult with extracted entities and confidence scores
        """
        import uuid
        
        doc_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        if progress_callback:
            progress_callback("Converting document to images...")
        
        # Convert to images
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            images, conv_info = self._pdf_to_images(file_bytes)
        else:
            images, conv_info = self._image_to_list(file_bytes, filename)
        
        if not images:
            raise ValueError(f"Failed to process document: {conv_info.get('error', 'Unknown error')}")
        
        if progress_callback:
            progress_callback(f"Running OCR on {len(images)} page(s)...")
        
        # Run OCR on all pages
        ocr_text, page_details = self._process_all_pages(images, progress_callback)
        
        if progress_callback:
            progress_callback("Extracting entities...")
        
        # Extract entities
        entities, confidence_scores = self._extract_entities(
            ocr_text, 
            document_type, 
            custom_schema,
            len(images)
        )
        
        # Build result
        result = ExtractionResult(
            document_id=doc_id,
            filename=filename,
            timestamp=timestamp,
            pages_processed=len(images),
            raw_text=ocr_text,
            entities=entities,
            confidence_scores=confidence_scores,
            metadata={
                "ocr_model": self.ocr_config["name"],
                "llm_model": self.llm_config["model"],
                "document_type": document_type,
                "page_details": page_details,
            }
        )
        
        return result
    
    def _pdf_to_images(self, file_bytes: bytes, dpi: int = 150) -> Tuple[List[Image.Image], Dict]:
        """Convert PDF to images."""
        from pdf2image import convert_from_bytes
        
        info = {"method": "pdf2image", "dpi": dpi}
        try:
            images = convert_from_bytes(file_bytes, dpi=dpi)
            info["pages"] = len(images)
            info["success"] = True
            return images, info
        except Exception as e:
            info["error"] = str(e)
            info["success"] = False
            return [], info
    
    def _image_to_list(self, file_bytes: bytes, filename: str) -> Tuple[List[Image.Image], Dict]:
        """Load image file."""
        info = {"method": "direct_image", "filename": filename}
        try:
            img = Image.open(io.BytesIO(file_bytes))
            info["size"] = f"{img.width}x{img.height}"
            info["success"] = True
            return [img], info
        except Exception as e:
            info["error"] = str(e)
            info["success"] = False
            return [], info
    
    def _image_to_base64(
        self, 
        image: Image.Image, 
        max_dim: int = 1024,
        format: str = "PNG",
        quality: int = 85
    ) -> Tuple[str, Dict]:
        """Convert image to base64."""
        info = {"original_size": f"{image.width}x{image.height}"}
        
        if image.width > max_dim or image.height > max_dim:
            ratio = min(max_dim / image.width, max_dim / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            info["resized_to"] = f"{image.width}x{image.height}"
        
        buffer = io.BytesIO()
        if format.upper() == "JPEG":
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            image.save(buffer, format="JPEG", quality=quality)
        else:
            image.save(buffer, format="PNG")
        
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        info["base64_length"] = len(b64)
        return b64, info
    
    def _call_nemo_ocr(self, image_b64: str, page_num: int) -> Tuple[str, Dict]:
        """Call NemoRetriever OCR API."""
        
        # Check base64 size limit for NemoRetriever (180K limit)
        if len(image_b64) >= 180_000:
            return "", {
                "page": page_num,
                "model": self.ocr_config["name"],
                "error": f"Image too large ({len(image_b64)} chars). Max 180,000 for NemoRetriever.",
                "success": False
            }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        payload = {
            "input": [{"type": "image_url", "url": f"data:image/jpeg;base64,{image_b64}"}]
        }
        
        details = {"page": page_num, "model": self.ocr_config["name"], "base64_size": len(image_b64)}
        
        try:
            print(f"[NemoRetriever] Calling API for page {page_num}, base64 size: {len(image_b64)}")
            response = requests.post(self.ocr_config["url"], headers=headers, json=payload, timeout=120)
            details["status_code"] = response.status_code
            print(f"[NemoRetriever] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                text_parts = []
                confidence_scores = []
                
                for item in data.get("data", []):
                    for detection in item.get("text_detections", []):
                        pred = detection.get("text_prediction", {})
                        text = pred.get("text", "")
                        conf = pred.get("confidence", 0.0)
                        if text:
                            text_parts.append(text)
                            confidence_scores.append(conf)
                
                combined_text = "\n".join(text_parts)
                avg_conf = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                
                details["success"] = True
                details["num_detections"] = len(text_parts)
                details["avg_confidence"] = round(avg_conf, 3)
                details["output_length"] = len(combined_text)
                
                print(f"[NemoRetriever] Success: {len(text_parts)} detections, {len(combined_text)} chars")
                return combined_text, details
            else:
                error_msg = response.text[:500]
                details["error"] = error_msg
                details["success"] = False
                print(f"[NemoRetriever] Error {response.status_code}: {error_msg}")
                return "", details
                
        except Exception as e:
            details["error"] = str(e)
            details["success"] = False
            print(f"[NemoRetriever] Exception: {str(e)}")
            return "", details
    
    def _call_vision_ocr(self, image_b64: str, page_num: int) -> Tuple[str, Dict]:
        """Call Vision LLM for OCR."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        prompt = """Extract ALL text from this document page. Include:
- All form fields and their values
- Checkbox states: [X] if checked, [ ] if unchecked
- Handwritten text (mark as "(handwritten)")
- Signatures (mark as "[SIGNATURE]")
- All names, dates, ID numbers, amounts
- Tables with all rows and columns

Extract everything visible on this page:"""
        
        payload = {
            "model": self.ocr_config["model"],
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                ]
            }],
            "max_tokens": 4096,
            "temperature": 0.1,
        }
        
        details = {"page": page_num, "model": self.ocr_config["name"]}
        
        try:
            response = requests.post(self.ocr_config["url"], headers=headers, json=payload, timeout=180)
            details["status_code"] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                details["success"] = True
                details["output_length"] = len(content)
                return content, details
            else:
                details["error"] = response.text[:500]
                details["success"] = False
                return "", details
                
        except Exception as e:
            details["error"] = str(e)
            details["success"] = False
            return "", details
    
    def _process_all_pages(
        self, 
        images: List[Image.Image],
        progress_callback: Optional[callable] = None
    ) -> Tuple[str, List[Dict]]:
        """Process all pages with OCR."""
        all_text = []
        page_details = []
        is_nemo = self.ocr_config["type"] == "nemo_ocr"
        
        for i, img in enumerate(images):
            page_num = i + 1
            
            if progress_callback:
                progress_callback(f"OCR: Page {page_num}/{len(images)}...")
            
            # Convert to base64
            if is_nemo:
                image_b64, _ = self._image_to_base64(img, max_dim=600, format="JPEG", quality=75)
                if len(image_b64) >= 180_000:
                    image_b64, _ = self._image_to_base64(img, max_dim=400, format="JPEG", quality=60)
                text, details = self._call_nemo_ocr(image_b64, page_num)
            else:
                image_b64, _ = self._image_to_base64(img, max_dim=1024)
                text, details = self._call_vision_ocr(image_b64, page_num)
            
            page_details.append(details)
            
            if text:
                all_text.append(f"\n{'='*50}\n📄 PAGE {page_num}\n{'='*50}\n\n{text}")
            
            if page_num < len(images):
                time.sleep(1)
        
        return "\n".join(all_text), page_details
    
    def _extract_entities(
        self,
        ocr_text: str,
        document_type: str,
        custom_schema: Optional[Dict],
        total_pages: int
    ) -> Tuple[Dict[str, Any], Dict[str, float]]:
        """Extract entities from OCR text using LLM."""
        import re
        
        # Build extraction prompt based on document type
        schema_prompt = self._get_schema_prompt(document_type, custom_schema)
        
        prompt = f"""You are a document data extraction system. Extract entities as JSON.

{schema_prompt}

RULES:
1. Extract ONLY what is present - do NOT invent fields
2. Use EXACT values as they appear
3. Include confidence score (0.0-1.0) for each field
4. Return valid JSON only

Output Format:
{{
  "entities": {{
    "field_name": "value",
    ...
  }},
  "confidence": {{
    "field_name": 0.95,
    ...
  }}
}}

DOCUMENT TEXT (from {total_pages} pages):
{ocr_text[:15000]}
"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        body = {
            "model": self.llm_config["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        
        try:
            resp = requests.post(self.llm_config["url"], headers=headers, json=body, timeout=self.timeout)
            
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content")
                
                # Handle None content
                if not content:
                    print("Entity extraction: LLM returned empty content")
                    return {}, {}
                
                # Clean and parse JSON - handle thinking tags
                if "</think>" in content:
                    content = content.split("</think>")[-1].strip()
                if "<think>" in content:
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    result = json.loads(json_match.group())
                    entities = result.get("entities", result)
                    confidence = result.get("confidence", {})
                    
                    # If no separate confidence dict, assume high confidence
                    if not confidence and entities:
                        confidence = {k: 0.90 for k in entities.keys()}
                    
                    return entities, confidence
                else:
                    print(f"Entity extraction: Could not find JSON in response: {content[:200]}")
            else:
                print(f"Entity extraction: LLM returned status {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            import traceback
            print(f"Entity extraction error: {e}")
            print(traceback.format_exc())
        
        return {}, {}
    
    def _get_schema_prompt(self, document_type: str, custom_schema: Optional[Dict]) -> str:
        """Get extraction schema based on document type."""
        
        schemas = {
            "invoice": """
Extract these fields for INVOICE:
- invoice_number, invoice_date, due_date
- vendor_name, vendor_address, vendor_tax_id
- customer_name, customer_address
- line_items (array with description, quantity, unit_price, amount)
- subtotal, tax_amount, total_amount
- payment_terms, bank_details
""",
            "claim": """
Extract these fields for INSURANCE CLAIM:
- claim_number, claim_date, policy_number
- claimant_name, claimant_address, claimant_phone, claimant_email
- incident_date, incident_location, incident_description
- claim_type (medical, auto, property, liability)
- damage_description, estimated_amount, requested_amount
- witnesses (array with name, contact)
- supporting_documents (array)
- signature_present (yes/no)
""",
            "application": """
Extract these fields for APPLICATION FORM:
- application_id, application_date
- applicant_name, date_of_birth, ssn_last4
- address, city, state, zip_code
- phone, email
- employment_status, employer_name, annual_income
- requested_product, requested_amount
- all checkbox selections
- signature_present (yes/no)
""",
            "auto": """
Extract ALL visible fields including:
- All names, dates, ID numbers, amounts
- All form fields and their values
- Checkbox states (checked/unchecked)
- Table data with all rows
- Any signatures present
"""
        }
        
        if custom_schema:
            return f"Extract these fields:\n{json.dumps(custom_schema, indent=2)}"
        
        return schemas.get(document_type, schemas["auto"])

