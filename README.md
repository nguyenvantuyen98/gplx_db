# GPLX Data Extraction

A Python script to extract Vietnamese driving license exam questions and answers from PDF documents and convert them into structured JSON format.

## Overview

This project processes Vietnamese driving license (GPLX - Giấy Phép Lái Xe) exam materials from PDF format and extracts:
- Questions and multiple choice answers
- Associated images
- Structured data in JSON format

## Features

- PDF text extraction using PyMuPDF
- Automatic question and answer parsing
- Image extraction from PDF pages
- Clean text processing (removes page numbers and formatting artifacts)
- JSON output with structured question data

## Requirements

- Python 3.x
- PyMuPDF 1.26.4

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Place your PDF file as `input.pdf` in the project directory
2. Run the extraction script:
   ```bash
   python extract_data.py
   ```
3. The script will generate:
   - `questions.json` - Structured question data
   - `images/` directory - Extracted images from the PDF

## Output Format

The generated `questions.json` contains an array of question objects:

```json
{
  "id": "1",
  "question": "Question text here",
  "answers": [
    {
      "id": "1", 
      "text": "Answer option text",
      "correct": true/false
    }
  ],
  "image": "image_filename.png" or null
}
```

## Project Structure

```
gplx_data/
├── extract_data.py      # Main extraction script
├── input.pdf           # Source PDF file
├── questions.json      # Generated structured data
├── requirements.txt    # Python dependencies
├── images/            # Extracted images
└── README.md          # This file
```