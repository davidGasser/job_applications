from openai import OpenAI
import ollama
import os
import time
import json
from pathlib import Path
from pydantic import BaseModel


class Reasoning(BaseModel):
    strengths: str
    concerns: str
    summary: str


class Score(BaseModel):
    skillset: int
    academic: int
    experience: int
    professional: int
    language: int
    preference: int
    overall: int
    reasoning: Reasoning


class CriterionRating(BaseModel):
    job_requirements: str
    candidate_qualifications: str
    score: int


class Rating(BaseModel):
    skillset: CriterionRating
    academics: CriterionRating
    experience_level: CriterionRating
    professional_experience: CriterionRating
    languages: CriterionRating
    preferences: CriterionRating
    overall: CriterionRating


def score_job(job: dict, cv: str, preferences: str, model: str = "llama-3.2-3b-instruct", **kwargs):
    """
    Compare job positions with the CV and the preference statement of the applicant.
    Returns a verified JSON file, with different rantings (int) and assessments (str).
    Uses llama-cpp-python for fast inference with KV caching.
    """
    llamacpp_host = os.getenv('LLAMACPP_HOST', 'http://localhost:11434')
    client = OpenAI(
        base_url=f"{llamacpp_host}/v1",
        api_key="dummy-key"  # llama-cpp-python doesn't require real API keys
    )

    prompt = """
            Your task is to rate how well job postings fit a provided CV and preference statement.
            Your rating scale is:
            0 = Critical mismatch, 25 = Poor match, 50 = Acceptable, 75 = Good match, 100 = Excellent match
            Make small adjustments of ±5-10 points if needed

            THE CRITERIA:
            1. Skillset Match: Does the applicant possess the required technical/soft skills,
            or could they acquire them quickly given their background?

            2. Academic Requirements: Are degree requirements, field of study, and grade
            thresholds (if specified) met?

            3. Experience Level: Is the applicant appropriately qualified (not under or
            over-qualified) for the seniority level?

            4. Professional Experience: Does the applicant have relevant industry/domain
            experience and comparable role experience?

            5. Language Requirements: What languages does the applicant speak? What languages are required by the job posting?
            Can they read the job description?

            6. Preference Alignment: Does the role, company, location, and work style match
            the applicant's stated preferences?

            7. Overall Assessment: Considering all factors, how successful and satisfied
            would the applicant likely be in this role?
            """
    message = f"""
                # CV:
                {cv}

                # PREFERENCES:
                {preferences}

                # JOB DETAILS
                TITLE: {job["title"]}
                COMPANY: {job["company"]}
                DESCRIPTION: {job["description"]}
                """

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ],
        stream=False,
        options={
            "num_predict": -1,
            "temperature": 0
        },
        response_format={"type": "json_object"}
    )

    return Score.model_validate_json(response.choices[0].message.content).model_dump_json(indent=2)


def summarize(job, cv, preferences, model, **kwargs):

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)

    prompt_summary = f"""
            Extract the information needed to answer the following questions:

            1. Skillset Match: What technical/soft skills are required by the job? What skills does the applicant have?

            2. Academic Requirements: What degree requirements, field of study, and grade thresholds are specified? Which does the applicant have?

            3. Experience Level: What seniority level does the job entail? What level does the applicant have?

            4. Professional Experience: What industry/domain experience does the job require? Which experience does the applicant have?

            5. Language Requirements: What language is the job posting in? Where is the job located? What languages are required by the job posting?
            What languages does the applicant speak?

            6. Preference Alignment: Does the role, company, location, and work style match the applicant's stated preferences?
            """
    chat_summary = f"""
            CV:
            {cv}

            PREFERENCE STATEMENT:
            {preferences}

            JOB:
            {job}
            """

    summary = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": prompt_summary},
            {"role": "user", "content": chat_summary}
        ],
        stream=False,
        options={
            "temperature": 0
        }
    )
    return summary.message.content


