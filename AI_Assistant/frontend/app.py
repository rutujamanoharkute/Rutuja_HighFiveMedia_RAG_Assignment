import streamlit as st
import requests
import os
from dotenv import load_dotenv
import pandas as pd
import io
import time

load_dotenv()

# Configure backend URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Private AI Assistant", layout="wide")

st.title("AI Assistant")
st.markdown("""
    <style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
    }
    .stTextInput>div>div>input {
        border: 1px solid #4CAF50;
    }
    .stDownloadButton>button {
        background-color: #2196F3;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "analysis_complete" not in st.session_state:
    st.session_state.analysis_complete = False

if "report_data" not in st.session_state:
    st.session_state.report_data = None

if "report_filename" not in st.session_state:
    st.session_state.report_filename = "analysis_report.xlsx"

# Sidebar for document upload
with st.sidebar:
    st.header("Document Management")
    uploaded_files = st.file_uploader(
        "Upload documents (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )
    
    if st.button("Process Documents"):
        if uploaded_files:
            with st.spinner("Uploading and processing documents..."):
                files = [("files", (file.name, file.getvalue())) for file in uploaded_files]
                try:
                    response = requests.post(
                        f"{BACKEND_URL}/upload",
                        files=files
                    )
                    if response.status_code == 200:
                        st.success("Documents processed successfully!")
                        # Reset previous analysis results
                        st.session_state.analysis_complete = False
                        st.session_state.report_data = None
                    else:
                        st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
                except Exception as e:
                    st.error(f"Connection error: {str(e)}")
        else:
            st.warning("Please upload at least one document")
    
    st.divider()
    
    analyze_button = st.button("Analyze Documents")
    if analyze_button:
        with st.spinner("Analyzing documents... This may take a minute"):
            try:
                # Use stream=True to handle large files
                response = requests.post(f"{BACKEND_URL}/analyze", stream=True)
                
                if response.status_code == 200:
                    # Extract binary content and filename
                    content_disposition = response.headers.get("content-disposition", "")
                    if "filename=" in content_disposition:
                        filename = content_disposition.split("filename=")[-1].strip('"')
                    else:
                        filename = "analysis_report.xlsx"
                    
                    # Read response content
                    file_content = response.content
                    
                    # Save to session state
                    st.session_state.analysis_complete = True
                    st.session_state.report_data = file_content
                    st.session_state.report_filename = filename
                    
                    st.success("Analysis completed!")
                else:
                    error_detail = "Unknown error"
                    try:
                        error_detail = response.json().get('detail', 'Unknown error')
                    except:
                        error_detail = response.text or "Unknown error"
                    st.error(f"Error: {error_detail}")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")
    
    # Display download button if analysis is complete
    if st.session_state.analysis_complete and st.session_state.report_data is not None:
        st.download_button(
            label="📊 Download Analysis Report",
            data=st.session_state.report_data,
            file_name=st.session_state.report_filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download_report"
        )

# Main chat interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.write(source)

if prompt := st.chat_input("Ask about your documents..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(
                    f"{BACKEND_URL}/query",
                    json={"question": prompt}
                )
                if response.status_code == 200:
                    data = response.json()
                    answer = data["answer"]
                    sources = data["sources"]
                    
                    st.markdown(answer)
                    if sources:
                        with st.expander("Sources"):
                            for source in sources:
                                st.write(source)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })
                else:
                    st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
            except Exception as e:
                st.error(f"Connection error: {str(e)}")