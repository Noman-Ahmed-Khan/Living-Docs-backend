from typing import List
import os
from langchain_community.document_loaders import (
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredPowerPointLoader,
    UnstructuredExcelLoader,
    TextLoader,
    BSHTMLLoader
)
from langchain_core.documents import Document

class DocumentLoader:
    @staticmethod
    def load(file_path: str) -> List[Document]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
        elif ext in [".docx", ".doc"]:
            loader = UnstructuredWordDocumentLoader(file_path)
        elif ext in [".pptx", ".ppt"]:
            loader = UnstructuredPowerPointLoader(file_path)
        elif ext in [".xlsx", ".xls"]:
            loader = UnstructuredExcelLoader(file_path)
        elif ext in [".md", ".txt"]:
            loader = TextLoader(file_path)
        elif ext in [".html", ".htm"]:
            loader = BSHTMLLoader(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {ext}")
        
        return loader.load()
