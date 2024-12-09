import pytesseract
from PIL import Image, UnidentifiedImageError
from pathlib import Path
from typing import Optional, Set, TypedDict, Tuple, List
import pymupdf


class UnsupportedExtensionError(ValueError):
    pass


class NotImplementedExtensionError(ValueError):
    pass


class FeaturedText(TypedDict):
    text: str  # The text content (e.g., a word or phrase).
    size: float  # The font size or relative size of the text.
    flags: int  # Flags providing metadata (e.g., styling or annotations).
    bbox: Tuple[float, float, float, float]  # Bounding box (x1, y1, x2, y2).
    page: int  # Page number where the text appears.


class TextExtractorPipeline:
    """A class to handle text extraction from any type of img based files."""
    

    @staticmethod
    def __validate_file_path(file_path: str, expected_extensions: Optional[Set[str]] = None) -> Path:
        """
        Validate the file path and extension.

        Args:
            file_path (str): Path to the file to validate.
            expected_extensions (set): A set of supported file extensions (e.g., {".jpg", ".pdf"}).

        Raises:
            FileNotFoundError: If the file does not exist.
            IsADirectoryError: If the provided path is a directory instead of a file.
            ValueError: If the file extension is not in the expected set.

        Returns:
            pathlib.Path: The validated file path as a Path object.
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not path.is_file():
            raise IsADirectoryError(f"Path is not a file: {file_path}")
        if expected_extensions and path.suffix.lower() not in expected_extensions:
            raise UnsupportedExtensionError(f"Unsupported file type: {file_path}. Expected extensions: {expected_extensions}")
        return path


    @staticmethod
    def extract(file_path: str, from_page: int = None, to_page: int = None):
        """
        Master method to convert an image to text using Tesseract OCR.

        Args:
            image_path (str): Path to the image file.

        Raises:
            FileNotFoundError: If the file does not exist.
            IsADirectoryError: If the provided path is a directory instead of a file.
            ValueError: If the file extension is not supported or the image cannot be processed.
            RuntimeError: If any other error occurs during processing.

        Returns:
            str: Extracted text from the image.
        """
        try:
            # supported extensions
            supported_extensions = set()

            picture_extensions = set(Image.registered_extensions())
            supported_extensions.update(picture_extensions)
            supported_extensions.add('.pdf')

            path = TextExtractorPipeline.__validate_file_path(file_path, supported_extensions)

            match path.suffix.lower():
                case '.pdf':
                    return TextExtractorPipeline.__pdf_to_text(path, from_page, to_page)
                
                case _ if path.suffix.lower() in picture_extensions:
                    return TextExtractorPipeline.__picture_to_text(path)
                
                case _:
                    raise NotImplementedExtensionError(f"Provided extension is not implemented '{path.suffix.lower()}'")

        except (UnsupportedExtensionError, NotImplementedExtensionError) as e:
            raise ValueError(e)    
        except UnidentifiedImageError:
            raise ValueError(f"Cannot process the image: {file_path}")
        except Exception as e:
            raise RuntimeError(f"An error occurred while processing the image: {str(e)}")


    @staticmethod
    def __pdf_to_text(path: Path, from_page: int = None, to_page: int = None) -> List[FeaturedText]:
        """
        Convert a PDF to text.

        Args:
            pdf_path (str): Path to the PDF file.

        Raises:
            RuntimeError: If an error occurs during processing.

        Returns:
            str: Extracted text from the PDF.
        """
        try:
          doc = pymupdf.open(path)
          last_page_num = len(doc) - 1
          if not from_page:
              from_page = 0
          if not to_page:
              to_page = last_page_num
          text_data = []

          for page in doc[from_page : to_page + 1]:
            blocks = page.get_text("dict")["blocks"]  # Extract blocks of text with metadata
            for block in blocks:
              if not "lines" in block:  # ignore img and other than text types of block
                  continue
              for line in block["lines"]:
                for span in line["spans"]:
                  text_data.append({
                    "text": span["text"],  # Actual text
                    "size": span["size"],  # Font size
                    "flags": span["flags"],  # Font style (e.g., bold, italic)
                    "bbox": span["bbox"],  # Position on the page
                    "len": len(span["text"]),
                    "page": page.number + 1
                  })

          return text_data
        except Exception as e:
            raise RuntimeError(f"An error occurred while processing the PDF: {str(e)}")

        finally:
            doc.close()

    @staticmethod
    def __picture_to_text(path: Path) -> str:
        """
        Convert an image to text using Tesseract OCR.

        Args:
            image_path (str): Path to the image file.

        Raises:
            ValueError: If the file cannot be processed as an image.
            RuntimeError: If an error occurs during processing.

        Returns:
            str: Extracted text from the image.
        """
        try:
            image = Image.open(path)
            return pytesseract.image_to_string(image)
        except UnidentifiedImageError:
            raise ValueError(f"Cannot process the image: {path}")
        except Exception as e:
            raise RuntimeError(f"An error occurred while processing the image: {str(e)}")