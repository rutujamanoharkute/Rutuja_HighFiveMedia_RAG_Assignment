from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import Ollama
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from azure.storage.blob import BlobServiceClient
import tempfile
import os
from typing import List
from dotenv import load_dotenv
from .guardrails import guard
import logging

logger = logging.getLogger(__name__)

load_dotenv()

# Initialize models
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
def get_ollama_llm():
    try:
        OLLAMA_HOST = os.getenv('OLLAMA_HOST')
        MODEL_NAME = os.getenv('OLLAMA_MODEL')

        # Update to use https for Ollama host
        llm = Ollama(
            model=MODEL_NAME,
            base_url=OLLAMA_HOST,  # Use https here
            timeout=300,
            temperature=0.1
        )
        # Test call to trigger a connection and raise error if fails
        llm.invoke("ping")
        return llm

    except Exception as e:
        print(f"[WARN] Failed to connect to primary Ollama model: {e}")
        try:
            OLLAMA_HOST = os.getenv('OLLAMA_HOST_LOCAL')
            MODEL_NAME = os.getenv('OLLAMA_MODEL')

            # Use https for fallback as well
            llm = Ollama(
                model=MODEL_NAME,
                base_url=OLLAMA_HOST,  # Use https here as well
                timeout=300,
                temperature=0.1
            )
            # Test again
            llm.invoke("ping")
            return llm

        except Exception as e:
            logger.error(f"[ERROR] Failed to connect to fallback Ollama model: {e}")
            print(f"[ERROR] Failed to connect to fallback Ollama model: {e}")
            raise RuntimeError("Both primary and fallback Ollama models are unreachable.")

# Use it
llm = get_ollama_llm()



# Azure Blob Storage setup
blob_service_client = BlobServiceClient(
    account_url=f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net",
    credential=os.getenv('AZURE_STORAGE_ACCOUNT_KEY')
)

# Prompt template
PROMPT_TEMPLATE = """
You are a helpful AI assistant for our organization. Your responses should align with our values of {values}.
Always be respectful, professional, and maintain confidentiality.

Context: {context}
Question: {question}

Please provide a thorough answer based on the context above, ensuring it reflects our organizational values.
"""

def download_from_blob(blob_name: str) -> str:
    """Download file from blob storage to temp location"""
    try:
        uploads_client = blob_service_client.get_container_client("uploads")
        blob_client = uploads_client.get_blob_client(blob_name)
        
        ext = os.path.splitext(blob_name)[1]
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
            download_stream = blob_client.download_blob()
            temp_file.write(download_stream.readall())
            return temp_file.name
    except Exception as e:
        logger.error(f"Failed to download blob {blob_name}: {str(e)}")
        raise RuntimeError(f"Failed to download blob {blob_name}: {str(e)}")
        

def backup_chromadb_to_blob():
    """Backup ChromaDB to blob storage"""
    chromadb_client = blob_service_client.get_container_client("chromadb")
    chromadb_dir = "./chroma_db"
    
    for root, _, files in os.walk(chromadb_dir):
        for file in files:
            blob_path = os.path.relpath(os.path.join(root, file), chromadb_dir)
            blob_client = chromadb_client.get_blob_client(blob_path)
            with open(os.path.join(root, file), "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

def load_and_split_documents(blob_names: List[str]):
    """Load and split documents with validation"""
    loaders = {
        '.pdf': PyPDFLoader,
        '.docx': Docx2txtLoader,
        '.txt': TextLoader
    }
    
    documents = []
    for blob_name in blob_names:
        try:
            temp_path = download_from_blob(blob_name)
            ext = os.path.splitext(blob_name)[1].lower()
            
            if ext in loaders:
                loader = loaders[ext](temp_path)
                loaded_docs = loader.load()
                
                # Add blob reference to metadata
                for doc in loaded_docs:
                    doc.metadata["source"] = f"blob:{blob_name}"
                documents.extend(loaded_docs)
            
            os.unlink(temp_path)
        except Exception as e:
            logger.error(f"Error processing {blob_name}: {str(e)}")
            print(f"Error processing {blob_name}: {str(e)}")
            continue
    
    if not documents:
        raise ValueError("No valid documents found")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    return text_splitter.split_documents(documents)

def process_documents(blob_names: List[str]):
    """Process documents and store in ChromaDB"""
    documents = load_and_split_documents(blob_names)
    
    # Create ChromaDB instance
    chroma_persist_dir = "./chroma_db"
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=chroma_persist_dir
    )
    
    # Backup to blob storage
    backup_chromadb_to_blob()

# def query_rag(question: str, values: str = "respect, integrity, and service"):
#     """Query the RAG system"""
#     # Initialize ChromaDB
#     db = Chroma(
#         persist_directory="./chroma_db",
#         embedding_function=embeddings
#     )
    
#     # Create prompt
#     prompt = PromptTemplate(
#         template=PROMPT_TEMPLATE,
#         input_variables=["context", "question", "values"]
#     )
    
#     # Create QA chain
#     qa_chain = RetrievalQA.from_chain_type(
#         llm=llm,
#         chain_type="stuff",
#         retriever=db.as_retriever(search_kwargs={"k": 3}),
#         chain_type_kwargs={
#             "prompt": prompt.partial(values=values)
#         },
#         return_source_documents=True
#     )
    
#     # Execute query
#     result = qa_chain({"query": question})
    
#     # Format sources
#     sources = []
#     for doc in result['source_documents']:
#         if doc.metadata['source'].startswith("blob:"):
#             blob_name = doc.metadata['source'][5:]
#             sources.append(
#                 f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net/uploads/{blob_name}"
#             )
    
#     return result['result'], sources



def query_rag(question: str, values: str = "respect, integrity, and service"):
    """RAG with response guardrails"""
    try:
    
        print("Restored ChromaDB")
        # Initialize ChromaDB
        db = Chroma(
            persist_directory="./chroma_db",
            embedding_function=embeddings
        )
        
        # Create prompt
        prompt = PromptTemplate(
            template=PROMPT_TEMPLATE,
            input_variables=["context", "question", "values"]
        )
        
        # Create QA chain
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=db.as_retriever(search_kwargs={"k": 3}),
            chain_type_kwargs={
                "prompt": prompt.partial(values=values)
            },
            return_source_documents=True
        )
        
        # Execute query
        result = qa_chain({"query": question})
        raw_answer = result['result']
        
        # Apply guardrails to response
        sanitized_answer = guard.audit_response(raw_answer)
        
        # Format sources
        sources = []
        for doc in result['source_documents']:
            if doc.metadata['source'].startswith("blob:"):
                blob_name = doc.metadata['source'][5:]
                sources.append(
                    f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net/uploads/{blob_name}"
                )
        
        return sanitized_answer, sources
        
    except Exception as e:
        logger.error(f"RAG processing failed: {str(e)}")
        return guard.get_fallback_response("error"), []
