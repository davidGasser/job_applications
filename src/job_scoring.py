import ollama 
import os 
import time
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
    
    
def score_job(job:dict, cv:str, preferences:str, model:str, **kwargs):
    """
    Compare job positions with the CV and the preference statement of the applicant.
    Returns a verified JSON file, with different rantings (int) and assessments (str).
    If the model is changed the ouptut might not be converted to string correctly.
    """  
    
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)
        
    prompt ="""
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
    
    response = client.chat(
        model, 
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ],
        stream = False,
        options = {
            "num_predict": -1,
            "temperature": 0
        }, 
        format = Score.model_json_schema()
    ) 

    return Score.model_validate_json(response.message.content).model_dump_json(indent=2)
    # return _calculate_final_score(response_json)

# def _calculate_final_score(score_dict):
#     """
#     Certain scores are more important than others.
#     This function reweights the assessments made.
#     """

#     score_dict["skillset"]
#     score_dict["academic"]
#     score_dict["experience"]
#     score_dict["professional"]
#     score_dict["language"]
#     score_dict["preference"]
#     score_dict["overall"]
    
#     final = 


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
        model = model, 
        messages = [
            {"role": "system", "content": prompt_summary},
            {"role": "user", "content": chat_summary}
        ],
        stream = False,
        options = {
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
        model = model, 
        messages = [
            {"role": "assistant", "content": summary},
            {"role": "user", "content": prompt_scoring}
        ],
        stream = False, 
        options = {
            "temperature": 0
        },
        format = Score.model_json_schema()
    )
    
    return Score.model_validate_json(response.message.content).model_dump_json(indent=2)