def score_on_summary(summary, model, **kwargs):
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)

    prompt_scoring = """
        Based on the provided summary, critically rate how well the candidate fits to job from.
        Your rating scale is:
        0 = Critical mismatch, 25 = Poor match, 50 = Acceptable, 75 = Good match, 100 = Excellent match
        Make small adjustments of ±5-10 points if needed:

        THE CRITERIA:
            1. Skillset Match: Does the applicant possess the required technical/soft skills,
            or could they acquire them quickly given their background?

            2. Academic Requirements: Are degree requirements, field of study, and grade
            thresholds (if specified) met?

            3. Experience Level: Is the applicant appropriately qualified (not under or
            over-qualified) for the seniority level?

            4. Professional Experience: Does the applicant have relevant industry/domain
            experience and comparable role experience?

            5. Language Requirements: Does the applicant fulfill all language requirements? Can they read the job description?

            6. Preference Alignment: Does the role, company, location, and work style match
            the applicant's stated preferences?

            7. Overall Assessment: Considering all factors, how successful and satisfied
            would the applicant likely be in this role?
        At the end include strength and concerns for each applicant, as well as a short summary.
    """

    response = client.chat(
        model=model,
        messages=[
            {"role": "assistant", "content": summary},
            {"role": "user", "content": prompt_scoring}
        ],
        stream=False,
        options={
            "temperature": 0
        },
        format=Score.model_json_schema()
    )

    return Score.model_validate_json(response.message.content).model_dump_json(indent=2)


def score_with_summary(job, cv, preferences, model, **kwargs):

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)

    prompt = """
            Your task is to rate how well job postings fit a provided CV and preference statement.
            Your rating scale is:
            0 = Critical mismatch, 25 = Poor match, 50 = Acceptable, 75 = Good match, 100 = Excellent match
            Make small adjustments of ±5-10 points if needed.
            Provide a brief reasoning for each score.

            1. Skillset Match: Does the applicant possess the required technical/soft skills,
            or could they acquire them quickly given their background?

            2. Academic Requirements: Are degree requirements, field of study, and grade
            thresholds (if specified) met?

            3. Experience Level: Is the applicant appropriately qualified (not under or
            over-qualified) for the seniority level?

            4. Professional Experience: Does the applicant have relevant industry/domain
            experience and comparable role experience?

            5. Language Requirements: What languages does the applicant speak? What languages are required by the job posting?
            Can they read the job description?

            6. Preference Alignment: Does the role, company, location, and work style match
            the applicant's stated preferences?

            7. Overall Assessment: Considering all factors, how successful and satisfied
            would the applicant likely be in this role?
            """
    message = f"""
                # CV:
                {cv}

                # PREFERENCES:
                {preferences}

                # JOB DETAILS
                TITLE: {job["title"]}
                COMPANY: {job["company"]}
                DESCRIPTION: {job["description"]}
                """

    response = client.chat(
        model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ],
        stream=False,
        options={
            "num_predict": -1,
            "temperature": 0
        },
        format=Rating.model_json_schema()
    )

    return Rating.model_validate_json(response.message.content).model_dump_json(indent=2)


