from pdf2image import convert_from_path
from pathlib import Path
import io
import base64
import ollama
import os
import logging


def _convert_cv_to_image(pdf_path: Path):
    # Converts up to two pages of a PDF to JPEG images in base64 format.
    images = convert_from_path(pdf_path, first_page=1, last_page=2)
    if type(images) != list:
        images = [images]

    base64_images = []
    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')  # Convert PPM to JPEG in memory
        base64_images.append(base64.b64encode(buffer.getvalue()).decode('utf-8'))
    return base64_images


def extract_text_from_cv(path_pdf: Path, model="qwen3-vl:2b"):
    # Extracts the CV's content from the image using Ollama vision model.

    # Create Ollama client with host from environment variable (defaults to http://localhost:11430)
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11430')
    client = ollama.Client(host=ollama_host)

    images = _convert_cv_to_image(path_pdf)

    client.pull(model)
    prompt = "Extract the text from the provided CV. Always provide direct, clear answers without excessive thinking."
    user_content = "What is the content of the CV?"
    response = client.chat(
        model=model,
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': user_content, 'images': images}
        ],
        stream=False,
        options={'temperature': 0},
    )
    output = response['message']['content']

    # Safe validation
    if not output:
        raise ValueError("CV extraction returned empty response - please try again")

    # Try to extract content
    if len(output) >= 2 and output[0] == "[" and output[-1] == "]":
        return output[1:-1]
    else:
        # Return as-is but log the issue
        logging.warning(f"CV extraction didn't follow expected format.")
        return output.strip()

if __name__ == "__main__": 
    
    path_cv = "/uploads/David_Gasser_public_CV_2025.pdf"
    output_text = extract_text_from_cv(path_cv)
    with open("keyword.txt", "w") as f: 
        f.write(output_text)