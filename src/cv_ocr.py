from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

from pdf2image import convert_from_path
import os
from pathlib import Path
import uuid
import shutil

def convert_cv_to_image(pdf_path: Path):
    """
    Converts the first page of a PDF to a PNG image.
    """

    images = convert_from_path(pdf_path, first_page=1, last_page=2)
    
    if images:
        for idx, img in enumerate(images):
            img.save(pdf_path.parent / f"page_{idx+1}.png")
            print(f"Successfully converted page_{idx+1}")
    else:
        print(f"Could not convert '{pdf_path}'")

class Ocr_Model():
    
    def __init__(self, prompt:str, path_cv_folder:Path):
        self.prompt = prompt
        self.path_cv_folder = path_cv_folder
        self.processor = AutoProcessor.from_pretrained("prithivMLmods/Camel-Doc-OCR-080125")
        self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            "prithivMLmods/Camel-Doc-OCR-080125", torch_dtype="auto", device_map="auto"
        )
        
    def perform_ocr(self):
        
        #assemble content
        content = []
        for file in self.path_cv_folder.iterdir():
            #get the png files 
            if file.suffix == ".png": 
                content.append({"type":"image", "image": file.absolute()})
        content.append({"type": "text", "text": self.prompt})
        
        messages = [
            {
                "role": "user",
                "content": content
            },
        ]
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(self.model.device)

        outputs = self.model.generate(**inputs, max_new_tokens=40)
        return self.processor.decode(outputs[0][inputs["input_ids"].shape[-1]:])
    
if __name__ == "__main__": 
    
    pdf_path = Path(os.getcwd()) / "data\cvs\cv_81f1d4f2-7821-45f8-a616-af0c3d32a9bd\David_Gasser_public_CV_2025.pdf"
    
    if pdf_path.parent.name == "cvs": 
        new_cv_folder = pdf_path.parent / f"cv_{uuid.uuid4()}"
        os.makedirs(new_cv_folder)
        shutil.move(pdf_path, new_cv_folder / pdf_path.name)
        pdf_path = new_cv_folder / pdf_path.name
        
    convert_cv_to_image(pdf_path)
    prompt = """Extract all information from the CV provided to you. Make sure to extract everything down to the last symbol and letter. 
                Make sure to group information that belongs together and mark it as such. In a similar vein, clearly destinguish content 
                that does not belong together."""
    ocr_model = Ocr_Model(prompt, pdf_path.parent)
    ocr_model.perform_ocr()
    
    