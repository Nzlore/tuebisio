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

def evaluate_answer(question: str, user_answer: str, eli5: bool = False) -> dict:
    """Evaluate user's answer using OpenAI."""
    try:
        eli5_instruction = """
        Falls 'explain_simple' aktiviert ist, formuliere die Erklärung sehr einfach, 
        als würdest du mit einem Kind sprechen. Benutze einfache Worte und kurze Sätze.
        """ if eli5 else ""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"""Du bist ein hilfreicher Lehrassistent, der Studentenantworten bewertet. 
                    Antworte immer mit gültigem JSON und formuliere alle Erklärungen auf Deutsch.
                    Bei falschen Antworten gib eine einprägsame Eselsbrücke, die beim Merken der richtigen Antwort hilft.
                    {eli5_instruction}"""
                },
                {
                    "role": "user",
                    "content": f"""
                    Frage: {question}
                    Antwort des Studenten: {user_answer}
                    Einfache Erklärung gewünscht: {str(eli5)}
                    
                    Bewerte die Antwort und gib folgendes an:
                    1. Ob sie korrekt ist (ja/nein)
                    2. Eine detaillierte Erklärung
                    3. Die richtige Antwort falls die Antwort falsch war
                    4. Eine Eselsbrücke falls die Antwort falsch war
                    
                    Antworte als JSON:
                    {{
                        "is_correct": true/false,
                        "explanation": "Deine Erklärung hier",
                        "correct_answer": "Die richtige Antwort falls nötig",
                        "eselsbruecke": "Eine hilfreiche Eselsbrücke falls die Antwort falsch war"
                    }}
                    """
                }
            ],
            temperature=0.3
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        st.error(f"Fehler bei der Auswertung: {str(e)}")
        return {
            "is_correct": False, 
            "explanation": "Fehler bei der Auswertung", 
            "correct_answer": "",
            "eselsbruecke": ""
        }

def display_questions(questions: list):
    """Display questions one by one with answer evaluation."""
    # Initialize session state
    if 'question_index' not in st.session_state:
        st.session_state.question_index = 0
    if 'show_evaluation' not in st.session_state:
        st.session_state.show_evaluation = False

    # Display question counter
    st.write(f"Frage {st.session_state.question_index + 1} von {len(questions)}")
    
    # Show the question
    current_question = questions[st.session_state.question_index]['text']
    st.markdown(f"### {current_question}")
    
    # Answer input and controls
    col1, col2 = st.columns([3, 1])
    with col1:
        user_answer = st.text_area("Deine Antwort:", key=f"answer_{st.session_state.question_index}")
    with col2:
        eli5_mode = st.toggle("Erkläre es einfach 🧸", help="Aktiviere für eine besonders einfache Erklärung")
    
    # Check answer button
    if st.button("Antwort prüfen"):
        if user_answer.strip():
            evaluation = evaluate_answer(current_question, user_answer, eli5_mode)
            
            # Show evaluation result
            if evaluation["is_correct"]:
                st.success("✅ Richtig!")
            else:
                st.error("❌ Nicht ganz richtig")
            
            # Show explanation in expander
            with st.expander("Erklärung anzeigen", expanded=True):
                if eli5_mode:
                    st.markdown("### 🧸 Einfache Erklärung:")
                st.write(evaluation["explanation"])
                if not evaluation["is_correct"]:
                    if evaluation["correct_answer"]:
                        st.write("**Richtige Antwort:**")
                        st.write(evaluation["correct_answer"])
                    if evaluation.get("eselsbruecke"):
                        st.write("**Eselsbrücke:**")
                        st.info(evaluation["eselsbruecke"])
    
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
            st.button("⬅️ Zurück", on_click=prev_question)
    with col2:
        if st.session_state.question_index < len(questions) - 1:
            st.button("Weiter ➡️", on_click=next_question)

def main():
    st.title("Wiederholungsfragen")
    uploaded_file = st.file_uploader("PDF hochladen", type=['pdf'])
    
    if uploaded_file:
        questions = process_pdf(uploaded_file.getvalue())
        if questions:
            display_questions(questions)

if __name__ == "__main__":
    if not os.getenv('OPENAI_API_KEY'):
        st.error('OpenAI API-Schlüssel nicht gefunden. Bitte setze die OPENAI_API_KEY Umgebungsvariable.')
        st.stop()
    main() 