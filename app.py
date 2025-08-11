import streamlit as st
import fitz  # PyMuPDF
import pandas as pd
from groq import Groq
import json
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import re
from datetime import datetime
import base64

def extract_text_from_pdf(uploaded_file):
    """Extract text from uploaded PDF file using PyMuPDF"""
    try:
        # Read the uploaded file
        pdf_bytes = uploaded_file.read()
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        text = ""
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            text += page.get_text()
        
        pdf_document.close()
        return text
    except Exception as e:
        st.error(f"Error extracting text from {uploaded_file.name}: {str(e)}")
        return ""

def analyze_cv_with_groq(cv_text, groq_api_key, candidate_name):
    """Analyze CV content using GROQ API"""
    try:
        client = Groq(api_key=groq_api_key)
        
        prompt = f"""
        Please analyze the following CV/Resume and extract key information in JSON format. 
        The candidate's name is likely: {candidate_name}
        
        Extract the following information:
        - name: Full name of the candidate
        - email: Email address
        - phone: Phone number
        - location: Current location/address
        - experience_years: Total years of experience (numeric)
        - current_role: Current job title
        - industry: Primary industry/sector
        - education: Highest qualification
        - key_skills: List of top 5-7 key skills
        - previous_companies: List of previous companies worked at
        - summary: Brief 2-3 sentence professional summary
        
        CV Content:
        {cv_text[:4000]}  # Limiting text to avoid token limits
        
        Please respond with only valid JSON format.
        """
        
        response = client.chat.completions.create(
            model="llama3-70b-8192",  # Using GROQ's Llama model
            messages=[
                {"role": "system", "content": "You are an expert HR analyst. Extract information from CVs and respond only in valid JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        
        # Parse the JSON response
        result = json.loads(response.choices[0].message.content)
        return result
        
    except json.JSONDecodeError as e:
        st.error(f"Error parsing JSON response for {candidate_name}: {str(e)}")
        return create_fallback_analysis(cv_text, candidate_name)
    except Exception as e:
        st.error(f"Error analyzing CV for {candidate_name}: {str(e)}")
        return create_fallback_analysis(cv_text, candidate_name)

def create_fallback_analysis(cv_text, candidate_name):
    """Create a basic analysis if GROQ API fails"""
    # Basic text analysis fallback
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phone_pattern = r'[\+]?[1-9]?[0-9]{7,15}'
    
    email = re.search(email_pattern, cv_text)
    phone = re.search(phone_pattern, cv_text)
    
    return {
        "name": candidate_name,
        "email": email.group() if email else "Not found",
        "phone": phone.group() if phone else "Not found",
        "location": "Not extracted",
        "experience_years": "Not determined",
        "current_role": "Not extracted",
        "industry": "Not determined",
        "education": "Not extracted",
        "key_skills": ["Analysis failed - manual review required"],
        "previous_companies": ["Not extracted"],
        "summary": "Automatic analysis failed. Manual review required."
    }

def create_pdf_report(candidates_data):
    """Create a PDF report with candidate summaries"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue,
        borderWidth=1,
        borderColor=colors.darkblue,
        borderPadding=5
    )
    
    # Title
    title = Paragraph("CV Screening Report", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Summary statistics
    total_candidates = len(candidates_data)
    summary_text = f"<b>Total Candidates Analyzed:</b> {total_candidates}<br/>"
    summary_text += f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br/>"
    
    summary_para = Paragraph(summary_text, styles['Normal'])
    story.append(summary_para)
    story.append(Spacer(1, 20))
    
    # Individual candidate details
    for i, candidate in enumerate(candidates_data, 1):
        # Candidate header
        candidate_header = Paragraph(f"Candidate {i}: {candidate.get('name', 'Unknown')}", heading_style)
        story.append(candidate_header)
        
        # Create candidate details table
        details = [
            ['Field', 'Information'],
            ['Name', candidate.get('name', 'N/A')],
            ['Email', candidate.get('email', 'N/A')],
            ['Phone', candidate.get('phone', 'N/A')],
            ['Location', candidate.get('location', 'N/A')],
            ['Experience', f"{candidate.get('experience_years', 'N/A')} years" if str(candidate.get('experience_years', '')).isdigit() else candidate.get('experience_years', 'N/A')],
            ['Current Role', candidate.get('current_role', 'N/A')],
            ['Industry', candidate.get('industry', 'N/A')],
            ['Education', candidate.get('education', 'N/A')],
            ['Key Skills', ', '.join(candidate.get('key_skills', [])) if candidate.get('key_skills') else 'N/A'],
            ['Previous Companies', ', '.join(candidate.get('previous_companies', [])) if candidate.get('previous_companies') else 'N/A']
        ]
        
        table = Table(details, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))
        
        story.append(table)
        story.append(Spacer(1, 12))
        
        # Professional summary
        summary_text = candidate.get('summary', 'No summary available')
        summary_para = Paragraph(f"<b>Professional Summary:</b><br/>{summary_text}", styles['Normal'])
        story.append(summary_para)
        story.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def main():
    st.set_page_config(
        page_title="CV Screening App", 
        page_icon="📄", 
        layout="wide"
    )
    
    st.title("📄 CV Screening Application")
    st.markdown("Upload multiple CV files to automatically extract key candidate information")
    
    # Sidebar for configuration
    st.sidebar.header("Configuration")
    
    # GROQ API Key input
    groq_api_key = st.sidebar.text_input(
        "GROQ API Key",
        type="password",
        help="Enter your GROQ API key to enable AI-powered CV analysis"
    )
    
    if not groq_api_key:
        st.sidebar.warning("Please enter your GROQ API key to use the CV analysis feature")
        st.info("👈 Please enter your GROQ API key in the sidebar to begin")
        return
    
    # File upload section
    st.header("📁 Upload CV Files")
    uploaded_files = st.file_uploader(
        "Choose CV files (PDF format)",
        accept_multiple_files=True,
        type=['pdf'],
        help="Upload one or more PDF files containing candidate CVs"
    )
    
    if uploaded_files:
        st.success(f"✅ {len(uploaded_files)} file(s) uploaded successfully")
        
        # Process CVs button
        if st.button("🔍 Analyze CVs", type="primary"):
            candidates_data = []
            
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, uploaded_file in enumerate(uploaded_files):
                status_text.text(f"Processing {uploaded_file.name}...")
                
                # Extract text from PDF
                cv_text = extract_text_from_pdf(uploaded_file)
                
                if cv_text:
                    # Get candidate name from filename (remove .pdf extension)
                    candidate_name = uploaded_file.name.replace('.pdf', '').replace('_', ' ').title()
                    
                    # Analyze CV with GROQ
                    candidate_data = analyze_cv_with_groq(cv_text, groq_api_key, candidate_name)
                    candidates_data.append(candidate_data)
                
                # Update progress
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_text.text("Analysis complete!")
            
            if candidates_data:
                # Display results
                st.header("📊 Analysis Results")
                
                # Create DataFrame for display
                df_display = pd.DataFrame(candidates_data)
                
                # Display summary table
                st.subheader("Candidate Summary")
                st.dataframe(df_display, use_container_width=True)
                
                # Detailed view
                st.subheader("Detailed Analysis")
                for i, candidate in enumerate(candidates_data):
                    with st.expander(f"👤 {candidate.get('name', 'Unknown Candidate')}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Contact Information:**")
                            st.write(f"📧 Email: {candidate.get('email', 'N/A')}")
                            st.write(f"📞 Phone: {candidate.get('phone', 'N/A')}")
                            st.write(f"📍 Location: {candidate.get('location', 'N/A')}")
                            
                            st.write("**Professional Details:**")
                            st.write(f"💼 Current Role: {candidate.get('current_role', 'N/A')}")
                            st.write(f"🏢 Industry: {candidate.get('industry', 'N/A')}")
                            st.write(f"⏱️ Experience: {candidate.get('experience_years', 'N/A')} years")
                        
                        with col2:
                            st.write("**Education:**")
                            st.write(f"🎓 {candidate.get('education', 'N/A')}")
                            
                            st.write("**Key Skills:**")
                            skills = candidate.get('key_skills', [])
                            if skills:
                                for skill in skills:
                                    st.write(f"• {skill}")
                            else:
                                st.write("No skills extracted")
                        
                        st.write("**Professional Summary:**")
                        st.write(candidate.get('summary', 'No summary available'))
                
                # Generate PDF report
                st.header("📄 Download Report")
                if st.button("Generate PDF Report", type="secondary"):
                    with st.spinner("Generating PDF report..."):
                        pdf_buffer = create_pdf_report(candidates_data)
                        
                        st.success("PDF report generated successfully!")
                        
                        # Download button
                        st.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_buffer.getvalue(),
                            file_name=f"CV_Screening_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
            else:
                st.error("No data was extracted from the uploaded files. Please check the file format and try again.")
    
    else:
        st.info("Please upload CV files to begin the analysis")
    
    # Footer
    st.markdown("---")
    st.markdown("Built with ❤️ using Streamlit, GROQ API, and PyMuPDF")

if __name__ == "__main__":
    main()
