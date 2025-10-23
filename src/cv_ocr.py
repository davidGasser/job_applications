from pdf2image import convert_from_path
import os
from pathlib import Path
import uuid
import shutil
import cv2
import numpy as np

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

def detect_lines(image_path: Path):
    """
    Detects horizontal and vertical lines in an image.

    Args:
        image_path: The path to the image file.
    """
    image = cv2.imread(str(image_path))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    
    # Resize image for display
    screen_res = 1280, 720
    scale_width = screen_res[0] / image.shape[1]
    scale_height = screen_res[1] / image.shape[0]
    scale = min(scale_width, scale_height)
    window_width = int(image.shape[1] * scale)
    window_height = int(image.shape[0] * scale)
    
    # # Horizontal line detection
    # sobel_x_h = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=31)
    # gradient_magnitude_h = np.sqrt(sobel_x_h**2)
    # gradient_magnitude_h = cv2.erode(gradient_magnitude_h, np.ones((3,300),np.uint8), iterations=2)
    # gradient_magnitude_h = cv2.normalize(gradient_magnitude_h, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    # kernel_h = np.ones((20, 120), np.uint8)
    # gradient_magnitude_h = cv2.morphologyEx(gradient_magnitude_h, cv2.MORPH_CLOSE, kernel_h)
    # _, thresh_h = cv2.threshold(gradient_magnitude_h, 10, 255, cv2.THRESH_BINARY)
    # cnts, _ = cv2.findContours(thresh_h, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # for cnt in cnts: 
    #     x,y,w,h = cv2.boundingRect(cnt)
    #     cv2.rectangle(image,(x,y),(x+w,y+h),(0,255,0),2)
    
    # # Display horizontal Sobel output
    # cv2.namedWindow("Horizontal Sobel Output", cv2.WINDOW_NORMAL)
    # cv2.resizeWindow("Horizontal Sobel Output", window_width, window_height)
    # cv2.imshow("Horizontal Sobel Output", image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    
    # # detect vertical lines
    # sobel_x_v = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=31)
    # gradient_magnitude_v = np.sqrt(sobel_x_v**2)
    # gradient_magnitude_v = cv2.erode(gradient_magnitude_v, np.ones((300,3),np.uint8), iterations=2)
    # gradient_magnitude_v = cv2.normalize(gradient_magnitude_v, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)
    # kernel_v = np.ones((120, 20), np.uint8)
    # gradient_magnitude_v = cv2.morphologyEx(gradient_magnitude_v, cv2.MORPH_CLOSE, kernel_v)
    # _, thresh_v = cv2.threshold(gradient_magnitude_v, 10, 255, cv2.THRESH_BINARY)
    # cnts, _ = cv2.findContours(thresh_v, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # for cnt in cnts: 
    #     x,y,w,h = cv2.boundingRect(cnt)
    #     cv2.rectangle(image,(x,y),(x+w,y+h),(0,255,0),2)
        
    # # Display vertical Sobel output
    # cv2.namedWindow("Vertical Sobel Output", cv2.WINDOW_NORMAL)
    # cv2.resizeWindow("Vertical Sobel Output", window_width, window_height)
    # cv2.imshow("Vertical Sobel Output", image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # detect whitespaces
    _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)

    # Calculate horizontal projection (vertical whitespace indicator)
    h_profile = np.sum(binary, axis=0)

    # Find columns with low values
    threshold = np.max(h_profile)
    whitespace_regions = np.where(h_profile == threshold)[0]
    for col in whitespace_regions:
        cv2.line(image, (col, 0), (col, image.shape[0]), (0, 255, 0), 1)

    cv2.namedWindow("Whitespace Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Whitespace Detection", window_width, window_height)
    cv2.imshow('Whitespace Detection', image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    # Combine horizontal and vertical lines
    # thresh = cv2.add(thresh_h, thresh_v)

    # # Find contours
    # cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # for c in cnts:
    #     cv2.drawContours(image, [c], -1, (0, 255, 0), 2)

    # cv2.namedWindow("Detected Lines", cv2.WINDOW_NORMAL)
    # cv2.resizeWindow("Detected Lines", window_width, window_height)

    # # Display the image with detected lines
    # cv2.imshow("Detected Lines", image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()