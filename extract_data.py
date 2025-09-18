import fitz  # PyMuPDF
import json
import os
import re


# -------------------
# B1. Gom spans toàn bộ PDF
# -------------------
def collect_all_spans(pdf_path, start_from_page=1):
    doc = fitz.open(pdf_path)
    spans = []
    for page in doc:
        page_number = page.number + 1
        if page_number < start_from_page:
            continue
        page_dict = page.get_text("dict")
        for block in page_dict["blocks"]:
            if block["type"] == 0:  # text
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        spans.append({
                            "text": span["text"],
                            "bbox": span["bbox"],
                            "page": page_number
                        })
    doc.close()
    return spans


# -------------------
# B1.6. Clean up text that might have page numbers appended
# -------------------
def clean_text_page_numbers(text):
    """
    Remove page numbers that might be appended to question/answer text.
    Pattern: text ending with space + 1-3 digits
    """
    # Remove trailing page numbers like " 25", " 123" etc.
    cleaned = re.sub(r'\s+\d{1,3}$', '', text.strip())
    return cleaned


# -------------------
# B1.5. Filter out page numbers
# -------------------
def filter_page_numbers(spans):
    """
    Remove spans that are likely page numbers.
    Page numbers are typically:
    - Small isolated numbers (1-3 digits)
    - Located at page edges (top/bottom)
    - Not part of question/answer content
    """
    filtered_spans = []
    
    for span in spans:
        text = span["text"].strip()
        
        # Check if this looks like a standalone page number
        if text.isdigit() and len(text) <= 3:
            page_num = int(text)
            x0, y0, x1, y1 = span["bbox"]
            
            # Get page dimensions to check if number is at edge
            # Assume typical page height is around 800-850 points
            is_at_top = y0 < 100  # Near top of page
            is_at_bottom = y1 > 750  # Near bottom of page
            is_small_isolated = (x1 - x0) < 50  # Small width
            
            # Consider it a page number if it's a reasonable page number and at page edge
            if (is_at_top or is_at_bottom) and is_small_isolated and page_num > 0:
                continue
        
        filtered_spans.append(span)
    
    return filtered_spans


# -------------------
# B2. Gom spans thành câu hỏi / đáp án
# -------------------
def merge_spans(spans):
    merged = []
    buffer = None
    current_type = None

    for span in spans:
        text = span["text"].strip()
        if not text:
            continue

        if re.match(r"^Câu\s+\d+", text):
            if buffer:
                merged.append(buffer)
            buffer = {"type": "question", "text": text, "bbox": span["bbox"], "page": span["page"]}
            current_type = "question"

        elif re.match(r"^\d+\.", text):
            if buffer:
                merged.append(buffer)
            buffer = {"type": "answer", "text": text, "bbox": span["bbox"], "page": span["page"]}
            current_type = "answer"

        else:
            if buffer and current_type:
                buffer["text"] += " " + text
                x0, y0, x1, y1 = buffer["bbox"]
                sx0, sy0, sx1, sy1 = span["bbox"]
                buffer["bbox"] = [min(x0, sx0), min(y0, sy0), max(x1, sx1), max(y1, sy1)]
            else:
                continue

    if buffer:
        merged.append(buffer)
    return merged


# -------------------
# B3. Extract ảnh + bbox
# -------------------
def extract_images(pdf_path, out_dir="images", start_from_page=1):
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_map = {}

    for page_number, page in enumerate(doc, start=1):
        if page_number < start_from_page:
            continue
        page_dict = page.get_text("dict")
        page_images = []

        for idx, block in enumerate(page_dict["blocks"], start=1):
            if block["type"] == 1:  # ảnh
                bbox = block["bbox"]
                img_bytes = block["image"]
                img_name = f"page{page_number}_img{idx}.png"
                img_path = os.path.join(out_dir, img_name)
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                page_images.append({
                    "file": img_name,
                    "bbox": bbox
                })

        image_map[page_number] = page_images

    doc.close()
    return image_map