def score_separately(job, cv, preferences, model, **kwargs):

    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)

    prompt = f"""
            Your task is to rate how well job postings fit a provided CV and preference statement.
            Your rating scale is:
            0 = Critical mismatch, 25 = Poor match, 50 = Acceptable, 75 = Good match, 100 = Excellent match
            Make small adjustments of ±5-10 points if needed
            """

    context = f"""
            CV:
            {cv}

            PREFERENCES:
            {preferences}

            JOB DETAILS
            TITLE: {job["title"]}
            COMPANY: {job["company"]}
            DESCRIPTION: {job["description"]}
            """

    questions = [
            "Skillset Match: Does the applicant possess the required technical/soft skills, \
            or could they acquire them quickly given their background?",

            "Academic Requirements: Are degree requirements, field of study, and grade \
            thresholds (if specified) met?",

            "Experience Level: Is the applicant appropriately qualified (not under or \
            over-qualified) for the seniority level?",

            "Professional Experience: Does the applicant have relevant industry/domain \
            experience and comparable role experience?",

            "Language Requirements: What languages does the applicant speak? What languages are required by the job posting?\
            Can they read the job description?",

            "Preference Alignment: Does the role, company, location, and work style match \
            the applicant's stated preferences?",

            "Overall Assessment: Considering all factors, how successful and satisfied \
            would the applicant likely be in this role?",
    ]

    answers = []
    for q in questions:
        response = client.chat(
            model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "assistant", "content": context},
                {"role": "user", "content": q}
            ],
            stream=False,
            options={
                "num_predict": -1,
                "temperature": 0
            },
        )
        answers.append(response.message.content)

    return "\n".join(answers)


