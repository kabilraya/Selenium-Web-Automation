import os
import tempfile

from pypdf import PdfReader, PdfWriter


def convert_to_mb(size_bytes):
    """Convert bytes to megabytes"""
    return round(size_bytes / (1024 * 1024), 2)


def get_pdf_size_with_pages(pdf_writer):
    """Get the actual size of a PdfWriter object by writing to a temporary file"""
    with tempfile.NamedTemporaryFile() as temp_file:
        pdf_writer.write(temp_file)
        temp_file.flush()
        return os.path.getsize(temp_file.name)


def split_pdf(file_path: str, max_size_mb: int = 50, max_chunks: int = 10) -> list:
    """
    Splits a PDF file into multiple smaller PDF files based on a given file path.
    Stops at max_chunks and puts remaining pages in the final chunk.

    Args:
        file_path (str): The path of the PDF file to be split.
        max_size_mb (int): Maximum size in MB for each split file.
        max_chunks (int): Maximum number of chunks to create.

    Returns:
        list: A list of tuples containing information about the split PDF files.
              Each tuple consists of the file name, file size in MB, and file path.
    """
    download_path = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    file_name_without_ext = os.path.splitext(file_name)[0]

    original_size_bytes = os.path.getsize(file_path)
    original_size_mb = convert_to_mb(original_size_bytes)

    print(f"Original file: {file_name} ({original_size_mb} MB)")

    if original_size_mb <= max_size_mb:
        return [(file_name, original_size_mb, file_path)]

    max_size_bytes = max_size_mb * 1024 * 1024
    file_info = []

    with open(file_path, "rb") as f:
        pdf_reader = PdfReader(f)
        total_pages = len(pdf_reader.pages)

        print(f"Total pages: {total_pages}")

        current_page = 0
        chunk_num = 1

        while current_page < total_pages:
            print(f"\nCreating chunk {chunk_num}...")

            remaining_pages = total_pages - current_page

            # Check if this is the last allowed chunk
            if chunk_num >= max_chunks:
                # Put all remaining pages in this final chunk
                print(
                    f"Reached max chunks ({max_chunks}), putting all remaining {remaining_pages} pages in final chunk..."
                )
                best_page_count = remaining_pages
            else:
                # Binary search for optimal page count
                left, right = 1, remaining_pages
                best_page_count = 0

                while left <= right:
                    mid = (left + right) // 2

                    # Test this page count
                    test_writer = PdfWriter()
                    for i in range(current_page, min(current_page + mid, total_pages)):
                        test_writer.add_page(pdf_reader.pages[i])

                    size_bytes = get_pdf_size_with_pages(test_writer)

                    if size_bytes <= max_size_bytes:
                        best_page_count = mid
                        left = mid + 1
                    else:
                        right = mid - 1

                # Check if even a single page exceeds the limit
                if best_page_count == 0:
                    print(
                        f"Warning: Single page at index {current_page} exceeds {max_size_mb} MB limit"
                    )
                    best_page_count = 1

            # Create chunk with best page count
            pdf_writer = PdfWriter()
            end_page = min(current_page + best_page_count, total_pages)

            for i in range(current_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[i])

            # Write file
            part_file_name = f"{file_name_without_ext}_part{chunk_num}.pdf"
            part_file_path = os.path.join(download_path, part_file_name)

            with open(part_file_path, "wb") as part_file:
                pdf_writer.write(part_file)

            actual_size_mb = convert_to_mb(os.path.getsize(part_file_path))
            pages_used = end_page - current_page

            # Warn if chunk exceeds limit
            if actual_size_mb > max_size_mb:
                print(
                    f"Created: {part_file_name} ({actual_size_mb} MB, {pages_used} pages) ⚠️ EXCEEDS LIMIT"
                )
            else:
                print(
                    f"Created: {part_file_name} ({actual_size_mb} MB, {pages_used} pages)"
                )

            file_info.append((part_file_name, actual_size_mb, part_file_path))

            current_page = end_page
            chunk_num += 1

            # Stop if we've reached max chunks
            if chunk_num > max_chunks:
                break

    os.remove(file_path)

    return file_info