# -------------------
# B4. Detect underline trong từng page
# -------------------
def collect_underlines(pdf_path, start_from_page=1):
    doc = fitz.open(pdf_path)
    underline_map = {}

    for page_number, page in enumerate(doc, start=1):
        if page_number < start_from_page:
            continue
        drawings = page.get_drawings()
        underlines = []
        for d in drawings:
            if d["type"] == "f" and d.get("fill") == (0.0, 0.0, 0.0):
                rect = d["rect"]
                if rect.height < 2:
                    underlines.append(rect)
        underline_map[page_number] = underlines
    doc.close()
    return underline_map


# -------------------
# B5. Map ảnh cho câu hỏi
# -------------------
def find_image_for_question(question_bbox, answers, page_images):
    if not answers or not page_images:
        return None

    _, _, _, qy1 = question_bbox
    _, ay0, _, _ = answers[0]["bbox"]

    for img in page_images:
        ix0, iy0, ix1, iy1 = img["bbox"]
        if qy1 <= iy0 <= ay0:
            return img["file"]

    return None


# -------------------
# B6. Parse thành JSON
# -------------------
def parse_questions(pdf_path, out_json="questions.json", start_from_page=1):
    spans = collect_all_spans(pdf_path, start_from_page)
    filtered_spans = filter_page_numbers(spans)
    merged_spans = merge_spans(filtered_spans)

    image_map = extract_images(pdf_path, out_dir="images", start_from_page=start_from_page)
    underline_map = collect_underlines(pdf_path, start_from_page)

    all_questions = []
    current_question = None
    current_question_id = None
    question_bbox = None
    question_page = None
    answers = []

    for span in merged_spans:
        if span["type"] == "question":
            if current_question:
                all_questions.append({
                    "id": current_question_id,
                    "question": current_question,
                    "answers": [
                        {"id": a["id"], "text": a["text"], "correct": a["correct"]}
                        for a in answers
                    ],
                    "image": find_image_for_question(
                        question_bbox, answers, image_map.get(question_page, [])
                    )
                })
                answers = []

            # Extract question ID and clean question text
            question_text = clean_text_page_numbers(span["text"])
            question_match = re.match(r"^Câu\s+(\d+)\.\s*(.+)$", question_text)
            if question_match:
                current_question_id = question_match.group(1)
                current_question = clean_text_page_numbers(question_match.group(2))
            else:
                # Fallback if pattern doesn't match
                current_question_id = None
                current_question = question_text
            
            question_bbox = span["bbox"]
            question_page = span["page"]

        elif span["type"] == "answer":
            x0, y0, x1, y1 = span["bbox"]
            page_underlines = underline_map.get(span["page"], [])
            is_underlined = any(
                (ul.y0 >= y1 - 3 and ul.y1 <= y1 + 3 and
                 ul.x0 <= x1 and ul.x1 >= x0)
                for ul in page_underlines
            )
            
            # Extract answer ID and clean answer text
            answer_text = clean_text_page_numbers(span["text"])
            answer_match = re.match(r"^(\d+)\.\s*(.+)$", answer_text)
            if answer_match:
                answer_id = answer_match.group(1)
                clean_answer_text = clean_text_page_numbers(answer_match.group(2))
            else:
                # Fallback if pattern doesn't match
                answer_id = None
                clean_answer_text = answer_text
            
            answers.append({
                "id": answer_id,
                "text": clean_answer_text,
                "bbox": span["bbox"],
                "correct": is_underlined
            })

    if current_question:
        all_questions.append({
            "id": current_question_id,
            "question": current_question,
            "answers": [
                {"id": a["id"], "text": a["text"], "correct": a["correct"]}
                for a in answers
            ],
            "image": find_image_for_question(
                question_bbox, answers, image_map.get(question_page, [])
            )
        })

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã xuất {len(all_questions)} câu hỏi vào {out_json}")


# -------------------
if __name__ == "__main__":
    pdf_path = "input.pdf"
    start_from_page = 5  # Change this to skip header/outline pages (e.g., set to 5 to start from page 5)
    
    parse_questions(pdf_path, out_json="questions.json", start_from_page=start_from_page)