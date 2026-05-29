import os
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import PyPDF2
from datetime import datetime

class DocumentProcessor:
    """Process and validate supplier documents"""
    
    ALLOWED_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @classmethod
    def validate_document(cls, file):
        """Validate uploaded document"""
        errors = []
        
        # Check file size
        if file.size > cls.MAX_FILE_SIZE:
            errors.append(f"File size exceeds {cls.MAX_FILE_SIZE // (1024*1024)}MB limit")
        
        # Check extension
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            errors.append(f"File type not allowed. Allowed: {', '.join(cls.ALLOWED_EXTENSIONS)}")
        
        return errors
    
    @classmethod
    def compress_image(cls, file, max_width=1200, quality=85):
        """Compress image to reduce size"""
        try:
            img = Image.open(file)
            
            # Convert RGBA to RGB
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Resize if too large
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save compressed image
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            output.seek(0)
            
            return ContentFile(output.read(), name=file.name.replace('.png', '.jpg').replace('.PNG', '.jpg'))
        except Exception as e:
            return file
    
    @classmethod
    def extract_pdf_info(cls, file):
        """Extract information from PDF document"""
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            # Extract first page text (for preview)
            first_page = pdf_reader.pages[0]
            text = first_page.extract_text()[:500] if first_page.extract_text() else ""
            
            return {
                'num_pages': num_pages,
                'preview_text': text,
                'is_encrypted': pdf_reader.is_encrypted
            }
        except Exception:
            return {
                'num_pages': 0,
                'preview_text': '',
                'is_encrypted': False
            }
    
    @classmethod
    def generate_document_hash(cls, file):
        """Generate unique hash for document"""
        import hashlib
        file.seek(0)
        file_hash = hashlib.md5(file.read()).hexdigest()
        file.seek(0)
        return file_hash


class SupplierValidator:
    """Validate supplier information"""
    
    @classmethod
    def validate_business_tin(cls, tax_id, country='RW'):
        """Validate Tax Identification Number (simplified)"""
        # This would integrate with tax authority API in production
        if not tax_id:
            return True, "No TIN provided"
        
        # Basic validation for Rwanda TIN format
        if country == 'RW' and len(tax_id) == 9 and tax_id.isdigit():
            return True, "TIN format valid"
        
        return False, "Invalid TIN format"
    
    @classmethod
    def check_duplicate_business(cls, business_name):
        """Check if business already registered"""
        from suppliers.models import SupplierApplication, SupplierProfile
        
        existing_applications = SupplierApplication.objects.filter(
            business_name__iexact=business_name,
            status__in=['pending', 'reviewing', 'approved']
        ).exists()
        
        existing_profiles = SupplierProfile.objects.filter(
            business_name__iexact=business_name
        ).exists()
        
        return existing_applications or existing_profiles