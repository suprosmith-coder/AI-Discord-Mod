"""
Cyanix AI - Advanced AI Moderation Functions
Enhanced version with better error handling, performance, and features
"""

from transformers import pipeline, AutoModelForImageClassification, AutoImageProcessor
from PIL import Image, ImageFile, UnidentifiedImageError
from io import BytesIO
import openai
import aiohttp
import asyncio
from typing import Optional, Tuple, Dict, List
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ImageFile.LOAD_TRUNCATED_IMAGES = True

class CyanixModerator:
    """Advanced AI Moderation with multiple models and fallbacks"""
    
    def __init__(self, openai_api_key: str, sensitivity: float = 0.85):
        """
        Initialize Cyanix AI Moderator
        
        Args:
            openai_api_key: Your OpenAI API key
            sensitivity: Moderation sensitivity (0.0 to 1.0)
        """
        openai.api_key = openai_api_key
        self.sensitivity = max(0.0, min(1.0, sensitivity))  # Clamp between 0-1
        
        # Initialize image moderation pipelines (with fallbacks)
        self.nsfw_detector = None
        self.violence_detector = None
        self.image_processor = None
        
        # Text moderation cache to reduce API calls
        self.text_cache = {}
        self.cache_duration = 300  # 5 minutes cache
        
        # Initialize models asynchronously
        asyncio.create_task(self._initialize_models())
        
    async def _initialize_models(self):
        """Initialize AI models in background"""
        try:
            # NSFW detection model (primary)
            self.nsfw_detector = pipeline(
                "image-classification", 
                model="Falconsai/nsfw_image_detection"
            )
            logger.info("✓ NSFW detection model loaded")
        except Exception as e:
            logger.warning(f"Failed to load NSFW model: {e}")
            self.nsfw_detector = None
            
        try:
            # Violence detection model
            self.violence_detector = pipeline(
                "image-classification",
                model="dima806/nsfw_violence_image_detection"
            )
            logger.info("✓ Violence detection model loaded")
        except Exception as e:
            logger.warning(f"Failed to load violence model: {e}")
            self.violence_detector = None
            
        try:
            # General image processor
            self.image_processor = AutoImageProcessor.from_pretrained(
                "google/vit-base-patch16-224"
            )
            logger.info("✓ Image processor loaded")
        except Exception as e:
            logger.warning(f"Failed to load image processor: {e}")
            self.image_processor = None
    
    async def moderate_image(self, image_url: str) -> Tuple[bool, Dict]:
        """
        Advanced image moderation with multiple detection models
        
        Args:
            image_url: URL or path to the image
            
        Returns:
            Tuple of (is_safe, moderation_details)
        """
        moderation_results = {
            "safe": True,
            "categories": {},
            "confidence": {},
            "warnings": []
        }
        
        try:
            # Download image
            image = await self._download_image(image_url)
            if not image:
                moderation_results["warnings"].append("Failed to download image")
                return False, moderation_results
            
            # Check image properties
            if not await self._validate_image(image):
                moderation_results["safe"] = False
                moderation_results["categories"]["invalid"] = True
                return False, moderation_results
            
            # Run multiple moderation checks
            checks = [
                self._check_nsfw(image),
                self._check_violence(image),
                self._check_hate_symbols(image),
            ]
            
            results = await asyncio.gather(*checks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Check {i} failed: {result}")
                    continue
                    
                if not result["safe"]:
                    moderation_results["safe"] = False
                    moderation_results["categories"].update(result["categories"])
                    moderation_results["confidence"].update(result.get("confidence", {}))
            
            return moderation_results["safe"], moderation_results
            
        except Exception as e:
            logger.error(f"Image moderation failed: {e}")
            moderation_results["safe"] = False
            moderation_results["warnings"].append(f"Processing error: {str(e)}")
            return False, moderation_results
    
    async def _download_image(self, image_url: str) -> Optional[Image.Image]:
        """Download image from URL"""
        try:
            if image_url.startswith(('http://', 'https://')):
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url, timeout=10) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            return Image.open(BytesIO(image_data))
            else:
                # Assume it's a file path
                return Image.open(image_url)
        except Exception as e:
            logger.error(f"Failed to download image {image_url}: {e}")
            return None
    
    async def _validate_image(self, image: Image.Image) -> bool:
        """Validate image properties"""
        try:
            # Check file size (max 10MB)
            buffer = BytesIO()
            image.save(buffer, format=image.format if image.format else 'JPEG')
            if buffer.tell() > 10 * 1024 * 1024:  # 10MB
                return False
            
            # Check dimensions
            if image.width > 10000 or image.height > 10000:
                return False
                
            # Check if image is valid
            image.verify()
            return True
            
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            return False
    
    async def _check_nsfw(self, image: Image.Image) -> Dict:
        """Check for NSFW content"""
        result = {
            "safe": True,
            "categories": {},
            "confidence": {}
        }
        
        if not self.nsfw_detector:
            result["warnings"] = ["NSFW model not available"]
            return result
        
        try:
            predictions = self.nsfw_detector(image)
            
            for pred in predictions:
                label = pred["label"].lower()
                score = pred["score"]
                
                if label in ["nsfw", "porn", "adult", "sexual"]:
                    if score > self.sensitivity:
                        result["safe"] = False
                        result["categories"]["nsfw"] = True
                        result["confidence"]["nsfw"] = score
                        
                elif label in ["hentai", "drawings"]:
                    if score > self.sensitivity * 0.8:  # Lower threshold for drawn content
                        result["safe"] = False
                        result["categories"]["hentai"] = True
                        result["confidence"]["hentai"] = score
            
            return result
            
        except Exception as e:
            logger.error(f"NSFW check failed: {e}")
            result["warnings"] = [f"NSFW check error: {str(e)}"]
            return result
    
    async def _check_violence(self, image: Image.Image) -> Dict:
        """Check for violent content"""
        result = {
            "safe": True,
            "categories": {},
            "confidence": {}
        }
        
        if not self.violence_detector:
            return result
        
        try:
            predictions = self.violence_detector(image)
            
            for pred in predictions:
                label = pred["label"].lower()
                score = pred["score"]
                
                if label in ["violence", "gore", "blood", "weapon"]:
                    if score > self.sensitivity:
                        result["safe"] = False
                        result["categories"]["violence"] = True
                        result["confidence"]["violence"] = score
            
            return result
            
        except Exception as e:
            logger.error(f"Violence check failed: {e}")
            return result
    
    async def _check_hate_symbols(self, image: Image.Image) -> Dict:
        """Check for hate symbols (placeholder - implement with custom model if needed)"""
        # This is a simplified version. You'd want a specialized model for this.
        result = {
            "safe": True,
            "categories": {},
            "confidence": {}
        }
        
        # Placeholder implementation
        # In production, you would use a hate symbol detection model
        # or integrate with a service like Google Cloud Vision
        
        return result
    
    async def moderate_message(self, message: str, user_id: str = None) -> Tuple[bool, Dict]:
        """
        Advanced text moderation with caching and detailed analysis
        
        Args:
            message: Text to moderate
            user_id: Optional user ID for caching
            
        Returns:
            Tuple of (is_safe, moderation_details)
        """
        moderation_results = {
            "safe": True,
            "categories": {},
            "scores": {},
            "flagged": False,
            "cache_hit": False
        }
        
        # Check cache first
        cache_key = f"{user_id}:{hash(message)}" if user_id else hash(message)
        current_time = time.time()
        
        if cache_key in self.text_cache:
            cache_entry = self.text_cache[cache_key]
            if current_time - cache_entry["timestamp"] < self.cache_duration:
                moderation_results.update(cache_entry["results"])
                moderation_results["cache_hit"] = True
                return moderation_results["safe"], moderation_results
        
        try:
            # Use OpenAI moderation API
            response = await openai.Moderation.acreate(input=message)
            
            if response and response.get("results"):
                result = response["results"][0]
                moderation_results["flagged"] = result["flagged"]
                moderation_results["categories"] = result["categories"]
                moderation_results["scores"] = result["category_scores"]
                
                # Determine if message is safe based on sensitivity
                moderation_results["safe"] = not result["flagged"]
                
                # Apply custom sensitivity per category
                if result["flagged"]:
                    high_risk_categories = {
                        "harassment": 0.85,
                        "hate": 0.80,
                        "self-harm": 0.75,
                        "sexual": 0.90,
                        "violence": 0.85,
                    }
                    
                    # Check if any high-risk category exceeds threshold
                    for category, threshold in high_risk_categories.items():
                        if result["categories"].get(category) and result["category_scores"][category] > threshold:
                            moderation_results["safe"] = False
                            break
                
                # Update cache
                self.text_cache[cache_key] = {
                    "timestamp": current_time,
                    "results": {
                        "safe": moderation_results["safe"],
                        "categories": moderation_results["categories"],
                        "scores": moderation_results["scores"],
                        "flagged": moderation_results["flagged"]
                    }
                }
                
                # Clean old cache entries
                self._clean_cache()
                
                return moderation_results["safe"], moderation_results
                
        except openai.error.RateLimitError:
            logger.warning("OpenAI rate limit exceeded")
            moderation_results["warnings"] = ["Rate limit exceeded - using fallback"]
            # Fallback to basic keyword checking
            return await self._fallback_moderation(message), moderation_results
            
        except openai.error.AuthenticationError:
            logger.error("OpenAI authentication failed")
            moderation_results["safe"] = False
            moderation_results["error"] = "Authentication failed"
            return False, moderation_results
            
        except Exception as e:
            logger.error(f"Text moderation failed: {e}")
            moderation_results["safe"] = False
            moderation_results["error"] = str(e)
            return False, moderation_results
        
        return True, moderation_results
    
    async def _fallback_moderation(self, message: str) -> bool:
        """Fallback moderation when API fails"""
        # Basic keyword checking
        dangerous_keywords = [
            "kill", "murder", "rape", "suicide", "terrorist",
            "nazi", "kkk", "hitler", "pedo", "cp", "child porn"
        ]
        
        message_lower = message.lower()
        for keyword in dangerous_keywords:
            if keyword in message_lower:
                return False
        return True
    
    def _clean_cache(self):
        """Remove old cache entries"""
        current_time = time.time()
        keys_to_remove = [
            key for key, value in self.text_cache.items()
            if current_time - value["timestamp"] > self.cache_duration
        ]
        for key in keys_to_remove:
            del self.text_cache[key]
    
    async def get_moderation_stats(self) -> Dict:
        """Get statistics about moderation performance"""
        return {
            "cache_size": len(self.text_cache),
            "sensitivity": self.sensitivity,
            "models_loaded": {
                "nsfw": self.nsfw_detector is not None,
                "violence": self.violence_detector is not None,
                "image_processor": self.image_processor is not None
            }
        }

