from langchain_text_splitters import RecursiveCharacterTextSplitter
from ai.config import settings


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split text into overlapping chunks optimized for Romanian + English."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.CHUNK_SIZE,
        chunk_overlap=chunk_overlap or settings.CHUNK_OVERLAP,
        separators=[
            "\n\n",       # Paragraph breaks
            "\n",         # Line breaks
            ". ",         # Sentence endings
            "! ",
            "? ",
            "; ",
            ", ",
            " ",
            "",
        ],
        length_function=len,
        is_separator_regex=False,
    )
    return splitter.split_text(text)
