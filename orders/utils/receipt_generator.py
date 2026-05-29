from io import BytesIO
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.utils import timezone

class ReceiptGenerator:
    """Generate PDF receipts for orders"""
    
    @staticmethod
    def generate_pdf_receipt(order):
        """Generate PDF receipt for an order"""
        
        # Create buffer for PDF
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=20*mm,
            bottomMargin=20*mm,
            leftMargin=20*mm,
            rightMargin=20*mm
        )
        
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#2C3E50'),
            alignment=1,  # Center
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#E67E22'),
            spaceAfter=12
        )
        
        # Story (content) list
        story = []
        
        # Company header
        story.append(Paragraph("HerosTechnology", title_style))
        story.append(Paragraph("Your Trusted Electronics Marketplace", styles['Italic']))
        story.append(Paragraph("Kigali, Rwanda | +250 788 123 456 | info@herostechnology.com", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Divider
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E67E22')))
        story.append(Spacer(1, 20))
        
        # Receipt title
        story.append(Paragraph(f"PAYMENT RECEIPT", heading_style))
        story.append(Spacer(1, 10))
        
        # Order information
        receipt_info = [
            ["Receipt Number:", order.order_number],
            ["Date:", timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M:%S")],
            ["Payment Method:", order.get_payment_method_display()],
            ["Transaction Status:", order.payment_status.upper()],
        ]
        
        receipt_table = Table(receipt_info, colWidths=[100, 300])
        receipt_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2C3E50')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(receipt_table)
        story.append(Spacer(1, 20))
        
        # Customer information
        story.append(Paragraph("Customer Information", heading_style))
        customer_info = [
            ["Name:", order.customer.full_name or order.customer.email],
            ["Email:", order.customer.email],
            ["Phone:", order.shipping_phone],
        ]
        
        customer_table = Table(customer_info, colWidths=[100, 300])
        customer_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2C3E50')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(customer_table)
        story.append(Spacer(1, 20))
        
        # Order items
        story.append(Paragraph("Order Items", heading_style))
        
        # Items table header
        items_data = [['Product', 'Quantity', 'Unit Price', 'Total']]
        
        for item in order.items.all():
            items_data.append([
                item.product.name,
                str(item.quantity),
                f"{item.final_price:,.0f} FRW",
                f"{item.get_total_final_price():,.0f} FRW"
            ])
        
        # Add VAT and total rows
        items_data.append(['', '', '', ''])
        items_data.append(['', '', 'Subtotal (excl. VAT):', f"{order.subtotal_base:,.0f} FRW"])
        items_data.append(['', '', 'VAT (18%):', f"{order.total_vat:,.0f} FRW"])
        items_data.append(['', '', 'GRAND TOTAL:', f"{order.grand_total:,.0f} FRW"])
        
        items_table = Table(items_data, colWidths=[250, 60, 100, 100])
        items_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (1, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -4), 0.5, colors.grey),
            ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (2, -3), (2, -1), colors.HexColor('#E67E22')),
            ('TEXTCOLOR', (3, -3), (3, -1), colors.HexColor('#E67E22')),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 20))
        
        # Shipping information
        story.append(Paragraph("Shipping Information", heading_style))
        shipping_info = [
            ["Address:", order.shipping_address],
            ["City:", order.shipping_city],
            ["Notes:", order.shipping_notes or "None"],
        ]
        
        shipping_table = Table(shipping_info, colWidths=[100, 300])
        shipping_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2C3E50')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(shipping_table)
        story.append(Spacer(1, 20))
        
        # Footer
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#E67E22')))
        story.append(Spacer(1, 10))
        story.append(Paragraph("Thank you for shopping with HerosTechnology!", styles['Italic']))
        story.append(Paragraph("For support, contact us at support@herostechnology.com", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        return pdf_data
    
    @staticmethod
    def download_receipt(request, order):
        """Generate and download receipt as PDF"""
        pdf_data = ReceiptGenerator.generate_pdf_receipt(order)
        
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.pdf"'
        
        return response