if __name__ == "__main__":

    model_llama_3b_q4 = "llama3.2:3b-instruct-q4_K_M"
    model_llama_3b_q5 = "llama3.2:3b-instruct-q5_K_M"
    model_llama_3b_q6 = "llama3.2:3b-instruct-q6_K"
    model_qwen_1_7b_q4 = "qwen3:1.7b-q4_K_M"
    model_qwen_4b_q4 = "qwen3:4b-q4_K_M"
    model_qwen_8b_q4 = "qwen3:8b-q4_K_M"
    model_mistral_7b_q4 = "mistral:7b-instruct-v0.3-q4_K_M"
    model_mistral_7b_q5 = "mistral:7b-instruct-q5_K_M"
    model_mistral_nemo_q4 = "mistral-nemo:12b-instruct-2407-q4_K_M"
    model_mistral_nemo_q2 = "mistral-nemo:12b-instruct-2407-q2_K"
    model_gemma = "gemma3:4b"
    model_deep_seek = "deepseek-r1:7b-qwen-distill-q4_K_M"
    model_llama_cpp = "llama-3.2-3b-instruct"  # For llama-cpp-python

    models = [
            model_llama_3b_q4, model_llama_3b_q5, model_llama_3b_q6,
            # model_qwen_1_7b_q4,
            model_qwen_4b_q4, model_qwen_8b_q4,
            model_mistral_7b_q4, model_mistral_7b_q5, model_mistral_nemo_q4,
            model_mistral_nemo_q2,
            model_gemma,
            model_deep_seek
    ]

    model_name_map = {
        model_llama_3b_q4: "llama_q4_K_M",
        model_llama_3b_q5: "llama_q5_K_M",
        model_llama_3b_q6: "llama3_q6_K",
        model_qwen_1_7b_q4: "qwen3_1_7b_q4_K_M",
        model_qwen_4b_q4: "qwen3_4b_q4_K_M",
        model_qwen_8b_q4: "qwen3_8b_q4_K_M",
        model_mistral_7b_q4: "mistral_7b_q4_K_M",
        model_mistral_7b_q5: "mistral_7b_q5_K_M",
        model_mistral_nemo_q2: "mistral_nemo_q2_K",
        model_mistral_nemo_q4: "mistral_nemo_q4_K_M",
        model_deep_seek: "deep_seek_q4_K_M",
        model_gemma: "gemma3:4b",
        model_llama_cpp: "llama_cpp",
    }

    job1 = {
        "title": "AI Consultant (all genders)",
        "company": "Lufthansa Industry Solutions",
        "description": """
            About the job
            Werde Teil unseres Teams als AI Consultant und gestalte die Zukunft der Künstlichen Intelligenz mit! Du berätst Kunden zu innovativen KI-Strategien, entwickelst Lösungen mit Generative AI, LLMs und Agentic AI, und setzt diese praxisnah um. Gestalte digitale Transformation aktiv mit und erweitere dein Know-how in spannenden Projekten.

            Aufgaben

            Als AI Consultant bist du zuständig für die Beratung von Unternehmen bei der Identifikation und Umsetzung von KI-Lösungen. Du konzeptionierst maßgeschneiderte Applikationen, unterstützt bei Implementierung und Betrieb, schulst Fachbereiche und sorgst für nachhaltigen Mehrwert durch KI.

            Analyse der Geschäfts- und Prozesslandschaften zur Identifikation von KI-Potenzialen und Entwicklung maßgeschneiderter KI-Strategien
            Eigenverantwortliche Umsetzung von KI-Projekten inklusive Auswahl passender Technologien und Integration in bestehende Systeme
            Beratung und Schulung der Kunden durch Workshops und Begleitung von der Ideenphase bis zur Implementierung
            Requirements Engineering und Zusammenarbeit mit internen Teams wie Fachbereichen, IT und Datenexperten zur Erzielung optimaler Ergebnisse
            Verantwortung für technisches Projektmanagement, kontinuierliche Optimierung und aktive Mitgestaltung der Unternehmenskultur

            Benefits

            Mentoring
            Flexible Arbeitszeiten
            Discounts bei ausgewählten Partnern
            Altersvorsorge / Betriebsrente
            Flugvergünstigungen
            Entwicklungsprogramme / Weiterbildung

            Voraussetzungen

            Abgeschlossene Ausbildung / abgeschlossenes Studium und einschlägige Berufserfahrung im Bereich IT
            Fundierte Kenntnisse in maschinellem Lernen, GenAI, sowie Agentic AI und deren Programmierung
            Erfahrung mit gängigen KI-Tools, Cloud Plattformen und Datenarchitekturen zur Integration und Umsetzung von KI Lösungen
            Verständnis für Datenschutz, IT-Security und regulatorischen Vorgaben (z.B. EU AI Act) zur sicheren Anwendung von KI-Systemen
            Ausgeprägte Beratungskompetenzen, Flexibilität sowie Kommunikationsfähigkeiten auf allen Ebenen
            Fließende Deutsch- und Englischkenntnisse
            Bereitschaft zu projektbezogenen Reisetätigkeiten

            Über uns

            Lufthansa Industry Solutions ist ein Dienstleistungsunternehmen für IT-Beratung und Systemintegration. Die Lufthansa-Tochter unterstützt ihre Kunden bei der digitalen Transformation ihrer Unternehmen. Die Kundenbasis umfasst sowohl Gesellschaften innerhalb des Lufthansa Konzerns als auch mehr als 300 Unternehmen in unterschiedlichen Branchen. Das Unternehmen mit Hauptsitz in Norderstedt beschäftigt über 2.500 Mitarbeiter an mehreren Niederlassungen in Deutschland, Albanien, der Schweiz und den USA.

            Kontakt

            Stefanie Lumpe
            """
    }

    # Additional test jobs would go here...
    # (keeping the code concise, but you have all those test jobs in your original)

    cv = """
            David Gasser CURRICULUM VITAE
            E-Mail davidgasser12@gmail.com LinkedIn linkedin.com/in/d-gasser
            Phone +4915143313694 Webpage davidgasser.github.io
            AI Engineer & Researcher focused on foundation models and applied machine learning. Experienced in developing,
            fine-tuning, and deploying transformer architectures and RAG pipelines across research and enterprise environments.
            PROFESSIONAL EXPERIENCE
            Mar 2025 – Sep 2025 AI Researcher - Japan National Institute of Informatics - Internship
            - Researched AI for time series prediction. Fine-tuned, evaluated, and deployed foundation models.
            - Developed and evaluated novel transformer-based architectures for structured financial data.
            - Coauthored paper on transformer-based time series forecasting; basis for Master's thesis.
            Aug 2024 – Nov 2024 IT Strategist - Munich Re AG - Internship
            - Conducted and managed tech trend research, culminating in an externally published report.
            - Tracked and supported internal as well as external IT product compliance.
            - Studied new insurance opportunities and enhanced external partner satisfaction and performance.
            May 2024 – Aug 2024 AI Engineer - Munich Re AG - Internship
            - Contributed, presented, and demoed an internal tool utilizing RAG/Semantic Search.
            - Conducted a vector database migration to Azure, resulting in a 30% performance improvement.
            - Developed a POC for Apache Airflow as a workflow orchestrator.
            Sep 2023 – Apr 2024 Software Engineer - Siemens AG/KeySpot GmbH - Internship
            - Implemented ML-driven table recognition software for technical datasheets.
            - Built and deployed a microservice for automatic document format conversion.
            - Evaluated libraries for document change detection and management.
            ACADEMIC EDUCATION
            Apr 2022 - Oct 2025 M.Sc. Robotics, Cognition, Intelligence - Technical University of Munich (proj. 1.4/US GPA 3.7)
            - Master's thesis in the field of AI for Financial Time Series Classification.
            Aug 2022 - Dec 2023 Exchange semester - National Taiwan University (1.4/US GPA 3.7)
            - Coursework consisted of 24 ECTS spanning Robotics, Bioinformatics, Automata Theory, and Mandarin.
            Oct 2018 - Apr 2022 B.Sc. Electrical and Computer Engineering - Technical University of Munich (1.9/US GPA 3.1)
            - Bachelor's Thesis in the field of Deep Learning Recommender Systems.
            SKILLS & QUALIFICATIONS
            Programming: Python, Go, C++, C, Solidity, JavaScript
            AI/ML: PyTorch, TensorFlow, HuggingFace, Optuna, Tensorboard, scikit-learn, pandas, NumPy
            Deployment: Git, Docker, Azure, Anaconda, Databricks, Linux, CI/CD
            Visualization: Matplotlib, Seaborn, NetworkX
            Websites: Django, React, HTML, CSS, Streamlit, Scrapy, Selenium
            Other Tools: Obsidian, Hyperledger Fabric, LaTeX, Gemini CLI, MATLAB, ROS
            Languages: German (mother tongue), English (mother tongue), Spanish (B1), Mandarin (A2)
            Nationalities: German, American, Swiss
            PROJECTS
            Blockchain Sustainability Tracker: Built a blockchain-based CO₂ token tracking system for supply chain transparency.
            Modeled emissions and material exchanges to ensure verifiable and confidential tracking using Solidity and Hyperledger Fabric.
            Robotic Painting Arm: User input was captured by speech detection and sent to DALL-E for image creation. Anipainter
            converted images into brush strokes, which were then painted with acrylics by a robot arm (TM5-700).
            Creative Greeting Card: Developed a full-stack, reactive web app for generative multimedia greeting cards, exploring
            computational creativity via NLP and image synthesis models.
            .
            LEISURE & VOLUNTEERING
            PADI Dive Master: Leading, managing, coordinating dives, and assisting in teaching with up to 12 divers.
            Network Administrator - Dormitory: Managed network infrastructure for ~40 residents.
            Mentor incoming exchange students: Supporting incoming students with educational and general questions.
"""
    preferences = """
                I am looking for competetive and somewhat challenging jobs in the AI sphere. My favorite position would be as an AI engineer,
                or something related to it. I am most interested in AI, ML and would love a job that deals with these topics on a daily level.
                The team and working environment matters a lot to me. I want to have the opportunity for growth and mentorship. Those are two
                very important things for me. I prefer working on something new or multi-faceted, then pure implementation. It should not be
                the same thing over and over. When it comes to the type of company, I am open for both larger companies and start ups, as long
                as they provide a good working athmosphere, great pay, and good benefits.
                """

    # Test with llama-cpp-python
    result = score_job(job1, cv, preferences, model_llama_cpp)
    print(result)
