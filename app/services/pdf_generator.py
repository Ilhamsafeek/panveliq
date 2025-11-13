"""
Professional Interactive PDF Generator for Proposals
Uses ReportLab with advanced features
File: app/services/pdf_generator.py
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    Image, KeepTogether, Frame, PageTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Rect, Line
from reportlab.graphics import renderPDF
from io import BytesIO
from datetime import datetime
import json


class ProposalPDFGenerator:
    """Professional PDF Generator with Interactive Elements"""
    
    def __init__(self):
        self.width, self.height = A4
        self.styles = self._create_custom_styles()
        
    def _create_custom_styles(self):
        """Create professional custom styles"""
        styles = getSampleStyleSheet()
        
        # Cover Page Title
        styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=styles['Heading1'],
            fontSize=36,
            textColor=colors.HexColor('#9926F3'),
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=42
        ))
        
        # Cover Subtitle
        styles.add(ParagraphStyle(
            name='CoverSubtitle',
            parent=styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#1DD8FC'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=22
        ))
        
        # Section Heading with Gradient Effect
        styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#9926F3'),
            spaceAfter=15,
            spaceBefore=20,
            fontName='Helvetica-Bold',
            borderWidth=2,
            borderColor=colors.HexColor('#1DD8FC'),
            borderPadding=10,
            backColor=colors.HexColor('#F8F9FA'),
            leading=24
        ))
        
        # Subsection Heading
        styles.add(ParagraphStyle(
            name='SubHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1DD8FC'),
            spaceAfter=10,
            spaceBefore=15,
            fontName='Helvetica-Bold',
            leading=20
        ))
        
        # Body Text - Professional
        styles.add(ParagraphStyle(
            name='BodyPro',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            fontName='Helvetica',
            leading=16
        ))
        
        # Bullet Points
        styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#555555'),
            spaceAfter=8,
            leftIndent=20,
            bulletIndent=10,
            fontName='Helvetica',
            leading=15
        ))
        
        # Highlighted Box
        styles.add(ParagraphStyle(
            name='HighlightBox',
            parent=styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#FFFFFF'),
            backColor=colors.HexColor('#9926F3'),
            borderPadding=15,
            spaceAfter=15,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold',
            leading=18
        ))
        
        # Footer Text
        styles.add(ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666666'),
            alignment=TA_CENTER,
            fontName='Helvetica',
            leading=12
        ))
        
        return styles
    
    def _draw_header_footer(self, canvas_obj, doc, proposal_data):
        """Draw professional header and footer"""
        canvas_obj.saveState()
        
        # Header - Gradient Bar
        canvas_obj.setFillColorRGB(0.6, 0.15, 0.95)  # #9926F3
        canvas_obj.rect(0, self.height - 30, self.width, 30, fill=1, stroke=0)
        
        # Company Name in Header
        canvas_obj.setFillColorRGB(1, 1, 1)
        canvas_obj.setFont('Helvetica-Bold', 12)
        canvas_obj.drawString(30, self.height - 20, "PanvelIQ Digital Marketing")
        
        # Page Number
        canvas_obj.setFont('Helvetica', 10)
        page_num = canvas_obj.getPageNumber()
        canvas_obj.drawRightString(self.width - 30, self.height - 20, f"Page {page_num}")
        
        # Footer - Gradient Bar
        canvas_obj.setFillColorRGB(0.11, 0.85, 0.99)  # #1DD8FC
        canvas_obj.rect(0, 0, self.width, 25, fill=1, stroke=0)
        
        # Footer Text
        canvas_obj.setFillColorRGB(1, 1, 1)
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.drawCentredString(
            self.width / 2, 10,
            f"Confidential Proposal • Generated {datetime.now().strftime('%B %d, %Y')}"
        )
        
        canvas_obj.restoreState()
    
    def _create_cover_page(self, proposal_data):
        """Create professional cover page"""
        story = []
        
        # Add spacing from top
        story.append(Spacer(1, 1.5*inch))
        
        # Main Title with Gradient Background Effect
        story.append(Paragraph("DIGITAL MARKETING", self.styles['CoverTitle']))
        story.append(Paragraph("PROPOSAL", self.styles['CoverTitle']))
        story.append(Spacer(1, 0.3*inch))
        
        # Subtitle
        story.append(Paragraph(
            f"Prepared for {proposal_data.get('client_name', 'Valued Client')}",
            self.styles['CoverSubtitle']
        ))
        story.append(Spacer(1, 0.5*inch))
        
        # Client Info Box
        client_info = [
            ['Company:', proposal_data.get('company_name', 'N/A')],
            ['Business Type:', proposal_data.get('business_type', 'N/A')],
            ['Investment Budget:', f"${proposal_data.get('budget', 0):,.2f}"],
            ['Prepared On:', datetime.now().strftime('%B %d, %Y')],
        ]
        
        client_table = Table(client_info, colWidths=[2*inch, 4*inch])
        client_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#9926F3')),
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('PADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
        ]))
        story.append(client_table)
        
        story.append(Spacer(1, 1*inch))
        
        # Highlight Box
        story.append(Paragraph(
            "Strategic Growth • AI-Powered Insights • Measurable Results",
            self.styles['HighlightBox']
        ))
        
        story.append(PageBreak())
        return story
    
    def _create_executive_summary(self, proposal_data):
        """Create executive summary section"""
        story = []
        
        story.append(Paragraph("EXECUTIVE SUMMARY", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        summary_text = f"""
        This comprehensive digital marketing proposal has been specifically designed for 
        <b>{proposal_data.get('company_name', 'your organization')}</b>, a {proposal_data.get('business_type', 'business')} 
        looking to enhance their digital presence and drive measurable growth.
        <br/><br/>
        Our AI-powered approach combines cutting-edge marketing technology with proven strategies 
        to deliver exceptional results within your investment budget of <b>${proposal_data.get('budget', 0):,.2f}</b>.
        <br/><br/>
        <b>Key Challenges We'll Address:</b><br/>
        {proposal_data.get('challenges', 'Market penetration and brand awareness')}
        <br/><br/>
        <b>Target Audience Focus:</b><br/>
        {proposal_data.get('target_audience', 'Defined target market segments')}
        """
        
        story.append(Paragraph(summary_text, self.styles['BodyPro']))
        story.append(Spacer(1, 0.3*inch))
        
        return story
    
    def _create_strategy_section(self, strategy_data):
        """Create detailed strategy section"""
        story = []
        
        story.append(Paragraph("STRATEGIC MARKETING APPROACH", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        if strategy_data and strategy_data.get('campaigns'):
            story.append(Paragraph("Recommended Campaign Mix", self.styles['SubHeading']))
            
            campaigns = strategy_data.get('campaigns', {})
            campaign_data = []
            
            for campaign_type, details in campaigns.items():
                if isinstance(details, dict):
                    platforms = ', '.join(details.get('platforms', [])) if details.get('platforms') else 'Multiple Platforms'
                    campaign_name = campaign_type.replace('_', ' ').title()
                    campaign_data.append([campaign_name, platforms])
            
            if campaign_data:
                campaign_table = Table(campaign_data, colWidths=[2.5*inch, 4*inch])
                campaign_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9926F3')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('PADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8F9FA')]),
                ]))
                story.append(campaign_table)
                story.append(Spacer(1, 0.2*inch))
        
        # Automation Tools
        if strategy_data and strategy_data.get('automation_tools'):
            story.append(Paragraph("Marketing Automation & Tools", self.styles['SubHeading']))
            
            tools = strategy_data.get('automation_tools', [])[:8]
            for tool in tools:
                story.append(Paragraph(f"• {tool}", self.styles['BulletPoint']))
            
            story.append(Spacer(1, 0.2*inch))
        
        return story
    
    def _create_differentiators_section(self, diff_data):
        """Create competitive advantage section"""
        story = []
        
        story.append(Paragraph("WHY CHOOSE US", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        if diff_data and diff_data.get('differentiators'):
            for idx, diff in enumerate(diff_data.get('differentiators', [])[:5], 1):
                # Differentiator Box
                diff_content = []
                
                # Title with number
                diff_content.append(Paragraph(
                    f"<b>{idx}. {diff.get('title', 'Key Advantage')}</b>",
                    self.styles['SubHeading']
                ))
                
                # Description
                diff_content.append(Paragraph(
                    diff.get('description', ''),
                    self.styles['BodyPro']
                ))
                
                # Impact box
                impact_table = Table(
                    [['Expected Impact:', diff.get('impact', 'Significant positive results')]],
                    colWidths=[1.5*inch, 4.5*inch]
                )
                impact_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1DD8FC')),
                    ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#E8F8FD')),
                    ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                    ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#333333')),
                    ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('PADDING', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1DD8FC')),
                ]))
                diff_content.append(impact_table)
                diff_content.append(Spacer(1, 0.15*inch))
                
                story.extend(diff_content)
        
        return story
    
    def _create_timeline_section(self, timeline_data):
        """Create project timeline section"""
        story = []
        
        story.append(Paragraph("PROJECT TIMELINE & MILESTONES", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        if timeline_data and timeline_data.get('phases'):
            phases = timeline_data.get('phases', [])
            
            for phase in phases:
                # Phase header
                phase_header = Table(
                    [[phase.get('phase', 'Phase'), phase.get('duration', 'Duration TBD')]],
                    colWidths=[4*inch, 2*inch]
                )
                phase_header.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#9926F3')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 12),
                    ('PADDING', (0, 0), (-1, -1), 10),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ]))
                story.append(phase_header)
                
                # Milestones
                if phase.get('milestones'):
                    for milestone in phase.get('milestones', []):
                        story.append(Paragraph(f"✓ {milestone}", self.styles['BulletPoint']))
                
                story.append(Spacer(1, 0.15*inch))
        
        return story
    
    def _create_investment_section(self, proposal_data):
        """Create investment breakdown section"""
        story = []
        
        story.append(Paragraph("INVESTMENT BREAKDOWN", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        budget = proposal_data.get('budget', 0)
        
        # Sample breakdown (you can customize this based on actual data)
        investment_data = [
            ['Investment Category', 'Allocation', 'Amount'],
            ['Strategy & Planning', '15%', f"${budget * 0.15:,.2f}"],
            ['Creative Development', '20%', f"${budget * 0.20:,.2f}"],
            ['Media & Advertising', '45%', f"${budget * 0.45:,.2f}"],
            ['Analytics & Optimization', '10%', f"${budget * 0.10:,.2f}"],
            ['Management & Support', '10%', f"${budget * 0.10:,.2f}"],
            ['', '<b>TOTAL INVESTMENT</b>', f"<b>${budget:,.2f}</b>"],
        ]
        
        investment_table = Table(investment_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
        investment_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9926F3')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#1DD8FC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('PADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F8F9FA')]),
        ]))
        story.append(investment_table)
        story.append(Spacer(1, 0.3*inch))
        
        return story
    
    def _create_next_steps_section(self):
        """Create next steps section"""
        story = []
        
        story.append(Paragraph("NEXT STEPS", self.styles['SectionHeading']))
        story.append(Spacer(1, 0.2*inch))
        
        next_steps = [
            "Review this comprehensive proposal and share any questions or feedback",
            "Schedule a discovery call to discuss your specific goals and requirements",
            "Finalize the strategy and customize the approach based on your input",
            "Sign the agreement and begin onboarding process",
            "Launch your digital marketing campaigns within 2 weeks",
        ]
        
        for idx, step in enumerate(next_steps, 1):
            story.append(Paragraph(
                f"<b>Step {idx}:</b> {step}",
                self.styles['BulletPoint']
            ))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Contact Information
        story.append(Paragraph("CONTACT INFORMATION", self.styles['SubHeading']))
        
        contact_info = """
        <b>PanvelIQ Digital Marketing</b><br/>
        Email: hello@panveliq.com<br/>
        Phone: +1 (555) 123-4567<br/>
        Website: www.panveliq.com<br/><br/>
        We look forward to partnering with you on this exciting journey!
        """
        
        story.append(Paragraph(contact_info, self.styles['BodyPro']))
        
        return story
    
    def generate_pdf(self, proposal_data, strategy_data, diff_data, timeline_data):
        """Generate complete professional PDF"""
        buffer = BytesIO()
        
        # Create document with custom page template
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=50,
            bottomMargin=40,
            leftMargin=40,
            rightMargin=40
        )
        
        # Build story
        story = []
        
        # Cover Page
        story.extend(self._create_cover_page(proposal_data))
        
        # Executive Summary
        story.extend(self._create_executive_summary(proposal_data))
        
        # Strategy Section
        story.append(PageBreak())
        story.extend(self._create_strategy_section(strategy_data))
        
        # Differentiators
        story.append(PageBreak())
        story.extend(self._create_differentiators_section(diff_data))
        
        # Timeline
        story.append(PageBreak())
        story.extend(self._create_timeline_section(timeline_data))
        
        # Investment
        story.append(PageBreak())
        story.extend(self._create_investment_section(proposal_data))
        
        # Next Steps
        story.extend(self._create_next_steps_section())
        
        # Build PDF with header/footer
        doc.build(
            story,
            onFirstPage=lambda c, d: self._draw_header_footer(c, d, proposal_data),
            onLaterPages=lambda c, d: self._draw_header_footer(c, d, proposal_data)
        )
        
        buffer.seek(0)
        return buffer