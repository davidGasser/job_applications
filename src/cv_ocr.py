from pdf2image import convert_from_path
from pathlib import Path
from PIL import Image
import torch
from transformers import AutoModelForCausalLM, AutoProcessor
from typing import List
import os


def perform_ocr(paths_images:List):
    
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    CHOSEN_TASK = "ocr"  # Options: 'ocr' | 'table' | 'chart' | 'formula'
    PROMPTS = {
        "ocr": "OCR:",
        "table": "Table Recognition:",
        "formula": "Formula Recognition:",
        "chart": "Chart Recognition:",
    }

    class PaddleOCR: 
        def __init__(self, model_path:str, path_images:List[str]): 
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path, trust_remote_code=True, torch_dtype=torch.bfloat16
            ).to(DEVICE).eval()
            self.processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
            self.path_images = path_images
            
        def ocr(self): 
            output_texts = []
        
            for path_img in paths_images:
                img = Image.open(path_img).convert("RGB")
                messages = [
                    {"role": "user",         
                    "content": [
                            {"type": "image", "image": img},
                            {"type": "text", "text": PROMPTS[CHOSEN_TASK]},
                        ]
                    }
                ]
                inputs = self.processor.apply_chat_template(
                    messages, 
                    tokenize=True, 
                    add_generation_prompt=True, 	
                    return_dict=True,
                    return_tensors="pt"
                ).to(DEVICE)

                outputs = self.model.generate(**inputs, max_new_tokens=1024)
                outputs = self.processor.batch_decode(outputs, skip_special_tokens=True)[0]
                output_texts.append(outputs)
        
            return output_texts
        
    model_path = "PaddlePaddle/PaddleOCR-VL"
    paddle_OCR = PaddleOCR(model_path, paths_images)
    output_texts = paddle_OCR.ocr()
    
    return output_texts
    

        


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

if __name__ == "__main__": 
 
    path_root = Path(os.getcwd())
    path_cvs = path_root / "data" / "cvs"
    paths_images = path_cvs.glob("*.png")
    output_texts = perform_ocr(paths_images)
    with open(path_root / "data" / "content.txt", "w") as f: 
        f.write("\n\n".join(output_texts))