def score_with_summary(job, cv, preferences, model, **kwargs):
    
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)
    
    prompt ="""
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
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message}
        ],
        stream = False,
        options = {
            "num_predict": -1,
            "temperature": 0
        }, 
        format = Rating.model_json_schema()
    ) 

    return Rating.model_validate_json(response.message.content).model_dump_json(indent=2)


def score_separately(job, cv, preferences, model, **kargs): 
    
    ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
    client = ollama.Client(host=ollama_host)
    client.pull(model)
        
    prompt =f"""
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
            messages = [
                {"role": "system", "content": prompt},
                {"role": "assistant", "content": context},
                {"role": "user", "content": q}
            ],
            stream = False,
            options = {
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
    models = [
            model_llama_3b_q4,model_llama_3b_q5,model_llama_3b_q6,
            # model_qwen_1_7b_q4,
            model_qwen_4b_q4,model_qwen_8b_q4,
            model_mistral_7b_q4,model_mistral_7b_q5,model_mistral_nemo_q4,
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
        model_gemma : "gemma3:4b",
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
    
    job_bad_fit = {
        "title": "Junior Trade Marketing Manager (m/w/d)",
        "company": "KoRo",
        "description": """
            About the job
            Deine Aufgaben

            Du suchst eine spannende Position als Junior Trade Marketing Manager, bei der Du kreative Marketingstrategien mit Deinem Geschäftssinn verbinden kannst? Dann bist Du hier genau richtig! Werde Teil unseres Sales Teams und gestalte aktiv neue, innovative Marketingpläne für unsere Retail-Expansionen mit.

            Dabei unterstützt Du nicht nur beim Wachstum unserer Retail-Teams in DACH, Italien und Frankreich, sondern wirkst auch bei der Planung, Umsetzung und Auswertung von Trade-Marketing-Kampagnen mit – um unsere Markenpräsenz zu stärken und den Umsatz nachhaltig zu steigern.

            Planung und Umsetzung von Handelsmarketing-Aktionen 
            Entwicklung und Implementierung von zielgruppenspezifischen POS-Marketingstrategien
            Enge Zusammenarbeit mit dem Marketing-, Key Account- und Sales-Team, um Kampagnen effektiv zu unterstützen und Verkaufsförderungsmaßnahmen abzustimmen
            Erstellung von Verkaufsförderungsmaterialien sowie Verantwortung für deren Produktion und Distribution
            Analyse von Markt-, Wettbewerbs- und Verkaufsdaten zur Ableitung von Handlungsempfehlungen für Deutschland, Österreich, die Schweiz und weitere europäische Märkte
            Planung und Durchführung von Produkteinführungen und -relaunches im Handel
            Kostenkontrolle aller durchgeführten Trade-Marketing-Aktivitäten
            Überwachung und Analyse relevanter KPIs sowie kontinuierliche Optimierung der Marketingstrategien

            Dein Profil

            Abgeschlossenes Studium in Betriebswirtschaft, Marketing oder einem vergleichbaren Fachbereich
            Erste Berufserfahrung im Trade Marketing und Projektmanagement, idealerweise im Lebensmitteleinzelhandel
            Sehr gute Deutsch- und Englischkenntnisse in Wort und Schrift
            Du wohnst in Berlin/Umgebung oder hast Lust, für Deinen neuen Job nach Berlin zu kommen
            Ausgeprägte analytische Fähigkeiten und Erfahrung im Umgang mit Markt- und Verkaufsdaten
            Starke Kommunikationsfähigkeiten und die Fähigkeit, in einem crossfunktionalen Team zu arbeiten
            Hohe Eigeninitiative, Selbstständigkeit und Lösungsorientierung
            Sicherer Umgang mit Google Suite

            Das erwartet dich bei uns

            Mit Deinen Ideen kannst Du unser vielfältiges Team bereichern und so die Zukunft des Lebensmittelhandels in einem stark wachsenden Scale-up aktiv mitgestalten!
            Umfangreiches Onboarding sowie abwechslungsreiche, anspruchsvolle Aufgaben.
            Flexible Arbeitszeiten und Möglichkeit zum Home Office sorgen für eine gute Work-Life-Balance.
            Modernes Office in Berlin Schöneberg, sehr gut mit den öffentlichen Verkehrsmitteln zu erreichen – und wir übernehmen die Kosten Deines BVG-Monatstickets.
            Finde den Weg (zurück) ins Gym dank Fitness-Kooperationen wie Urban Sports Club oder FitX.
            Optimale Performance wahlweise mit einem Windows Laptop oder MacBook.
            Perfekt ausgestattete Küche mit frischem Obst, leckeren KoRo-Naschereien & Kaffee sowie Tee inklusive.
            20 % Discount in unserem KoRo-Online Shop.
            Regelmäßige Team-Events und gemeinsame Aktivitäten sowie legendäre Firmenpartys.

            Das hört sich gut an?

            Dann bewirb Dich mit Deinen aussagekräftigen Bewerbungsunterlagen (CV und Motivationsschreiben) über unsere Website. Wir suchen echte Teammitglieder – lass uns in ein paar Sätzen gern wissen, wer Du bist und was Dich bewegt.

            Über uns

            KoRo definiert die Standards der Lebensmittelindustrie neu, indem es eine breite Palette an hochwertigen und innovativen Produkten anbietet. Das Sortiment reicht von naturbelassenen Lebensmitteln wie Nussmusen und Trockenfrüchten bis hin zu Clean Label Snacks und Functional Food. Das kontinuierliche Engagement für Transparenz und Produktinnovation treibt das Unternehmen dazu an, neue Wege in der Lebensmittelbranche zu gehen. Ziel ist es, Konsument:innen Produkte für eine bewusste Ernährung anzubieten, die einfach zugänglich und – wie immer – besser und anders sind.

            KoRo wurde 2014 in Deutschland gegründet und von Constantinos Calios und Piran Asci aufgebaut. Heute bilden CEO Florian Schwenkert, CFO Dr. Daniel Kundt, CPO Constantinos Calios und COO Steﬀani Busch das Managementteam. Das Unternehmen beschäftigt mehr als 300 Mitarbeitende und hat seinen Sitz in Berlin.

            Mehr als 2 Millionen Kund:innen kaufen online unter www.koro.com sowie in über 15 000 Einzelhandelsgeschäften in ganz Europa.

            Das KoRo-Team ist genauso vielfältig wie unsere Product Range! Damit Diversity bei uns weiterhin ebenso schnell wächst wie unser nussbegeistertes Team, bewerten wir Bewerber:innen unabhängig von Geschlecht, Nationalität, ethnischer und sozialer Herkunft, Religion/Konfession, Weltanschauung, Behinderung, Alter und sexueller Orientierung oder Identität.

            Du möchtest mit Deinen Fähigkeiten und Talenten Deinen Teil zu unserer Mission beitragen und die Zukunft von KoRo aktiv mitgestalten? Dann bewirb Dich jetzt und werde Mitglied unseres Teams!
            """
    }
    
    job_no_lang = {
        "title": "AIコンサルタント(生成AI領域/AIデータプラットフォーム「FastLabel」)",
        "company": "FastLabel株式会社",
        "description": """
        【仕事内容】

        【職務内容】

        同社はグローバルで100兆円を超える市場を対象に、AIインフラを創造し、

        日本を再び世界レベルへ押し上げることを目指しております。

        2020年1月の創業以来、教師データ作成を核として、AI開発の各工程を

        効率化・高度化するためのプロフェッショナルサービスと

        AIデータプラットフォーム「FastLabel」を提供しております。

        高品質なデータを収集し、専門人材による教師データ作成を通して、

        日本を代表する生成AI企業のAI開発に貢献しております。

        生成AIに取り組むお客様に対し、データ収集・作成の支援も行っております。

        【具体的には】

        ・ 生成AI領域のAIデータプロジェクトにおける

        プロジェクトマネジメント（全体工程設計、進捗管理、リソース管理）

        ・ 詳細要件定義（仕様書及びデータに基づく要件の洗い出し、整理、並びに要件擦り合わせ）

        ・ デリバリー（詳細要件書及び手順マニュアルの作成、作業者への手順説明、作業品質管理、納品対応）

        ・ リピート案件の獲得、他事業部との連携による顧客攻略

        ・ 主な業務内容

        ・ グローバル規模のAIデータ関連事業

        ・ 生成AIを活用した業務効率化の支援

        ・ AIデータプラットフォーム「FastLabel」の提供

        ・ 生成AI領域におけるコンサルティング（データ分布や仕様の策定支援）

        【求める人材】

        【必須】

        ・ お客様との深い信頼関係の構築経験

        ・ 積極的に技術や知識を身につけられる、学習意欲が高い方

        ・ 他部門やパートナー企業様と円滑なコミュニケーションを通し、人を巻き込む能力

        ・ 構想策定、要件定義など、クライアントの意見をまとめあげ、やるべきことを決める業務の経験

        ・ プロジェクトマネジメントやベンダーコントロールの経験2年以上

        【歓迎】

        ・ Webアプリケーションプロダクト・ソフトウェア提供企業におけるCS経験、またはそれに準ずる経験1年以上

        ・ エンタープライズのお客様へのアップセル・クロスセル提案経験

        ・ 開発チームとの協業経験

        ・ 機械学習や自動運転に関する知識・経験

        【給与】

        年収750~1200万円,※職務経験を考慮のうえ決定いたします。

        【勤務地】

        東京都新宿区

        【勤務時間】

        09:00～18:00

        【雇用・契約形態】

        【待遇・福利厚生】

        通勤手当 残業手当

        【休日・休暇】

        慶弔休暇 年末年始 夏期休暇 有給休暇 完全週休2日制（土日、祝祭日、年末年始等） 有給休暇 慶弔休暇 生理休暇 出産育児・介護休業
        """
    }
    
    job_no_lang2 = {
        "title": "AI・機械学習エンジニア（コンピュータビジョン）",
        "company": "株式会社OkojoAI", 
        "description": """
        


              About the job
                        


            




            【勤務地】
            フルリモート
            【企業名】
            株式会社OkojoAI
            【求人名】
            AI・機械学習エンジニア（コンピュータビジョン）
            【仕事の内容】
            法人顧客向け事業において、人工知能・機械学習技術を活用した顧客向けソリューション開発と自社プロダクト開発の両面を担当いただきます。顧客の抱える課題に対してAI技術の適用可能性を検証するPoC（概念検証）や、自社AIプロダクトの企画開発・機能拡張に取り組んでいただきます。営業やプロジェクトマネージャー、エンジニアチームと協力しながら、顧客折衝や要件定義にも参画し、技術面でのリードを担いながら課題解決を推進します。また、最新の学術論文や先端技術の調査業務にも携わっていただきます。
            ※コンピュータビジョンがメインですが、本人のご興味によっては深層学習を活用した自然言語処理、音声認識、最適化、強化学習など幅広い領域への挑戦も可能です
            【募集職種】
            AI・機械学習エンジニア（コンピュータビジョン）
            【必要な経験・能力等】
            以下の技術経験とビジネススキルを重視します。すべてを完璧に満たしている必要はありませんが、コンピュータビジョンの実務経験とコミュニケーション能力は特に重視します。
            【必須要件】
            
            
            画像処理、パターン認識に関する知識と実務または研究経験
            コンピュータビジョン技術（物体認識・追跡、動作認識、生成モデル、VLM等）への理解
            PyTorch・TensorFlowなどの深層学習フレームワークを用いた研究・開発経験
            AI関連の学術論文や実装を理解し、キャッチアップする能力
            GPU、クラウド、Gitなどに関する基礎知識
            顧客との技術的な折衝や要件定義ができるコミュニケーション力
            技術的な内容を分かりやすく伝えるプレゼンテーション能力
            チーム開発における協調性
            英語での技術文書・論文の読解力


            【歓迎要件】
            
            情報系・理学系分野での修士号または博士号取得
            AI・機械学習関連テーマでの研究実績、トップ国際会議での論文投稿・採択経験
            アジャイル開発手法によるチーム開発経験
            自然言語処理、音声認識、最適化、強化学習などの分野への知見
            機械学習・深層学習を活用したPoC開発またはプロダクト開発の実務経験
            ONNX、CoreMLなどへのモデル形式変換に関する知識
            OSSプロジェクトへの貢献・技術系書籍の執筆・テックイベント登壇の経験
            競技プログラミングやAI・機械学習コンペの実績
            本番環境での機械学習システムの開発・運用経験
            製造業、建設業などの業界知識や業務プロセスへの理解
            開発プロジェクトにおけるリーダー経験
            プロジェクトマネジメント経験（進捗管理、品質管理、予算管理等）
            プロダクトマネジメント経験または新規事業・サービスの企画提案経験


            【求める人物】
            
            当社のミッション・バリューに共感し、会社のことを自分ごととして捉え、AI業界の健全な発展に貢献したい志を持つ方
            専門性を深めながら、幅広い技術領域にも挑戦できる方
            顧客折衝からモデル開発まで、柔軟に対応できる方
            発言に責任を持ち、主体的に行動できる方


            【仕事のやりがい】
            
            [事業を0から作れる環境] まだまだ黎明期の段階だからこそ、事業の立ち上げから成長までのすべてに関わることができます。自分のアイデアや技術が直接サービスに反映され、その成果を実感できる環境です。
            
            [AI業界のリーディングランナーとしてのキャリア形成] 今後事業が拡大していく中で、初期メンバーとして最先端のAI技術開発に携わり、業界をリードする存在としてのキャリアを築くことができます。


            【現在の体制】
            
            
            代表取締役CEO（AIエンジニア兼務）: 1名
            
            営業・BizDev（業務委託）: 1名
            
            マーケティング（業務委託）: 1名
            
            AIエンジニア（業務委託・副業含む）: 3名


            【会社紹介】
            OkojoAIは、最先端の研究開発と革新的なAI技術で未来を創造する企業です。「小さくても世界をときめかせる」というミッションのもと、画像認識やLLMなどのAI技術を活用し、企業の課題解決や新しいサービス開発を支援しています。
            代表は、世界トップレベルのAIカンファレンスNeurIPSに論文採択された実績を持ち、 2025年3月には日本初の「人工知能科学」の名がつく博士号を取得。最先端のAI研究を基盤としながら、技術の社会実装に注力しています。現在は、エンタープライズ企業のAI/DXプロジェクトや自社AIプロダクトの開発を推進中です。今後は、点検・外観検査 の分野を重点領域と定め、安全管理や品質管理の効率化を目指していきます。
            研究開発で培った技術を活かした新しいAIサービスの提供を視野に入れ、研究から 実装まで一貫して対応し、ワクワクするAIプロダクトを生み出していきます。
            【大切にしていること】
            1. 研究と実装の融合——「おもしろい！」を社会に届ける
            OkojoAIは、AI研究そのものと最新のAI研究の成果を社会に実装することに全力を注いでいます。 代表自身がNeurIPSに論文採択され、2025年3月には日本初の「人工知能科学」の名がつく博士号を取得。 しかし、私たちは研究成果を論文の中だけに閉じ込めるつもりはありません。
            「この技術、すごくおもしろい！でも、どうすればビジネスとして価値を生み出せる？」
            「社会の課題を解決しつつ、事業として成り立たせるには？」
            こうした問いを常に考え、技術の価値を最大化するためにビジネスを意識した研究開発を行っています。
            2. 研究とビジネスの好循環で、持続的なイノベーションを生み出す
            OkojoAIでは、技術開発がビジネスのための手段ではなく、ビジネスが技術研究を加速させる手段でもあります。
            ・ビジネスの成功が、新たな研究のための資金を生み出す
            ・研究の成果が、次のビジネスの種を生む
            この好循環をつくることで、私たちは「研究者が研究に没頭できる環境」をビジネスの力で実現しようとしています。
            企業と協業するプロジェクトだけでなく、自社のAIプロダクト開発にも投資し、研究とビジネスを連動させながら、より大きな価値を生み出すことを目指しています。
            3. オープンマインドがイノベーションを生む
            「楽しい」チームには、オープンマインドな文化が欠かせません。
            ・知識を積極的に共有し、学び合う
            ・「正解」ではなく「新しい視点」を歓迎する
            ・役職や肩書きに関係なく、自由にアイデアを出せる
            研究機関のように、技術や知見を閉じるのではなく、世界に向けて発信し、仲間を増やしながら成長していく。
            「こうあるべき」ではなく、「こうしたらもっと楽しい！」が尊重される環境をつくっています。
            4. 成果を最大化するための合理的な環境設計
            OkojoAIでは、「どれだけ働いたか」ではなく、「どれだけ価値を生み出したか」 を重視します。
            そのため、時間や場所に縛られず、研究・開発・ビジネスのすべてにおいて、最適な環境で成果を出せる仕組みを整えています。
            A. 成果を出すための柔軟な働き方
            ・リモートワークOK、最適な環境を自分で選ぶ
            → 業務に支障がない限り、働く場所は個人の判断に委ねる。必要に応じてオフィスでの議論も活用。
            ・適切な休憩を取り、集中力を維持
            → 長時間働くよりも、リフレッシュしながら生産性を高めることが重要。適度な休憩を挟み、パフォーマンスを最適化する。
            B. 自律と成果を重視するカルチャー
            ・個々の裁量を尊重し、マイクロマネジメントはしない
            → 細かい指示を待つのではなく、自ら考え、成果を出せる人が活躍できる環境を用意する。
            ・「とりあえず会議」は禁止、意思決定は最小限の時間で
            → 会議は問題解決の手段であり、ダラダラ話すものではない。目的を明確にし、最小の時間で最大の成果を出す。
            ・業務に必要なリソースは、予算内で合理的に選定
            → 業務の効率化や成果向上に必要なものは、適切に判断して導入。
            C. 環境の最適化＝創造性の最大化
            ・「働く環境」は固定されたものではなく、目的に応じて最適化されるべき
            ・業務の効率化に役立つツールや仕組みは積極的に導入
            ・「考える時間」を確保し、目の前のタスクに追われすぎない
            OkojoAIは、成果を最大化するために働き方をデザインする組織です。
            制約を取り払い、「研究 × 実装 × ビジネス」の新しい価値を生み出すことにフォーカスします。
            【理念(ビジョン)、行動指針など】
            [Mission]
            小さくても世界をときめかせる
            私たちは、規模の大小に関わらず、AI技術の力で世界にワクワクする変化を生み出すことを使命としています。
            革新的なアイデアと最先端技術を駆使し、小さなチームだからこそできるスピード感と柔軟性で、新しい価値を創り出します。
            [Vision]
            最先端のAI技術を切り拓き、その技術を通して世界中に驚きを届ける
            OkojoAIは、研究・実装・ビジネスを一体化させ、AI技術の可能性を最大限に引き出す組織です。
            研究の枠を超えて、実際に使える技術として社会に浸透させ、世界を変えるような驚きを生み出します。
            【就業時間】
            標準労働時間 8時間（3ヶ月単位フレックス制度-コアタイムなしを導入）
            ※10:00〜19:00の間を目安としています
            
            
            ・休憩時間 60分
            所定時間外労働 有
            ※始業時刻及び終業時刻については社員の自主的決定に委ねる。自主的決定に委ねる時間帯は午前5時から午後10時までの間とする。ただし、22時から5時までの深夜時間での業務については、1か月で5時間以内であれば社員の自主的決定に委ね、5時間を超える場合は会社の承認を必要とする。
            【勤務形態】
            年間休日：125日 (2025年)
            完全週休二日制 土曜 日曜 祝日
            有給休暇：有（10～20日）（※有給は入社6ヶ月後から10日付与されます）
            特別休暇：有
            慶弔休暇：有
            年末年始休暇：12月29日〜1月3日
            【勤務地所在地】
            東京都 板橋区
            【本社】東京都板橋区蓮根2-27-12 古谷野ビル3F-13
            ※基本的にフルリモート体制、必要に応じてレンタルオフィスにて対面での打ち合わせをすることはあります。
            転勤：無 ※ただし、オフィス移転に伴う勤務地変更の可能性があります
            【想定年収】
            606万円～960万円
            * 想定年収/6,060,000円~9,660,000円
            * 月給/505,000円~805,000円
            ※経験・能力を考慮の上、決定いたします
            【雇用形態】
            正社員
            期間の定め：無
            【賃金形態】
            形態：月給制
            給与改定：年1回（10月）
            賞与：なし
            備考：月給￥505,000～ 賞与なし
            <内訳>
            基本給: 308,000円~/月
            生涯設計手当: 55,000円/月 ※企業型DC(確定拠出年金)に拠出可能な手当。残業代の算定基礎に含まれます。
            固定残業手当: 143,000円~/月
            
            ※時間外労働割増賃金分(45時間/月) 126,000円~/月
            ※深夜労働割増賃金分(30時間/月) 17,000円~/月
            ※超過した時間外労働の残業代は1分単位で支給
            リモートワーク手当: 5,000円/月
            【試用期間】
            
            有(3ヶ月間)
            
            ※採用日から3ヶ月後の賃金締切日まで
            ※試用期間中の労働条件(給与・勤務時間等)は本採用後と同じ
            ※能力・適性により短縮または延長する場合あり(最長6ヶ月)
            ※試用期間も勤続年数に含む
            【制度・設備】
            退職金：無
            寮・社宅：無
            在宅勤務 （全従業員利用可）
            リモートワーク可 （全従業員利用可） ー 手当あり
            時短制度 （全従業員利用可）
            服装自由 （全従業員利用可）
            出産・育児支援制度 （一部従業員利用可）
            企業型確定拠出年金制度（正社員利用可）
            交通費実費支給
            副業可
            ⁜制度が完璧に整っていないからこそ、あなたの状況に寄り添った働き方を一緒に考えます。
            * 子育て中の方
            * 学業と両立したい方
            * 介護やその他の事情がある方
            まずはご相談ください！
            画一的なルールではなく、一人ひとりに合った働き方を実現することを大切にしています。
            【社会保険】
            
            雇用保険
            労災保険
            健康保険
            厚生年金


            【選考内容】
            カジュアル面談（任意・選考には含まれません） ご希望の方には、選考前に代表とのカジュアル面談の機会を設けています。会社やポジションについて気軽にお話しできる場です。
            書類選考
            1次面接：代表との面談（60分）
            
            ・これまでのキャリアや経験について
            
            ・カルチャーフィット確認
            
            ・技術に関する簡単な会話
            最終面接：2部構成・連続開催（計90分）
            A. BizDev担当者との相性確認（30分）
            B. 代表との技術面接（60分） ※1日で完結しますので、ご安心ください。事前課題を課す場合があります。
            ※すべての面接はオンライン実施可能
            採用予定人数：1名
            """
    }
    
    job_lang = {
        "title": "Machine Learning Quantitative Researcher",
        "company": "AlphaGrep",
        "description": """
        About the job
        关于我们 / About Us 

        AlphaGrep 是一家全球领先的量化交易公司，专注于股票、商品、外汇及固定收益等资产的算法交易。我们在国际市场拥有显著份额，依托自主开发的超低延迟系统与严格的风控体系，持续构建高效能策略。

        AlphaGrep is a leading global quantitative trading firm specializing in algorithmic strategies across equities, commodities, FX, and fixed income. We hold significant market share internationally, powered by proprietary low-latency infrastructure and robust risk controls.

        AlphaGrep China 是专注于中国市场人民币资产管理的机构，服务对象涵盖机构投资人、家族办公室与高净值客户。我们深耕中国资本市场，涵盖股票及衍生品等多类资产，结合全球量化研究体系与本地实战经验，构建多元交易策略，致力于实现长期稳健增长。

        AlphaGrep China is a dedicated RMB asset management platform focused on the Chinese market, serving institutional investors, family offices, and high-net-worth individuals. We leverage deep expertise in China’s equity and derivatives markets, together with AlphaGrep’s global quantitative research capabilities, to deliver diversified strategies targeting long-term and stable returns.

        岗位职责 / Responsibilities 

        将机器学习和深度学习应用到股票市场的量化业务场景之中，包括但不限于从金融数据中挖掘并构建全新交易信号，负责中高频策略的生成、评估和生产化部署等；Apply machine learning and deep learning to quantitative trading strategies in the stock market by (not limited to) mining and constructing trading signals from financial data, and managing the full lifecycle (generation, evaluation, and production deployment) of mid-to-high-frequency trading strategies.

        设计并应用机器学习和深度学习模型（如Transformer, GRU, LSTM, DLinear, GNN, NLP等），使其在不同量化场景下发挥信息提取、模型搭建等作用；Design and implement advanced ML&DL models (e.g., Transformer, GRU, LSTM, DLinear, GNN, and NLP) to perform information extraction and model construction across diverse quantitative applications.

        开发和维护严谨的回测和风险评估系统，确保策略在实盘前的稳健性，并根据市场变化，持续监控、优化和升级已上线的策略模型；Develop and maintain back-testing and risk evaluation systems to ensure strategy robustness before live trading and continuously monitor, optimize, and upgrade live strategy models in response to market changes.

        紧跟机器学习和深度学习领域的前沿进展，积极探索先进技术在量化投资中的应用潜力；Keep up with frontier advancements in ML/DL, and explore the application potential of advanced techniques in quantitative investment.

        任职要求 / Qualifications

        国内外知名高校专业硕士及以上学历（博士优先），计算机、数学、物理、统计等STEM专业优先；Master's degree or higher from a reputable university in a STEM field, such as Computer Science, Mathematics, Physics, or Statistics (Ph.D. preferred).

        具备创新能力和扎实的python编程基础，对模型做改进和调优；A solid foundation in Python programming is required for model improvement and tuning, along with innovative capabilities.

        熟练掌握 Pytorch/Tensorflow，能够基于其中的一个框架快速开发和实现各类前沿深度学习模型；Excellent programming skills, proficient in Pytorch/Tensorflow, capable of rapidly developing and implementing various cutting-edge deep learning models based on one of the frameworks.

        热爱量化行业，坚定职业发展方向，自我驱动能力较强者优先；Passionate for the quantitative industry with a clear commitment to the career path and exhibit strong self-drive.

        英语流利，可以作为工作语言；Fluent in English and can use it as a working language.

        加入我们 / Why You Should Join Us 

        信任是团队协作的根基

        我们鼓励坦诚沟通与主动承担，让每一位成员都能在安全感中成长，自主决策、共同前行。这份信任源于彼此支持与并肩作战，是我们最珍贵的团队资产。

        Trust is the foundation of collaboration.

        We foster open communication and proactive ownership, empowering every team member to grow with a strong sense of security, make autonomous decisions, and move forward together. This trust—built through mutual support and shared commitment—is our most valued asset.

        优秀的团队成员，我们汇聚了工程师、数学家、统计学家，保持好奇心，乐在其中。

        Great People. We’re curious engineers, mathematicians, statisticians and like to have fun while achieving our goals.

        透明的组织架构，我们重视每一位成员的想法与贡献。

        Transparent Structure. Our employees know that we value their ideas and contributions.

        轻松的办公环境，无等级文化，常有团建、聚会与休闲活动。

        Relaxed Environment. Flat organization with yearly offsites, happy hours, and more.

        健康福利支持，健身补贴、零食饮品、充足年假。

        Health & Wellness Programs. Gym membership, stocked kitchen, and generous vacation.
        """
    }
    
    job_no_acad = {
        "title": "Junior Research Scientist (VLAs)",
        "company": "AIRoA (AI Robot Association)",
        "description": """
                   About the job
                                


                    




                    About AIRoA
                    The AI Robot Association (AIRoA) is launching a groundbreaking initiative: collecting one million hours of humanoid robot operation data with hundreds of robots, and leveraging it to train the world's most powerful Vision-Language-Action (VLA) models.
                    What makes AIRoA unique is not only the unprecedented scale of real-world data and humanoid platforms, but also our commitment to making everything open and accessible. We are building a shared "robot data ecosystem" where datasets, trained models, and benchmarks are available to everyone. Researchers around the world will be able to evaluate their models on standardized humanoid robots through our open evaluation platform.
                    For researchers, this means an opportunity to:
                    
                    
                    Work on fundamental challenges in robotics and AI: multimodal learning, tactile-rich manipulation, sim-to-real transfer, and large-scale benchmarking
                    
                    Access state-of-the-art infrastructure: hundreds of humanoid robots, GPU clusters, high-fidelity simulators, and a global-scale evaluation pipeline
                    
                    Collaborate with leading experts across academia and industry, and publish results that will shape the next decade of robotics
                    
                    Contribute to an initiative that will redefine the future of embodied AI—with all results made open to the world


                    As we prepare for our official launch on October 1, 2025, we are assembling a world-class team ready to pioneer the next era of robotics.
                    We invite ambitious researchers and engineers to join us in this bold challenge to rewrite the history of robotics.
                    Job Description
                    In this role, you will be responsible for:
                    
                    
                    Design and implement data preprocessing pipelines for multimodal robot datasets
                    
                    Train VLA models using supervised learning, RL, fine-tuning, RLHF, and training from scratch
                    
                    Develop and evaluate models in both simulation and on physical robots
                    
                    Improve training robustness and efficiency through algorithmic innovation
                    
                    Analyze model performance and propose enhancements based on empirical results
                    
                    Deploy VLA models onto real humanoid and mobile robotic platforms
                    
                    Publish research in top-tier conferences (e.g., NeurIPS, CoRL, CVPR)


                    Requirements
                    Required Qualifications
                    (All Of The Following Qualifications Must Be Met)
                    
                    
                    MS degree with 3+ years of industry experience, or PhD in Computer Science, Electrical Engineering, or a related field
                    
                    Have at least one first-author publication in a top-tier conference such as CoRL, ICML, CVPR, NeurIPS, IROS, ICLR, ICCV, or ECCV
                    
                    Experience with open-ended learning, reinforcement learning, and frontier methods for training LLMs/VLMs/VLAs such as RLHF and reward function design
                    
                    Experience working with simulators or real-world robots
                    
                    Knowledge of the latest advancements in large-scale machine learning research
                    
                    Experience with deep learning frameworks such as PyTorch


                    Preferred Qualifications
                    
                    
                    PhD or equivalent research experience in robot learning
                    
                    Practical experience implementing advanced control strategies on hardware, including impedance control, adaptive control, force control, or MPC
                    
                    Experience using tactile sensing for dexterous manipulation and contact-rich tasks
                    
                    Familiarity with simulation platforms and benchmarks (e.g., MuJoCo, PyBullet, Isaac Sim) for training and evaluation
                    
                    Proven track record of achieving significant results as demonstrated by publications at leading conferences in Machine Learning (NeurIPS, ICML, ICLR), Robotics (ICRA, IROS, RSS, CoRL), and Computer Vision (CVPR, ICCV, ECCV)
                    
                    Strong end-to-end system building and rapid prototyping skills
                    
                    Experience with robotics frameworks like ROS


                    Benefits
                    There are currently no comparable projects in the world that collect data and develop foundation models on such a large scale. As mentioned above, this is one of Japan's leading national projects, supported by a substantial investment of 20.5 billion yen from NEDO.
                    This position will play a crucial role in determining the success of the project. You will have broad discretion and responsibility, and we are confident that, if successful, you will gain both a great sense of achievement and the opportunity to make a meaningful contribution to society.
                    Furthermore, we strongly encourage engineers to actively build their careers through this project—for example, by publishing research papers and engaging in academic activities.
                    """
    }
    
    job_no_pref = {
        "title": "Full Stack Software Engineer (On-site)", 
        "company": "ExecutivePlacements.com", 
        "description": """
        


              About the job
                        


            




            We're seeking a
            
            Full-Stack Software Engineer
            
            to help build and scale our platform from the ground up. This is a high-impact role with
            
            end-to-end ownership
            
            of projects from design to launchdriving outcomes in user growth, operational efficiency, and revenue.
            If You Join, You Will
            
            
            Own large parts of our product surface area and drive the relevant roadmaps to deliver on specific outcomes (See below for focus areas)
            
            Drive zero-to-one product development from conceptualization through production, collaborating with our go-to-market and operations teams
            
            Build new features and products top-to-bottom: front-end, back-end, system design, debugging, and testing
            
            Participate actively in client engagements, working directly with customers to understand requirements and deliver innovative solutions
            
            Establish and improve engineering processes, tools, and systems that will allow us to scale the code base and team productivity over time
            
            Work closely with the rest of our team and the CEO to make business decisions as we balance speed of growth and long-term profitability


            We Need Your Help To
            
            
            Decipher and automate complex, branching workflows for insurance coverage, affordability programs, and fulfillment
            
            Combining AI/ML approaches to achieve high precision document classification, unstructured data extraction, and reference-based question answering
            
            Automating multi-step, path-dependent processes, using a combination of


            RPA/scraping approaches to navigate and operate third-party platforms
            
            
            Building a state machine that drives system decisions and handles failure modes across a set of processes that are technically independent but practically intertwined
            
            Scale across a growing range of drug classes, patient populations, and provider markets
            
            Making our data and ML pipelines robust to variation and inconsistency in input data formats (e.g., clinical documentation structure and style)
            
            Leveraging empirical data to build and continuously update our understanding of opaque external systems (e.g., insurance company policies)
            
            Creating consumer-grade experiences for patients, physicians, and other users that incorporate intuitive AI-powered workflows
            
            Use our network to help biopharma partners accelerate drug development,


            launch, and access
            
            
            Translating large volumes of heterogeneous data into reliable insights, informing decisions like clinical indication selection, launch markets, and insurer negotiations
            
            Developing predictive and simulation models to forecast outcomes such as


            clinical trial site performance, drug adoption rates, and the impact of
            rebates/subsidies
            
            
            Using real-time data and direct engagement channels to enroll criteria-matching patients and physicians in clinical studies and access programs


            Additional
            
            
            0 - 15 years of experience as a Full Stack software engineer at a high-quality, fast-growing, product-driven company (i.e., Scale AI, Square, Stripe) or early-stage startups






            

            Close
        """
    }
    
    jobs = [job1, job_bad_fit, job_lang, job_no_lang, job_no_lang2, job_no_acad, job_no_pref]
    
    job_to_string_map = {
        job1["title"]: "job1",
        job_bad_fit["title"]: "job_bad_fit",
        job_lang["title"]: "job_lang",
        job_no_lang["title"]: "job_no_lang",
        job_no_lang2["title"]: "job_no_lang2",
        job_no_acad["title"]: "job_no_acad",
        job_no_pref["title"]: "job_no_pref"
    }
    
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
            - Coauthored paper on transformer-based time series forecasting; basis for Master’s thesis.
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
    
    output_folder_scoring = Path("output/scoring")     
    output_folder_summarize = Path("output/summarize")      
    output_folder_score_on_summary = Path("output/score_on_summary")
    output_folder_sum_with_score = Path("output/score_with_summary")
    output_folder_separate = Path("output/separate_scoring")
    output_folders = [output_folder_scoring, output_folder_summarize, output_folder_score_on_summary, 
                      output_folder_sum_with_score, output_folder_separate]
    
    ## Selection
    for model in models: 
        for job in jobs: 
            summary = None
            ## testing
            def test_functions(function, output_path): 
                start_time = time.time()
                response = function(**{"job":job, "cv":cv, "preferences":preferences, "model":model, "summary":summary})
                print(response)
                print("-"*60)
                print(f"Response time Score Job: {(time.time()-start_time):.3f}")
                print("-"*60)
                
                with open(output_path, "w") as f: 
                    if type(response) == Score or type(response) == Rating:
                        f.write(f"Response time: {(time.time()-start_time):.3f}\n\n{response}")
                    else: 
                        f.write(f"Response time: {(time.time()-start_time):.3f}\n\n{response}")
                return response
            
            
            model_folder = model_name_map[model]
            [os.makedirs(out_folder / model_folder, exist_ok=True) for out_folder in output_folders]
            output_file = f"{model_folder}/{job_to_string_map[job['title']]}.txt"
            
            test_functions(score_job, output_folder_scoring / output_file)
            summary = test_functions(summarize, output_folder_summarize / output_file)
            test_functions(score_on_summary, output_folder_score_on_summary / output_file)
            test_functions(score_with_summary, output_folder_sum_with_score / output_file)
            test_functions(score_separately, output_folder_separate / output_file)