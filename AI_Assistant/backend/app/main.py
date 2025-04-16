from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
from dotenv import load_dotenv
from .models import QueryRequest, QueryResponse, UploadResponse, AnalysisReport
from .rag import process_documents, query_rag, backup_chromadb_to_blob
from .document_analyzer import analyze_documents_from_blob
from datetime import datetime
from fastapi.responses import StreamingResponse
from fastapi.responses import FileResponse
from .guardrails import guard
import logging
import io
import uuid
from azure.storage.blob import BlobServiceClient
import tempfile

load_dotenv()

app = FastAPI(title="Private AI Assistant API")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Blob Service Client
blob_service_client = BlobServiceClient(
    account_url=f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net",
    credential=os.getenv('AZURE_STORAGE_ACCOUNT_KEY')
)

# Get container clients
uploads_container_client = blob_service_client.get_container_client(os.getenv('UPLOAD_CONTAINER', 'uploads'))
chromadb_container_client = blob_service_client.get_container_client(os.getenv('CHROMADB_CONTAINER', 'chromadb'))

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.post("/upload", response_model=UploadResponse)
async def upload_documents(files: List[UploadFile] = File(...)):
    """Endpoint for uploading documents"""
    try:
        blob_names = []  # Store blob names instead of temp paths
        for file in files:
            file_id = str(uuid.uuid4())
            blob_name = f"{file_id}_{file.filename}"
            blob_client = uploads_container_client.get_blob_client(blob_name)
            
            # Upload to blob storage
            file_content = await file.read()
            blob_client.upload_blob(file_content)
            
            # Store blob name for processing
            blob_names.append(blob_name)
        
        # Process using blob names instead of temp files
        process_documents(blob_names)
        backup_chromadb_to_blob()
        
        return UploadResponse(
            message="Documents uploaded and processed successfully",
            file_ids=blob_names
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# @app.post("/query", response_model=QueryResponse)
# async def query_documents(request: QueryRequest):
#     """Endpoint for querying documents"""
#     try:
#         answer, sources = query_rag(request.question)
#         accessible_sources = [
#             f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net/{os.getenv('UPLOAD_CONTAINER')}/{os.path.basename(source)}"
#             for source in sources
#         ]
#         return QueryResponse(
#             answer=answer,
#             sources=accessible_sources
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Endpoint with full guardrail integration"""
    try:
        # 1. Input Auditing
        is_flagged, audit_result = guard.audit_prompt(request.question)
        if is_flagged:
            logger.warning(f"Blocked query - {audit_result}")
            return QueryResponse(
                answer=guard.get_fallback_response(audit_result["flagged_categories"][0]),
                sources=[],
                audit_log=audit_result
            )
        
        # 2. Process Query
        answer, sources = query_rag(request.question)
        
        # 3. Output Sanitization
        sanitized_answer = guard.audit_response(answer)
        
        # 4. Logging
        logger.info(f"Processed query - {request.question[:50]}...")
        
        return QueryResponse(
            answer=sanitized_answer,
            sources=sources,
            audit_log=audit_result
        )
        
    except Exception as e:
        logger.error(f"Query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# @app.post("/analyze", response_model=AnalysisReport)
# async def analyze_uploaded_documents():
#     """Endpoint for analyzing documents"""
#     try:
#         report_path = analyze_documents(UPLOAD_DIR)
#         return AnalysisReport(
#             message="Document analysis completed",
#             report_path=report_path
#         )
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
async def analyze_uploaded_documents():
    try:
        # Generate report with improved analyzer
        excel_buffer, filename = analyze_documents_from_blob(
            container_client=uploads_container_client,
            organizational_values="respect, integrity, and service"
        )
        
        # Verify data was generated
        buffer_size = excel_buffer.getbuffer().nbytes
        if buffer_size < 1024:  # Check if file is too small
            raise HTTPException(status_code=400, detail="Analysis produced no results")
        
        logger.info(f"Analysis report generated successfully: {filename} ({buffer_size} bytes)")
        
        # Return as streaming response
        return StreamingResponse(
            excel_buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        uploads_container_client.get_container_properties()
        chromadb_container_client.get_container_properties()
        return {
            "status": "healthy",
            "storage": {
                "uploads_container": "accessible",
                "chromadb_container": "accessible"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage health check failed: {str(e)}")