# Backward compatibility functions
async def image_is_safe(image_url: str, sensitivity: float = 0.85) -> Tuple[bool, Dict]:
    """
    Legacy function for backward compatibility
    
    Args:
        image_url: URL or path to image
        sensitivity: Sensitivity level (0.0 to 1.0)
        
    Returns:
        Tuple of (is_safe, details)
    """
    # This is a simplified wrapper for backward compatibility
    # In production, you should use the CyanixModerator class directly
    
    try:
        # Simple VQA approach (original method)
        from transformers import pipeline
        vqa_pipeline = pipeline("visual-question-answering")
        
        # Download image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                image_data = await response.read()
                image = Image.open(BytesIO(image_data))
        
        # Ask questions
        questions = [
            "Does this image contain adult or pornographic content?",
            "Does this image contain violent or gory content?",
            "Does this image contain hate symbols or hate speech?"
        ]
        
        for question in questions:
            result = vqa_pipeline(image, question, top_k=1)[0]
            answer = result["answer"].lower()
            
            if answer.startswith("y") and result["score"] > (1 - sensitivity):
                return False, {"reason": question, "confidence": result["score"]}
        
        return True, {"safe": True}
        
    except Exception as e:
        logger.error(f"Legacy image check failed: {e}")
        return False, {"error": str(e)}

async def message_is_safe(message: str, apikey: str) -> Tuple[bool, Dict]:
    """
    Legacy function for backward compatibility
    
    Args:
        message: Text to moderate
        apikey: OpenAI API key
        
    Returns:
        Tuple of (is_safe, details)
    """
    moderator = CyanixModerator(apikey)
    return await moderator.moderate_message(message)

# Example usage
if __name__ == "__main__":
    # Example usage
    async def test():
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        moderator = CyanixModerator(os.getenv("OPENAI_API_KEY"))
        
        # Test text moderation
        text_result = await moderator.moderate_message(
            "This is a test message with inappropriate content",
            user_id="test123"
        )
        print(f"Text moderation: {text_result}")
        
        # Test image moderation (requires actual image URL)
        # image_result = await moderator.moderate_image("https://example.com/image.jpg")
        # print(f"Image moderation: {image_result}")
        
        # Get stats
        stats = await moderator.get_moderation_stats()
        print(f"Stats: {stats}")
    
    asyncio.run(test())