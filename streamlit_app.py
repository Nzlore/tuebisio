import streamlit as st
import PyPDF2
from pdf2image import convert_from_path
import tempfile
import os
from io import BytesIO
from openai import OpenAI
import re
import json

# Use environment variable for API key
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@st.cache_data
def process_pdf(pdf_content):
    """Cache PDF processing results."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        tmp_file.write(pdf_content)
        pdf_path = tmp_file.name
        try:
            pdf_images = convert_from_path(pdf_path)
            pdf_file = BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            questions = extract_review_questions(pdf_reader)
            return questions
        finally:
            os.unlink(pdf_path)

def extract_review_questions(pdf_reader) -> list:
    """Extract Wiederholungsfragen from PDF."""
    questions = []
    
    for page_num, page in enumerate(pdf_reader.pages):
        page_text = page.extract_text()
        if "Wiederholungsfragen" in page_text:
            lines = page_text.split('\n')
            current_question = ""
            
            for line in lines:
                line = line.strip()
                if any(line.startswith(f"{i}.") for i in range(1, 20)):
                    if current_question:
                        clean_question = re.sub(r'^\d+\.\s*', '', current_question.strip())
                        questions.append({
                            "text": clean_question,
                            "page": page_num + 1
                        })
                    current_question = line
                else:
                    if current_question and line:
                        current_question += " " + line

            if current_question:
                clean_question = re.sub(r'^\d+\.\s*', '', current_question.strip())
                questions.append({
                    "text": clean_question,
                    "page": page_num + 1
                })
    return questions

def evaluate_answer(question: str, user_answer: str) -> dict:
    """Evaluate user's answer using OpenAI."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful teaching assistant evaluating student answers. Always respond with valid JSON."
                },
                {
                    "role": "user",
                    "content": f"""
                    Question: {question}
                    Student's Answer: {user_answer}
                    
                    Evaluate the answer and provide:
                    1. Whether it's correct (yes/no)
                    2. A detailed explanation
                    3. The correct answer if the student's answer was incorrect
                    
                    Return as JSON:
                    {{
                        "is_correct": true/false,
                        "explanation": "Your explanation here",
                        "correct_answer": "The correct answer if needed"
                    }}
                    """
                }
            ],
            temperature=0.3
        )
        
        # Use json.loads instead of eval
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Error evaluating answer: {str(e)}")
        return {"is_correct": False, "explanation": "Error evaluating answer", "correct_answer": ""}

def display_questions(questions: list):
    """Display questions one by one with answer evaluation."""
    # Initialize session state
    if 'question_index' not in st.session_state:
        st.session_state.question_index = 0
    if 'show_evaluation' not in st.session_state:
        st.session_state.show_evaluation = False

    # Display question counter
    st.write(f"Question {st.session_state.question_index + 1} of {len(questions)}")
    
    # Show the question
    current_question = questions[st.session_state.question_index]['text']
    st.markdown(f"### {current_question}")
    
    # Answer input
    user_answer = st.text_area("Your Answer:", key=f"answer_{st.session_state.question_index}")
    
    # Check answer button
    if st.button("Check Answer"):
        if user_answer.strip():
            evaluation = evaluate_answer(current_question, user_answer)
            
            # Show evaluation result
            if evaluation["is_correct"]:
                st.success("✅ Correct!")
            else:
                st.error("❌ Not quite right")
            
            # Show explanation in expander
            with st.expander("See Explanation", expanded=True):
                st.write(evaluation["explanation"])
                if not evaluation["is_correct"] and evaluation["correct_answer"]:
                    st.write("**Correct Answer:**")
                    st.write(evaluation["correct_answer"])
    
    # Navigation buttons in columns
    col1, col2 = st.columns(2)
    
    def prev_question():
        st.session_state.question_index -= 1
        st.session_state.show_evaluation = False

    def next_question():
        st.session_state.question_index += 1
        st.session_state.show_evaluation = False

    with col1:
        if st.session_state.question_index > 0:
            st.button("⬅️ Previous", on_click=prev_question)
    with col2:
        if st.session_state.question_index < len(questions) - 1:
            st.button("Next ➡️", on_click=next_question)

def main():
    st.title("Review Questions")
    uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
    
    if uploaded_file:
        questions = process_pdf(uploaded_file.getvalue())
        if questions:
            display_questions(questions)

if __name__ == "__main__":
    if not os.getenv('OPENAI_API_KEY'):
        st.error('OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.')
        st.stop()
    main() 